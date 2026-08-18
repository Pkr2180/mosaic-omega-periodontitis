"""Agent taxonomy.

Every agent has (a) a deterministic heuristic cognition path so the system runs
with no network, and (b) an optional LLM path when a backend is attached.
Cognition is always wrapped by the contract layer and the blinding filter.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from .llm import LLMBackend, NullBackend, parse_json_block
from .problem import Problem
from .rng import rng_for, stable_sig
from .types import (
    AgentRole,
    AgentRuntime,
    AgentSpec,
    Attack,
    Candidate,
    Claim,
    Contradiction,
    FalsificationReport,
    JurorBallot,
)


@dataclass
class AgentOutput:
    agent_id: str
    claims: List[Claim] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    tokens: int = 0
    elapsed_s: float = 0.0
    tools_used: Set[str] = field(default_factory=set)
    scopes_touched: Set[str] = field(default_factory=set)
    error: Optional[str] = None

    def as_deliverable(self) -> Dict[str, Any]:
        d = dict(self.payload)
        d["claims"] = [c.to_dict() for c in self.claims]
        return d


# ---------------------------------------------------------------------------
class BaseAgent:
    role: AgentRole = AgentRole.SPECIALIST

    def __init__(self, runtime: AgentRuntime, problem: Problem,
                 backend: Optional[LLMBackend] = None) -> None:
        self.rt = runtime
        self.problem = problem
        self.backend = backend or NullBackend()

    # -- helpers ------------------------------------------------------------
    @property
    def agent_id(self) -> str:
        return self.rt.agent_id

    @property
    def spec(self) -> AgentSpec:
        return self.rt.spec

    def skill_for(self, capability: str) -> float:
        return float(self.spec.skill.get(capability, 0.05))

    def _charge(self, tokens: int, elapsed: float) -> None:
        self.rt.tokens_used += tokens
        self.rt.time_used_s += elapsed
        self.rt.last_heartbeat = time.time()

    def _use_llm(self) -> bool:
        return not isinstance(self.backend, NullBackend)

    def _llm_json(self, system: str, prompt: str, max_tokens: int = 900) -> Optional[Any]:
        if not self._use_llm():
            return None
        try:
            return parse_json_block(self.backend.complete(system, prompt, max_tokens))
        except Exception:
            return None

    # -- interface ----------------------------------------------------------
    def act(self, context: Dict[str, Any]) -> AgentOutput:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
class SpecialistAgent(BaseAgent):
    role = AgentRole.SPECIALIST

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        constraints: Sequence[str] = context.get("constraints", [])
        iteration = int(context.get("iteration", 0))
        universe = str(context.get("universe", "root"))
        nonce = str(context.get("nonce", iteration))
        claims: List[Claim] = []
        tokens = 0
        # If blinding did NOT strip peer conclusions, this agent is exposed to
        # anchoring -- exactly the failure mode Agentic Blinding exists to stop.
        peers: Dict[str, Any] = context.get("peer_conclusions") or {}
        susceptibility = float(context.get("anchor_susceptibility", 0.55))

        llm = self._llm_json(
            "You are a specialist agent. Return JSON: "
            '{"claims":[{"constraint_id":str,"value":str,"confidence":float}]}',
            f"Goal: {context.get('goal','')}\nConstraints: {list(constraints)}\n"
            f"Admissible values per constraint: "
            f"{ {c: self.problem.value_space(c) for c in constraints} }",
        )
        llm_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(llm, dict):
            for item in llm.get("claims", []):
                if isinstance(item, dict) and "constraint_id" in item:
                    llm_map[str(item["constraint_id"])] = item

        for cid in constraints:
            cap = self.problem.capability_for(cid)
            skill = self.skill_for(cap)
            if cid in llm_map and llm_map[cid].get("value") in self.problem.value_space(cid):
                value = str(llm_map[cid]["value"])
                conf = float(llm_map[cid].get("confidence", 0.6))
            else:
                value = self.problem.propose(cid, self.agent_id, skill, nonce)
                rng = rng_for("conf", self.agent_id, cid, nonce)
                conf = max(0.05, min(0.98, 0.45 + 0.5 * skill + rng.uniform(-0.12, 0.12)))
            evidence = [f"capability:{cap}", f"skill:{skill:.2f}"]
            peer_value = peers.get(cid) if isinstance(peers, dict) else None
            if peer_value and peer_value in self.problem.value_space(cid):
                anchor_rng = rng_for("anchor", self.agent_id, cid, nonce)
                if anchor_rng.random() < susceptibility * (1.0 - skill):
                    value = str(peer_value)
                    conf = min(0.99, conf + 0.15)      # anchoring inflates confidence
                    evidence.append("anchored:peer")
            claims.append(
                Claim(
                    claim_id=stable_sig("claim", self.agent_id, cid, universe, nonce),
                    constraint_id=cid,
                    value=value,
                    author=self.agent_id,
                    confidence=conf,
                    universe=universe,
                    iteration=iteration,
                    evidence=evidence,
                )
            )
            tokens += 180 + 40 * len(self.problem.value_space(cid))

        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, claims, {"role": "specialist"},
                           tokens, elapsed, {"reason"}, set())


# ---------------------------------------------------------------------------
class MicroAgent(SpecialistAgent):
    """Ephemeral single-subproblem agent; expires via `spec.ttl`."""
    role = AgentRole.MICRO


# ---------------------------------------------------------------------------
class VerifierAgent(BaseAgent):
    role = AgentRole.VERIFIER

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        claims: List[Claim] = context.get("claims_to_verify", [])
        intensity = float(context.get("verification_intensity", 0.45))
        nonce = str(context.get("nonce", 0))
        rng = rng_for("verify_sel", self.agent_id, nonce)
        checked = 0
        for claim in claims:
            if rng.random() > intensity:
                continue
            cap = self.problem.capability_for(claim.constraint_id)
            ok = self.problem.verify(claim.constraint_id, claim.value,
                                     self.skill_for(cap), nonce)
            claim.verified = ok
            claim.evidence.append(f"verified_by:{self.agent_id}")
            checked += 1
        tokens = 120 * max(1, checked)
        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, [], {"checked": checked},
                           tokens, elapsed, {"verify"}, set())


# ---------------------------------------------------------------------------
class FalsifierAgent(BaseAgent):
    role = AgentRole.FALSIFIER
    KINDS = ("counterexample", "assumption", "edge_case", "metric_gaming")

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        candidate: Candidate = context["candidate"]
        n_attacks = int(context.get("attacks", 3))
        nonce = str(context.get("nonce", 0))
        rng = rng_for("falsify", self.agent_id, candidate.candidate_id, nonce)
        targets = list(candidate.assignment.keys())
        report = FalsificationReport(candidate_id=candidate.candidate_id)
        if targets:
            for i in range(n_attacks):
                cid = targets[rng.randrange(len(targets))]
                cap = self.problem.capability_for(cid)
                kind = self.KINDS[rng.randrange(len(self.KINDS))]
                ok = self.problem.attack(cid, candidate.assignment[cid],
                                         self.skill_for(cap), f"{nonce}:{i}")
                report.attacks.append(
                    Attack(
                        attack_id=stable_sig("atk", self.agent_id, cid, nonce, i),
                        attacker=self.agent_id,
                        candidate_id=candidate.candidate_id,
                        constraint_id=cid,
                        kind=kind,
                        succeeded=ok,
                        rationale=f"{kind} against {cid}={candidate.assignment[cid]}",
                    )
                )
        tokens = 150 * max(1, n_attacks)
        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, [], {"report": report},
                           tokens, elapsed, {"reason"}, set())


# ---------------------------------------------------------------------------
class ContradictionAgent(BaseAgent):
    role = AgentRole.CONTRADICTION

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        claims: List[Claim] = context.get("claims", [])
        commitments: Dict[str, str] = context.get("commitments", {})
        found: List[Contradiction] = []
        by_constraint: Dict[str, List[Claim]] = {}
        for c in claims:
            by_constraint.setdefault(c.constraint_id, []).append(c)
        for cid, group in by_constraint.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if group[i].value != group[j].value:
                        found.append(Contradiction(cid, group[i].claim_id,
                                                   group[j].claim_id,
                                                   "value_conflict", self.agent_id))
            committed = commitments.get(cid)
            if committed is not None:
                for c in group:
                    if c.value != committed:
                        found.append(Contradiction(cid, c.claim_id, f"commit:{cid}",
                                                   "commitment_conflict", self.agent_id))
        tokens = 90 + 12 * len(claims)
        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, [], {"contradictions": found},
                           tokens, elapsed, {"reason"}, set())


# ---------------------------------------------------------------------------
class MinorityPreservationAgent(BaseAgent):
    """Advocates for a dissenting candidate so consensus cannot close early."""
    role = AgentRole.MINORITY

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        minority: Optional[Candidate] = context.get("minority_candidate")
        payload: Dict[str, Any] = {"advocated": None, "arguments": []}
        if minority is not None:
            minority.is_minority = True
            payload["advocated"] = minority.candidate_id
            payload["arguments"] = [
                f"{cid}={val} remains unfalsified under current evidence"
                for cid, val in list(minority.assignment.items())[:3]
            ]
        tokens = 140
        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, [], payload, tokens, elapsed, {"reason"}, set())


# ---------------------------------------------------------------------------
class JurorAgent(BaseAgent):
    role = AgentRole.JUROR
    RUBRIC = ("evidential_support", "internal_consistency",
              "falsification_survival", "coverage")

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        blinded: List[Dict[str, Any]] = context.get("blinded_candidates", [])
        nonce = str(context.get("nonce", 0))
        scores: Dict[str, float] = {}
        for item in blinded:
            alias = item["alias"]
            rng = rng_for("juror", self.agent_id, alias, nonce)
            base = (
                0.40 * float(item.get("verified_ratio", 0.0))
                + 0.25 * float(item.get("survival", 1.0))
                + 0.20 * float(item.get("mean_confidence", 0.5))
                + 0.15 * (1.0 - float(item.get("contradiction_density", 0.0)))
            )
            acuity = sum(self.spec.skill.values()) / max(1, len(self.spec.skill))
            noise = rng.uniform(-0.18, 0.18) * (1.0 - acuity)
            scores[alias] = max(0.0, min(1.0, base + noise))
        top = max(scores, key=lambda k: scores[k]) if scores else ""
        ballot = JurorBallot(self.agent_id, scores, top, self.rt.reputation)
        tokens = 130 * max(1, len(blinded))
        elapsed = time.perf_counter() - t0
        self._charge(tokens, elapsed)
        self.rt.tasks_done += 1
        return AgentOutput(self.agent_id, [], {"ballot": ballot},
                           tokens, elapsed, {"reason"}, set())


# ---------------------------------------------------------------------------
class WatchdogAgent(BaseAgent):
    """Monitors per-agent budgets and heartbeats; kills runaway agents."""
    role = AgentRole.WATCHDOG

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        runtimes: Dict[str, AgentRuntime] = context.get("runtimes", {})
        now = float(context.get("now", time.time()))
        heartbeat_s = float(context.get("heartbeat_s", 30.0))
        killed: List[Dict[str, str]] = []
        for aid, rt in runtimes.items():
            if not rt.alive or rt.spec.role in (AgentRole.WATCHDOG, AgentRole.META):
                continue
            reason = None
            if rt.tokens_used > rt.spec.token_budget:
                reason = f"token_overrun:{rt.tokens_used}>{rt.spec.token_budget}"
            elif rt.time_used_s > rt.spec.wall_clock_budget_s:
                reason = f"time_overrun:{rt.time_used_s:.2f}s"
            elif rt.last_heartbeat and (now - rt.last_heartbeat) > heartbeat_s * 4:
                reason = "heartbeat_lost"
            if reason:
                rt.alive = False
                rt.pruned_reason = f"watchdog:{reason}"
                killed.append({"agent": aid, "reason": reason})
        elapsed = time.perf_counter() - t0
        self._charge(40, elapsed)
        return AgentOutput(self.agent_id, [], {"killed": killed}, 40, elapsed,
                           {"reason"}, set())


# ---------------------------------------------------------------------------
class MetaAgent(BaseAgent):
    """Architecture-level escalation target. Only invoked when ordinary
    recovery has failed `max_recovery_attempts` times."""
    role = AgentRole.META

    DIRECTIVES = (
        "relax_verification",       # lower the bar, keep going
        "reprovision_capability",   # the roster is wrong for the problem
        "restart_universe",         # the branch is poisoned beyond repair
        "terminate_unresolved",     # honest failure
    )

    def act(self, context: Dict[str, Any]) -> AgentOutput:
        t0 = time.perf_counter()
        failures: int = int(context.get("consecutive_failures", 0))
        coverage: float = float(context.get("capability_coverage", 1.0))
        budget_left: float = float(context.get("budget_fraction_left", 1.0))
        progress: float = float(context.get("recent_progress", 0.0))

        if coverage < 0.75:
            directive = "reprovision_capability"
        elif failures >= 3 and budget_left > 0.35:
            directive = "restart_universe"
        elif budget_left < 0.15 or progress <= 0.0:
            directive = "terminate_unresolved"
        else:
            directive = "relax_verification"

        payload = {
            "directive": directive,
            "rationale": (
                f"failures={failures} coverage={coverage:.2f} "
                f"budget_left={budget_left:.2f} progress={progress:.3f}"
            ),
        }
        elapsed = time.perf_counter() - t0
        self._charge(220, elapsed)
        return AgentOutput(self.agent_id, [], payload, 220, elapsed, {"reason"}, set())


AGENT_CLASSES = {
    AgentRole.SPECIALIST: SpecialistAgent,
    AgentRole.MICRO: MicroAgent,
    AgentRole.VERIFIER: VerifierAgent,
    AgentRole.FALSIFIER: FalsifierAgent,
    AgentRole.CONTRADICTION: ContradictionAgent,
    AgentRole.MINORITY: MinorityPreservationAgent,
    AgentRole.JUROR: JurorAgent,
    AgentRole.WATCHDOG: WatchdogAgent,
    AgentRole.META: MetaAgent,
}


def build_agent(runtime: AgentRuntime, problem: Problem,
                backend: Optional[LLMBackend] = None) -> BaseAgent:
    cls = AGENT_CLASSES.get(runtime.spec.role, SpecialistAgent)
    return cls(runtime, problem, backend)
