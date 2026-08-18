"""The fail-safe control loop.

Observe -> Plan -> Route -> Delegate -> Execute -> Verify -> Falsify -> Score
-> Commit/Rollback -> Rewire -> Continue/Stop
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .adjudication import (
    BlindedJury,
    ContradictionScanner,
    FalsificationEngine,
    MinorityPreserver,
)
from .agents import (
    ContradictionAgent,
    FalsifierAgent,
    JurorAgent,
    MinorityPreservationAgent,
    VerifierAgent,
    WatchdogAgent,
    MetaAgent,
)
from .config import MosaicConfig
from .failsafe import (
    BudgetManager,
    CheckpointStore,
    IdempotencyLedger,
    LoopGuards,
    RecoveryManager,
)
from .governance import BlindingFilter, BlindingPolicy, ContractLedger
from .kernel import AgentPruner, DynamicAgentProvisioner, MissionKernel
from .memory import MemoryFabric
from .problem import Problem
from .rng import stable_sig
from .topology import TopologyGraph
from .types import (
    AgentRole,
    Candidate,
    Claim,
    FailureClass,
    MissionSpec,
    Phase,
    RiskLevel,
    RunTrace,
    StageSpec,
    Termination,
)
from .universes import UniverseManager, UniverseState


@dataclass
class LoopOutcome:
    termination: Termination
    final_candidate: Optional[Candidate]
    unresolved_constraints: List[str] = field(default_factory=list)
    stage_id: str = ""


class FailSafeLoop:
    """Executes one mission stage under full fail-safe governance."""

    def __init__(
        self,
        config: MosaicConfig,
        problem: Problem,
        mission: MissionSpec,
        trace: RunTrace,
        *,
        memory: MemoryFabric,
        provisioner: DynamicAgentProvisioner,
        universes: UniverseManager,
        topology: TopologyGraph,
        contracts: ContractLedger,
        budgets: BudgetManager,
        checkpoints: CheckpointStore,
        pruner: AgentPruner,
    ) -> None:
        self.cfg = config
        self.problem = problem
        self.mission = mission
        self.trace = trace
        self.memory = memory
        self.provisioner = provisioner
        self.universes = universes
        self.topology = topology
        self.contracts = contracts
        self.budgets = budgets
        self.checkpoints = checkpoints
        self.pruner = pruner

        self.guards = LoopGuards(config)
        self.recovery = RecoveryManager(config, checkpoints)
        self.idempotency = IdempotencyLedger()
        self.falsification = FalsificationEngine(config)
        self.contradictions = ContradictionScanner()
        self.minority = MinorityPreserver(config)
        self.jury = BlindedJury(config)
        self.blinder = BlindingFilter(BlindingPolicy(level=config.blinding_level))

        self.iteration = 0
        self.best_score = 0.0
        self.best_candidate: Optional[Candidate] = None
        self.ema_gain = 0.15
        self.prev_edges: Set[Tuple[str, str]] = set()
        self.uncertainty = 1.0
        self.verification_relaxation = 0.0
        self.failing_constraints: Set[str] = set()
        self._sovereignty_cursor: Dict[str, int] = {}

    # ------------------------------------------------------------------
    def _chaos_hit(self, rate: float, kind: str, *coords: Any) -> bool:
        if rate <= 0.0:
            return False
        from .rng import rng_for
        return rng_for("chaos", kind, self.cfg.seed, self.iteration, *coords).random() < rate

    def _event(self, phase: Phase, universe: str = "root", **detail: Any) -> None:
        from .types import LoopEvent
        self.trace.events.append(
            LoopEvent(self.iteration, phase, universe, detail, time.time())
        )

    def _state_signature(self, stage: StageSpec) -> str:
        parts = []
        for u in sorted(self.universes.universes):
            st = self.universes.universes[u]
            sig = st.candidate.signature() if st.candidate else "none"
            parts.append(f"{u}:{sig}:{len(st.alive_agents())}")
        return stable_sig("state", stage.stage_id, tuple(parts),
                          self.memory.digest())

    # ==================================================================
    # PHASE 1 - OBSERVE
    # ==================================================================
    def observe(self, stage: StageSpec) -> Dict[str, Any]:
        watchdog_kills: List[Dict[str, str]] = []
        for st in self.universes.universes.values():
            for wd in st.agents_of(AgentRole.WATCHDOG):
                assert isinstance(wd, WatchdogAgent)
                self.trace.agents_used.add(wd.agent_id)
                out = wd.act({
                    "runtimes": st.runtimes,
                    "now": time.time(),
                    "heartbeat_s": self.cfg.watchdog_heartbeat_s,
                })
                watchdog_kills.extend(out.payload["killed"])
                self.budgets.consume(tokens=out.tokens, tool_calls=1)

        verified = [c for c in self.trace.claims if c.verified is not None]
        coverage = len(verified) / max(1, len(self.trace.claims))
        agreement = self._current_agreement()
        self.uncertainty = max(0.0, min(1.0, 1.0 - 0.5 * coverage - 0.5 * agreement))

        obs = {
            "coverage": coverage,
            "agreement": agreement,
            "uncertainty": self.uncertainty,
            "budget_left": self.budgets.fraction_left(),
            "watchdog_kills": watchdog_kills,
            "failing_constraints": sorted(self.failing_constraints),
        }
        self.memory.record_episode(self.iteration, "root", "observe",
                                   "state observed", **obs)
        self._event(Phase.OBSERVE, **obs)
        return obs

    def _current_agreement(self) -> float:
        cands = self.universes.candidates()
        if len(cands) < 2:
            return 0.0
        sigs = [c.signature() for c in cands]
        top = max(set(sigs), key=sigs.count)
        return sigs.count(top) / len(sigs)

    # ==================================================================
    # PHASE 2 - PLAN
    # ==================================================================
    def plan(self, stage: StageSpec) -> Dict[str, Any]:
        created_total = 0
        uncovered_total: List[str] = []
        for st in self.universes.universes.values():
            result = self.provisioner.provision_for_stage(
                stage, st.runtimes, self.iteration, st.universe_id, st.strategy
            )
            specs = list(result.created)
            if not st.alive_agents(AgentRole.VERIFIER):
                specs += self.provisioner.provision_support(
                    stage, self.iteration, st.universe_id,
                    self.cfg.falsifiers_per_candidate, self.cfg.n_jurors
                )
            # Ephemeral micro-agents for subproblems that keep failing, capped
            # per iteration and never duplicated for a constraint already served.
            served = {
                r.spec.agent_id.rsplit("-", 2)[-2]
                for r in st.alive_agents(AgentRole.MICRO)
            }
            spawned = 0
            for cid in sorted(self.failing_constraints & set(stage.constraint_ids)):
                if spawned >= self.cfg.max_micro_agents_per_iteration:
                    break
                if cid in served:
                    continue
                specs.append(
                    self.provisioner.spawn_micro_agent(cid, self.iteration, st.universe_id)
                )
                spawned += 1
            for rt in self.universes.install(st, specs):
                self.topology.add_node(st.node_id(rt.agent_id))
                self.trace.agents_provisioned.append(rt.spec)
            created_total += len(specs)
            uncovered_total.extend(result.uncovered)

        detail = {"agents_created": created_total, "uncovered_capabilities": uncovered_total,
                  "stage": stage.stage_id}
        self._event(Phase.PLAN, **detail)
        return detail

    # ==================================================================
    # PHASE 3 - ROUTE
    # ==================================================================
    def route(self, stage: StageSpec) -> Dict[str, Dict[str, List[str]]]:
        plan: Dict[str, Dict[str, List[str]]] = {}
        for st in self.universes.universes.values():
            assignments: Dict[str, List[str]] = {}
            affinity = self._topology_affinity(st)
            for cid in stage.constraint_ids:
                cap = self.problem.capability_for(cid)
                decision = st.router.route(
                    task_id=f"{stage.stage_id}:{cid}",
                    capability=cap,
                    runtimes=st.runtimes,
                    iteration=self.iteration,
                    topo_affinity=affinity,
                )
                if decision is None:
                    st.blocked.add(cid)
                    continue
                self.trace.routing.append(decision)
                assignments.setdefault(decision.chosen, []).append(cid)
            plan[st.universe_id] = assignments
        self._event(Phase.ROUTE, tasks=sum(len(v) for a in plan.values() for v in a.values()))
        return plan

    def _topology_affinity(self, st: UniverseState) -> Dict[str, float]:
        sovereign = st.sovereignty.current
        if sovereign is None:
            return {}
        s_node = st.node_id(sovereign)
        out: Dict[str, float] = {}
        for aid in st.runtimes:
            k = self.topology.key(s_node, st.node_id(aid))
            out[aid] = self.topology.weights.get(k, 0.0)
        return out

    # ==================================================================
    # PHASE 4 + 5 - DELEGATE and EXECUTE
    # ==================================================================
    def delegate_and_execute(
        self, stage: StageSpec, plan: Dict[str, Dict[str, List[str]]]
    ) -> Dict[str, Any]:
        executed = 0
        violations = 0
        for st in self.universes.universes.values():
            principal = st.sovereignty.current or "mission_kernel"
            claims: List[Claim] = []
            authors: List[str] = []
            # The standing draft is the real anchoring surface: it overlaps every
            # agent's own constraints. Blinding decides whether they ever see it.
            draft: Dict[str, str] = dict(st.candidate.assignment) if st.candidate else {}
            for agent_id, cids in sorted(plan.get(st.universe_id, {}).items()):
                rt = st.runtimes.get(agent_id)
                if rt is None or not rt.alive:
                    continue
                depth = 1 if agent_id == principal else 2
                try:
                    contract = self.contracts.issue(
                        principal=principal,
                        agent=agent_id,
                        task_id=f"{stage.stage_id}:{st.universe_id}",
                        depth=depth,
                        preconditions=[f"capability:{self.problem.capability_for(c)}"
                                       for c in cids],
                        allowed_tools={"reason", "verify"},
                        forbidden_scopes={f"universe:{o}" for o in self.universes.universes
                                          if o != st.universe_id},
                        deliverable_keys={"claims"},
                        token_budget=rt.spec.token_budget,
                        deadline_s=rt.spec.wall_clock_budget_s,
                    )
                except RecursionError as exc:
                    self.memory.record_failure(
                        MemoryFabric.failure_signature("depth", agent_id),
                        "delegation_depth", str(exc), self.iteration
                    )
                    continue
                self.trace.contracts.append(contract)
                if principal != agent_id:
                    self.topology.add_handoff(st.node_id(principal), st.node_id(agent_id))

                context = {
                    "goal": self.mission.goal,
                    "constraints": cids,
                    "iteration": self.iteration,
                    "universe": st.universe_id,
                    "nonce": f"{stage.stage_id}:{self.iteration}:{st.branch}",
                    "anchor_susceptibility": self.cfg.anchor_susceptibility,
                    # blindable surfaces deliberately included, then stripped:
                    "peer_conclusions": {**draft,
                                         **{c.constraint_id: c.value for c in claims}},
                    "peer_authors": list(authors),
                    "current_best": self.best_candidate.candidate_id if self.best_candidate else "",
                    "reputation_table": {a: round(r.reputation, 3)
                                         for a, r in st.runtimes.items()},
                }
                blinded_ctx, blind_report = self.blinder.apply(context)
                self.trace.blinding_checks += 1
                self.trace.blinding_leaks += int(blind_report.leaked)
                exposed = set(draft) & set(cids)
                if exposed:
                    self.trace.anchor_opportunities += 1

                if self._chaos_hit(self.cfg.chaos_agent_failure_rate,
                                   "agent", agent_id, st.branch):
                    rt.contract_violations += 1
                    violations += 1
                    self.memory.record_failure(
                        MemoryFabric.failure_signature("agent_fault", agent_id),
                        "agent_fault", f"injected fault in {agent_id}", self.iteration
                    )
                    self.contracts.settle(contract, {}, 0, 0.0, set(), set())
                    self.trace.contract_results.append(self.contracts.results[-1])
                    continue

                key = self.idempotency.key(agent_id, "reason", sorted(cids),
                                           self.checkpoints.head.checkpoint_id
                                           if self.checkpoints.head else None)
                try:
                    out = self.idempotency.run_once(
                        key, lambda a=st.agents[agent_id], c=blinded_ctx: a.act(c)
                    )
                except Exception as exc:                      # agent-local containment
                    rt.alive = False
                    rt.pruned_reason = f"exception:{type(exc).__name__}"
                    self.memory.record_failure(
                        MemoryFabric.failure_signature("agent_exc", agent_id, str(exc)),
                        "agent_exception", str(exc), self.iteration
                    )
                    continue
                executed += 1
                self.budgets.consume(tokens=out.tokens, tool_calls=1)

                if exposed and any("anchored:peer" in c.evidence for c in out.claims):
                    self.trace.anchored_outputs += 1

                result = self.contracts.settle(
                    contract, out.as_deliverable(), out.tokens, out.elapsed_s,
                    out.tools_used, out.scopes_touched
                )
                self.trace.contract_results.append(result)
                if not result.ok:
                    violations += 1
                    rt.contract_violations += 1
                    self.memory.record_failure(
                        MemoryFabric.failure_signature("contract", agent_id,
                                                       tuple(result.violations)),
                        "contract_violation", ";".join(result.violations), self.iteration
                    )
                    continue

                claims.extend(out.claims)
                authors.append(agent_id)
                rt.contributions += len(out.claims)
                st.provenance.update(c.claim_id for c in out.claims)
                self.memory.learn_procedure(
                    self.problem.capability_for(cids[0]) if cids else "generic",
                    f"route->{agent_id}", True
                )

            assignment: Dict[str, str] = {}
            kept: List[Claim] = []
            for c in sorted(claims, key=lambda x: (x.constraint_id, -x.confidence, x.claim_id)):
                if c.constraint_id not in assignment:
                    assignment[c.constraint_id] = c.value
                    kept.append(c)
            candidate = Candidate(
                candidate_id=stable_sig("cand", st.universe_id, st.branch, self.iteration),
                universe=st.universe_id,
                iteration=self.iteration,
                assignment=assignment,
                claims=kept,
                authors=sorted(set(authors)),
            )
            history = [c for c in st.memory.get("claim_history", [])
                       if c.iteration >= self.iteration - 2]
            history.extend(claims)
            st.memory.set("claim_history", history)
            st.memory.set("raw_claims", claims)
            st.candidate = candidate
            self.trace.candidates.append(candidate)
            self.trace.claims.extend(kept)
            self.trace.agents_used.update(authors)

        self._event(Phase.DELEGATE, executed=executed, violations=violations)
        self._event(Phase.EXECUTE, candidates=len(self.universes.candidates()))
        return {"executed": executed, "violations": violations}

    # ==================================================================
    # PHASE 6 - VERIFY
    # ==================================================================
    def verify(self, stage: StageSpec) -> Dict[str, Any]:
        intensity = max(0.05, stage.verification_intensity - self.verification_relaxation)
        checked = 0
        for st in self.universes.universes.values():
            if st.candidate is None:
                continue
            for verifier in st.agents_of(AgentRole.VERIFIER):
                out = verifier.act({
                    "claims_to_verify": st.candidate.claims,
                    "verification_intensity": intensity,
                    "nonce": f"{stage.stage_id}:{self.iteration}:{st.branch}",
                })
                checked += out.payload["checked"]
                self.trace.agents_used.add(verifier.agent_id)
                self.budgets.consume(tokens=out.tokens, tool_calls=1)
            for claim in st.candidate.claims:
                rt = st.runtimes.get(claim.author)
                if rt is None or claim.verified is None:
                    continue
                if claim.verified:
                    rt.verified_true += 1
                    st.router.update_reputation(rt, 1, 0)
                else:
                    rt.verified_false += 1
                    st.router.update_reputation(rt, 0, 1)
        for decision in self.trace.routing:
            if decision.realized_success is None and decision.iteration == self.iteration:
                claim = next(
                    (c for c in self.trace.claims
                     if c.author == decision.chosen
                     and decision.task_id.endswith(c.constraint_id)
                     and c.iteration == self.iteration),
                    None,
                )
                if claim is not None and claim.verified is not None:
                    decision.realized_success = bool(claim.verified)
        self._event(Phase.VERIFY, checked=checked, intensity=intensity)
        return {"checked": checked, "intensity": intensity}

    # ==================================================================
    # PHASE 7 - FALSIFY
    # ==================================================================
    def falsify(self, stage: StageSpec) -> Dict[str, Any]:
        n_contradictions = 0
        for st in self.universes.universes.values():
            if st.candidate is None:
                continue
            nonce = f"{stage.stage_id}:{self.iteration}:{st.branch}"
            falsifiers = [a for a in st.agents_of(AgentRole.FALSIFIER)]
            report = self.falsification.run(st.candidate, falsifiers, nonce)
            self.trace.agents_used.update(f.agent_id for f in falsifiers)
            self.budgets.consume(tokens=150 * self.cfg.attacks_per_falsifier * len(falsifiers),
                                 tool_calls=len(falsifiers))
            self.trace.falsifications.append(report)
            for atk in report.attacks:
                if atk.succeeded:
                    self.failing_constraints.add(atk.constraint_id)
                    self.memory.record_failure(
                        MemoryFabric.failure_signature("falsified", atk.constraint_id,
                                                       st.candidate.assignment[atk.constraint_id]),
                        "falsified_assignment",
                        f"{atk.constraint_id}={st.candidate.assignment[atk.constraint_id]}",
                        self.iteration,
                    )
            for claim in st.candidate.claims:
                if claim.falsified:
                    rt = st.runtimes.get(claim.author)
                    if rt:
                        rt.falsified_claims += 1
                        st.router.update_reputation(rt, 0, 1, weight=0.5)

            scanners = st.agents_of(AgentRole.CONTRADICTION)
            if scanners:
                scanned = st.memory.get("claim_history", st.candidate.claims)
                found = self.contradictions.run(
                    scanners[0], scanned,
                    {k: v.value for k, v in self.memory.commitment.items()},
                )
                self.trace.contradictions.extend(found)
                st.candidate.contradiction_penalty = self.contradictions.density(
                    found, len(scanned)
                )
                n_contradictions += len(found)
                self.trace.agents_used.add(scanners[0].agent_id)

        cands = self.universes.candidates()
        evidence_sufficiency = self._evidence_sufficiency(cands)
        consensus = self.minority.analyse(cands, evidence_sufficiency)
        self.trace.entropy_history.append(consensus.entropy)
        advocate = None
        for st in self.universes.universes.values():
            agents = st.agents_of(AgentRole.MINORITY)
            if agents:
                advocate = agents[0]
                break
        preserved = self.minority.preserve(consensus, cands, advocate)
        if preserved is not None:
            self.trace.minority_preserved += 1

        detail = {
            "contradictions": n_contradictions,
            "entropy": consensus.entropy,
            "premature_consensus": consensus.premature,
            "minority_preserved": preserved.candidate_id if preserved else None,
        }
        self._event(Phase.FALSIFY, **detail)
        return detail

    @staticmethod
    def _evidence_sufficiency(cands: Sequence[Candidate]) -> float:
        total = sum(len(c.claims) for c in cands)
        if total == 0:
            return 0.0
        verified = sum(1 for c in cands for cl in c.claims if cl.verified is not None)
        return verified / total

    # ==================================================================
    # PHASE 8 - SCORE
    # ==================================================================
    def score(self, stage: StageSpec) -> Optional[Candidate]:
        cands = self.universes.candidates()
        if not cands:
            return None
        for c in cands:
            verified = [cl for cl in c.claims if cl.verified is not None]
            v_true = sum(1 for cl in verified if cl.verified)
            unknown = len(c.claims) - len(verified)
            c.verified_score = (
                (v_true + 0.5 * unknown) / len(c.claims) if c.claims else 0.0
            )
            c.raw_score = c.verified_score
            c.confidence = (
                sum(cl.confidence for cl in c.claims) / len(c.claims) if c.claims else 0.5
            )

        jurors = []
        for st in self.universes.universes.values():
            jurors.extend(st.agents_of(AgentRole.JUROR))
        jurors = jurors[: max(self.cfg.n_jurors, 3)]
        verdict, leaks, checks = self.jury.adjudicate(
            cands, jurors, f"{stage.stage_id}:{self.iteration}"
        )
        self.trace.verdicts.append(verdict)
        self.trace.blinding_leaks += leaks
        self.trace.blinding_checks += checks
        for j in jurors:
            self.trace.agents_used.add(j.agent_id)
            self.budgets.consume(tokens=200, tool_calls=1)

        for c in cands:
            c.composite_score = max(0.0, min(1.0,
                0.45 * c.verified_score
                + 0.25 * c.falsification_survival
                + 0.20 * c.jury_score
                + 0.10 * c.confidence
                - 0.15 * c.contradiction_penalty
            ))
        winner = max(cands, key=lambda c: (c.composite_score, c.candidate_id))
        self.trace.score_history.append(winner.composite_score)
        self._event(Phase.SCORE, winner=winner.candidate_id,
                    composite=winner.composite_score, margin=verdict.margin)
        return winner

    # ==================================================================
    # PHASE 9 - COMMIT / ROLLBACK
    # ==================================================================
    def commit_or_rollback(self, stage: StageSpec, winner: Optional[Candidate]) -> bool:
        if winner is None:
            self._recover(FailureClass.ORCHESTRATION, "no candidate produced")
            return False

        if self._chaos_hit(self.cfg.chaos_branch_corruption_rate,
                           "branch", winner.candidate_id, self.iteration):
            winner.contradiction_penalty = 1.0

        invariant_ok = (
            winner.falsification_survival >= 0.4
            and winner.contradiction_penalty <= 0.5
            and not self.universes.isolation_violations()
        )
        if not invariant_ok:
            self._recover(FailureClass.BRANCH,
                          f"invariant breach on {winner.candidate_id}")
            return False

        for cid, value in winner.assignment.items():
            if self.memory.commitment_conflict(cid, value):
                prior = self.memory.commitment[cid]
                if winner.composite_score > self.best_score:
                    self.memory.release_commitment(cid)
                else:
                    winner.assignment[cid] = prior.value
        cp = self.checkpoints.commit(
            self.iteration, Phase.COMMIT,
            {
                "iteration": self.iteration,
                "stage": stage.stage_id,
                "assignment": dict(winner.assignment),
                "score": winner.composite_score,
                "survival": winner.falsification_survival,
                "contradiction": winner.contradiction_penalty,
                "invariant_ok": True,
            },
            branch=winner.universe,
        )
        self.trace.checkpoints.append(cp)
        for cid, value in winner.assignment.items():
            claim = next((c for c in winner.claims if c.constraint_id == cid), None)
            self.memory.commit(cid, value, claim.author if claim else "unknown",
                               self.iteration, cp.checkpoint_id)
        if winner.composite_score > self.best_score:
            self.best_score = winner.composite_score
            self.best_candidate = winner
        self.recovery.mark_recovered(self.iteration)
        self._event(Phase.COMMIT, checkpoint=cp.checkpoint_id,
                    score=winner.composite_score)
        return True

    def _recover(self, failure_class: FailureClass, detail: str) -> None:
        def validator(state: Dict[str, Any]) -> bool:
            return bool(state.get("invariant_ok", False))

        def restore(state: Dict[str, Any]) -> None:
            assignment = state.get("assignment", {})
            for cid, value in assignment.items():
                self.memory.commit(cid, value, "rollback", self.iteration)

        record = self.recovery.handle(self.iteration, failure_class, detail,
                                      validator, restore)
        self.trace.recoveries.append(record)
        self._event(Phase.ROLLBACK, failure=failure_class.value, detail=detail,
                    rolled_back_to=record.rolled_back_to, escalated=record.escalated)
        if record.escalated:
            self._escalate(detail)
        else:
            # alternative-branch replay: rebuild the worst universe
            worst = min(
                self.universes.universes.values(),
                key=lambda u: (u.candidate.composite_score if u.candidate else -1.0,
                               u.universe_id),
            )
            worst.poisoned = True
            self.universes.restart(worst, self.memory)

    def _escalate(self, detail: str) -> None:
        spec = self.provisioner.spawn_meta_agent(self.iteration, "root")
        from .agents import build_agent
        from .types import AgentRuntime
        rt = AgentRuntime(spec=spec)
        meta = build_agent(rt, self.problem)
        required = set()
        for s in self.mission.stages:
            required |= set(s.required_capabilities)
        have: Set[str] = set()
        for st in self.universes.universes.values():
            for r in st.alive_agents():
                have |= r.spec.capabilities
        coverage = len(required & have) / len(required) if required else 1.0
        recent_progress = (
            self.trace.score_history[-1] - self.trace.score_history[-2]
            if len(self.trace.score_history) >= 2 else 0.0
        )
        out = meta.act({
            "consecutive_failures": self.recovery.consecutive_failures,
            "capability_coverage": coverage,
            "budget_fraction_left": self.budgets.fraction_left(),
            "recent_progress": recent_progress,
        })
        directive = out.payload["directive"]
        self.trace.escalations.append({
            "iteration": self.iteration, "directive": directive,
            "rationale": out.payload["rationale"], "trigger": detail,
        })
        self.budgets.consume(tokens=out.tokens, tool_calls=1)

        if directive == "relax_verification":
            self.verification_relaxation = min(0.35, self.verification_relaxation + 0.15)
            self.recovery.consecutive_failures = 0
        elif directive == "reprovision_capability":
            self.failing_constraints |= set(self.mission.all_constraints)
            self.recovery.consecutive_failures = 0
        elif directive == "restart_universe":
            for st in list(self.universes.universes.values()):
                self.universes.restart(st, self.memory)
            self.recovery.consecutive_failures = 0
        # 'terminate_unresolved' is handled by the decide phase

    # ==================================================================
    # PHASE 10 - REWIRE
    # ==================================================================
    def rewire(self, stage: StageSpec) -> None:
        capabilities: Dict[str, Set[str]] = {}
        competence: Dict[str, float] = {}
        failure: Dict[str, float] = {}
        evidence: Dict[Tuple[str, str], float] = {}

        for st in self.universes.universes.values():
            sovereign, comp_scores = st.sovereignty.evaluate(
                st.runtimes, stage, self.iteration
            )
            seen = self._sovereignty_cursor.get(st.universe_id, 0)
            new_transfers = st.sovereignty.transfers[seen:]
            self._sovereignty_cursor[st.universe_id] = len(st.sovereignty.transfers)
            self.trace.sovereignty.extend(new_transfers)
            for rt in st.alive_agents():
                node = st.node_id(rt.agent_id)
                capabilities[node] = set(rt.spec.capabilities)
                competence[node] = comp_scores.get(rt.agent_id, rt.reputation)
                failure[node] = rt.failure_rate
            if st.candidate:
                authors = [st.node_id(a) for a in st.candidate.authors]
                bonus = st.candidate.verified_score
                for i in range(len(authors)):
                    for j in range(i + 1, len(authors)):
                        evidence[self.topology.key(authors[i], authors[j])] = bonus
            # isolation: cross-universe edges are contamination
            for other in self.universes.universes.values():
                if other.universe_id == st.universe_id:
                    continue
                for a in st.runtimes:
                    for b in other.runtimes:
                        self.topology.contamination[
                            self.topology.key(st.node_id(a), other.node_id(b))
                        ] = 1.0

        for node in list(self.topology.nodes):
            if node not in capabilities:
                self.topology.remove_node(node)

        snapshot = self.topology.rewire(
            self.iteration, capabilities, competence, failure,
            self.uncertainty, evidence
        )
        self.trace.topology.append(snapshot)
        self.prev_edges = set(self.topology.weights.keys())

        cycle = self.topology.find_handoff_cycle()
        if cycle:
            broken = self.topology.break_cycle(cycle)
            self.trace.guard_trips.append({
                "guard": "circular_handoff", "iteration": self.iteration,
                "detail": f"cycle {cycle} broken at {broken}",
            })

        required = set(stage.required_capabilities)
        for st in self.universes.universes.values():
            # Ground truth for pruning quality: an agent is genuinely useful iff
            # it is non-dominated -- i.e. it is the strongest live agent on at
            # least one capability the stage still requires.
            live = [r for r in st.alive_agents() if r.spec.capabilities & required]
            best_on: Dict[str, float] = {}
            for cap in required:
                best_on[cap] = max((r.spec.skill.get(cap, 0.0) for r in live), default=0.0)
            gt: Dict[str, float] = {}
            for a, r in st.runtimes.items():
                gt[a] = max(
                    (r.spec.skill.get(cap, 0.0) / best_on[cap]
                     for cap in (r.spec.capabilities & required) if best_on.get(cap, 0.0) > 0),
                    default=0.0,
                )
            decisions = self.pruner.prune(
                st.runtimes, self.iteration, st.sovereignty.current, required, gt
            )
            for d in decisions:
                self.topology.remove_node(st.node_id(d.agent_id))
                self.trace.prune_decisions.append({
                    "agent": d.agent_id, "utility": d.utility, "reason": d.reason,
                    "ground_truth_useful": d.ground_truth_useful,
                    "iteration": self.iteration,
                })
        self._event(Phase.REWIRE, edges=snapshot.n_edges,
                    added=snapshot.edges_added, removed=snapshot.edges_removed,
                    modularity=snapshot.modularity)

    # ==================================================================
    # PHASE 11 - CONTINUE / STOP
    # ==================================================================
    def decide(self, stage: StageSpec, winner: Optional[Candidate]) -> Optional[Termination]:
        sig = self._state_signature(stage)
        self.trace.state_signatures.append(sig)
        current = winner.composite_score if winner else 0.0
        self.guards.observe(sig, current, self.iteration)

        realized = (
            self.trace.score_history[-1] - self.trace.score_history[-2]
            if len(self.trace.score_history) >= 2 else current
        )
        self.trace.evoi_realized.append(realized)
        self.ema_gain = 0.6 * self.ema_gain + 0.4 * max(0.0, realized)

        # Value of another iteration = free energy the next rewire can still shed
        # (a *derived* quantity in the units of J), net of its compute/risk cost.
        # See freeenergy.py: EVOI_t = sum (g - kappa*w)^2 / (2 kappa) + lambda_U*U.
        headroom = max(0.0, self.mission.acceptance_threshold - current)
        est_tokens = self.budgets.tokens_used / max(1, self.iteration + 1)
        est_time = self.budgets.elapsed() / max(1, self.iteration + 1)
        risk = (
            (winner.contradiction_penalty if winner else 1.0)
            + (1.0 - (winner.falsification_survival if winner else 0.0))
            + 0.2 * self.recovery.consecutive_failures
        )
        descent = self.topology.predicted_descent
        evoi = (
            self.cfg.evoi_quality_weight * descent * (0.25 + headroom)
            - self.cfg.token_cost_per_unit * est_tokens
            - self.cfg.time_cost_per_second * est_time
            - self.cfg.evoi_risk_weight * risk * 0.1
        )
        self.trace.evoi_predicted.append(evoi)

        if self.trace.escalations and self.trace.escalations[-1]["directive"] == "terminate_unresolved":
            return Termination.ESCALATED_UNRESOLVED

        budget_hit = self.budgets.check()
        if budget_hit:
            self.budgets.record_overrun(budget_hit)
            self.trace.budget_overruns.append(budget_hit)
            return Termination.BUDGET_EXHAUSTED

        verdict = self.trace.verdicts[-1] if self.trace.verdicts else None
        converged = (
            winner is not None
            and winner.composite_score >= self.mission.acceptance_threshold
            and winner.falsification_survival >= 0.75
            and (verdict is None or verdict.margin >= self.cfg.jury_margin_threshold
                 or len(self.universes.candidates()) == 1)
        )
        if converged:
            return Termination.CONVERGED

        for guard, trip in (
            ("duplicate_loop", self.guards.duplicate_loop(self.iteration)),
            ("oscillation", self.guards.oscillation(self.iteration)),
            ("stagnation", self.guards.stagnation(self.iteration)),
        ):
            if trip:
                self.trace.guard_trips.append({
                    "guard": trip.guard, "iteration": trip.iteration,
                    "detail": trip.detail,
                })
                return {
                    "duplicate_loop": Termination.DUPLICATE_LOOP,
                    "oscillation": Termination.OSCILLATION,
                    "stagnation": Termination.STAGNATION,
                }[guard]

        blocked = sorted({c for st in self.universes.universes.values() for c in st.blocked})
        active = sorted({a for st in self.universes.universes.values()
                         for a in (r.agent_id for r in st.alive_agents())})
        if blocked and not active:
            trip = self.guards.deadlock(self.iteration, blocked, blocked)
            if trip:
                self.trace.guard_trips.append({
                    "guard": "deadlock", "iteration": trip.iteration,
                    "detail": trip.detail,
                })
                return Termination.DEADLOCK

        if evoi <= self.cfg.min_evoi and self.iteration >= 2:
            return Termination.NEGATIVE_EVOI

        if self.iteration + 1 >= self.cfg.max_iterations:
            return Termination.MAX_ITERATIONS
        self._event(Phase.DECIDE, evoi=evoi, continue_=True, score=current)
        return None

    # ==================================================================
    def run_stage(self, stage: StageSpec) -> LoopOutcome:
        termination: Optional[Termination] = None
        winner: Optional[Candidate] = None
        self.iteration = 0
        self.best_score = 0.0
        self.best_candidate = None
        self.guards = LoopGuards(self.cfg)
        self.failing_constraints.clear()
        while termination is None:
            self.observe(stage)
            self.plan(stage)
            plan = self.route(stage)
            self.delegate_and_execute(stage, plan)
            self.verify(stage)
            self.falsify(stage)
            winner = self.score(stage)
            self.commit_or_rollback(stage, winner)
            self.rewire(stage)
            termination = self.decide(stage, winner)
            self.iteration += 1
            self.trace.total_iterations += 1
            self.trace.iterations = self.trace.total_iterations

        best = self.best_candidate or winner
        unresolved: List[str] = []
        if best:
            for cid in stage.constraint_ids:
                claim = next((c for c in best.claims if c.constraint_id == cid), None)
                if claim is None or claim.falsified or claim.verified is False:
                    unresolved.append(cid)
        else:
            unresolved = list(stage.constraint_ids)
        return LoopOutcome(termination, best, unresolved, stage.stage_id)
