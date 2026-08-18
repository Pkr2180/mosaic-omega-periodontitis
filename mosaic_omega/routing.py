"""Reputation-weighted routing with oracle-regret instrumentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .config import MosaicConfig
from .types import AgentRole, AgentRuntime, RoutingDecision


class ReputationRouter:
    W_CAP, W_REP, W_LOAD, W_TOPO = 0.40, 0.32, 0.13, 0.15

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.decisions: List[RoutingDecision] = []

    def _load(self, rt: AgentRuntime) -> float:
        return min(1.0, rt.tokens_used / max(1, rt.spec.token_budget))

    def score(self, rt: AgentRuntime, capability: str,
              topo_affinity: float) -> float:
        cap_match = 1.0 if capability in rt.spec.capabilities else 0.15
        return (
            self.W_CAP * cap_match
            + self.W_REP * rt.reputation
            + self.W_LOAD * (1.0 - self._load(rt))
            + self.W_TOPO * topo_affinity
        )

    def route(
        self,
        task_id: str,
        capability: str,
        runtimes: Dict[str, AgentRuntime],
        iteration: int,
        topo_affinity: Optional[Dict[str, float]] = None,
        roles: Sequence[AgentRole] = (AgentRole.SPECIALIST, AgentRole.MICRO),
    ) -> Optional[RoutingDecision]:
        topo_affinity = topo_affinity or {}
        pool = {
            a: r for a, r in runtimes.items()
            if r.alive and r.spec.role in roles
        }
        if not pool:
            return None
        ranked = sorted(
            ((a, self.score(r, capability, topo_affinity.get(a, 0.0)))
             for a, r in pool.items()),
            key=lambda kv: (-kv[1], kv[0]),
        )
        chosen = ranked[0][0]
        # oracle = highest latent skill on the required capability
        oracle = max(sorted(pool), key=lambda a: pool[a].spec.skill.get(capability, 0.0))
        decision = RoutingDecision(
            iteration=iteration,
            task_id=task_id,
            chosen=chosen,
            ranked=ranked,
            oracle_choice=oracle,
            oracle_utility=pool[oracle].spec.skill.get(capability, 0.0),
            chosen_utility=pool[chosen].spec.skill.get(capability, 0.0),
            predicted_reliability=pool[chosen].reputation,
        )
        self.decisions.append(decision)
        return decision

    @staticmethod
    def update_reputation(rt: AgentRuntime, successes: int, failures: int,
                          weight: float = 1.0) -> None:
        rt.alpha += weight * successes
        rt.beta += weight * failures

    def load_gini(self, runtimes: Dict[str, AgentRuntime]) -> float:
        loads = sorted(r.tokens_used for r in runtimes.values() if r.alive)
        n = len(loads)
        if n == 0 or sum(loads) == 0:
            return 0.0
        cum = sum((i + 1) * v for i, v in enumerate(loads))
        return (2 * cum) / (n * sum(loads)) - (n + 1) / n
