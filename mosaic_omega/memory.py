"""Five-stratum memory fabric.

working      - volatile scratch for the current iteration
episodic     - what happened, per iteration, per universe
procedural   - reusable recipes keyed by capability, with success statistics
failure      - signatures of things that already went wrong (never repeat them)
commitment   - decisions the system has bound itself to (consistency guard)
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .rng import stable_sig


@dataclass
class Episode:
    iteration: int
    universe: str
    phase: str
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Procedure:
    capability: str
    recipe: str
    uses: int = 0
    successes: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.uses if self.uses else 0.5


@dataclass
class FailureRecord:
    signature: str
    kind: str
    detail: str
    count: int = 1
    last_iteration: int = 0


@dataclass
class Commitment:
    constraint_id: str
    value: str
    agent: str
    iteration: int
    checkpoint_id: Optional[str]
    rationale: str = ""


class MemoryFabric:
    def __init__(self) -> None:
        self.working: Dict[str, Any] = {}
        self.episodic: List[Episode] = []
        self.procedural: Dict[str, Procedure] = {}
        self.failure: Dict[str, FailureRecord] = {}
        self.commitment: Dict[str, Commitment] = {}

    # -- working ------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        self.working[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.working.get(key, default)

    def clear_working(self) -> None:
        self.working.clear()

    # -- episodic -----------------------------------------------------------
    def record_episode(self, iteration: int, universe: str, phase: str,
                       summary: str, **payload: Any) -> None:
        self.episodic.append(Episode(iteration, universe, phase, summary, payload))

    def recent_episodes(self, n: int = 10) -> List[Episode]:
        return self.episodic[-n:]

    # -- procedural ---------------------------------------------------------
    def learn_procedure(self, capability: str, recipe: str, success: bool) -> Procedure:
        proc = self.procedural.get(capability)
        if proc is None:
            proc = Procedure(capability=capability, recipe=recipe)
            self.procedural[capability] = proc
        proc.uses += 1
        proc.successes += int(success)
        if success:
            proc.recipe = recipe
        return proc

    def best_recipe(self, capability: str) -> Optional[str]:
        proc = self.procedural.get(capability)
        return proc.recipe if proc and proc.success_rate >= 0.5 else None

    # -- failure ------------------------------------------------------------
    @staticmethod
    def failure_signature(*parts: Any) -> str:
        return stable_sig("failure", *parts)

    def record_failure(self, signature: str, kind: str, detail: str,
                       iteration: int = 0) -> FailureRecord:
        rec = self.failure.get(signature)
        if rec is None:
            rec = FailureRecord(signature, kind, detail, 0, iteration)
            self.failure[signature] = rec
        rec.count += 1
        rec.last_iteration = iteration
        rec.detail = detail
        return rec

    def is_known_failure(self, signature: str) -> bool:
        return signature in self.failure

    # -- commitment ---------------------------------------------------------
    def commit(self, constraint_id: str, value: str, agent: str, iteration: int,
               checkpoint_id: Optional[str] = None, rationale: str = "") -> None:
        self.commitment[constraint_id] = Commitment(
            constraint_id, value, agent, iteration, checkpoint_id, rationale
        )

    def commitment_conflict(self, constraint_id: str, value: str) -> bool:
        c = self.commitment.get(constraint_id)
        return c is not None and c.value != value

    def release_commitment(self, constraint_id: str) -> None:
        self.commitment.pop(constraint_id, None)

    # -- snapshot / restore (used by checkpointing & universe isolation) -----
    def snapshot(self) -> Dict[str, Any]:
        return {
            "working": copy.deepcopy(self.working),
            "episodic": [asdict(e) for e in self.episodic],
            "procedural": {k: asdict(v) for k, v in self.procedural.items()},
            "failure": {k: asdict(v) for k, v in self.failure.items()},
            "commitment": {k: asdict(v) for k, v in self.commitment.items()},
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        self.working = copy.deepcopy(snap.get("working", {}))
        self.episodic = [Episode(**e) for e in snap.get("episodic", [])]
        self.procedural = {k: Procedure(**v) for k, v in snap.get("procedural", {}).items()}
        self.failure = {k: FailureRecord(**v) for k, v in snap.get("failure", {}).items()}
        self.commitment = {k: Commitment(**v) for k, v in snap.get("commitment", {}).items()}

    def fork(self, universe: str) -> "MemoryFabric":
        """Isolated copy for a Parallel Agent Universe.

        Failure and procedural memory carry over (hard-won knowledge), episodic
        memory is tagged, working memory starts empty, commitments are copied
        but may diverge inside the branch.
        """
        child = MemoryFabric()
        child.procedural = {k: Procedure(**asdict(v)) for k, v in self.procedural.items()}
        child.failure = {k: FailureRecord(**asdict(v)) for k, v in self.failure.items()}
        child.commitment = {k: Commitment(**asdict(v)) for k, v in self.commitment.items()}
        child.set("universe", universe)
        return child

    def digest(self) -> str:
        return stable_sig(json.dumps({
            "commitment": {k: v.value for k, v in sorted(self.commitment.items())},
            "failures": sorted(self.failure.keys()),
        }, sort_keys=True))
