"""Mission Kernel, Dynamic Agent Provisioning, Agent Pruning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .config import MosaicConfig
from .problem import Problem
from .rng import rng_for, stable_sig
from .types import (
    AgentRole,
    AgentRuntime,
    AgentSpec,
    MissionSpec,
    RiskLevel,
    StageSpec,
)


# ---------------------------------------------------------------------------
class MissionKernel:
    """Compiles a goal into an executable agent specification."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    def compile(self, goal: str, problem: Problem) -> MissionSpec:
        stages: List[StageSpec] = []
        for s in problem.stages():
            intensity = (
                self.config.high_risk_verification_fraction
                if s.risk == RiskLevel.HIGH
                else self.config.base_verification_fraction
            )
            stages.append(
                StageSpec(
                    stage_id=s.stage_id,
                    description=s.description,
                    constraint_ids=list(s.constraint_ids),
                    required_capabilities=list(s.required_capabilities),
                    risk=s.risk,
                    success_predicate=s.success_predicate,
                    verification_intensity=intensity,
                )
            )
        return MissionSpec(
            mission_id=stable_sig("mission", goal, len(stages)),
            goal=goal,
            stages=stages,
            capability_catalog=list(problem.capability_catalog()),
            acceptance_threshold=0.85,
        )


# ---------------------------------------------------------------------------
@dataclass
class ProvisionResult:
    created: List[AgentSpec]
    reused: List[str]
    uncovered: List[str]


