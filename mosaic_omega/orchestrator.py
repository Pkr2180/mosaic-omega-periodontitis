"""MOSAIC-Omega top-level orchestrator."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import MosaicConfig
from .failsafe import BudgetManager, CheckpointStore
from .governance import ContractLedger
from .kernel import AgentPruner, DynamicAgentProvisioner, MissionKernel
from .llm import LLMBackend
from .loop import FailSafeLoop, LoopOutcome
from .memory import MemoryFabric
from .metrics import MetricsEngine
from .problem import Problem
from .rng import stable_sig
from .topology import TopologyGraph
from .types import Candidate, Claim, MissionSpec, Phase, RunTrace, Termination
from .universes import UniverseManager


@dataclass
class RunResult:
    mission: MissionSpec
    termination: Termination
    final_candidate: Optional[Candidate]
    unresolved_constraints: List[str]
    stage_outcomes: List[LoopOutcome]
    trace: RunTrace
    metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def resolved(self) -> bool:
        return not self.unresolved_constraints and self.termination == Termination.CONVERGED

    def summary(self) -> str:
        score = self.final_candidate.composite_score if self.final_candidate else 0.0
        gt = self.metrics.get("outcome", {}).get("ground_truth_accuracy")
        gt_s = f"{gt:.3f}" if isinstance(gt, float) else "n/a"
        return (
            f"MOSAIC-Omega | termination={self.termination.value} "
            f"| composite={score:.3f} | ground_truth={gt_s} "
            f"| iterations={self.trace.iterations} "
            f"| unresolved={len(self.unresolved_constraints)}"
        )


class MosaicOmega:
    """Self-constructing, self-pruning, self-routing, self-testing,
    self-repairing, rollback-capable, convergence-controlled agentic system."""

    def __init__(self, config: Optional[MosaicConfig] = None,
                 backend: Optional[LLMBackend] = None) -> None:
        self.cfg = config or MosaicConfig()
        self.backend = backend

    def solve(self, problem: Problem, goal: Optional[str] = None) -> RunResult:
        started = time.perf_counter()
        goal = goal or problem.goal
        trace = RunTrace()

        mission = MissionKernel(self.cfg).compile(goal, problem)
        trace.mission = mission

        memory = MemoryFabric()
        memory.set("goal", goal)
        memory.set("mission_id", mission.mission_id)

        provisioner = DynamicAgentProvisioner(self.cfg, problem)
        universes = UniverseManager(self.cfg, problem, self.backend)
        universes.spawn(memory)
        topology = TopologyGraph(self.cfg)
        contracts = ContractLedger(max_depth=self.cfg.max_delegation_depth)
        budgets = BudgetManager(self.cfg)
        checkpoints = CheckpointStore()
        pruner = AgentPruner(self.cfg)

        checkpoints.commit(-1, Phase.OBSERVE,
                           {"iteration": -1, "assignment": {}, "score": 0.0,
                            "invariant_ok": True}, branch="root")

        loop = FailSafeLoop(
            self.cfg, problem, mission, trace,
            memory=memory, provisioner=provisioner, universes=universes,
            topology=topology, contracts=contracts, budgets=budgets,
            checkpoints=checkpoints, pruner=pruner,
        )

        outcomes: List[LoopOutcome] = []
        for stage in mission.stages:
            outcome = loop.run_stage(stage)
            outcomes.append(outcome)
            if outcome.termination in (
                Termination.BUDGET_EXHAUSTED,
                Termination.ESCALATED_UNRESOLVED,
                Termination.DEADLOCK,
            ):
                break
        terminal = self._aggregate_termination([o.termination for o in outcomes])

        final = self._assemble_final(memory, trace, outcomes)
        unresolved = sorted({c for o in outcomes for c in o.unresolved_constraints})
        covered = set(final.assignment) if final else set()
        unresolved += [c for c in mission.all_constraints if c not in covered]
        unresolved = sorted(set(unresolved))

        if unresolved and terminal == Termination.CONVERGED:
            terminal = Termination.UNRESOLVED

        trace.termination = terminal
        trace.final_candidate = final
        trace.tokens_used = budgets.tokens_used
        trace.tool_calls_used = budgets.tool_calls_used
        trace.wall_clock_s = time.perf_counter() - started
        trace.budget_overruns.extend(budgets.overruns)
        trace.idempotent_hits = loop.idempotency.hits
        trace.duplicates_prevented = loop.idempotency.duplicates_prevented
        trace.isolation_purity = universes.isolation_purity()

        metrics = MetricsEngine(trace, problem).compute()
        return RunResult(mission, terminal, final, unresolved, outcomes, trace, metrics)

    # ------------------------------------------------------------------
    SEVERITY = [
        Termination.ESCALATED_UNRESOLVED,
        Termination.DEADLOCK,
        Termination.BUDGET_EXHAUSTED,
        Termination.OSCILLATION,
        Termination.DUPLICATE_LOOP,
        Termination.STAGNATION,
        Termination.MAX_ITERATIONS,
        Termination.NEGATIVE_EVOI,
        Termination.UNRESOLVED,
        Termination.SAFE_STOP,
        Termination.CONVERGED,
    ]

    @classmethod
    def _aggregate_termination(cls, terminations: List[Termination]) -> Termination:
        if not terminations:
            return Termination.UNRESOLVED
        return min(terminations, key=lambda t: cls.SEVERITY.index(t))

    @staticmethod
    def _assemble_final(memory: MemoryFabric, trace: RunTrace,
                        outcomes: List[LoopOutcome]) -> Optional[Candidate]:
        assignment = {cid: c.value for cid, c in memory.commitment.items()}
        if not assignment:
            best = [o.final_candidate for o in outcomes if o.final_candidate]
            return max(best, key=lambda c: c.composite_score) if best else None
        claims: List[Claim] = []
        seen = set()
        for cand in reversed(trace.candidates):
            for cl in cand.claims:
                if cl.constraint_id in assignment and cl.value == assignment[cl.constraint_id] \
                        and cl.constraint_id not in seen:
                    claims.append(cl)
                    seen.add(cl.constraint_id)
        stage_cands = [o.final_candidate for o in outcomes if o.final_candidate]
        composite = (
            sum(c.composite_score for c in stage_cands) / len(stage_cands)
            if stage_cands else 0.0
        )
        survival = (
            sum(c.falsification_survival for c in stage_cands) / len(stage_cands)
            if stage_cands else 1.0
        )
        verified = [c for c in claims if c.verified is not None]
        verified_score = (
            (sum(1 for c in verified if c.verified) + 0.5 * (len(claims) - len(verified)))
            / len(claims) if claims else 0.0
        )
        return Candidate(
            candidate_id=stable_sig("final", tuple(sorted(assignment.items()))),
            universe="root",
            iteration=trace.iterations,
            assignment=assignment,
            claims=claims,
            authors=sorted({c.author for c in claims}),
            raw_score=verified_score,
            verified_score=verified_score,
            falsification_survival=survival,
            jury_score=composite,
            composite_score=composite,
            confidence=(sum(c.confidence for c in claims) / len(claims)) if claims else 0.5,
            is_minority=any(c.is_minority for c in stage_cands),
        )
