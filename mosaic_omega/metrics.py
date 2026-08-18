"""Evaluation suite for MOSAIC-Omega.

Every metric is computed from the run trace and, where ground truth exists,
from the problem oracle. Nothing here is hard-coded or asserted: if a metric
is not computable from the trace, it returns None rather than a placeholder.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .problem import Problem
from .types import Candidate, RunTrace, Termination


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------
def mean(xs: Sequence[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def entropy(probs: Sequence[float]) -> float:
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log(p, 2)
    return h


def gini(values: Sequence[float]) -> float:
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * cum) / (n * sum(vals)) - (n + 1) / n


def brier_score(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    if not pairs:
        return None
    return sum((p - float(o)) ** 2 for p, o in pairs) / len(pairs)


def expected_calibration_error(pairs: Sequence[Tuple[float, bool]],
                               bins: int = 10) -> Optional[float]:
    if not pairs:
        return None
    buckets: List[List[Tuple[float, bool]]] = [[] for _ in range(bins)]
    for p, o in pairs:
        idx = min(bins - 1, max(0, int(p * bins)))
        buckets[idx].append((p, o))
    n = len(pairs)
    ece = 0.0
    for b in buckets:
        if not b:
            continue
        conf = sum(p for p, _ in b) / len(b)
        acc = sum(float(o) for _, o in b) / len(b)
        ece += (len(b) / n) * abs(conf - acc)
    return ece


def auroc(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    pos = [p for p, o in pairs if o]
    neg = [p for p, o in pairs if not o]
    if not pos or not neg:
        return None
    ranked = sorted(pairs, key=lambda t: t[0])
    ranks: Dict[int, float] = {}
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1
    rank_sum = sum(ranks[k] for k, (_, o) in enumerate(ranked) if o)
    n_pos, n_neg = len(pos), len(neg)
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    num = sum((x - mx) * (y - my) for x, y in pairs)
    dx = math.sqrt(sum((x - mx) ** 2 for x, _ in pairs))
    dy = math.sqrt(sum((y - my) ** 2 for _, y in pairs))
    return num / (dx * dy) if dx > 0 and dy > 0 else None


# ---------------------------------------------------------------------------
@dataclass
class MetricGroup:
    name: str
    values: Dict[str, Any] = field(default_factory=dict)


class MetricsEngine:
    """Turns a `RunTrace` into a full evaluation report."""

    def __init__(self, trace: RunTrace, problem: Optional[Problem] = None) -> None:
        self.trace = trace
        self.problem = problem

    # -- 1. outcome ---------------------------------------------------------
    def outcome(self) -> MetricGroup:
        t = self.trace
        final = t.final_candidate
        g = MetricGroup("outcome")
        g.values["termination"] = t.termination.value if t.termination else None
        g.values["iterations"] = t.iterations
        g.values["final_composite_score"] = final.composite_score if final else None
        g.values["final_verified_score"] = final.verified_score if final else None
        g.values["final_confidence"] = final.confidence if final else None
        if self.problem and final:
            truth = self.problem.true_score(final.assignment)
            g.values["ground_truth_accuracy"] = truth
            g.values["solved"] = truth >= 0.85
            # Overconfidence detector: how far the system's own composite score
            # sits above (or below) reality. Positive = self-flattering.
            g.values["score_truth_gap"] = final.composite_score - truth
        else:
            g.values["ground_truth_accuracy"] = None
            g.values["solved"] = None
            g.values["score_truth_gap"] = None
        verified = [c for c in t.claims if c.verified is not None]
        g.values["claim_verification_coverage"] = (
            len(verified) / len(t.claims) if t.claims else None
        )
        g.values["verified_claim_ratio"] = (
            sum(1 for c in verified if c.verified) / len(verified) if verified else None
        )
        g.values["unresolved_returned"] = (
            t.termination in (Termination.UNRESOLVED, Termination.ESCALATED_UNRESOLVED)
            if t.termination else None
        )
        return g

    # -- 2. reasoning quality ----------------------------------------------
    def reasoning(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("reasoning")
        attempted = sum(r.attempted for r in t.falsifications)
        successful = sum(r.successful for r in t.falsifications)
        g.values["falsification_attempts"] = attempted
        g.values["falsification_success_rate"] = (
            successful / attempted if attempted else None
        )
        g.values["mean_falsification_survival"] = mean(
            [r.survival for r in t.falsifications]
        )
        g.values["contradictions_detected"] = len(t.contradictions)
        g.values["contradiction_density"] = mean(
            [c.contradiction_penalty for c in t.candidates]
        )
        g.values["commitment_conflicts"] = sum(
            1 for c in t.contradictions if c.kind == "commitment_conflict"
        )
        conflicted = {c.constraint_id for c in t.contradictions}
        constraints = {c.constraint_id for c in t.claims}
        g.values["claim_consistency_index"] = (
            1.0 - len(conflicted) / len(constraints) if constraints else None
        )
        g.values["falsified_claim_rate"] = (
            sum(1 for c in t.claims if c.falsified) / len(t.claims) if t.claims else None
        )
        return g

    # -- 3. consensus & adjudication ---------------------------------------
    def consensus(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("consensus")
        g.values["jury_rounds"] = len(t.verdicts)
        g.values["mean_jury_margin"] = mean([v.margin for v in t.verdicts])
        g.values["mean_jury_kappa"] = mean([v.agreement_kappa for v in t.verdicts])
        g.values["entropy_trajectory"] = list(t.entropy_history)
        g.values["final_candidate_entropy"] = (
            t.entropy_history[-1] if t.entropy_history else None
        )
        early = t.entropy_history[: max(1, len(t.entropy_history) // 2)]
        g.values["premature_consensus_index"] = (
            1.0 - (mean(early) or 0.0) if early else None
        )
        g.values["minority_preservations"] = t.minority_preserved
        final = t.final_candidate
        g.values["minority_won"] = bool(final.is_minority) if final else None
        g.values["blinded_adjudication"] = all(v.blinded for v in t.verdicts) if t.verdicts else None
        return g

    # -- 4. efficiency ------------------------------------------------------
    def efficiency(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("efficiency")
        g.values["tokens_used"] = t.tokens_used
        g.values["tool_calls_used"] = t.tool_calls_used
        g.values["wall_clock_s"] = round(t.wall_clock_s, 4)
        g.values["agents_provisioned"] = len(t.agents_provisioned)
        g.values["agents_used"] = len(t.agents_used)
        g.values["provisioning_efficiency"] = (
            len(t.agents_used) / len(t.agents_provisioned) if t.agents_provisioned else None
        )
        producers = [s for s in t.agents_provisioned
                     if s.role.value in ("specialist", "micro")]
        used_producers = [s for s in producers if s.agent_id in t.agents_used]
        g.values["producer_utilisation"] = (
            len(used_producers) / len(producers) if producers else None
        )
        verified_true = sum(1 for c in t.claims if c.verified)
        g.values["tokens_per_verified_claim"] = (
            t.tokens_used / verified_true if verified_true else None
        )
        g.values["tokens_per_iteration"] = (
            t.tokens_used / t.iterations if t.iterations else None
        )
        pruned = t.prune_decisions
        # TTL expiry is by design, not a judgement call: excluded from quality.
        judged = [d for d in pruned if d.get("reason") != "ttl_expired"]
        tp = sum(1 for d in judged if d.get("ground_truth_useful") is False)
        fp = sum(1 for d in judged if d.get("ground_truth_useful") is True)
        g.values["agents_pruned"] = len(pruned)
        g.values["agents_expired_ttl"] = len(pruned) - len(judged)
        g.values["pruning_precision"] = tp / (tp + fp) if (tp + fp) else None
        kept_useless = sum(
            1 for s in t.agents_provisioned
            if s.agent_id not in {d["agent"] for d in pruned}
            and s.role.value in ("specialist", "micro")
            and max(s.skill.values(), default=0.0) < 0.55
        )
        g.values["pruning_recall"] = tp / (tp + kept_useless) if (tp + kept_useless) else None
        return g

    # -- 5. loop control ----------------------------------------------------
    def control(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("control")
        g.values["score_trajectory"] = [round(s, 4) for s in t.score_history]
        g.values["total_improvement"] = (
            t.score_history[-1] - t.score_history[0] if len(t.score_history) >= 2 else None
        )
        g.values["convergence_iteration"] = next(
            (i for i, s in enumerate(t.score_history) if s >= 0.85), None
        )
        g.values["evoi_predicted"] = [round(v, 5) for v in t.evoi_predicted]
        g.values["evoi_realized"] = [round(v, 5) for v in t.evoi_realized]
        g.values["evoi_calibration_r"] = pearson(t.evoi_predicted, t.evoi_realized)
        g.values["evoi_mae"] = mean(
            [abs(p - r) for p, r in zip(t.evoi_predicted, t.evoi_realized)]
        )
        trips = {}
        for trip in t.guard_trips:
            trips[trip["guard"]] = trips.get(trip["guard"], 0) + 1
        g.values["guard_trips"] = trips
        g.values["duplicate_loops_detected"] = trips.get("duplicate_loop", 0)
        g.values["oscillations_detected"] = trips.get("oscillation", 0)
        g.values["circular_handoffs_broken"] = trips.get("circular_handoff", 0)
        g.values["distinct_state_signatures"] = len(set(t.state_signatures))
        g.values["state_revisit_rate"] = (
            1.0 - len(set(t.state_signatures)) / len(t.state_signatures)
            if t.state_signatures else None
        )
        return g

    # -- 6. reliability -----------------------------------------------------
    def reliability(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("reliability")
        g.values["checkpoints_written"] = len(t.checkpoints)
        g.values["recoveries"] = len(t.recoveries)
        g.values["rollbacks_performed"] = sum(
            1 for r in t.recoveries if r.rolled_back_to
        )
        g.values["containment_ratio"] = (
            sum(1 for r in t.recoveries if r.contained) / len(t.recoveries)
            if t.recoveries else 1.0
        )
        mttr = [
            r.recovered_at_iteration - r.iteration
            for r in t.recoveries if r.recovered_at_iteration is not None
        ]
        g.values["mttr_iterations"] = mean(mttr)
        g.values["escalations"] = len(t.escalations)
        g.values["escalation_rate"] = (
            len(t.escalations) / t.iterations if t.iterations else None
        )
        g.values["idempotency_hits"] = t.idempotent_hits
        g.values["duplicate_side_effects_prevented"] = t.duplicates_prevented
        g.values["budget_overruns"] = list(t.budget_overruns)
        g.values["contract_compliance_rate"] = (
            sum(1 for r in t.contract_results if r.ok) / len(t.contract_results)
            if t.contract_results else None
        )
        g.values["contract_violations"] = sum(1 for r in t.contract_results if not r.ok)
        return g

    # -- 7. routing & reputation -------------------------------------------
    def routing(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("routing")
        decisions = t.routing
        g.values["routing_decisions"] = len(decisions)
        regrets = [d.oracle_utility - d.chosen_utility for d in decisions]
        g.values["mean_routing_regret"] = mean(regrets)
        g.values["oracle_match_rate"] = (
            sum(1 for d in decisions if d.chosen == d.oracle_choice) / len(decisions)
            if decisions else None
        )
        pairs = [
            (d.predicted_reliability, d.realized_success)
            for d in decisions if d.realized_success is not None
        ]
        g.values["reputation_brier"] = brier_score(pairs)
        g.values["reputation_ece"] = expected_calibration_error(pairs)
        g.values["reputation_auroc"] = auroc(pairs)
        conf_pairs = [
            (c.confidence, bool(c.verified))
            for c in t.claims if c.verified is not None
        ]
        g.values["confidence_brier"] = brier_score(conf_pairs)
        g.values["confidence_ece"] = expected_calibration_error(conf_pairs)
        g.values["confidence_auroc"] = auroc(conf_pairs)
        return g

    # -- 8. topology & sovereignty -----------------------------------------
    def structure(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("structure")
        snaps = t.topology
        g.values["rewiring_events"] = len(snaps)
        g.values["mean_edges"] = mean([s.n_edges for s in snaps])
        g.values["mean_degree"] = mean([s.avg_degree for s in snaps])
        g.values["mean_modularity"] = mean([s.modularity for s in snaps])
        g.values["mean_path_length"] = mean([s.avg_path_length for s in snaps])
        g.values["mean_degree_entropy"] = mean([s.degree_entropy for s in snaps])
        total_edges = sum(s.n_edges for s in snaps) or 1
        g.values["edge_churn_rate"] = (
            sum(s.edges_added + s.edges_removed for s in snaps) / total_edges
        )
        g.values["sovereignty_transfers"] = len(t.sovereignty)
        g.values["sovereignty_transfer_rate"] = (
            len(t.sovereignty) / t.iterations if t.iterations else None
        )
        g.values["mean_competence_gain_on_transfer"] = mean(
            [s.competence_to - s.competence_from for s in t.sovereignty]
        )
        return g

    # -- 9. safety & isolation ---------------------------------------------
    def safety(self) -> MetricGroup:
        t = self.trace
        g = MetricGroup("safety")
        g.values["blinding_checks"] = t.blinding_checks
        g.values["blinding_leaks"] = t.blinding_leaks
        g.values["blinding_leak_rate"] = (
            t.blinding_leaks / t.blinding_checks if t.blinding_checks else None
        )
        g.values["anchor_opportunities"] = t.anchor_opportunities
        g.values["anchoring_index"] = (
            t.anchored_outputs / t.anchor_opportunities
            if t.anchor_opportunities else None
        )
        g.values["branch_isolation_purity"] = t.isolation_purity
        g.values["safe_termination"] = (
            t.termination in (
                Termination.CONVERGED, Termination.NEGATIVE_EVOI,
                Termination.STAGNATION, Termination.OSCILLATION,
                Termination.DUPLICATE_LOOP, Termination.BUDGET_EXHAUSTED,
                Termination.MAX_ITERATIONS, Termination.SAFE_STOP,
                Termination.ESCALATED_UNRESOLVED, Termination.UNRESOLVED,
                Termination.DEADLOCK,
            ) if t.termination else None
        )
        return g

    # -- assembly -----------------------------------------------------------
    def compute(self) -> Dict[str, Dict[str, Any]]:
        groups = [
            self.outcome(), self.reasoning(), self.consensus(), self.efficiency(),
            self.control(), self.reliability(), self.routing(), self.structure(),
            self.safety(),
        ]
        return {g.name: g.values for g in groups}

    def report(self) -> str:
        data = self.compute()
        lines: List[str] = ["# MOSAIC-Omega evaluation report", ""]
        for group, values in data.items():
            lines.append(f"## {group}")
            for k, v in values.items():
                if isinstance(v, float):
                    lines.append(f"- {k}: {v:.4f}")
                elif isinstance(v, list) and len(v) > 8:
                    lines.append(f"- {k}: [{len(v)} values] {v[:8]} ...")
                else:
                    lines.append(f"- {k}: {v}")
            lines.append("")
        return "\n".join(lines)