class DynamicAgentProvisioner:
    """Creates only the agents a stage actually needs (greedy set cover over
    the capability gap), plus the fixed adversarial/adjudication complement."""

    def __init__(self, config: MosaicConfig, problem: Problem) -> None:
        self.config = config
        self.problem = problem
        self._counter = 0

    def _new_id(self, role: AgentRole, universe: str, tag: str) -> str:
        self._counter += 1
        return f"{role.value[:4]}-{universe}-{tag}-{self._counter:03d}"

    def _skill_profile(self, primary: Sequence[str], universe: str,
                       tag: str, strength: float) -> Dict[str, float]:
        rng = rng_for("skill", universe, tag, tuple(primary), self.config.seed)
        profile: Dict[str, float] = {}
        for cap in self.problem.capability_catalog():
            if cap in primary:
                profile[cap] = max(0.0, min(1.0, strength + rng.uniform(-0.10, 0.10)))
            else:
                profile[cap] = max(0.0, min(1.0, 0.18 + rng.uniform(-0.12, 0.18)))
        return profile

    def provision_for_stage(
        self,
        stage: StageSpec,
        active: Dict[str, AgentRuntime],
        iteration: int,
        universe: str,
        strategy: str = "conservative",
    ) -> ProvisionResult:
        needed: Set[str] = set(stage.required_capabilities)
        covered: Set[str] = set()
        reused: List[str] = []
        for aid, rt in active.items():
            if not rt.alive or rt.spec.role != AgentRole.SPECIALIST:
                continue
            overlap = rt.spec.capabilities & needed
            if overlap and rt.reputation >= 0.35:
                covered |= overlap
                reused.append(aid)

        gap = sorted(needed - covered)
        created: List[AgentSpec] = []
        strength = {"conservative": 0.72, "exploratory": 0.60, "adversarial": 0.66}.get(
            strategy, 0.68
        )
        # Greedy set cover: pack up to 2 capabilities per specialist.
        i = 0
        while i < len(gap) and len(active) + len(created) < self.config.max_active_agents:
            bundle = gap[i:i + 2]
            spec = AgentSpec(
                agent_id=self._new_id(AgentRole.SPECIALIST, universe, stage.stage_id),
                role=AgentRole.SPECIALIST,
                capabilities=set(bundle),
                skill=self._skill_profile(bundle, universe, f"{stage.stage_id}:{i}", strength),
                token_budget=self.config.per_agent_token_budget,
                wall_clock_budget_s=self.config.per_agent_wall_clock_s,
                created_iteration=iteration,
                universe=universe,
            )
            created.append(spec)
            i += 2

        uncovered = [c for c in gap
                     if not any(c in s.capabilities for s in created)]
        return ProvisionResult(created, reused, uncovered)

    def provision_support(self, stage: StageSpec, iteration: int, universe: str,
                          n_falsifiers: int, n_jurors: int) -> List[AgentSpec]:
        """Verifier, falsifiers, contradiction, minority, jurors, watchdog."""
        caps = list(stage.required_capabilities) or self.problem.capability_catalog()[:2]
        out: List[AgentSpec] = []

        def mk(role: AgentRole, tag: str, primary: Sequence[str], strength: float,
               ttl: Optional[int] = None) -> AgentSpec:
            return AgentSpec(
                agent_id=self._new_id(role, universe, tag),
                role=role,
                capabilities=set(primary),
                skill=self._skill_profile(primary, universe, f"{tag}:{role.value}", strength),
                token_budget=self.config.per_agent_token_budget,
                wall_clock_budget_s=self.config.per_agent_wall_clock_s,
                ttl=ttl,
                created_iteration=iteration,
                universe=universe,
            )

        out.append(mk(AgentRole.VERIFIER, stage.stage_id, caps, 0.70))
        for k in range(n_falsifiers):
            out.append(mk(AgentRole.FALSIFIER, f"{stage.stage_id}f{k}", caps, 0.68))
        out.append(mk(AgentRole.CONTRADICTION, stage.stage_id, caps, 0.62))
        out.append(mk(AgentRole.MINORITY, stage.stage_id, caps, 0.55))
        for k in range(n_jurors):
            out.append(mk(AgentRole.JUROR, f"{stage.stage_id}j{k}", caps, 0.64))
        out.append(mk(AgentRole.WATCHDOG, stage.stage_id, caps, 0.50))
        return out

    def spawn_micro_agent(self, constraint_id: str, iteration: int,
                          universe: str) -> AgentSpec:
        cap = self.problem.capability_for(constraint_id)
        return AgentSpec(
            agent_id=self._new_id(AgentRole.MICRO, universe, constraint_id),
            role=AgentRole.MICRO,
            capabilities={cap},
            skill=self._skill_profile([cap], universe, f"micro:{constraint_id}", 0.78),
            token_budget=max(600, self.config.per_agent_token_budget // 8),
            wall_clock_budget_s=max(2.0, self.config.per_agent_wall_clock_s / 6),
            ttl=self.config.micro_agent_ttl,
            created_iteration=iteration,
            universe=universe,
        )

    def spawn_meta_agent(self, iteration: int, universe: str) -> AgentSpec:
        caps = self.problem.capability_catalog()
        return AgentSpec(
            agent_id=self._new_id(AgentRole.META, universe, "escalation"),
            role=AgentRole.META,
            capabilities=set(caps),
            skill={c: 0.80 for c in caps},
            token_budget=self.config.per_agent_token_budget,
            wall_clock_budget_s=self.config.per_agent_wall_clock_s,
            created_iteration=iteration,
            universe=universe,
        )


# ---------------------------------------------------------------------------
@dataclass
class PruneDecision:
    agent_id: str
    utility: float
    reason: str
    ground_truth_useful: Optional[bool] = None   # for pruning precision/recall


class AgentPruner:
    """Terminates redundant or low-utility agents.

    utility = w1*contribution + w2*reputation - w3*cost - w4*redundancy
    Never prunes the sovereign, protected roles, or agents inside their
    grace window. Micro-agents expire on TTL.
    """

    W_CONTRIB, W_REP, W_COST, W_REDUND = 0.40, 0.30, 0.15, 0.35
    PROTECTED = {AgentRole.WATCHDOG, AgentRole.META}
    # Only producer agents may be pruned for low utility; the adversarial and
    # adjudication complement must persist for the stage or verification
    # intensity silently collapses.
    UTILITY_PRUNABLE = {AgentRole.SPECIALIST, AgentRole.MICRO}

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        if not a and not b:
            return 1.0
        u = a | b
        return len(a & b) / len(u) if u else 0.0

    def utility(self, rt: AgentRuntime, max_contrib: float) -> float:
        contrib = rt.contributions / max_contrib if max_contrib > 0 else 0.0
        cost = rt.tokens_used / max(1, rt.spec.token_budget)
        return (
            self.W_CONTRIB * contrib
            + self.W_REP * rt.reputation
            - self.W_COST * cost
        )

    def prune(
        self,
        runtimes: Dict[str, AgentRuntime],
        iteration: int,
        sovereign: Optional[str],
        required_caps: Set[str],
        ground_truth_skill: Optional[Dict[str, float]] = None,
    ) -> List[PruneDecision]:
        decisions: List[PruneDecision] = []
        alive = {a: r for a, r in runtimes.items() if r.alive}
        max_contrib = max((r.contributions for r in alive.values()), default=0.0)

        scored: List[Tuple[str, float]] = sorted(
            ((a, self.utility(r, max_contrib)) for a, r in alive.items()),
            key=lambda kv: kv[1],
            reverse=True,
        )
        util_map = dict(scored)
        # redundancy is only meaningful within a role: a second falsifier or
        # juror is plurality, not duplication.
        kept_caps: Dict[AgentRole, List[Tuple[str, Set[str]]]] = {}

        for aid, util in scored:
            rt = alive[aid]
            role = rt.spec.role
            kept_caps.setdefault(role, [])
            if role in self.PROTECTED or aid == sovereign:
                kept_caps[role].append((aid, rt.spec.capabilities))
                continue
            # TTL expiry for ephemeral micro-agents
            if rt.spec.ttl is not None and iteration - rt.spec.created_iteration >= rt.spec.ttl:
                rt.alive = False
                rt.pruned_reason = "ttl_expired"
                decisions.append(PruneDecision(aid, util, "ttl_expired"))
                continue
            if iteration - rt.spec.created_iteration < self.config.prune_grace_iterations:
                kept_caps[role].append((aid, rt.spec.capabilities))
                continue
            if role not in self.UTILITY_PRUNABLE:
                kept_caps[role].append((aid, rt.spec.capabilities))
                continue

            peers = kept_caps[role]
            redundancy = max(
                (self._jaccard(rt.spec.capabilities, caps) for _, caps in peers),
                default=0.0,
            )
            adj = util - self.W_REDUND * redundancy
            if redundancy >= self.config.redundancy_jaccard and peers:
                rt.alive = False
                rt.pruned_reason = f"redundant:{redundancy:.2f}"
                decisions.append(PruneDecision(aid, adj, "redundant"))
                continue
            n_alive = sum(1 for d in alive.values() if d.alive)
            if adj < self.config.prune_utility_threshold and n_alive > self.config.min_active_agents:
                rt.alive = False
                rt.pruned_reason = f"low_utility:{adj:.2f}"
                decisions.append(PruneDecision(aid, adj, "low_utility"))
                continue
            kept_caps[role].append((aid, rt.spec.capabilities))

        if ground_truth_skill is not None:
            for d in decisions:
                rt = runtimes.get(d.agent_id)
                if rt is not None and rt.spec.role in self.UTILITY_PRUNABLE:
                    d.ground_truth_useful = ground_truth_skill.get(d.agent_id, 0.0) >= 0.98
        return decisions
