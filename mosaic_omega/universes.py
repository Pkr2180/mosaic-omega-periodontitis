"""Parallel Agent Universes: isolated reasoning branches."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from .agents import BaseAgent, build_agent
from .config import MosaicConfig
from .llm import LLMBackend
from .memory import MemoryFabric
from .problem import Problem
from .routing import ReputationRouter
from .topology import SovereigntyController
from .types import AgentRole, AgentRuntime, AgentSpec, Candidate


@dataclass
class UniverseState:
    universe_id: str
    strategy: str
    memory: MemoryFabric
    runtimes: Dict[str, AgentRuntime] = field(default_factory=dict)
    agents: Dict[str, BaseAgent] = field(default_factory=dict)
    sovereignty: Optional[SovereigntyController] = None
    router: Optional[ReputationRouter] = None
    branch: str = "root"
    poisoned: bool = False
    blocked: Set[str] = field(default_factory=set)
    candidate: Optional[Candidate] = None
    provenance: Set[str] = field(default_factory=set)
    restarts: int = 0

    def alive_agents(self, role: Optional[AgentRole] = None) -> List[AgentRuntime]:
        return [
            r for r in self.runtimes.values()
            if r.alive and (role is None or r.spec.role == role)
        ]

    def agents_of(self, role: AgentRole) -> List[BaseAgent]:
        return [
            self.agents[r.agent_id] for r in self.alive_agents(role)
            if r.agent_id in self.agents
        ]

    def node_id(self, agent_id: str) -> str:
        return f"{self.universe_id}::{agent_id}"


class UniverseManager:
    """Creates, isolates, audits and restarts parallel universes."""

    def __init__(self, config: MosaicConfig, problem: Problem,
                 backend: Optional[LLMBackend] = None) -> None:
        self.config = config
        self.problem = problem
        self.backend = backend
        self.universes: Dict[str, UniverseState] = {}
        self.contamination_events: List[Dict[str, Any]] = []

    def spawn(self, root_memory: MemoryFabric, n: Optional[int] = None) -> List[UniverseState]:
        n = n or self.config.n_universes
        strategies = list(self.config.universe_strategies)
        out: List[UniverseState] = []
        for i in range(n):
            uid = f"U{i}"
            strategy = strategies[i % len(strategies)]
            state = UniverseState(
                universe_id=uid,
                strategy=strategy,
                memory=root_memory.fork(uid),
                sovereignty=SovereigntyController(self.config),
                router=ReputationRouter(self.config),
                branch=f"{uid}-b0",
            )
            self.universes[uid] = state
            out.append(state)
        return out

    def install(self, state: UniverseState, specs: Sequence[AgentSpec]) -> List[AgentRuntime]:
        created: List[AgentRuntime] = []
        for spec in specs:
            if spec.agent_id in state.runtimes:
                continue
            spec.universe = state.universe_id
            rt = AgentRuntime(spec=spec)
            state.runtimes[spec.agent_id] = rt
            state.agents[spec.agent_id] = build_agent(rt, self.problem, self.backend)
            created.append(rt)
        return created

    def restart(self, state: UniverseState, root_memory: MemoryFabric) -> UniverseState:
        """Poisoned-branch recovery: rebuild the universe from root knowledge."""
        state.restarts += 1
        state.memory = root_memory.fork(state.universe_id)
        state.runtimes.clear()
        state.agents.clear()
        state.candidate = None
        state.provenance.clear()
        state.blocked.clear()
        state.poisoned = False
        state.branch = f"{state.universe_id}-b{state.restarts}"
        state.sovereignty = SovereigntyController(self.config)
        state.router = ReputationRouter(self.config)
        return state

    # -- isolation audit ----------------------------------------------------
    def isolation_violations(self) -> List[Dict[str, Any]]:
        """Cross-universe claim leakage must be zero. Any shared claim id is a
        contamination event (measured as `branch_isolation_purity`)."""
        violations: List[Dict[str, Any]] = []
        ids = sorted(self.universes)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = self.universes[ids[i]], self.universes[ids[j]]
                shared = a.provenance & b.provenance
                if shared:
                    violations.append(
                        {"a": a.universe_id, "b": b.universe_id,
                         "shared": sorted(shared)[:5], "count": len(shared)}
                    )
        self.contamination_events.extend(violations)
        return violations

    def isolation_purity(self) -> float:
        total = sum(len(u.provenance) for u in self.universes.values())
        if total == 0:
            return 1.0
        shared = sum(v["count"] for v in self.isolation_violations())
        return max(0.0, 1.0 - shared / total)

    def candidates(self) -> List[Candidate]:
        return [u.candidate for u in self.universes.values() if u.candidate is not None]
