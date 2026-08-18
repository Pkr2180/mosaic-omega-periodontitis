"""Problem interface + a fully-instrumented synthetic benchmark environment.

`Problem` is the plug-point for real work. `SyntheticConstraintProblem` is a
deterministic, ground-truth-bearing environment that lets every metric in
`metrics.py` be computed from actual computation rather than from assertion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .rng import rng_for
from .types import RiskLevel, StageSpec


class Problem(ABC):
    """Implement this to run MOSAIC-Omega on a real task."""

    goal: str = "unspecified goal"

    @abstractmethod
    def stages(self) -> List[StageSpec]:
        """Ordered work stages with required capabilities."""

    @abstractmethod
    def capability_catalog(self) -> List[str]:
        """Every capability the provisioner may instantiate."""

    @abstractmethod
    def value_space(self, constraint_id: str) -> List[str]:
        """Admissible resolutions for a constraint."""

    @abstractmethod
    def capability_for(self, constraint_id: str) -> str:
        """Capability required to resolve a constraint."""

    @abstractmethod
    def propose(self, constraint_id: str, agent_id: str, skill: float, nonce: str) -> str:
        """Agent proposes a resolution. Deterministic given the arguments."""

    @abstractmethod
    def verify(self, constraint_id: str, value: str, verifier_skill: float, nonce: str) -> bool:
        """Noisy verification oracle."""

    @abstractmethod
    def attack(self, constraint_id: str, value: str, attacker_skill: float, nonce: str) -> bool:
        """Return True if a falsification attempt on this assignment succeeds."""

    @abstractmethod
    def true_score(self, assignment: Dict[str, str]) -> float:
        """Ground-truth quality in [0,1]. Used for evaluation only."""


# ---------------------------------------------------------------------------
@dataclass
class _Constraint:
    constraint_id: str
    capability: str
    values: List[str]
    truth: str
    weight: float = 1.0


class SyntheticConstraintProblem(Problem):
    """A constraint-satisfaction world with known ground truth.

    Each constraint requires one capability. An agent's probability of
    proposing the true value rises with its skill on that capability, so
    provisioning, routing, pruning and sovereignty all have real consequences
    that show up in the metrics.
    """

    def __init__(
        self,
        goal: str = "Resolve every constraint in the mission correctly",
        n_stages: int = 3,
        constraints_per_stage: int = 5,
        arity: int = 4,
        capabilities: Optional[Sequence[str]] = None,
        seed: int = 20260807,
        floor_accuracy: float = 0.28,
        skill_gain: float = 0.66,
        verifier_false_negative: float = 0.06,
    ) -> None:
        self.goal = goal
        self.seed = seed
        self.floor_accuracy = floor_accuracy
        self.skill_gain = skill_gain
        self.verifier_false_negative = verifier_false_negative
        self._caps = list(
            capabilities
            or ("retrieval", "formal_reasoning", "quantitative", "domain_expert",
                "synthesis", "risk_analysis")
        )
        rng = rng_for("problem", seed)
        self._constraints: Dict[str, _Constraint] = {}
        self._stages: List[StageSpec] = []
        risks = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
        for s in range(n_stages):
            cids: List[str] = []
            caps: List[str] = []
            for c in range(constraints_per_stage):
                cid = f"C{s}_{c}"
                cap = self._caps[rng.randrange(len(self._caps))]
                values = [f"v{i}" for i in range(arity)]
                truth = values[rng.randrange(arity)]
                self._constraints[cid] = _Constraint(cid, cap, values, truth)
                cids.append(cid)
                if cap not in caps:
                    caps.append(cap)
            risk = risks[min(s, len(risks) - 1)]
            self._stages.append(
                StageSpec(
                    stage_id=f"S{s}",
                    description=f"Stage {s}: resolve {len(cids)} constraints",
                    constraint_ids=cids,
                    required_capabilities=caps,
                    risk=risk,
                    success_predicate="verified_score >= 0.85",
                    verification_intensity=0.45 if risk != RiskLevel.HIGH else 0.90,
                )
            )

    # -- introspection ------------------------------------------------------
    def stages(self) -> List[StageSpec]:
        return list(self._stages)

    def capability_catalog(self) -> List[str]:
        return list(self._caps)

    def value_space(self, constraint_id: str) -> List[str]:
        return list(self._constraints[constraint_id].values)

    def capability_for(self, constraint_id: str) -> str:
        return self._constraints[constraint_id].capability

    def truth_of(self, constraint_id: str) -> str:
        return self._constraints[constraint_id].truth

    def all_constraints(self) -> List[str]:
        return list(self._constraints.keys())

    # -- agent-facing oracles ----------------------------------------------
    def _p_correct(self, skill: float) -> float:
        return max(0.0, min(0.99, self.floor_accuracy + self.skill_gain * skill))

    def propose(self, constraint_id: str, agent_id: str, skill: float, nonce: str) -> str:
        c = self._constraints[constraint_id]
        rng = rng_for("propose", self.seed, constraint_id, agent_id, nonce)
        if rng.random() < self._p_correct(skill):
            return c.truth
        wrong = [v for v in c.values if v != c.truth]
        return wrong[rng.randrange(len(wrong))]

    def verify(self, constraint_id: str, value: str, verifier_skill: float, nonce: str) -> bool:
        c = self._constraints[constraint_id]
        rng = rng_for("verify", self.seed, constraint_id, value, nonce)
        correct = value == c.truth
        fn = self.verifier_false_negative * (1.0 - 0.7 * verifier_skill)
        fp = fn * 0.5
        if correct:
            return rng.random() >= fn          # occasionally rejects a true value
        return rng.random() < fp               # occasionally accepts a false one

    def attack(self, constraint_id: str, value: str, attacker_skill: float, nonce: str) -> bool:
        c = self._constraints[constraint_id]
        rng = rng_for("attack", self.seed, constraint_id, value, nonce)
        if value == c.truth:
            # A correct assignment can only be "broken" by a spurious attack.
            return rng.random() < 0.05 * (1.0 - attacker_skill)
        return rng.random() < (0.35 + 0.6 * attacker_skill)

    # -- evaluation ---------------------------------------------------------
    def true_score(self, assignment: Dict[str, str]) -> float:
        if not self._constraints:
            return 0.0
        total = sum(c.weight for c in self._constraints.values())
        hit = sum(
            c.weight for cid, c in self._constraints.items()
            if assignment.get(cid) == c.truth
        )
        return hit / total
