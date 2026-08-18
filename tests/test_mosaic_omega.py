"""Test suite: one or more tests per architectural component."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mosaic_omega import (
    AgentPruner, AgentRole, AgentRuntime, AgentSpec, BlindedJury, BlindingFilter,
    BlindingPolicy, Candidate, CheckpointStore, Claim, ContractLedger,
    DynamicAgentProvisioner, FalsificationEngine, IdempotencyLedger, LoopGuards,
    MemoryFabric, MetricsEngine, MinorityPreserver, MissionKernel, MosaicConfig,
    MosaicOmega, Phase, RecoveryManager, ReputationRouter, SovereigntyController,
    SyntheticConstraintProblem, Termination, TopologyGraph, UniverseManager,
    build_agent,
)
from mosaic_omega import FreeEnergyParams, StructuralFreeEnergy
from mosaic_omega.metrics import auroc, brier_score, expected_calibration_error, gini
from mosaic_omega.types import RiskLevel

CFG = MosaicConfig()
PROBLEM = SyntheticConstraintProblem()


def _spec(aid, role, caps, strength=0.8, ttl=None, created=0):
    return AgentSpec(aid, role, set(caps), {c: strength for c in caps},
                     ttl=ttl, created_iteration=created)


# --- Mission Kernel --------------------------------------------------------
def test_mission_kernel_compiles_executable_spec():
    mission = MissionKernel(CFG).compile("goal", PROBLEM)
    assert mission.stages and mission.mission_id
    assert len(mission.all_constraints) == len(PROBLEM.all_constraints())
    high = [s for s in mission.stages if s.risk == RiskLevel.HIGH]
    assert all(s.verification_intensity == CFG.high_risk_verification_fraction for s in high)


# --- Dynamic Agent Provisioning -------------------------------------------
def test_provisioning_covers_capability_gap_and_reuses():
    prov = DynamicAgentProvisioner(CFG, PROBLEM)
    stage = PROBLEM.stages()[0]
    result = prov.provision_for_stage(stage, {}, 0, "U0")
    covered = set().union(*[s.capabilities for s in result.created])
    assert set(stage.required_capabilities) <= covered
    assert not result.uncovered

    runtimes = {s.agent_id: AgentRuntime(spec=s) for s in result.created}
    for r in runtimes.values():
        r.alpha = 9.0
    again = prov.provision_for_stage(stage, runtimes, 1, "U0")
    assert len(again.created) < len(result.created)


def test_micro_agent_is_ephemeral():
    prov = DynamicAgentProvisioner(CFG, PROBLEM)
    micro = prov.spawn_micro_agent(PROBLEM.all_constraints()[0], 0, "U0")
    assert micro.role == AgentRole.MICRO and micro.ttl == CFG.micro_agent_ttl


# --- Agent Pruning ---------------------------------------------------------
def test_pruner_removes_redundant_low_utility_and_expired():
    pruner = AgentPruner(CFG)
    rts = {
        "keep": AgentRuntime(spec=_spec("keep", AgentRole.SPECIALIST, ["retrieval"])),
        "dupe": AgentRuntime(spec=_spec("dupe", AgentRole.SPECIALIST, ["retrieval"])),
        "micro": AgentRuntime(spec=_spec("micro", AgentRole.MICRO, ["retrieval"], ttl=1)),
        "wd": AgentRuntime(spec=_spec("wd", AgentRole.WATCHDOG, ["retrieval"])),
    }
    rts["keep"].contributions = 10.0
    rts["keep"].alpha = 12.0
    out = {d.agent_id: d.reason for d in pruner.prune(rts, 3, "keep", {"retrieval"})}
    assert out.get("dupe") in ("redundant", "low_utility")
    assert out.get("micro") == "ttl_expired"
    assert "wd" not in out and rts["wd"].alive


# --- Dynamic Sovereignty ---------------------------------------------------
def test_sovereignty_transfers_only_past_hysteresis():
    ctrl = SovereigntyController(CFG)
    stage = PROBLEM.stages()[0]
    cap = stage.required_capabilities[0]
    weak = AgentRuntime(spec=_spec("weak", AgentRole.SPECIALIST, [cap]))
    strong = AgentRuntime(spec=_spec("strong", AgentRole.SPECIALIST, [cap]))
    rts = {"weak": weak}
    first, _ = ctrl.evaluate(rts, stage, 0)
    assert first == "weak"
    rts["strong"] = strong
    strong.alpha, strong.verified_true = 40.0, 20
    weak.beta, weak.verified_false = 20.0, 20
    second, _ = ctrl.evaluate(rts, stage, 1)
    assert second == "strong"
    n = len(ctrl.transfers)
    ctrl.evaluate(rts, stage, 2)
    assert len(ctrl.transfers) == n           # hysteresis prevents thrash


# --- Topology rewiring -----------------------------------------------------
def test_topology_rewires_and_detects_cycles():
    g = TopologyGraph(CFG)
    for n in "abcd":
        g.add_node(n)
    caps = {"a": {"x"}, "b": {"y"}, "c": {"x", "z"}, "d": {"w"}}
    comp = {n: 0.8 for n in caps}
    snap = g.rewire(1, caps, comp, {n: 0.0 for n in caps}, 0.5, {})
    assert snap.n_edges > 0 and snap.edges_added > 0
    assert 0.0 <= snap.modularity <= 1.0
    g.add_handoff("a", "b"); g.add_handoff("b", "c"); g.add_handoff("c", "a")
    cycle = g.find_handoff_cycle()
    assert cycle and cycle[0] == cycle[-1]
    g.break_cycle(cycle)
    assert g.find_handoff_cycle() is None


# --- Reputation-weighted routing ------------------------------------------
def test_router_prefers_reputable_capable_agent():
    router = ReputationRouter(CFG)
    good = AgentRuntime(spec=_spec("good", AgentRole.SPECIALIST, ["retrieval"], 0.9))
    bad = AgentRuntime(spec=_spec("bad", AgentRole.SPECIALIST, ["synthesis"], 0.1))
    good.alpha = 20.0
    d = router.route("t", "retrieval", {"good": good, "bad": bad}, 0)
    assert d.chosen == "good" and d.oracle_choice == "good"
    assert d.oracle_utility - d.chosen_utility == 0.0


# --- Agentic Blinding ------------------------------------------------------
def test_blinding_redacts_and_audits_leakage():
    f = BlindingFilter(BlindingPolicy("strict"))
    clean, rep = f.apply({"task": "solve", "peer_conclusions": ["v2"]})
    assert "peer_conclusions" not in clean and not rep.leaked
    leaky, rep2 = f.apply({"notes": "the answer is v2xyz", "peer_conclusions": ["v2xyz"]})
    assert rep2.leaked
    none = BlindingFilter(BlindingPolicy("none")).apply({"peer_conclusions": ["v2"]})[0]
    assert "peer_conclusions" in none


# --- Contractual Handoffs --------------------------------------------------
def test_contract_detects_every_violation_class():
    led = ContractLedger(max_depth=2)
    c = led.issue("p", "a", "t", 1, allowed_tools={"reason"},
                  forbidden_scopes={"universe:U1"}, token_budget=100, deadline_s=1.0)
    bad = led.settle(c, {}, 500, 5.0, {"shell"}, {"universe:U1"})
    assert not bad.ok and len(bad.violations) == 5
    c2 = led.issue("p", "a", "t2", 1)
    assert led.settle(c2, {"claims": []}, 10, 0.1, {"reason"}).ok
    try:
        led.issue("p", "a", "t3", 5)
        assert False, "bounded recursive delegation not enforced"
    except RecursionError:
        pass


# --- Falsifier -------------------------------------------------------------
def test_falsification_lowers_survival_for_wrong_assignments():
    engine = FalsificationEngine(CFG)
    cids = PROBLEM.all_constraints()[:5]
    wrong = {c: next(v for v in PROBLEM.value_space(c) if v != PROBLEM.truth_of(c))
             for c in cids}
    right = {c: PROBLEM.truth_of(c) for c in cids}
    fals = [build_agent(AgentRuntime(spec=_spec(f"f{i}", AgentRole.FALSIFIER,
                                                PROBLEM.capability_catalog(), 0.9)), PROBLEM)
            for i in range(3)]
    cw = Candidate("cw", "U0", 0, wrong)
    cr = Candidate("cr", "U0", 0, right)
    sw = engine.run(cw, fals, "n").survival
    sr = engine.run(cr, fals, "n").survival
    assert sw < sr


# --- Contradiction agent ---------------------------------------------------
def test_contradiction_agent_finds_value_and_commitment_conflicts():
    agent = build_agent(AgentRuntime(spec=_spec("cd", AgentRole.CONTRADICTION, ["x"])), PROBLEM)
    claims = [
        Claim("1", "C0_0", "v0", "a", 0.9, "U0", 0),
        Claim("2", "C0_0", "v1", "b", 0.8, "U0", 0),
    ]
    found = agent.act({"claims": claims, "commitments": {"C0_0": "v2"}}).payload["contradictions"]
    kinds = {c.kind for c in found}
    assert "value_conflict" in kinds and "commitment_conflict" in kinds


# --- Minority preservation -------------------------------------------------
def test_minority_preserved_under_premature_consensus():
    mp = MinorityPreserver(CFG)
    majority = {"C0_0": "v0"}
    minority = {"C0_0": "v1"}
    cands = [Candidate(f"m{i}", "U0", 0, dict(majority)) for i in range(5)]
    cands.append(Candidate("dissent", "U1", 0, dict(minority)))
    state = mp.analyse(cands, evidence_sufficiency=0.1)
    assert state.premature and state.majority_share > CFG.consensus_share_ceiling
    champion = mp.preserve(state, cands, None)
    assert champion is not None and champion.is_minority
    settled = mp.analyse(cands, evidence_sufficiency=0.95)
    assert not settled.premature          # sufficient evidence -> no override


# --- Blinded jury ----------------------------------------------------------
def test_blinded_jury_produces_weighted_verdict():
    jury = BlindedJury(CFG)
    strong = Candidate("A", "U0", 0, {"C0_0": "v0"},
                       claims=[Claim("1", "C0_0", "v0", "a", 0.95, "U0", 0, verified=True)])
    strong.falsification_survival = 1.0
    weak = Candidate("B", "U1", 0, {"C0_0": "v1"},
                     claims=[Claim("2", "C0_0", "v1", "b", 0.2, "U1", 0, verified=False)])
    weak.falsification_survival = 0.2
    jurors = [build_agent(AgentRuntime(spec=_spec(f"j{i}", AgentRole.JUROR,
                                                  PROBLEM.capability_catalog(), 0.95)), PROBLEM)
              for i in range(5)]
    verdict, leaks, checks = jury.adjudicate([strong, weak], jurors, "n")
    assert verdict.winner_id == "A" and verdict.blinded
    assert leaks == 0 and checks == 2
    assert -1.0 <= verdict.agreement_kappa <= 1.0


# --- Memory ----------------------------------------------------------------
def test_memory_strata_and_isolation():
    m = MemoryFabric()
    m.set("k", 1)
    m.record_episode(0, "U0", "observe", "ok")
    m.learn_procedure("retrieval", "recipe", True)
    sig = m.failure_signature("x")
    m.record_failure(sig, "kind", "detail")
    m.commit("C0_0", "v0", "a", 0)
    assert m.is_known_failure(sig)
    assert m.commitment_conflict("C0_0", "v1") and not m.commitment_conflict("C0_0", "v0")
    snap = m.snapshot()
    m.commit("C0_0", "v9", "b", 1)
    m.restore(snap)
    assert m.commitment["C0_0"].value == "v0"
    child = m.fork("U1")
    assert child.failure and not child.episodic and child.get("universe") == "U1"


# --- Checkpointing / rollback ---------------------------------------------
def test_rollback_targets_earliest_corrupted_checkpoint():
    store = CheckpointStore()
    for i in range(9):
        store.commit(i, Phase.COMMIT, {"i": i, "invariant_ok": i < 4})
    bad = store.find_earliest_corrupted(lambda s: s["invariant_ok"])
    assert bad.iteration == 4
    good = store.last_good_before(bad)
    assert good.iteration == 3
    state = store.rollback_to(good.checkpoint_id)
    assert state["i"] == 3 and len(store.chain) == 4
    assert store.verify_integrity(store.head)


# --- Loop guards -----------------------------------------------------------
def test_guards_detect_duplicates_oscillation_stagnation_deadlock():
    g = LoopGuards(CFG)
    for i, s in enumerate(["A", "B", "A", "B", "A", "B"]):
        g.observe(s, 0.5, i)
    assert g.duplicate_loop(6) and g.oscillation(6) and g.stagnation(6)
    g2 = LoopGuards(CFG)
    for i, s in enumerate(["A", "B", "C", "D"]):
        g2.observe(s, i * 0.1, i)
    assert g2.oscillation(4) is None and g2.duplicate_loop(4) is None
    assert g2.stagnation(4) is None
    assert g2.deadlock(4, ["a", "b"], ["a", "b"]) is not None
    assert g2.deadlock(4, [], ["a"]) is None


# --- Idempotency -----------------------------------------------------------
def test_idempotent_execution_prevents_duplicate_side_effects():
    led = IdempotencyLedger()
    calls = []
    k = led.key("a", "tool", {"x": 1}, "cp")
    assert led.run_once(k, lambda: calls.append(1) or "r") == "r"
    assert led.run_once(k, lambda: calls.append(1) or "r") == "r"
    assert len(calls) == 1 and led.duplicates_prevented == 1


# --- Recovery / escalation -------------------------------------------------
def test_recovery_rolls_back_then_escalates():
    store = CheckpointStore()
    store.commit(0, Phase.COMMIT, {"invariant_ok": True, "assignment": {}})
    store.commit(1, Phase.COMMIT, {"invariant_ok": False, "assignment": {}})
    rec = RecoveryManager(MosaicConfig(max_recovery_attempts=1), store)
    r1 = rec.handle(1, __import__("mosaic_omega").types.FailureClass.BRANCH, "x",
                    lambda s: s["invariant_ok"], lambda s: None)
    assert r1.contained and not r1.escalated and r1.rolled_back_to
    r2 = rec.handle(2, __import__("mosaic_omega").types.FailureClass.BRANCH, "x",
                    lambda s: s["invariant_ok"], lambda s: None)
    assert r2.escalated
    rec.mark_recovered(3)
    assert rec.consecutive_failures == 0


# --- Parallel universes ----------------------------------------------------
def test_universes_are_isolated():
    mgr = UniverseManager(CFG, PROBLEM)
    mgr.spawn(MemoryFabric(), n=3)
    assert len(mgr.universes) == 3
    us = list(mgr.universes.values())
    us[0].provenance.update({"c1", "c2"})
    us[1].provenance.update({"c3"})
    assert not mgr.isolation_violations() and mgr.isolation_purity() == 1.0
    us[1].provenance.add("c1")
    assert mgr.isolation_violations() and mgr.isolation_purity() < 1.0


# --- Free-Energy Structural Control ----------------------------------------
def test_free_energy_closed_form_optimum_and_monotone_descent():
    fe = StructuralFreeEnergy(FreeEnergyParams(kappa=1.4, lambda_U=0.0))
    g = fe.edge_gain(complement=0.8, competence=0.7, evidence=0.3,
                     failure=0.1, uncertainty=0.5, contamination=0.0)
    w_star = fe.optimal_weight(g)

    # 1. w* is the unique minimiser: any admissible perturbation raises J.
    j_star = fe.edge_energy(w_star, g)
    for dw in (-0.2, -0.05, 0.05, 0.2):
        w = min(1.0, max(0.0, w_star + dw))
        if w != w_star:
            assert fe.edge_energy(w, g) >= j_star - 1e-12

    # 2. descent is exactly J(w) - J(w*), and never negative.
    w0 = 0.0
    assert fe.edge_descent(w0, g) >= 0.0
    assert abs(fe.edge_descent(w0, g) - (fe.edge_energy(w0, g) - j_star)) < 1e-9

    # 3. gradient descent w <- w - eta*(kappa*w - g) converges monotonically to w*.
    eta, w, prev = 0.35, w0, fe.edge_energy(w0, g)
    for _ in range(200):
        w = min(1.0, max(0.0, w - eta * (fe.p.kappa * w - g)))
        cur = fe.edge_energy(w, g)
        assert cur <= prev + 1e-12          # J never increases
        prev = cur
    assert abs(w - w_star) < 1e-6           # reaches the closed-form optimum


# --- Metric primitives -----------------------------------------------------
def test_metric_primitives():
    assert auroc([(0.9, True), (0.1, False)]) == 1.0
    assert auroc([(0.9, True), (0.9, True)]) is None
    assert brier_score([(1.0, True)]) == 0.0
    assert expected_calibration_error([(1.0, True), (0.0, False)]) == 0.0
    assert gini([5, 5, 5, 5]) == 0.0
    assert gini([0, 0, 0, 10]) > 0.5


# --- End-to-end ------------------------------------------------------------
def test_end_to_end_run_is_deterministic_and_reports_all_metrics():
    a = MosaicOmega(MosaicConfig(max_iterations=6)).solve(SyntheticConstraintProblem())
    b = MosaicOmega(MosaicConfig(max_iterations=6)).solve(SyntheticConstraintProblem())
    assert a.trace.state_signatures == b.trace.state_signatures
    assert a.termination in set(Termination)
    for group in ("outcome", "reasoning", "consensus", "efficiency", "control",
                  "reliability", "routing", "structure", "safety"):
        assert group in a.metrics and a.metrics[group]
    assert a.metrics["safety"]["safe_termination"] is True
    assert a.metrics["safety"]["branch_isolation_purity"] == 1.0
    assert a.metrics["reliability"]["contract_compliance_rate"] is not None
    assert MetricsEngine(a.trace, SyntheticConstraintProblem()).report().startswith("#")


def test_chaos_run_contains_failures_and_still_terminates_safely():
    cfg = MosaicConfig(max_iterations=6, chaos_agent_failure_rate=0.3,
                       chaos_branch_corruption_rate=0.5)
    r = MosaicOmega(cfg).solve(SyntheticConstraintProblem())
    assert r.termination in set(Termination)
    assert r.metrics["safety"]["safe_termination"] is True
    assert r.metrics["reliability"]["recoveries"] > 0
    assert r.metrics["reliability"]["containment_ratio"] >= 0.0
    assert r.metrics["reliability"]["contract_compliance_rate"] < 1.0


def test_unresolved_state_is_returned_explicitly():
    cfg = MosaicConfig(max_iterations=2, token_budget=4000)
    r = MosaicOmega(cfg).solve(SyntheticConstraintProblem())
    assert r.termination != Termination.CONVERGED
    assert isinstance(r.unresolved_constraints, list)
    assert r.resolved is False


def _run_all() -> int:
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            import traceback
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
