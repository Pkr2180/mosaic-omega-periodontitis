# MOSAIC-Ω — Reference Implementation

*A self-reconfiguring agentic architecture with fail-safe loop engineering.*

Python ≥ 3.9 · the core package has zero third-party dependencies · 24/24 tests passing · bit-for-bit deterministic · every number in this document produced by running the code.

> **Scope of this document.** This is a literate reference for the **core architecture
> package only** — `mosaic_omega/` and `tests/`, which are pure standard library. It is
> *not* a description of the whole repository. The single-cell periodontitis pipeline in
> `analysis/` is a separate layer that does need third-party packages (scanpy, numpy,
> pandas, …); see the top-level [`README.md`](../README.md) and
> [`requirements.txt`](../requirements.txt) for that. Where this document and the
> repository disagree about a path, **the repository is correct**.

---

## 1. How to use this file in VS Code

Every fenced block below is the exact source of one file, dumped from the working
package. To read the architecture, open the files in this repository. To lift the
architecture out as a standalone project, run the extractor in §3.

**Where these files live in this repository:**

```text
mosaic-omega-periodontitis/
├── mosaic_omega/               ← the architecture (pure standard library)
│   ├── __init__.py        rng.py            config.py        types.py
│   ├── problem.py         llm.py            memory.py        governance.py
│   ├── agents.py          kernel.py         topology.py      routing.py
│   ├── adjudication.py    universes.py      failsafe.py      loop.py
│   ├── metrics.py         orchestrator.py   benchmark.py     cli.py
├── tests/
│   ├── __init__.py
│   ├── test_mosaic_omega.py    ← architecture suite (24 tests)
│   └── test_reproducibility.py ← reproducibility guards (5 tests)
├── analysis/
│   ├── _paths.py               ← repo-relative path resolver
│   ├── run_demo.py             ← the demo (NOT at the repository root)
│   └── …                       ← periodontitis pipeline
├── requirements.txt            ← analysis dependencies (NOT empty)
└── README.md
```

Run these **from the repository root**:

```bash
python analysis/run_demo.py         # single run + 9-group metric report + ablations
python tests/test_mosaic_omega.py   # 24 tests, no pytest needed
python tests/test_reproducibility.py
python -m mosaic_omega.cli --report
```

All four work straight from a clone with **no `pip install` step**, because the core
package is standard-library-only and `analysis/_paths.py` puts the repository root on
`sys.path`. Installing (`pip install -e .`) is only needed to `import mosaic_omega`
from outside the repository; `pip install -r requirements.txt` is needed only for the
`analysis/` single-cell pipeline.

Recommended VS Code extensions: Python, Pylance.

---

## 2. Design position

Most agentic systems are **static org charts with an LLM in every box**: fixed
roles, a permanent supervisor, a loop that stops when a step counter runs out.
MOSAIC-Ω inverts three of those assumptions.

1. **The team is a decision variable, not a configuration.** Agents are
   provisioned against a measured capability gap, pruned when dominated, and
   micro-agents are spawned with a TTL for single constraints. Team composition
   is re-derived every iteration.
2. **Authority is earned per iteration.** There is no permanent supervisor.
   `SovereigntyController` transfers sovereignty to the agent with the highest
   contextual competence, but only past a hysteresis band, so authority does not
   thrash on noise.
3. **Iteration must pay for itself.** The loop continues only when expected
   value of information exceeds the compute and risk cost of another pass. This
   is measured (`evoi_predicted` vs `evoi_realized`, `evoi_calibration_r`),
   not asserted.

The state update is the governing equation

```
G_{t+1} = F(G_t, E_t, C_t, F_t, U_t)
```

where `G_t` is the agent-topology graph, `E_t` accumulated evidence, `C_t`
contradiction pressure, `F_t` the failure record, and `U_t` residual
uncertainty. It is implemented literally in `TopologyGraph.rewire`, whose edge
affinity is a weighted sum over exactly those five terms.

### Component map

| Spec term | Module | Class / function |
|---|---|---|
| Mission Kernel | `kernel.py` | `MissionKernel.compile` |
| Dynamic Agent Provisioning | `kernel.py` | `DynamicAgentProvisioner` |
| Agent Pruning | `kernel.py` | `AgentPruner` |
| Dynamic Sovereignty | `topology.py` | `SovereigntyController` |
| Continuous topology rewiring | `topology.py` | `TopologyGraph.rewire` |
| Parallel Agent Universes | `universes.py` | `UniverseManager` |
| Agentic Blinding | `governance.py` | `BlindingFilter`, `BlindingPolicy` |
| Contractual Handoffs | `governance.py` | `ContractLedger` |
| Ephemeral Micro-Agents | `agents.py` | `MicroAgent` |
| Falsifier Agents | `agents.py` / `adjudication.py` | `FalsifierAgent`, `FalsificationEngine` |
| Contradiction Agents | `agents.py` / `adjudication.py` | `ContradictionAgent`, `ContradictionScanner` |
| Minority-Preservation Agents | `adjudication.py` | `MinorityPreserver` |
| Reputation-weighted routing | `routing.py` | `ReputationRouter` |
| Blinded Agent Jury | `adjudication.py` | `BlindedJury` |
| Five memory strata | `memory.py` | `MemoryFabric` |
| 11-phase fail-safe loop | `loop.py` | `FailSafeLoop` |
| Checkpoint / rollback / replay | `failsafe.py` | `CheckpointStore`, `RecoveryManager` |
| Loop guards | `failsafe.py` | `LoopGuards` |
| Budgets & idempotency | `failsafe.py` | `BudgetManager`, `IdempotencyLedger` |
| Meta-Agent escalation | `agents.py` | `MetaAgent` |
| Evaluation suite | `metrics.py` | `MetricsEngine` |
| Multi-seed benchmark + ablations | `benchmark.py` | `Benchmark`, `ablation_suite` |

### The eleven phases

| # | Phase | What happens | Fail-safe attached |
|---|---|---|---|
| 1 | Observe | Read the five memory strata, compute residual uncertainty | Budget check; watchdog arm |
| 2 | Plan | Mission Kernel emits stage sub-goals and a capability gap | Duplicate-plan hash guard |
| 3 | Route | Reputation-weighted assignment of constraints to agents | Load Gini; oracle-regret logging |
| 4 | Delegate | Contracts issued (inputs, deliverable, tolerance, deadline) | Bounded recursion depth; 5 violation classes |
| 5 | Execute | Agents produce claims in isolated universe branches | Per-agent exception containment; idempotent side effects |
| 6 | Verify | Verifier agents score claims against the problem oracle | Verification coverage tracked, not assumed |
| 7 | Falsify | Falsifiers attack surviving claims from four angles | Survival rate is a first-class metric |
| 8 | Score | Blinded jury adjudicates; minority preserved if evidence thin | Anonymise → shuffle → weighted aggregate; κ reported |
| 9 | Commit / Rollback | Checkpoint written or earliest corrupted checkpoint restored | Content-addressed chain, binary-search corruption find |
| 10 | Rewire | `G_{t+1} = F(...)`; sovereignty transferred; agents pruned/spawned | Cycle detection and breaking; degree cap |
| 11 | Continue / Stop | EVOI vs cost; stagnation, oscillation, deadlock, budget | Safe termination with explicit unresolved set |

### Recovery ladder

`contain → rollback → replay alternative branch → escalate to Meta-Agent`.
The Meta-Agent has four directives: `relax_verification`,
`reprovision_capability`, `restart_universe`, `terminate_unresolved`. The last
is the honest one — the system returns the unresolved constraint set rather than
manufacturing a confident answer. `unresolved_returned` is a reported metric.

---

## 3. Extracting the files from this document

If you would rather not paste 20 blocks by hand, save this file as
`MOSAIC_OMEGA.md` and run:

```python
# extract.py — rebuild the package from this markdown file
import pathlib, re

md = pathlib.Path("MOSAIC_OMEGA.md").read_text(encoding="utf-8")
pattern = re.compile(r"^### `([^`]+)`\n\n(?:.*?\n\n)??```(?:python|text)\n(.*?)\n```",
                     re.S | re.M)
root = pathlib.Path("mosaic-omega")
for path, body in pattern.findall(md):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body + "\n", encoding="utf-8")
    print("wrote", target)
```

Each `### \`path\`` heading is repository-relative, so the extractor reproduces this
repository's layout — `mosaic_omega/…`, `tests/…`, `analysis/run_demo.py`. Then
`cd mosaic-omega && python analysis/run_demo.py`.

> **These blocks are generated from the repository, not maintained by hand.**
> `python analysis/sync_reference_doc.py` rewrites every block from the file it names,
> and `tests/test_reproducibility.py` fails if any block drifts out of sync. If this
> document and the source ever disagree, the source is correct.

---

## 4. Metric catalogue

Nine groups, computed in `MetricsEngine`. A metric that cannot be computed from
a given run returns `None` — never a placeholder value.

### 4.1 Outcome — did it get the right answer

| Metric | Definition |
|---|---|
| `termination` | Terminal state: solved / stagnation / budget / deadlock / unresolved |
| `iterations` | Total loop iterations across all stages |
| `final_composite_score` | The system's own belief in its answer |
| `final_verified_score` | Fraction passing verification |
| `final_confidence` | Mean confidence of committed claims |
| `ground_truth_accuracy` | Accuracy against the benchmark's hidden optimum |
| `solved` | Whether every constraint was satisfied |
| `score_truth_gap` | `composite − ground_truth`. **Positive = overconfident.** |
| `claim_verification_coverage` | Share of claims that were actually verified |
| `verified_claim_ratio` | Share of verified claims that passed |
| `unresolved_returned` | Whether the system admitted an unresolved set |

### 4.2 Reasoning — did it survive attack

| Metric | Definition |
|---|---|
| `falsification_attempts` | Total attacks mounted |
| `falsification_success_rate` | Share of attacks that broke a claim |
| `mean_falsification_survival` | Mean per-claim survival — the adversarial robustness number |
| `contradictions_detected` | Cross-claim conflicts found |
| `contradiction_density` | Normalised by scanned claim pairs (bounded) |
| `commitment_conflicts` | Conflicts against committed memory |
| `claim_consistency_index` | Fraction of constraints with no conflicting claim |
| `falsified_claim_rate` | Share of claims that were broken at least once |

### 4.3 Consensus — was agreement earned or manufactured

| Metric | Definition |
|---|---|
| `jury_rounds` | Adjudication rounds held |
| `mean_jury_margin` | Winning margin — small margin means a genuine contest |
| `mean_jury_kappa` | Fleiss' κ on juror ballots; 0 means no independent agreement signal |
| `entropy_trajectory` | Candidate-diversity entropy per iteration |
| `final_candidate_entropy` | Diversity at termination |
| `premature_consensus_index` | Share of iterations where consensus formed on thin evidence |
| `minority_preservations` | Times a minority view was protected from elimination |
| `minority_won` | Whether a preserved minority view was ultimately adopted |
| `blinded_adjudication` | Whether the jury was actually blinded |

### 4.4 Efficiency — what it cost

`tokens_used`, `tool_calls_used`, `wall_clock_s`, `agents_provisioned`,
`agents_used`, `provisioning_efficiency`, `producer_utilisation`,
`tokens_per_verified_claim`, `tokens_per_iteration`, `agents_pruned`,
`agents_expired_ttl`, `pruning_precision`, `pruning_recall`.

Pruning quality is scored on **non-domination**: an agent is genuinely useful iff
it is the strongest live agent on at least one still-required capability. TTL
expiries are excluded from prune scoring — they are not decisions.

### 4.5 Control — was iteration justified

`score_trajectory`, `total_improvement`, `convergence_iteration`,
`evoi_predicted`, `evoi_realized`, `evoi_calibration_r`, `evoi_mae`,
`guard_trips`, `duplicate_loops_detected`, `oscillations_detected`,
`circular_handoffs_broken`, `distinct_state_signatures`, `state_revisit_rate`.

`evoi_calibration_r` is the load-bearing one: it asks whether the system's
prediction that another iteration is worth the compute actually came true.

### 4.6 Reliability — what happened when things broke

`checkpoints_written`, `recoveries`, `rollbacks_performed`, `containment_ratio`,
`mttr_iterations`, `escalations`, `escalation_rate`, `idempotency_hits`,
`duplicate_side_effects_prevented`, `budget_overruns`,
`contract_compliance_rate`, `contract_violations`.

### 4.7 Routing — was work sent to the right agent

`routing_decisions`, `mean_routing_regret`, `oracle_match_rate`,
`reputation_brier`, `reputation_ece`, `reputation_auroc`, `confidence_brier`,
`confidence_ece`, `confidence_auroc`.

Regret and oracle match are measured against the benchmark's hidden
best-agent-for-this-constraint; the router never sees it.

### 4.8 Structure — what the graph did

`rewiring_events`, `mean_edges`, `mean_degree`, `mean_modularity`,
`mean_path_length`, `mean_degree_entropy`, `edge_churn_rate`,
`sovereignty_transfers`, `sovereignty_transfer_rate`,
`mean_competence_gain_on_transfer`.

### 4.9 Safety — did the guarantees hold

| Metric | Definition |
|---|---|
| `blinding_checks` | Redaction operations audited |
| `blinding_leaks` | Residual identity fingerprints found after redaction |
| `blinding_leak_rate` | Leaks per check |
| `anchor_opportunities` | Occasions an agent could have copied a visible peer |
| `anchoring_index` | Share of those occasions where it did — the causal test of blinding |
| `branch_isolation_purity` | Share of universe branches with zero cross-contamination |
| `safe_termination` | Whether the run ended in a defined, checkpointed state |

---

## 5. Measured results

All figures below come from executing `analysis/run_demo.py` on this exact source. The
benchmark problem is `SyntheticConstraintProblem`, which carries ground truth
that the architecture's own scorers never see.

### 5.1 Single run — 3 stages × 5 constraints, seed 20260807

```
MOSAIC-Omega | termination=stagnation | composite=0.903 | ground_truth=1.000 | iterations=11 | unresolved=0
```

Full nine-group report:

```text
# MOSAIC-Omega evaluation report

## outcome
- termination: stagnation
- iterations: 11
- final_composite_score: 0.9031
- final_verified_score: 0.7667
- final_confidence: 0.7994
- ground_truth_accuracy: 1.0000
- solved: True
- score_truth_gap: -0.0969
- claim_verification_coverage: 0.4727
- verified_claim_ratio: 0.6667
- unresolved_returned: False

## reasoning
- falsification_attempts: 198
- falsification_success_rate: 0.2172
- mean_falsification_survival: 0.7828
- contradictions_detected: 472
- contradiction_density: 0.0659
- commitment_conflicts: 188
- claim_consistency_index: 0.3333
- falsified_claim_rate: 0.1879

## consensus
- jury_rounds: 11
- mean_jury_margin: 0.1190
- mean_jury_kappa: 0.3182
- entropy_trajectory: [11 values] [0.9182958340544896, 0.9999999999999999, 0.9999999999999999, 0.9999999999999999, 0.9999999999999999, 0.9999999999999999, 0.9182958340544896, 0.9999999999999999] ...
- final_candidate_entropy: 1.0000
- premature_consensus_index: 0.0163
- minority_preservations: 2
- minority_won: False
- blinded_adjudication: True

## efficiency
- tokens_used: 107720
- tool_calls_used: 267
- wall_clock_s: 0.1487
- agents_provisioned: 84
- agents_used: 48
- provisioning_efficiency: 0.5714
- producer_utilisation: 0.5490
- tokens_per_verified_claim: 2071.5385
- tokens_per_iteration: 9792.7273
- agents_pruned: 32
- agents_expired_ttl: 26
- pruning_precision: 0.5000
- pruning_recall: 1.0000

## control
- score_trajectory: [11 values] [0.7713, 0.8414, 0.7854, 0.6967, 0.449, 0.7524, 0.9077, 0.8106] ...
- total_improvement: 0.1888
- convergence_iteration: 6
- evoi_predicted: [11 values] [0.12612, 0.06427, 0.04196, 0.01862, 0.01125, 0.02312, 0.01982, 0.00658] ...
- evoi_realized: [11 values] [0.77128, 0.0701, -0.056, -0.08871, -0.24771, 0.30346, 0.1553, -0.09708] ...
- evoi_calibration_r: 0.6455
- evoi_mae: 0.1820
- guard_trips: {'stagnation': 2, 'circular_handoff': 5}
- duplicate_loops_detected: 0
- oscillations_detected: 0
- circular_handoffs_broken: 5
- distinct_state_signatures: 11
- state_revisit_rate: 0.0000

## reliability
- checkpoints_written: 11
- recoveries: 0
- rollbacks_performed: 0
- containment_ratio: 1.0000
- mttr_iterations: None
- escalations: 0
- escalation_rate: 0.0000
- idempotency_hits: 0
- duplicate_side_effects_prevented: 0
- budget_overruns: []
- contract_compliance_rate: 1.0000
- contract_violations: 0

## routing
- routing_decisions: 165
- mean_routing_regret: 0.0335
- oracle_match_rate: 0.6909
- reputation_brier: 0.2742
- reputation_ece: 0.2179
- reputation_auroc: 0.3879
- confidence_brier: 0.2446
- confidence_ece: 0.1756
- confidence_auroc: 0.5274

## structure
- rewiring_events: 11
- mean_edges: 80.7273
- mean_degree: 2.9788
- mean_modularity: 0.8393
- mean_path_length: 1.8459
- mean_degree_entropy: 4.9849
- edge_churn_rate: 0.3176
- sovereignty_transfers: 11
- sovereignty_transfer_rate: 1.0000
- mean_competence_gain_on_transfer: 0.2577

## safety
- blinding_checks: 116
- blinding_leaks: 0
- blinding_leak_rate: 0.0000
- anchor_opportunities: 65
- anchoring_index: 0.0000
- branch_isolation_purity: 1.0000
- safe_termination: True
```

Reading of this run: ground truth 1.000 with a composite of 0.903 gives a
`score_truth_gap` of **−0.097** — the system was *under*confident, which is the
safe direction. Blinding leak rate 0.0000 over 116 checks, anchoring index
0.0000 over 65 opportunities, branch isolation purity 1.0000, contract
compliance 1.0000. It terminated on stagnation rather than on a step counter,
having detected and broken 5 circular handoffs.

### 5.2 Ablations — 3 seeds per variant, means with delta against `full`

```text
metric                                                full        no_blinding    single_universe   no_falsification         no_pruning         small_jury           chaos_25
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
outcome.ground_truth_accuracy                       0.9556             0.9556   0.8889 (-0.0667)   0.9111 (-0.0444)   0.8889 (-0.0667)   0.8889 (-0.0667)   0.7111 (-0.2444)
outcome.final_composite_score                       0.8921   0.8843 (-0.0079)   0.8688 (-0.0234)   0.9027 (+0.0106)   0.8590 (-0.0332)   0.8928 (+0.0007)   0.8987 (+0.0065)
outcome.score_truth_gap                            -0.0634  -0.0713 (-0.0079)  -0.0201 (+0.0433)  -0.0084 (+0.0550)  -0.0299 (+0.0335)   0.0039 (+0.0674)   0.1876 (+0.2510)
outcome.iterations                                  9.0000   8.3333 (-0.6667)   9.3333 (+0.3333)   8.6667 (-0.3333)  11.0000 (+2.0000)  10.0000 (+1.0000)   7.6667 (-1.3333)
reasoning.mean_falsification_survival               0.8156   0.8304 (+0.0148)   0.8657 (+0.0501)   1.0000 (+0.1844)   0.8133 (-0.0023)   0.7900 (-0.0256)   0.8107 (-0.0049)
consensus.mean_jury_kappa                           0.3576   0.3452 (-0.0124)   0.0000 (-0.3576)   0.2256 (-0.1320)   0.3634 (+0.0058)   0.3625 (+0.0049)   0.2923 (-0.0653)
efficiency.tokens_used                              89,040  82,533 (-6506.67)   37,080 (-51,960)   61,427 (-27,613)  109,480 (+20,440)  94,680 (+5640.00)   66,760 (-22,280)
efficiency.producer_utilisation                     0.5881   0.5596 (-0.0285)   0.7146 (+0.1265)   0.9792 (+0.3910)   0.5686 (-0.0195)   0.5924 (+0.0043)   0.5679 (-0.0203)
reliability.contract_compliance_rate                1.0000             1.0000             1.0000             1.0000             1.0000             1.0000   0.8146 (-0.1854)
reliability.containment_ratio                       1.0000             1.0000             1.0000             1.0000             1.0000             1.0000             1.0000
routing.oracle_match_rate                           0.6286   0.6648 (+0.0363)   0.8913 (+0.2628)   0.9877 (+0.3591)   0.5043 (-0.1243)   0.6169 (-0.0117)   0.6882 (+0.0596)
routing.confidence_ece                              0.0952   0.1040 (+0.0089)   0.1212 (+0.0261)   0.0856 (-0.0096)   0.1380 (+0.0428)   0.1074 (+0.0123)   0.1714 (+0.0762)
structure.mean_modularity                           0.7998   0.7947 (-0.0051)   0.4198 (-0.3800)   0.7903 (-0.0094)   0.8089 (+0.0092)   0.8067 (+0.0070)   0.7872 (-0.0126)
safety.blinding_leak_rate                           0.0000             0.0000             0.0000             0.0000             0.0000             0.0000             0.0000
safety.anchoring_index                              0.0000   0.2279 (+0.2279)             0.0000             0.0000             0.0000             0.0000             0.0000
safety.branch_isolation_purity                      1.0000             1.0000             1.0000             1.0000             1.0000             1.0000             1.0000
consensus.premature_consensus_index                 0.0000             0.0000   1.0000 (+1.0000)             0.0000             0.0000   0.0145 (+0.0145)             0.0000
control.evoi_calibration_r                          0.6654   0.7051 (+0.0397)   0.6799 (+0.0145)   0.6305 (-0.0349)   0.6967 (+0.0313)   0.6821 (+0.0167)   0.7333 (+0.0679)
```

Per-variant detail (mean / std / min / max over 3 seeds):

**full**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.9556   0.0314   0.9333   1.0000
outcome.final_composite_score             0.8921   0.0029   0.8882   0.8949
outcome.score_truth_gap                  -0.0634   0.0342  -0.1118  -0.0384
outcome.iterations                        9.0000   0.8165   8.0000  10.0000
reasoning.mean_falsification_survival     0.8156   0.0085   0.8056   0.8264
consensus.mean_jury_kappa                 0.3576   0.1493   0.1667   0.5312
efficiency.tokens_used                    89,040  7481.03   80,000   98,320
efficiency.producer_utilisation           0.5881   0.0764   0.5111   0.6923
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.6286   0.1154   0.5407   0.7917
routing.confidence_ece                    0.0952   0.0252   0.0676   0.1285
structure.mean_modularity                 0.7998   0.0351   0.7505   0.8292
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0000   0.0000   0.0000   0.0000
control.evoi_calibration_r                0.6654   0.0658   0.6144   0.7583
```

**no_blinding**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.9556   0.0314   0.9333   1.0000
outcome.final_composite_score             0.8843   0.0219   0.8533   0.8998
outcome.score_truth_gap                  -0.0713   0.0279  -0.1002  -0.0336
outcome.iterations                        8.3333   1.2472   7.0000  10.0000
reasoning.mean_falsification_survival     0.8304   0.0103   0.8167   0.8413
consensus.mean_jury_kappa                 0.3452   0.0421   0.2857   0.3750
efficiency.tokens_used                    82,533   11,893   69,400   98,200
efficiency.producer_utilisation           0.5596   0.0759   0.5000   0.6667
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.6648   0.0899   0.5933   0.7917
routing.confidence_ece                    0.1040   0.0241   0.0824   0.1377
structure.mean_modularity                 0.7947   0.0384   0.7414   0.8307
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.2279   0.0193   0.2029   0.2500
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0000   0.0000   0.0000   0.0000
control.evoi_calibration_r                0.7051   0.0883   0.6380   0.8299
```

**single_universe**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.8889   0.0629   0.8000   0.9333
outcome.final_composite_score             0.8688   0.0233   0.8396   0.8967
outcome.score_truth_gap                  -0.0201   0.0678  -0.0937   0.0700
outcome.iterations                        9.3333   1.6997   7.0000  11.0000
reasoning.mean_falsification_survival     0.8657   0.0273   0.8333   0.9000
consensus.mean_jury_kappa                 0.0000   0.0000   0.0000   0.0000
efficiency.tokens_used                    37,080  6780.44   27,840   43,920
efficiency.producer_utilisation           0.7146   0.0352   0.6667   0.7500
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.8913   0.0481   0.8286   0.9455
routing.confidence_ece                    0.1212   0.0374   0.0853   0.1729
structure.mean_modularity                 0.4198   0.0527   0.3549   0.4840
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       1.0000   0.0000   1.0000   1.0000
control.evoi_calibration_r                0.6799   0.0972   0.5629   0.8009
```

**no_falsification**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.9111   0.0831   0.8000   1.0000
outcome.final_composite_score             0.9027   0.0044   0.8985   0.9088
outcome.score_truth_gap                  -0.0084   0.0805  -0.0912   0.1007
outcome.iterations                        8.6667   2.0548   6.0000  11.0000
reasoning.mean_falsification_survival     1.0000   0.0000   1.0000   1.0000
consensus.mean_jury_kappa                 0.2256   0.2839  -0.1111   0.5833
efficiency.tokens_used                    61,427   14,625   42,360   77,900
efficiency.producer_utilisation           0.9792   0.0295   0.9375   1.0000
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.9877   0.0175   0.9630   1.0000
routing.confidence_ece                    0.0856   0.0297   0.0459   0.1173
structure.mean_modularity                 0.7903   0.0091   0.7804   0.8024
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0000   0.0000   0.0000   0.0000
control.evoi_calibration_r                0.6305   0.0507   0.5764   0.6983
```

**no_pruning**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.8889   0.0314   0.8667   0.9333
outcome.final_composite_score             0.8590   0.0243   0.8250   0.8806
outcome.score_truth_gap                  -0.0299   0.0321  -0.0621   0.0139
outcome.iterations                       11.0000   1.4142   9.0000  12.0000
reasoning.mean_falsification_survival     0.8133   0.0257   0.7778   0.8380
consensus.mean_jury_kappa                 0.3634   0.2202   0.0625   0.5833
efficiency.tokens_used                   109,480   13,872   89,880  120,000
efficiency.producer_utilisation           0.5686   0.1230   0.3958   0.6724
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.5043   0.0570   0.4389   0.5778
routing.confidence_ece                    0.1380   0.0329   0.0919   0.1665
structure.mean_modularity                 0.8089   0.0281   0.7701   0.8359
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0000   0.0000   0.0000   0.0000
control.evoi_calibration_r                0.6967   0.1101   0.5412   0.7792
```

**small_jury**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.8889   0.0629   0.8000   0.9333
outcome.final_composite_score             0.8928   0.0282   0.8561   0.9244
outcome.score_truth_gap                   0.0039   0.0384  -0.0353   0.0561
outcome.iterations                       10.0000   1.6330   8.0000  12.0000
reasoning.mean_falsification_survival     0.7900   0.0261   0.7546   0.8167
consensus.mean_jury_kappa                 0.3625   0.2312   0.0625   0.6250
efficiency.tokens_used                    94,680   15,873   75,240  114,120
efficiency.producer_utilisation           0.5924   0.0680   0.5325   0.6875
reliability.contract_compliance_rate      1.0000   0.0000   1.0000   1.0000
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.6169   0.1032   0.4889   0.7417
routing.confidence_ece                    0.1074   0.0150   0.0887   0.1253
structure.mean_modularity                 0.8067   0.0145   0.7865   0.8199
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0145   0.0112   0.0000   0.0272
control.evoi_calibration_r                0.6821   0.0523   0.6132   0.7399
```

**chaos_25**

```text
metric                                      mean      std      min      max
outcome.ground_truth_accuracy             0.7111   0.1133   0.6000   0.8667
outcome.final_composite_score             0.8987   0.0181   0.8760   0.9202
outcome.score_truth_gap                   0.1876   0.1274   0.0094   0.2998
outcome.iterations                        7.6667   0.9428   7.0000   9.0000
reasoning.mean_falsification_survival     0.8107   0.0327   0.7654   0.8413
consensus.mean_jury_kappa                 0.2923   0.2918  -0.0714   0.6429
efficiency.tokens_used                    66,760  9433.83   59,920   80,100
efficiency.producer_utilisation           0.5679   0.1012   0.4250   0.6471
reliability.contract_compliance_rate      0.8146   0.0104   0.8060   0.8293
reliability.containment_ratio             1.0000   0.0000   1.0000   1.0000
routing.oracle_match_rate                 0.6882   0.0874   0.6074   0.8095
routing.confidence_ece                    0.1714   0.0145   0.1565   0.1911
structure.mean_modularity                 0.7872   0.0306   0.7452   0.8171
safety.blinding_leak_rate                 0.0000   0.0000   0.0000   0.0000
safety.anchoring_index                    0.0000   0.0000   0.0000   0.0000
safety.branch_isolation_purity            1.0000   0.0000   1.0000   1.0000
consensus.premature_consensus_index       0.0000   0.0000   0.0000   0.0000
control.evoi_calibration_r                0.7333   0.0582   0.6547   0.7937
```

### 5.3 What the ablations establish

**Blinding is causal, not decorative.** `no_blinding` moves the anchoring index
from 0.0000 to 0.2279 — roughly a quarter of the occasions where an agent could
copy a visible peer answer, it did. Ground-truth accuracy happens to hold on
this benchmark, but the independence of the ensemble is measurably destroyed,
which is the property the jury's validity rests on.

**Parallel universes buy diversity, and diversity is what the jury adjudicates.**
`single_universe` collapses modularity from 0.80 to 0.42, drives jury κ to
exactly 0.0 (no independent agreement signal remains), pins
`premature_consensus_index` at 1.0000, and costs 6.7 points of ground-truth
accuracy — while looking cheaper at 37k tokens against 89k. This is the
efficiency trap the metric suite exists to expose: the cheap variant is the one
that stops disagreeing with itself.

**Falsification is what keeps the score honest.** Removing it makes survival
trivially 1.0000 and raises the composite score to 0.9027 — the highest of any
variant — while ground truth *falls* to 0.9111 with variance more than doubling
(std 0.0831 against 0.0314). The system scores itself better precisely because
nothing is attacking its claims. `score_truth_gap` moves from −0.0634 toward
zero for the same reason.

**Pruning pays for itself.** `no_pruning` costs 20,440 extra tokens, runs 2 more
iterations, and drops oracle match rate from 0.629 to 0.504 — a bloated roster
routes worse, because more marginal agents are competing for each constraint.

**Under fault injection the architecture degrades safely but rates itself
poorly.** At 25% agent-failure and branch-corruption rates, ground truth falls to
0.7111 and contract compliance to 0.8146, yet containment ratio stays 1.0000 and
every run still terminates safely. The honest finding is `score_truth_gap`
**+0.1876**: self-assessment degrades faster than performance does. Any system of
this class that reports only its own composite score will look fine while it is
failing.

**Jury size matters less than jury independence.** `small_jury` (1 juror) barely
moves κ, because κ is already carried by the diversity of the universes feeding
it — but it does push `score_truth_gap` positive (+0.0039 against −0.0634).

### 5.4 Reproducibility

Randomness is derived per decision from semantic coordinates via blake2b
(`rng.py`); there is no global mutable RNG. Two runs with the same seed produce
identical `state_signatures` and identical summaries — asserted in
`test_end_to_end_determinism`. The `full` and `no_blinding` variants share
ground-truth accuracy (0.9556) not by coincidence but because the seeds and
problem instances are identical; only the blinding channel differs.

### 5.5 Test suite

`24/24 passed` on this source, no pytest required. Coverage: mission kernel compilation;
provisioning gap-cover and reuse; micro-agent TTL; all four pruning paths
including protected roles; sovereignty hysteresis; topology rewire and cycle
break; routing oracle match; blinding redaction and leak audit; all five
contract violation classes plus depth bound; falsification discriminating wrong
from right assignments; contradiction detection on values and commitments;
minority preservation trigger *and* non-trigger; blinded jury weighted verdict;
five memory strata and fork isolation; rollback to earliest corrupted
checkpoint; all four loop guards; idempotency; the full recovery→escalation
ladder; universe isolation; metric primitives; end-to-end determinism with all
nine metric groups present; chaos run reaching safe termination with recoveries;
explicit unresolved-state return.

---

## 6. Adapting it to your own domain

Subclass `Problem` in `problem.py` with eight methods: `stages`,
`capability_catalog`, `value_space`, `capability_for`, `propose`, `verify`,
`attack`, and `true_score` (the last is optional and used only for evaluation —
omit it and the ground-truth metrics report `None` rather than guessing).
Everything else — provisioning, routing, sovereignty, falsification, jury,
checkpointing, recovery, metrics — is domain-agnostic.

To route agent cognition through a real model instead of the deterministic
heuristic reasoner:

```python
from mosaic_omega import MosaicOmega, AnthropicBackend
MosaicOmega(backend=AnthropicBackend(model="claude-sonnet-4-6")).solve(problem)
```

Agents fall back to the heuristic path on any backend failure, so a dropped API
call degrades answer quality rather than crashing the run. Note that with a live
backend the runs are no longer bit-for-bit deterministic; the metric suite still
applies, but comparisons need more seeds.

---


## 7. Source


### Contents

- [`mosaic_omega/__init__.py`](#mosaicomegainitpy)
- [`mosaic_omega/rng.py`](#mosaicomegarngpy)
- [`mosaic_omega/config.py`](#mosaicomegaconfigpy)
- [`mosaic_omega/types.py`](#mosaicomegatypespy)
- [`mosaic_omega/problem.py`](#mosaicomegaproblempy)
- [`mosaic_omega/llm.py`](#mosaicomegallmpy)
- [`mosaic_omega/memory.py`](#mosaicomegamemorypy)
- [`mosaic_omega/governance.py`](#mosaicomegagovernancepy)
- [`mosaic_omega/agents.py`](#mosaicomegaagentspy)
- [`mosaic_omega/kernel.py`](#mosaicomegakernelpy)
- [`mosaic_omega/topology.py`](#mosaicomegatopologypy)
- [`mosaic_omega/routing.py`](#mosaicomegaroutingpy)
- [`mosaic_omega/adjudication.py`](#mosaicomegaadjudicationpy)
- [`mosaic_omega/universes.py`](#mosaicomegauniversespy)
- [`mosaic_omega/failsafe.py`](#mosaicomegafailsafepy)
- [`mosaic_omega/loop.py`](#mosaicomegalooppy)
- [`mosaic_omega/metrics.py`](#mosaicomegametricspy)
- [`mosaic_omega/orchestrator.py`](#mosaicomegaorchestratorpy)
- [`mosaic_omega/benchmark.py`](#mosaicomegabenchmarkpy)
- [`mosaic_omega/cli.py`](#mosaicomegaclipy)
- [`tests/__init__.py`](#testsinitpy)
- [`tests/test_mosaic_omega.py`](#teststestmosaicomegapy)
- [`analysis/run_demo.py`](#rundemopy)
- [`requirements.txt`](#requirementstxt)


<a id="mosaicomegainitpy"></a>

### `mosaic_omega/__init__.py`

Public API surface.

```python
"""MOSAIC-Omega: a self-reconfiguring agentic architecture with fail-safe
loop engineering.

Quick start
-----------
    from mosaic_omega import MosaicOmega, MosaicConfig, SyntheticConstraintProblem

    problem = SyntheticConstraintProblem()
    result = MosaicOmega(MosaicConfig()).solve(problem)
    print(result.summary())
    print(MetricsEngine(result.trace, problem).report())
"""
from .adjudication import BlindedJury, ContradictionScanner, FalsificationEngine, MinorityPreserver
from .agents import (
    BaseAgent, ContradictionAgent, FalsifierAgent, JurorAgent, MetaAgent,
    MicroAgent, MinorityPreservationAgent, SpecialistAgent, VerifierAgent, WatchdogAgent,
    build_agent,
)
from .config import MosaicConfig
from .failsafe import (
    BudgetManager, CheckpointStore, IdempotencyLedger, LoopGuards, RecoveryManager,
)
from .freeenergy import FreeEnergyParams, StructuralFreeEnergy
from .governance import BlindingFilter, BlindingPolicy, ContractLedger
from .kernel import AgentPruner, DynamicAgentProvisioner, MissionKernel
from .llm import AnthropicBackend, LLMBackend, NullBackend
from .loop import FailSafeLoop, LoopOutcome
from .memory import MemoryFabric
from .metrics import MetricsEngine
from .orchestrator import MosaicOmega, RunResult
from .problem import Problem, SyntheticConstraintProblem
from .routing import ReputationRouter
from .topology import SovereigntyController, TopologyGraph
from .types import (
    AgentRole, AgentRuntime, AgentSpec, Candidate, Claim, MissionSpec, Phase,
    RiskLevel, RunTrace, StageSpec, Termination,
)
from .universes import UniverseManager, UniverseState

__version__ = "1.0.0"
__all__ = [
    "MosaicOmega", "MosaicConfig", "RunResult", "MetricsEngine",
    "Problem", "SyntheticConstraintProblem", "MissionKernel",
    "DynamicAgentProvisioner", "AgentPruner", "TopologyGraph",
    "SovereigntyController", "ReputationRouter", "UniverseManager",
    "UniverseState", "BlindingFilter", "BlindingPolicy", "ContractLedger",
    "FalsificationEngine", "ContradictionScanner", "MinorityPreserver",
    "BlindedJury", "MemoryFabric", "FailSafeLoop", "LoopOutcome",
    "StructuralFreeEnergy", "FreeEnergyParams",
    "CheckpointStore", "LoopGuards", "RecoveryManager", "BudgetManager",
    "IdempotencyLedger", "BaseAgent", "SpecialistAgent", "MicroAgent",
    "VerifierAgent", "FalsifierAgent", "ContradictionAgent",
    "MinorityPreservationAgent", "JurorAgent", "WatchdogAgent", "MetaAgent",
    "build_agent", "AnthropicBackend", "NullBackend", "LLMBackend",
    "AgentRole", "AgentSpec", "AgentRuntime", "Candidate", "Claim",
    "MissionSpec", "StageSpec", "Phase", "RiskLevel", "Termination", "RunTrace",
    "__version__",
]
```


<a id="mosaicomegarngpy"></a>

### `mosaic_omega/rng.py`

Deterministic randomness. No global mutable RNG — every stochastic decision is seeded from its own semantic coordinates, which is what makes runs bit-for-bit reproducible.

```python
"""Deterministic randomness utilities.

Every stochastic decision in MOSAIC-Omega is derived from a stable hash of its
semantic coordinates (agent id, constraint id, iteration, ...) rather than from
a global mutable RNG. This makes any run bit-for-bit reproducible and makes
`deterministic replay fidelity` an actually measurable metric.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Iterable


def stable_hash(*parts: Any) -> int:
    """Order-sensitive, process-independent 64-bit hash."""
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big")


def stable_sig(*parts: Any) -> str:
    """Short hex signature, used for state/loop signatures."""
    return format(stable_hash(*parts), "016x")


def rng_for(*parts: Any) -> random.Random:
    """A seeded RNG bound to a semantic coordinate."""
    return random.Random(stable_hash(*parts))


def stable_shuffle(items: Iterable[Any], *seed_parts: Any) -> list:
    out = list(items)
    rng_for(*seed_parts).shuffle(out)
    return out
```


<a id="mosaicomegaconfigpy"></a>

### `mosaic_omega/config.py`

Every tunable in one dataclass, including budgets, hysteresis, blinding level and chaos-injection rates.

```python
"""Global configuration for MOSAIC-Omega."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass
class MosaicConfig:
    # --- determinism -------------------------------------------------------
    seed: int = 20260807

    # --- loop control ------------------------------------------------------
    max_iterations: int = 10
    max_delegation_depth: int = 4
    min_evoi: float = 0.0                 # continue only if EVOI > this
    evoi_quality_weight: float = 1.0
    evoi_risk_weight: float = 0.35

    # --- budgets -----------------------------------------------------------
    token_budget: int = 250_000
    tool_call_budget: int = 600
    wall_clock_budget_s: float = 600.0
    per_agent_token_budget: int = 14_000
    per_agent_wall_clock_s: float = 45.0
    token_cost_per_unit: float = 5.0e-7   # quality-units per token
    time_cost_per_second: float = 5.0e-4

    # --- provisioning / pruning -------------------------------------------
    max_active_agents: int = 24
    min_active_agents: int = 3
    prune_utility_threshold: float = 0.30
    redundancy_jaccard: float = 0.75
    prune_grace_iterations: int = 1       # agents are immune for N iterations
    micro_agent_ttl: int = 1              # ephemeral micro-agents expire fast
    max_micro_agents_per_iteration: int = 3

    # --- sovereignty -------------------------------------------------------
    sovereignty_hysteresis: float = 0.12
    sovereignty_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "domain_match": 0.40,
            "reputation": 0.30,
            "verification_pass": 0.20,
            "failure_penalty": 0.10,
        }
    )

    # --- topology ----------------------------------------------------------
    edge_learning_rate: float = 0.35      # gradient-descent step size eta on J
    edge_prune_threshold: float = 0.18
    max_degree: int = 6
    topology_add_top_k: int = 2
    contamination_penalty: float = 0.45

    # --- free-energy structural control (FESC) -----------------------------
    fe_kappa: float = 1.0                 # wiring cost; kappa=1 => legacy update
    fe_lambda_U: float = 0.15             # price of residual belief uncertainty

    # --- universes ---------------------------------------------------------
    n_universes: int = 3
    universe_strategies: tuple = ("conservative", "exploratory", "adversarial")

    # --- adjudication ------------------------------------------------------
    n_jurors: int = 5
    jury_margin_threshold: float = 0.04
    falsifiers_per_candidate: int = 2
    attacks_per_falsifier: int = 3
    minority_entropy_floor: float = 0.35   # reporting threshold for entropy collapse
    consensus_share_ceiling: float = 0.60  # top cluster share that counts as consensus
    evidence_sufficiency_floor: float = 0.60

    # --- verification ------------------------------------------------------
    base_verification_fraction: float = 0.45
    high_risk_verification_fraction: float = 0.90
    verifier_false_negative_rate: float = 0.06

    # --- guards ------------------------------------------------------------
    duplicate_loop_k: int = 3
    oscillation_window: int = 8
    oscillation_min_period: int = 2
    oscillation_max_period: int = 4
    oscillation_min_repeats: int = 2
    stagnation_window: int = 3
    stagnation_epsilon: float = 0.01
    max_recovery_attempts: int = 3
    watchdog_heartbeat_s: float = 30.0

    # --- blinding ----------------------------------------------------------
    blinding_level: str = "strict"         # strict | partial | none
    anchor_susceptibility: float = 0.55    # P(adopt a visible peer answer | unblinded)

    # --- chaos / fault injection (reliability benchmarking) ----------------
    chaos_agent_failure_rate: float = 0.0      # P(agent call raises)
    chaos_branch_corruption_rate: float = 0.0  # P(branch invariant is broken)

    # --- execution ---------------------------------------------------------
    parallel_universes: bool = False       # thread pool; results stay deterministic
    verbose: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["universe_strategies"] = list(self.universe_strategies)
        return d
```


<a id="mosaicomegatypespy"></a>

### `mosaic_omega/types.py`

Enums and dataclasses for the whole system, plus the append-only `RunTrace` that the metric engine reads.

```python
"""Core data types for MOSAIC-Omega."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class Phase(str, Enum):
    OBSERVE = "observe"
    PLAN = "plan"
    ROUTE = "route"
    DELEGATE = "delegate"
    EXECUTE = "execute"
    VERIFY = "verify"
    FALSIFY = "falsify"
    SCORE = "score"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    REWIRE = "rewire"
    DECIDE = "decide"


class AgentRole(str, Enum):
    SPECIALIST = "specialist"
    VERIFIER = "verifier"
    FALSIFIER = "falsifier"
    CONTRADICTION = "contradiction"
    MINORITY = "minority"
    JUROR = "juror"
    MICRO = "micro"
    WATCHDOG = "watchdog"
    META = "meta"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Termination(str, Enum):
    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    STAGNATION = "stagnation"
    OSCILLATION = "oscillation"
    DEADLOCK = "deadlock"
    DUPLICATE_LOOP = "duplicate_loop"
    NEGATIVE_EVOI = "negative_evoi"
    UNRESOLVED = "unresolved"
    ESCALATED_UNRESOLVED = "escalated_unresolved"
    SAFE_STOP = "safe_stop"


class FailureClass(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    BRANCH = "branch"
    ORCHESTRATION = "orchestration"
    CONTRACT = "contract"


# ---------------------------------------------------------------------------
# Mission specification
# ---------------------------------------------------------------------------
@dataclass
class StageSpec:
    stage_id: str
    description: str
    constraint_ids: List[str]
    required_capabilities: List[str]
    risk: RiskLevel = RiskLevel.MEDIUM
    success_predicate: str = "verified_score >= 0.85"
    verification_intensity: float = 0.45


@dataclass
class MissionSpec:
    mission_id: str
    goal: str
    stages: List[StageSpec]
    global_constraints: List[str] = field(default_factory=list)
    capability_catalog: List[str] = field(default_factory=list)
    acceptance_threshold: float = 0.85

    @property
    def all_constraints(self) -> List[str]:
        seen, out = set(), []
        for s in self.stages:
            for c in s.constraint_ids:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
@dataclass
class AgentSpec:
    agent_id: str
    role: AgentRole
    capabilities: Set[str]
    skill: Dict[str, float]              # capability -> latent competence [0,1]
    token_budget: int = 10_000
    wall_clock_budget_s: float = 30.0
    ttl: Optional[int] = None            # iterations before auto-expiry (micro agents)
    created_iteration: int = 0
    universe: str = "root"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["capabilities"] = sorted(self.capabilities)
        d["role"] = self.role.value
        return d


@dataclass
class AgentRuntime:
    spec: AgentSpec
    alpha: float = 1.0                   # Beta posterior successes (+prior)
    beta: float = 1.0                    # Beta posterior failures (+prior)
    tokens_used: int = 0
    time_used_s: float = 0.0
    tasks_done: int = 0
    verified_true: int = 0
    verified_false: int = 0
    falsified_claims: int = 0
    contract_violations: int = 0
    alive: bool = True
    pruned_reason: Optional[str] = None
    last_heartbeat: float = 0.0
    contributions: float = 0.0

    @property
    def agent_id(self) -> str:
        return self.spec.agent_id

    @property
    def reputation(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def verification_pass_rate(self) -> float:
        n = self.verified_true + self.verified_false
        return self.verified_true / n if n else 0.5

    @property
    def failure_rate(self) -> float:
        n = self.tasks_done
        return (self.falsified_claims + self.contract_violations) / n if n else 0.0


# ---------------------------------------------------------------------------
# Claims, candidates, verdicts
# ---------------------------------------------------------------------------
@dataclass
class Claim:
    claim_id: str
    constraint_id: str
    value: str
    author: str
    confidence: float
    universe: str
    iteration: int
    verified: Optional[bool] = None      # None = unverified
    falsified: bool = False
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    candidate_id: str
    universe: str
    iteration: int
    assignment: Dict[str, str]
    claims: List[Claim] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    raw_score: float = 0.0
    verified_score: float = 0.0
    falsification_survival: float = 1.0
    contradiction_penalty: float = 0.0
    jury_score: float = 0.0
    composite_score: float = 0.0
    confidence: float = 0.5
    is_minority: bool = False

    def signature(self) -> str:
        from .rng import stable_sig
        return stable_sig(tuple(sorted(self.assignment.items())))


@dataclass
class Attack:
    attack_id: str
    attacker: str
    candidate_id: str
    constraint_id: str
    kind: str                            # counterexample | assumption | edge_case | metric_gaming
    succeeded: bool
    rationale: str


@dataclass
class FalsificationReport:
    candidate_id: str
    attacks: List[Attack] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        return len(self.attacks)

    @property
    def successful(self) -> int:
        return sum(1 for a in self.attacks if a.succeeded)

    @property
    def survival(self) -> float:
        return 1.0 - (self.successful / self.attempted) if self.attempted else 1.0


@dataclass
class Contradiction:
    constraint_id: str
    claim_a: str
    claim_b: str
    kind: str                            # value_conflict | commitment_conflict
    detected_by: str


@dataclass
class JurorBallot:
    juror_id: str
    scores: Dict[str, float]             # candidate_id -> score
    top_choice: str
    reputation: float


@dataclass
class JuryVerdict:
    winner_id: Optional[str]
    ballots: List[JurorBallot] = field(default_factory=list)
    aggregate: Dict[str, float] = field(default_factory=dict)
    margin: float = 0.0
    agreement_kappa: float = 0.0
    blinded: bool = True


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------
@dataclass
class Contract:
    contract_id: str
    principal: str
    agent: str
    task_id: str
    depth: int
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    allowed_tools: Set[str] = field(default_factory=set)
    forbidden_scopes: Set[str] = field(default_factory=set)
    deliverable_keys: Set[str] = field(default_factory=set)
    token_budget: int = 8_000
    deadline_s: float = 30.0
    max_depth: int = 4


@dataclass
class ContractResult:
    contract_id: str
    ok: bool
    violations: List[str] = field(default_factory=list)
    tokens_used: int = 0
    elapsed_s: float = 0.0


# ---------------------------------------------------------------------------
# Checkpoints & events
# ---------------------------------------------------------------------------
@dataclass
class Checkpoint:
    checkpoint_id: str
    parent_id: Optional[str]
    iteration: int
    phase: Phase
    state_blob: str                      # JSON serialised orchestration state
    integrity_hash: str
    branch: str = "root"
    corrupted: bool = False


@dataclass
class LoopEvent:
    iteration: int
    phase: Phase
    universe: str
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class RoutingDecision:
    iteration: int
    task_id: str
    chosen: str
    ranked: List[Tuple[str, float]]
    oracle_choice: str
    oracle_utility: float
    chosen_utility: float
    predicted_reliability: float
    realized_success: Optional[bool] = None


@dataclass
class SovereigntyTransfer:
    iteration: int
    from_agent: Optional[str]
    to_agent: str
    competence_from: float
    competence_to: float


@dataclass
class TopologySnapshot:
    iteration: int
    n_nodes: int
    n_edges: int
    edges_added: int
    edges_removed: int
    avg_degree: float
    degree_entropy: float
    modularity: float
    avg_path_length: float


@dataclass
class RecoveryRecord:
    iteration: int
    failure_class: FailureClass
    detail: str
    rolled_back_to: Optional[str]
    attempts: int
    contained: bool
    escalated: bool
    recovered_at_iteration: Optional[int] = None


@dataclass
class RunTrace:
    """Everything the metrics engine needs. Append-only during a run."""
    mission: Optional[MissionSpec] = None
    events: List[LoopEvent] = field(default_factory=list)
    iterations: int = 0
    termination: Optional[Termination] = None
    final_candidate: Optional[Candidate] = None

    claims: List[Claim] = field(default_factory=list)
    candidates: List[Candidate] = field(default_factory=list)
    falsifications: List[FalsificationReport] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    verdicts: List[JuryVerdict] = field(default_factory=list)

    agents_provisioned: List[AgentSpec] = field(default_factory=list)
    agents_used: Set[str] = field(default_factory=set)
    prune_decisions: List[Dict[str, Any]] = field(default_factory=list)
    routing: List[RoutingDecision] = field(default_factory=list)
    sovereignty: List[SovereigntyTransfer] = field(default_factory=list)
    topology: List[TopologySnapshot] = field(default_factory=list)

    contracts: List[Contract] = field(default_factory=list)
    contract_results: List[ContractResult] = field(default_factory=list)

    checkpoints: List[Checkpoint] = field(default_factory=list)
    recoveries: List[RecoveryRecord] = field(default_factory=list)
    guard_trips: List[Dict[str, Any]] = field(default_factory=list)
    escalations: List[Dict[str, Any]] = field(default_factory=list)

    blinding_leaks: int = 0
    blinding_checks: int = 0
    anchored_outputs: int = 0
    anchor_opportunities: int = 0

    tokens_used: int = 0
    tool_calls_used: int = 0
    wall_clock_s: float = 0.0
    budget_overruns: List[str] = field(default_factory=list)

    score_history: List[float] = field(default_factory=list)
    entropy_history: List[float] = field(default_factory=list)
    evoi_predicted: List[float] = field(default_factory=list)
    evoi_realized: List[float] = field(default_factory=list)
    minority_preserved: int = 0
    minority_survived_to_final: int = 0
    idempotent_hits: int = 0
    duplicates_prevented: int = 0
    isolation_purity: float = 1.0
    total_iterations: int = 0
    state_signatures: List[str] = field(default_factory=list)
```


<a id="mosaicomegaproblempy"></a>

### `mosaic_omega/problem.py`

The domain plug-point. `SyntheticConstraintProblem` is the ground-truth-bearing benchmark.

```python
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
```


<a id="mosaicomegallmpy"></a>

### `mosaic_omega/llm.py`

Backends. `NullBackend` is the default and needs no network; `AnthropicBackend` uses stdlib urllib only.

```python
"""Optional LLM backends.

MOSAIC-Omega runs end to end with no network access and no API key: agents fall
back to `HeuristicReasoner`, which is deterministic. Attach `AnthropicBackend`
to route agent cognition through a real model instead.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


class LLMBackend(Protocol):
    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str: ...


@dataclass
class NullBackend:
    """No-op backend. Agents use their heuristic reasoner."""
    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        return ""


@dataclass
class AnthropicBackend:
    """Minimal stdlib client for the Anthropic Messages API."""
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    base_url: str = "https://api.anthropic.com/v1/messages"
    timeout_s: float = 60.0
    last_usage: Dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.last_usage = data.get("usage", self.last_usage)
        return "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        )


def parse_json_block(text: str) -> Any:
    """Tolerant JSON extraction from a model reply."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("{")
    alt = cleaned.find("[")
    if alt != -1 and (start == -1 or alt < start):
        start = alt
    if start == -1:
        raise ValueError("no JSON object found")
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    return json.loads(cleaned[start:end + 1])
```


<a id="mosaicomegamemorypy"></a>

### `mosaic_omega/memory.py`

Five memory strata — working, episodic, procedural, failure, commitment — with snapshot/restore and per-universe fork.

```python
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
```


<a id="mosaicomegagovernancepy"></a>

### `mosaic_omega/governance.py`

Agentic Blinding (redaction plus leak audit) and Contractual Handoffs (five violation classes, bounded recursion).

```python
"""Agentic Blinding and Contractual Handoffs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .rng import stable_sig
from .types import Contract, ContractResult


# ---------------------------------------------------------------------------
# Agentic Blinding
# ---------------------------------------------------------------------------
BLINDABLE_KEYS: Set[str] = {
    "peer_conclusions", "peer_confidences", "peer_scores", "peer_authors",
    "author", "author_reputation", "prior_verdicts", "universe_leaderboard",
    "current_best", "jury_history", "sovereign_opinion", "reputation_table",
}

PARTIAL_KEEP: Set[str] = {"peer_conclusions"}


@dataclass
class BlindingPolicy:
    level: str = "strict"                # strict | partial | none
    extra_blind: Set[str] = field(default_factory=set)
    allow: Set[str] = field(default_factory=set)

    def blinded_keys(self) -> Set[str]:
        if self.level == "none":
            return set()
        keys = set(BLINDABLE_KEYS) | set(self.extra_blind)
        if self.level == "partial":
            keys -= PARTIAL_KEEP
        return keys - set(self.allow)


@dataclass
class BlindingReport:
    redacted: List[str] = field(default_factory=list)
    leaks: List[str] = field(default_factory=list)

    @property
    def leaked(self) -> bool:
        return bool(self.leaks)


class BlindingFilter:
    """Removes anchoring/contamination surfaces from an agent's context and
    then audits the redacted context for residual fingerprints."""

    def __init__(self, policy: Optional[BlindingPolicy] = None) -> None:
        self.policy = policy or BlindingPolicy()

    def apply(self, context: Dict[str, Any]) -> Tuple[Dict[str, Any], BlindingReport]:
        blind = self.policy.blinded_keys()
        report = BlindingReport()
        fingerprints: Set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for v in value.values():
                    collect(v)
            elif isinstance(value, (list, tuple, set)):
                for v in value:
                    collect(v)
            elif isinstance(value, str) and value:
                fingerprints.add(value)

        redacted: Dict[str, Any] = {}
        for k, v in context.items():
            if k in blind:
                report.redacted.append(k)
                collect(v)
            else:
                redacted[k] = v

        # audit: did a blinded string survive anywhere in the kept context?
        def scan(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for kk, vv in value.items():
                    scan(vv, f"{path}.{kk}")
            elif isinstance(value, (list, tuple, set)):
                for i, vv in enumerate(value):
                    scan(vv, f"{path}[{i}]")
            elif isinstance(value, str):
                for fp in fingerprints:
                    if len(fp) >= 4 and fp in value:
                        report.leaks.append(f"{path}:{fp}")

        scan(redacted, "ctx")
        redacted["_blinding"] = {
            "level": self.policy.level,
            "redacted": sorted(report.redacted),
            "seal": stable_sig(sorted(report.redacted), self.policy.level),
        }
        return redacted, report


# ---------------------------------------------------------------------------
# Contractual Handoffs
# ---------------------------------------------------------------------------
class ContractLedger:
    """Issues, tracks and adjudicates constrained delegations."""

    def __init__(self, max_depth: int = 4) -> None:
        self.max_depth = max_depth
        self.open: Dict[str, Contract] = {}
        self.issued: List[Contract] = []
        self.results: List[ContractResult] = []

    def issue(
        self,
        principal: str,
        agent: str,
        task_id: str,
        depth: int,
        *,
        preconditions: Optional[List[str]] = None,
        postconditions: Optional[List[str]] = None,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_scopes: Optional[Set[str]] = None,
        deliverable_keys: Optional[Set[str]] = None,
        token_budget: int = 8_000,
        deadline_s: float = 30.0,
    ) -> Contract:
        if depth > self.max_depth:
            raise RecursionError(
                f"bounded recursive delegation exceeded: depth={depth} > {self.max_depth}"
            )
        cid = stable_sig("contract", principal, agent, task_id, depth, len(self.issued))
        contract = Contract(
            contract_id=cid,
            principal=principal,
            agent=agent,
            task_id=task_id,
            depth=depth,
            preconditions=list(preconditions or []),
            postconditions=list(postconditions or ["deliverable_present", "within_scope"]),
            allowed_tools=set(allowed_tools or {"reason", "verify"}),
            forbidden_scopes=set(forbidden_scopes or set()),
            deliverable_keys=set(deliverable_keys or {"claims"}),
            token_budget=token_budget,
            deadline_s=deadline_s,
            max_depth=self.max_depth,
        )
        self.open[cid] = contract
        self.issued.append(contract)
        return contract

    def settle(
        self,
        contract: Contract,
        deliverable: Dict[str, Any],
        tokens_used: int,
        elapsed_s: float,
        tools_used: Optional[Set[str]] = None,
        touched_scopes: Optional[Set[str]] = None,
    ) -> ContractResult:
        violations: List[str] = []
        missing = contract.deliverable_keys - set(deliverable.keys())
        if missing:
            violations.append(f"missing_deliverable:{sorted(missing)}")
        if tokens_used > contract.token_budget:
            violations.append(f"token_overrun:{tokens_used}>{contract.token_budget}")
        if elapsed_s > contract.deadline_s:
            violations.append(f"deadline_exceeded:{elapsed_s:.2f}>{contract.deadline_s}")
        illegal = set(tools_used or set()) - contract.allowed_tools
        if illegal:
            violations.append(f"illegal_tools:{sorted(illegal)}")
        out_of_scope = set(touched_scopes or set()) & contract.forbidden_scopes
        if out_of_scope:
            violations.append(f"scope_violation:{sorted(out_of_scope)}")

        result = ContractResult(
            contract_id=contract.contract_id,
            ok=not violations,
            violations=violations,
            tokens_used=tokens_used,
            elapsed_s=elapsed_s,
        )
        self.open.pop(contract.contract_id, None)
        self.results.append(result)
        return result

    @property
    def compliance_rate(self) -> float:
        if not self.results:
            return 1.0
        return sum(1 for r in self.results if r.ok) / len(self.results)
```


<a id="mosaicomegaagentspy"></a>

### `mosaic_omega/agents.py`

All agent classes, including falsifiers, contradiction agents, minority preservers, jurors, watchdogs and the Meta-Agent.

```python
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
```


<a id="mosaicomegakernelpy"></a>

### `mosaic_omega/kernel.py`

Mission Kernel compilation, dynamic provisioning by capability gap, and pruning by non-domination.

```python
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
```


<a id="mosaicomegatopologypy"></a>

### `mosaic_omega/topology.py`

`G_{t+1} = F(G_t, E_t, C_t, F_t, U_t)` implemented literally, plus sovereignty transfer with hysteresis and structural metrics.

```python
"""Dynamic communication topology and Dynamic Sovereignty.

Implements the governing state equation

    G_{t+1} = F(G_t, E_t, C_t, F_t, U_t)

where E_t is the evidence/event signal, C_t the competence vector, F_t the
failure signal and U_t the uncertainty signal.

Under Free-Energy Structural Control (see ``freeenergy.py``) ``F`` is no longer a
hand-tuned score: each edge target is the closed-form minimiser
``w* = clip(g/kappa, 0, 1)`` of the convex structural free energy ``J``, and the
learning-rate update is a provably convergent coordinate gradient step toward it.
``rewire`` also reports the free energy still recoverable next iteration, which
the loop consumes as a *derived* value-of-information estimate.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .config import MosaicConfig
from .freeenergy import FreeEnergyParams, StructuralFreeEnergy
from .types import AgentRuntime, SovereigntyTransfer, StageSpec, TopologySnapshot


# ---------------------------------------------------------------------------
class TopologyGraph:
    """Weighted, undirected communication graph + a directed handoff graph."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.nodes: Set[str] = set()
        self.weights: Dict[Tuple[str, str], float] = {}     # undirected, key sorted
        self.handoffs: Dict[str, Set[str]] = {}             # directed delegation edges
        self.co_success: Dict[Tuple[str, str], float] = {}
        self.contamination: Dict[Tuple[str, str], float] = {}
        # The convex objective whose minimiser defines every edge target.
        self.fe = StructuralFreeEnergy(FreeEnergyParams(
            kappa=config.fe_kappa,
            w_complement=0.35,
            w_competence=0.30,
            w_evidence=0.20,
            w_uncertainty=0.15,
            w_failure=0.30,
            contamination_penalty=config.contamination_penalty,
            lambda_U=config.fe_lambda_U,
        ))
        # Free energy the *next* rewire can still shed; the loop reads this as
        # the derived value-of-information for the continue/stop decision.
        self.predicted_descent: float = 0.0

    # -- basic ops ----------------------------------------------------------
    @staticmethod
    def key(a: str, b: str) -> Tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        self.handoffs.setdefault(node, set())

    def remove_node(self, node: str) -> None:
        self.nodes.discard(node)
        self.handoffs.pop(node, None)
        for targets in self.handoffs.values():
            targets.discard(node)
        for k in [k for k in self.weights if node in k]:
            del self.weights[k]

    def neighbors(self, node: str) -> Set[str]:
        return {b if a == node else a for (a, b) in self.weights if node in (a, b)}

    def degree(self, node: str) -> int:
        return len(self.neighbors(node))

    def add_handoff(self, src: str, dst: str) -> None:
        self.handoffs.setdefault(src, set()).add(dst)
        self.handoffs.setdefault(dst, set())

    # -- cycle detection (circular handoff guard) ---------------------------
    def find_handoff_cycle(self) -> Optional[List[str]]:
        color: Dict[str, int] = {n: 0 for n in self.handoffs}
        parent: Dict[str, Optional[str]] = {n: None for n in self.handoffs}

        for start in sorted(self.handoffs):
            if color[start] != 0:
                continue
            stack: List[Tuple[str, Iterable[str]]] = [(start, iter(sorted(self.handoffs[start])))]
            color[start] = 1
            while stack:
                node, it = stack[-1]
                advanced = False
                for nxt in it:
                    if color.get(nxt, 0) == 0:
                        color[nxt] = 1
                        parent[nxt] = node
                        stack.append((nxt, iter(sorted(self.handoffs.get(nxt, ())))))
                        advanced = True
                        break
                    if color.get(nxt, 0) == 1:
                        cycle = [nxt]
                        cur: Optional[str] = node
                        while cur is not None and cur != nxt:
                            cycle.append(cur)
                            cur = parent[cur]
                        cycle.append(nxt)
                        return list(reversed(cycle))
                if not advanced:
                    color[node] = 2
                    stack.pop()
        return None

    def break_cycle(self, cycle: List[str]) -> Optional[Tuple[str, str]]:
        if len(cycle) < 2:
            return None
        src, dst = cycle[-2], cycle[-1]
        self.handoffs.get(src, set()).discard(dst)
        return (src, dst)

    # -- rewiring: G_{t+1} = F(G_t, E_t, C_t, F_t, U_t) ---------------------
    def rewire(
        self,
        iteration: int,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> TopologySnapshot:
        cfg = self.config
        lr = cfg.edge_learning_rate
        before = set(self.weights.keys())
        active = sorted(n for n in self.nodes if n in capabilities)

        # 1. update existing edges toward their affinity target
        for a in active:
            for b in active:
                if a >= b:
                    continue
                k = self.key(a, b)
                aff = self._affinity(a, b, capabilities, competence, failure,
                                     uncertainty, evidence)
                if k in self.weights:
                    self.weights[k] += lr * (aff - self.weights[k])

        # 2. grow: top-k complementary pairs not yet connected
        candidates: List[Tuple[float, Tuple[str, str]]] = []
        for a in active:
            for b in active:
                if a >= b:
                    continue
                k = self.key(a, b)
                if k in self.weights:
                    continue
                aff = self._affinity(a, b, capabilities, competence, failure,
                                     uncertainty, evidence)
                candidates.append((aff, k))
        candidates.sort(key=lambda t: (-t[0], t[1]))
        added = 0
        for aff, k in candidates:
            if added >= cfg.topology_add_top_k * max(1, len(active) // 4):
                break
            if aff <= cfg.edge_prune_threshold:
                break
            if self.degree(k[0]) >= cfg.max_degree or self.degree(k[1]) >= cfg.max_degree:
                continue
            self.weights[k] = aff
            added += 1

        # 3. prune weak edges, keeping every node minimally connected
        for k in sorted(list(self.weights.keys())):
            if self.weights[k] < cfg.edge_prune_threshold:
                a, b = k
                if self.degree(a) > 1 and self.degree(b) > 1:
                    del self.weights[k]

        # 4. enforce degree cap
        for node in active:
            nbrs = sorted(self.neighbors(node),
                          key=lambda m: self.weights[self.key(node, m)])
            while len(nbrs) > cfg.max_degree:
                drop = nbrs.pop(0)
                self.weights.pop(self.key(node, drop), None)

        # Derived value-of-information: free energy still recoverable by moving
        # every active pair to its optimum next iteration (EVOI = predicted J descent).
        descent = 0.0
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                g = self._gain(a, b, capabilities, competence, failure,
                               uncertainty, evidence)
                w = self.weights.get(self.key(a, b), 0.0)
                descent += self.fe.edge_descent(w, g)
        self.predicted_descent = self.fe.predicted_descent([], uncertainty) + descent

        after = set(self.weights.keys())
        return TopologySnapshot(
            iteration=iteration,
            n_nodes=len(active),
            n_edges=len(after),
            edges_added=len(after - before),
            edges_removed=len(before - after),
            avg_degree=(2 * len(after) / len(active)) if active else 0.0,
            degree_entropy=self.degree_entropy(),
            modularity=self.modularity(),
            avg_path_length=self.avg_path_length(),
        )

    def _gain(
        self,
        a: str,
        b: str,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> float:
        """Expected epistemic gain ``g_ab`` of the edge (the ``-g w`` term of J)."""
        ca, cb = capabilities.get(a, set()), capabilities.get(b, set())
        union = ca | cb
        complement = len(union - (ca & cb)) / len(union) if union else 0.0
        comp = 0.5 * (competence.get(a, 0.5) + competence.get(b, 0.5))
        fail = 0.5 * (failure.get(a, 0.0) + failure.get(b, 0.0))
        ev = evidence.get(self.key(a, b), 0.0)
        contam = self.contamination.get(self.key(a, b), 0.0)
        return self.fe.edge_gain(complement, comp, ev, fail, uncertainty, contam)

    def _affinity(
        self,
        a: str,
        b: str,
        capabilities: Dict[str, Set[str]],
        competence: Dict[str, float],
        failure: Dict[str, float],
        uncertainty: float,
        evidence: Dict[Tuple[str, str], float],
    ) -> float:
        """Edge target = convex-optimal weight ``w* = clip(g/kappa, 0, 1)``."""
        g = self._gain(a, b, capabilities, competence, failure, uncertainty, evidence)
        return self.fe.optimal_weight(g)

    # -- structural metrics -------------------------------------------------
    def degree_entropy(self) -> float:
        if not self.nodes:
            return 0.0
        degs = [self.degree(n) for n in self.nodes]
        total = sum(degs)
        if total == 0:
            return 0.0
        h = 0.0
        for d in degs:
            if d:
                p = d / total
                h -= p * math.log(p, 2)
        return h

    def communities(self) -> Dict[str, int]:
        """Deterministic label propagation."""
        labels = {n: i for i, n in enumerate(sorted(self.nodes))}
        for _ in range(12):
            changed = False
            for n in sorted(self.nodes):
                nbrs = self.neighbors(n)
                if not nbrs:
                    continue
                tally: Dict[int, float] = {}
                for m in nbrs:
                    w = self.weights.get(self.key(n, m), 0.0)
                    tally[labels[m]] = tally.get(labels[m], 0.0) + w
                if not tally:
                    continue
                best = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                if labels[n] != best:
                    labels[n] = best
                    changed = True
            if not changed:
                break
        return labels

    def modularity(self) -> float:
        m = sum(self.weights.values())
        if m <= 0:
            return 0.0
        labels = self.communities()
        strength: Dict[str, float] = {n: 0.0 for n in self.nodes}
        for (a, b), w in self.weights.items():
            strength[a] = strength.get(a, 0.0) + w
            strength[b] = strength.get(b, 0.0) + w
        q = 0.0
        for (a, b), w in self.weights.items():
            if labels.get(a) == labels.get(b):
                q += (w / m) - (strength[a] * strength[b]) / (2 * m * m)
        return q

    def avg_path_length(self) -> float:
        nodes = sorted(self.nodes)
        if len(nodes) < 2:
            return 0.0
        total, pairs = 0, 0
        for src in nodes:
            dist = {src: 0}
            q = deque([src])
            while q:
                cur = q.popleft()
                for nb in sorted(self.neighbors(cur)):
                    if nb not in dist:
                        dist[nb] = dist[cur] + 1
                        q.append(nb)
            for dst in nodes:
                if dst != src and dst in dist:
                    total += dist[dst]
                    pairs += 1
        return total / pairs if pairs else 0.0

    def edge_churn(self, prev: Set[Tuple[str, str]]) -> float:
        cur = set(self.weights.keys())
        union = prev | cur
        return len(union - (prev & cur)) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
class SovereigntyController:
    """Transfers control to the most competent active agent.

    Hysteresis prevents leadership thrash (which would otherwise register as
    oscillation in the loop guards).
    """

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.current: Optional[str] = None
        self.transfers: List[SovereigntyTransfer] = []

    def competence(self, rt: AgentRuntime, stage: StageSpec) -> float:
        w = self.config.sovereignty_weights
        need = set(stage.required_capabilities)
        match = len(rt.spec.capabilities & need) / len(need) if need else 0.0
        return (
            w["domain_match"] * match
            + w["reputation"] * rt.reputation
            + w["verification_pass"] * rt.verification_pass_rate
            - w["failure_penalty"] * rt.failure_rate
        )

    def evaluate(self, runtimes: Dict[str, AgentRuntime], stage: StageSpec,
                 iteration: int) -> Tuple[Optional[str], Dict[str, float]]:
        from .types import AgentRole
        eligible = {
            a: r for a, r in runtimes.items()
            if r.alive and r.spec.role in (AgentRole.SPECIALIST, AgentRole.MICRO)
        }
        scores = {a: self.competence(r, stage) for a, r in eligible.items()}
        if not scores:
            return self.current, scores
        best = max(sorted(scores), key=lambda a: scores[a])
        if self.current is None or self.current not in eligible:
            prev, prev_c = self.current, scores.get(self.current or "", 0.0)
            self.current = best
            self.transfers.append(
                SovereigntyTransfer(iteration, prev, best, prev_c, scores[best])
            )
        elif scores[best] > scores[self.current] * (1.0 + self.config.sovereignty_hysteresis):
            prev, prev_c = self.current, scores[self.current]
            self.current = best
            self.transfers.append(
                SovereigntyTransfer(iteration, prev, best, prev_c, scores[best])
            )
        return self.current, scores
```


<a id="mosaicomegaroutingpy"></a>

### `mosaic_omega/routing.py`

Reputation-weighted routing over Beta posteriors, with oracle-regret logging.

```python
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
```


<a id="mosaicomegaadjudicationpy"></a>

### `mosaic_omega/adjudication.py`

Falsification engine, contradiction scanner, minority preserver, and the blinded jury with Fleiss' kappa.

```python
"""Falsification, contradiction scanning, minority preservation, blinded jury."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .agents import BaseAgent, ContradictionAgent, FalsifierAgent, JurorAgent, MinorityPreservationAgent
from .config import MosaicConfig
from .governance import BlindingFilter, BlindingPolicy
from .rng import stable_shuffle, stable_sig
from .types import (
    Candidate,
    Claim,
    Contradiction,
    FalsificationReport,
    JurorBallot,
    JuryVerdict,
)


# ---------------------------------------------------------------------------
class FalsificationEngine:
    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    def run(self, candidate: Candidate, falsifiers: Sequence[FalsifierAgent],
            nonce: str) -> FalsificationReport:
        merged = FalsificationReport(candidate_id=candidate.candidate_id)
        for f in falsifiers:
            out = f.act({
                "candidate": candidate,
                "attacks": self.config.attacks_per_falsifier,
                "nonce": f"{nonce}:{f.agent_id}",
            })
            rep: FalsificationReport = out.payload["report"]
            merged.attacks.extend(rep.attacks)
        candidate.falsification_survival = merged.survival
        for atk in merged.attacks:
            if atk.succeeded:
                for claim in candidate.claims:
                    if claim.constraint_id == atk.constraint_id:
                        claim.falsified = True
        return merged


# ---------------------------------------------------------------------------
class ContradictionScanner:
    def run(self, agent: ContradictionAgent, claims: List[Claim],
            commitments: Dict[str, str]) -> List[Contradiction]:
        out = agent.act({"claims": claims, "commitments": commitments})
        return out.payload["contradictions"]

    @staticmethod
    def density(contradictions: Sequence[Contradiction], n_scanned: int) -> float:
        """Contradictions per scanned claim pair, clamped to [0,1]."""
        pairs = n_scanned * (n_scanned - 1) / 2
        return min(1.0, len(contradictions) / pairs) if pairs > 0 else 0.0


# ---------------------------------------------------------------------------
@dataclass
class ConsensusState:
    entropy: float
    majority_share: float
    clusters: Dict[str, List[str]]           # signature -> candidate ids
    majority_sig: Optional[str]
    minority_sig: Optional[str]
    premature: bool


class MinorityPreserver:
    """Prevents premature consensus.

    If candidate-space entropy collapses before evidence is sufficient, the
    top minority cluster is protected and handed to an advocate agent.
    """

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config

    def analyse(self, candidates: Sequence[Candidate],
                evidence_sufficiency: float) -> ConsensusState:
        clusters: Dict[str, List[str]] = {}
        for c in candidates:
            clusters.setdefault(c.signature(), []).append(c.candidate_id)
        total = sum(len(v) for v in clusters.values())
        entropy = 0.0
        if total > 0 and len(clusters) > 1:
            for ids in clusters.values():
                p = len(ids) / total
                entropy -= p * math.log(p, 2)
            entropy /= math.log(len(clusters), 2)
        ordered = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        majority = ordered[0][0] if ordered else None
        minority = ordered[-1][0] if len(ordered) > 1 else None
        share = len(ordered[0][1]) / total if ordered and total else 0.0
        # Consensus is "premature" when the field has narrowed to a dominant
        # cluster while the evidence base is still thin, or when entropy has
        # collapsed outright. Either way a dissenting branch is protected.
        premature = (
            len(clusters) > 1
            and evidence_sufficiency < self.config.evidence_sufficiency_floor
            and (share >= self.config.consensus_share_ceiling
                 or entropy < self.config.minority_entropy_floor)
        )
        return ConsensusState(entropy, share, clusters, majority, minority, premature)

    def preserve(self, state: ConsensusState, candidates: Sequence[Candidate],
                 advocate: Optional[MinorityPreservationAgent]) -> Optional[Candidate]:
        if not state.premature or state.minority_sig is None:
            return None
        pool = [c for c in candidates if c.signature() == state.minority_sig]
        if not pool:
            return None
        champion = max(pool, key=lambda c: (c.verified_score, c.candidate_id))
        champion.is_minority = True
        if advocate is not None:
            advocate.act({"minority_candidate": champion})
        return champion


# ---------------------------------------------------------------------------
class BlindedJury:
    """Anonymises, shuffles and adjudicates competing candidates."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.blinder = BlindingFilter(BlindingPolicy(level=config.blinding_level))

    def _blind(self, candidates: Sequence[Candidate], nonce: str
               ) -> Tuple[List[Dict[str, Any]], Dict[str, str], int, int]:
        shuffled = stable_shuffle(candidates, "jury", nonce)
        alias_to_id: Dict[str, str] = {}
        packets: List[Dict[str, Any]] = []
        leaks = checks = 0
        for i, c in enumerate(shuffled):
            alias = f"CAND-{i}"
            alias_to_id[alias] = c.candidate_id
            verified = [cl for cl in c.claims if cl.verified is not None]
            verified_ratio = (
                sum(1 for cl in verified if cl.verified) / len(verified)
                if verified else 0.0
            )
            mean_conf = (
                sum(cl.confidence for cl in c.claims) / len(c.claims)
                if c.claims else 0.5
            )
            raw = {
                "alias": alias,
                "verified_ratio": verified_ratio,
                "survival": c.falsification_survival,
                "mean_confidence": mean_conf,
                "contradiction_density": c.contradiction_penalty,
                # blinded surfaces:
                "peer_authors": list(c.authors),
                "author": c.authors[0] if c.authors else "",
                "peer_scores": [c.raw_score, c.jury_score],
                "universe_leaderboard": c.universe,
            }
            packet, report = self.blinder.apply(raw)
            checks += 1
            leaks += int(report.leaked)
            packet["alias"] = alias
            packets.append(packet)
        return packets, alias_to_id, leaks, checks

    def adjudicate(self, candidates: Sequence[Candidate],
                   jurors: Sequence[JurorAgent], nonce: str
                   ) -> Tuple[JuryVerdict, int, int]:
        if not candidates:
            return JuryVerdict(winner_id=None), 0, 0
        packets, alias_to_id, leaks, checks = self._blind(candidates, nonce)
        ballots: List[JurorBallot] = []
        for j in jurors:
            out = j.act({"blinded_candidates": packets, "nonce": nonce})
            ballots.append(out.payload["ballot"])

        weight_sum = sum(max(0.05, b.reputation) for b in ballots) or 1.0
        aggregate: Dict[str, float] = {}
        for packet in packets:
            alias = packet["alias"]
            agg = sum(max(0.05, b.reputation) * b.scores.get(alias, 0.0) for b in ballots)
            aggregate[alias_to_id[alias]] = agg / weight_sum

        ordered = sorted(aggregate.items(), key=lambda kv: (-kv[1], kv[0]))
        winner = ordered[0][0] if ordered else None
        margin = (ordered[0][1] - ordered[1][1]) if len(ordered) > 1 else 1.0
        kappa = self.fleiss_kappa([b.top_choice for b in ballots],
                                  [p["alias"] for p in packets])
        for c in candidates:
            c.jury_score = aggregate.get(c.candidate_id, 0.0)
        verdict = JuryVerdict(
            winner_id=winner,
            ballots=ballots,
            aggregate=aggregate,
            margin=margin,
            agreement_kappa=kappa,
            blinded=self.config.blinding_level != "none",
        )
        return verdict, leaks, checks

    @staticmethod
    def fleiss_kappa(votes: Sequence[str], categories: Sequence[str]) -> float:
        """Single-item Fleiss' kappa over top-choice votes.

        With one item, kappa reduces to (P_observed - P_expected)/(1 - P_expected)
        where P_observed is the pairwise agreement rate among raters.
        """
        n = len(votes)
        k = len(categories)
        if n < 2 or k < 2:
            return 0.0
        counts = {c: 0 for c in categories}
        for v in votes:
            if v in counts:
                counts[v] += 1
        p_obs = (sum(c * c for c in counts.values()) - n) / (n * (n - 1))
        p_exp = sum((c / n) ** 2 for c in counts.values())
        if p_exp >= 1.0:
            return 1.0
        return (p_obs - p_exp) / (1.0 - p_exp)
```


<a id="mosaicomegauniversespy"></a>

### `mosaic_omega/universes.py`

Parallel agent universes with measured isolation purity.

```python
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
```


<a id="mosaicomegafailsafepy"></a>

### `mosaic_omega/failsafe.py`

Budgets, idempotency, the content-addressed checkpoint chain with binary-search corruption find, loop guards, and the recovery ladder.

```python
"""Fail-safe loop engineering: budgets, checkpoints, guards, recovery."""
from __future__ import annotations

import json
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Set, Tuple

from .config import MosaicConfig
from .rng import stable_sig
from .types import Checkpoint, FailureClass, Phase, RecoveryRecord


# ---------------------------------------------------------------------------
class BudgetExhausted(Exception):
    pass


class BudgetManager:
    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.tokens_used = 0
        self.tool_calls_used = 0
        self.started = time.perf_counter()
        self.overruns: List[str] = []

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def consume(self, tokens: int = 0, tool_calls: int = 0) -> None:
        self.tokens_used += tokens
        self.tool_calls_used += tool_calls

    def fraction_left(self) -> float:
        f_tok = 1.0 - self.tokens_used / max(1, self.config.token_budget)
        f_tool = 1.0 - self.tool_calls_used / max(1, self.config.tool_call_budget)
        f_time = 1.0 - self.elapsed() / max(1e-9, self.config.wall_clock_budget_s)
        return max(0.0, min(f_tok, f_tool, f_time))

    def check(self) -> Optional[str]:
        if self.tokens_used >= self.config.token_budget:
            return "token_budget"
        if self.tool_calls_used >= self.config.tool_call_budget:
            return "tool_call_budget"
        if self.elapsed() >= self.config.wall_clock_budget_s:
            return "wall_clock_budget"
        return None

    def record_overrun(self, what: str) -> None:
        self.overruns.append(what)


# ---------------------------------------------------------------------------
class IdempotencyLedger:
    """Prevents duplicate side effects on replay/rollback."""

    def __init__(self) -> None:
        self.executed: Dict[str, Any] = {}
        self.hits = 0
        self.duplicates_prevented = 0

    @staticmethod
    def key(agent: str, tool: str, args: Any, checkpoint_id: Optional[str]) -> str:
        return stable_sig("action", agent, tool, json.dumps(args, sort_keys=True,
                                                            default=str), checkpoint_id)

    def run_once(self, key: str, fn: Callable[[], Any]) -> Any:
        if key in self.executed:
            self.hits += 1
            self.duplicates_prevented += 1
            return self.executed[key]
        result = fn()
        self.executed[key] = result
        return result


# ---------------------------------------------------------------------------
class CheckpointStore:
    """Content-addressed checkpoint chain with rollback to earliest corruption."""

    def __init__(self) -> None:
        self.chain: List[Checkpoint] = []
        self.by_id: Dict[str, Checkpoint] = {}

    @property
    def head(self) -> Optional[Checkpoint]:
        return self.chain[-1] if self.chain else None

    def commit(self, iteration: int, phase: Phase, state: Dict[str, Any],
               branch: str = "root") -> Checkpoint:
        blob = json.dumps(state, sort_keys=True, default=str)
        parent = self.head.checkpoint_id if self.head else None
        cp = Checkpoint(
            checkpoint_id=stable_sig("cp", branch, iteration, phase.value, blob, len(self.chain)),
            parent_id=parent,
            iteration=iteration,
            phase=phase,
            state_blob=blob,
            integrity_hash=stable_sig(blob),
            branch=branch,
        )
        self.chain.append(cp)
        self.by_id[cp.checkpoint_id] = cp
        return cp

    def verify_integrity(self, cp: Checkpoint) -> bool:
        return stable_sig(cp.state_blob) == cp.integrity_hash

    def find_earliest_corrupted(
        self, validator: Callable[[Dict[str, Any]], bool]
    ) -> Optional[Checkpoint]:
        """Binary search along the chain for the first checkpoint that fails
        the invariant (the chain is assumed monotone: once broken, stays broken)."""
        if not self.chain:
            return None
        lo, hi, found = 0, len(self.chain) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            cp = self.chain[mid]
            ok = self.verify_integrity(cp) and validator(json.loads(cp.state_blob))
            if ok:
                lo = mid + 1
            else:
                found = cp
                hi = mid - 1
        return found

    def rollback_to(self, checkpoint_id: str) -> Dict[str, Any]:
        cp = self.by_id.get(checkpoint_id)
        if cp is None:
            raise KeyError(f"unknown checkpoint {checkpoint_id}")
        idx = self.chain.index(cp)
        for dropped in self.chain[idx + 1:]:
            dropped.corrupted = True
        self.chain = self.chain[: idx + 1]
        return json.loads(cp.state_blob)

    def last_good_before(self, cp: Checkpoint) -> Optional[Checkpoint]:
        idx = self.chain.index(cp) if cp in self.chain else len(self.chain)
        return self.chain[idx - 1] if idx > 0 else None


# ---------------------------------------------------------------------------
@dataclass
class GuardTrip:
    guard: str
    iteration: int
    detail: str


class LoopGuards:
    """Duplicate-loop, oscillation, stagnation and deadlock detection."""

    def __init__(self, config: MosaicConfig) -> None:
        self.config = config
        self.signatures: List[str] = []
        self.signature_counts: Counter = Counter()
        self.scores: List[float] = []
        self.trips: List[GuardTrip] = []

    def observe(self, signature: str, score: float, iteration: int) -> None:
        self.signatures.append(signature)
        self.signature_counts[signature] += 1
        self.scores.append(score)

    # -- duplicate loop -----------------------------------------------------
    def duplicate_loop(self, iteration: int) -> Optional[GuardTrip]:
        if not self.signatures:
            return None
        sig = self.signatures[-1]
        if self.signature_counts[sig] >= self.config.duplicate_loop_k:
            trip = GuardTrip("duplicate_loop", iteration,
                             f"signature {sig} seen {self.signature_counts[sig]}x")
            self.trips.append(trip)
            return trip
        return None

    # -- oscillation --------------------------------------------------------
    def oscillation(self, iteration: int) -> Optional[GuardTrip]:
        w = self.signatures[-self.config.oscillation_window:]
        for period in range(self.config.oscillation_min_period,
                            self.config.oscillation_max_period + 1):
            need = period * (self.config.oscillation_min_repeats + 1)
            if len(w) < need:
                continue
            tail = w[-need:]
            block = tail[:period]
            if len(set(block)) < 2:
                continue
            if all(tail[i] == block[i % period] for i in range(need)):
                trip = GuardTrip("oscillation", iteration,
                                 f"period-{period} cycle over {need} steps")
                self.trips.append(trip)
                return trip
        return None

    # -- stagnation ---------------------------------------------------------
    def stagnation(self, iteration: int) -> Optional[GuardTrip]:
        w = self.config.stagnation_window
        if len(self.scores) < w + 1:
            return None
        recent = self.scores[-(w + 1):]
        gain = max(recent[1:]) - recent[0]
        if gain < self.config.stagnation_epsilon:
            trip = GuardTrip("stagnation", iteration,
                             f"gain {gain:.4f} < eps over {w} iterations")
            self.trips.append(trip)
            return trip
        return None

    # -- deadlock -----------------------------------------------------------
    def deadlock(self, iteration: int, blocked: Sequence[str],
                 active: Sequence[str]) -> Optional[GuardTrip]:
        if active and set(blocked) >= set(active):
            trip = GuardTrip("deadlock", iteration,
                             f"all {len(active)} active agents blocked")
            self.trips.append(trip)
            return trip
        return None


# ---------------------------------------------------------------------------
class RecoveryManager:
    """Contain -> rollback -> replay alternative branch -> escalate."""

    def __init__(self, config: MosaicConfig, store: CheckpointStore) -> None:
        self.config = config
        self.store = store
        self.records: List[RecoveryRecord] = []
        self.consecutive_failures = 0
        self.branch_counter = 0

    def new_branch(self) -> str:
        self.branch_counter += 1
        return f"branch-{self.branch_counter:02d}"

    def handle(
        self,
        iteration: int,
        failure_class: FailureClass,
        detail: str,
        validator: Callable[[Dict[str, Any]], bool],
        restore: Callable[[Dict[str, Any]], None],
    ) -> RecoveryRecord:
        self.consecutive_failures += 1
        attempts = self.consecutive_failures
        escalated = attempts > self.config.max_recovery_attempts
        rolled_to: Optional[str] = None
        contained = False

        if not escalated:
            corrupted = self.store.find_earliest_corrupted(validator)
            target = self.store.last_good_before(corrupted) if corrupted else self.store.head
            if target is not None:
                state = self.store.rollback_to(target.checkpoint_id)
                restore(state)
                rolled_to = target.checkpoint_id
                contained = True

        record = RecoveryRecord(
            iteration=iteration,
            failure_class=failure_class,
            detail=detail,
            rolled_back_to=rolled_to,
            attempts=attempts,
            contained=contained,
            escalated=escalated,
        )
        self.records.append(record)
        return record

    def mark_recovered(self, iteration: int) -> None:
        for rec in reversed(self.records):
            if rec.recovered_at_iteration is None:
                rec.recovered_at_iteration = iteration
                break
        self.consecutive_failures = 0
```


<a id="mosaicomegalooppy"></a>

### `mosaic_omega/loop.py`

The eleven phases, one method each, with chaos hooks and per-agent exception containment.

```python
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
```


<a id="mosaicomegametricspy"></a>

### `mosaic_omega/metrics.py`

Nine metric groups and their statistical primitives. Returns `None` rather than a placeholder when a metric is not computable.

```python
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
```


<a id="mosaicomegaorchestratorpy"></a>

### `mosaic_omega/orchestrator.py`

Top-level `solve()`, severity-ordered termination aggregation, and final answer assembly from commitment memory.

```python
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
```


<a id="mosaicomegabenchmarkpy"></a>

### `mosaic_omega/benchmark.py`

Multi-seed harness, seven ablation variants, and the comparison table renderer.

```python
"""Multi-seed benchmark harness.

Runs MOSAIC-Omega across seeds (and optionally across ablations) and aggregates
every numeric metric with mean / std / min / max, so architecture changes can be
compared against a fixed protocol rather than a single lucky run.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .config import MosaicConfig
from .orchestrator import MosaicOmega, RunResult
from .problem import Problem, SyntheticConstraintProblem


def fmt_number(value: Optional[float]) -> str:
    """Compact fixed-width-friendly rendering: big numbers lose decimals."""
    if value is None:
        return "n/a"
    a = abs(value)
    if a >= 10000:
        return f"{value:,.0f}"
    if a >= 100:
        return f"{value:.2f}"
    return f"{value:.4f}"


@dataclass
class BenchmarkResult:
    label: str
    runs: List[RunResult] = field(default_factory=list)
    aggregate: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def table(self, keys: Optional[Sequence[str]] = None) -> str:
        keys = [k for k in (keys or sorted(self.aggregate)) if k in self.aggregate]
        width = max((len(k) for k in keys), default=10) + 2
        cells = {
            k: [fmt_number(self.aggregate[k][f]) for f in ("mean", "std", "min", "max")]
            for k in keys
        }
        num_w = max([len(c) for row in cells.values() for c in row] + [6]) + 2
        head = "".join(h.rjust(num_w) for h in ("mean", "std", "min", "max"))
        lines = [f"{'metric'.ljust(width)}{head}"]
        for k in keys:
            lines.append(k.ljust(width) + "".join(c.rjust(num_w) for c in cells[k]))
        return "\n".join(lines)


class Benchmark:
    def __init__(self, seeds: Sequence[int] = (1, 2, 3, 4, 5),
                 problem_factory: Optional[Callable[[int], Problem]] = None) -> None:
        self.seeds = list(seeds)
        self.problem_factory = problem_factory or (
            lambda seed: SyntheticConstraintProblem(seed=seed)
        )

    def run(self, config: Optional[MosaicConfig] = None,
            label: str = "default") -> BenchmarkResult:
        base = config or MosaicConfig()
        result = BenchmarkResult(label=label)
        for seed in self.seeds:
            cfg = MosaicConfig(**{**base.to_dict(),
                                  "seed": seed,
                                  "universe_strategies": base.universe_strategies})
            problem = self.problem_factory(seed)
            result.runs.append(MosaicOmega(cfg).solve(problem))
        result.aggregate = self._aggregate(result.runs)
        return result

    def compare(self, variants: Dict[str, MosaicConfig]) -> Dict[str, BenchmarkResult]:
        return {name: self.run(cfg, label=name) for name, cfg in variants.items()}

    @staticmethod
    def _aggregate(runs: Sequence[RunResult]) -> Dict[str, Dict[str, float]]:
        buckets: Dict[str, List[float]] = {}
        for r in runs:
            for group, values in r.metrics.items():
                for key, value in values.items():
                    if isinstance(value, bool):
                        value = float(value)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        if value is None or (isinstance(value, float) and math.isnan(value)):
                            continue
                        buckets.setdefault(f"{group}.{key}", []).append(float(value))
        out: Dict[str, Dict[str, float]] = {}
        for key, vals in buckets.items():
            out[key] = {
                "mean": statistics.fmean(vals),
                "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                "min": min(vals),
                "max": max(vals),
                "n": float(len(vals)),
            }
        return out


ABLATIONS: Dict[str, Dict[str, Any]] = {
    "full": {},
    "no_blinding": {"blinding_level": "none"},
    "single_universe": {"n_universes": 1},
    "no_falsification": {"falsifiers_per_candidate": 0, "attacks_per_falsifier": 0},
    "no_pruning": {"prune_utility_threshold": -1.0, "redundancy_jaccard": 2.0},
    "small_jury": {"n_jurors": 1},
    "chaos_25": {"chaos_agent_failure_rate": 0.25, "chaos_branch_corruption_rate": 0.25},
}


def comparison_table(results: Dict[str, "BenchmarkResult"],
                     keys: Sequence[str],
                     baseline: str = "full") -> str:
    """Render variants side by side (means), with delta against the baseline."""
    names = [n for n in results if n != baseline]
    names = ([baseline] if baseline in results else []) + names
    label_w = max((len(k) for k in keys), default=10) + 2
    col_w = max([len(n) for n in names] + [10]) + 2

    def cell(name: str, key: str) -> str:
        agg = results[name].aggregate.get(key)
        if not agg:
            return "n/a"
        text = fmt_number(agg["mean"])
        base = results.get(baseline)
        if base is not None and name != baseline:
            b = base.aggregate.get(key)
            if b:
                d = agg["mean"] - b["mean"]
                if abs(d) >= 1e-9:
                    text += f" ({'+' if d > 0 else ''}{fmt_number(d)})"
        return text

    rows = {k: [cell(n, k) for n in names] for k in keys}
    col_w = max([col_w] + [len(c) + 2 for row in rows.values() for c in row])
    lines = ["metric".ljust(label_w) + "".join(n.rjust(col_w) for n in names)]
    lines.append("-" * (label_w + col_w * len(names)))
    for k in keys:
        lines.append(k.ljust(label_w) + "".join(c.rjust(col_w) for c in rows[k]))
    return "\n".join(lines)


def ablation_suite(seeds: Sequence[int] = (1, 2, 3),
                   base: Optional[MosaicConfig] = None) -> Dict[str, BenchmarkResult]:
    base = base or MosaicConfig(max_iterations=6)
    variants: Dict[str, MosaicConfig] = {}
    for name, overrides in ABLATIONS.items():
        d = base.to_dict()
        d.update(overrides)
        d["universe_strategies"] = base.universe_strategies
        variants[name] = MosaicConfig(**d)
    return Benchmark(seeds).compare(variants)
```


<a id="mosaicomegaclipy"></a>

### `mosaic_omega/cli.py`

`python -m mosaic_omega.cli` entry point.

```python
"""Command-line entry point:  python -m mosaic_omega.cli --help"""
from __future__ import annotations

import argparse
import json
import sys

from .config import MosaicConfig
from .metrics import MetricsEngine
from .orchestrator import MosaicOmega
from .problem import SyntheticConstraintProblem


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mosaic-omega",
                                description="Run the MOSAIC-Omega agentic architecture.")
    p.add_argument("--seed", type=int, default=20260807)
    p.add_argument("--stages", type=int, default=3)
    p.add_argument("--constraints", type=int, default=5, help="constraints per stage")
    p.add_argument("--universes", type=int, default=3)
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--jurors", type=int, default=5)
    p.add_argument("--blinding", choices=["strict", "partial", "none"], default="strict")
    p.add_argument("--chaos-agent", type=float, default=0.0,
                   help="probability an agent call is faulted (reliability testing)")
    p.add_argument("--chaos-branch", type=float, default=0.0,
                   help="probability a branch invariant is corrupted")
    p.add_argument("--json", action="store_true", help="emit metrics as JSON")
    p.add_argument("--report", action="store_true", help="print the markdown report")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = MosaicConfig(
        seed=args.seed,
        n_universes=args.universes,
        max_iterations=args.max_iterations,
        n_jurors=args.jurors,
        blinding_level=args.blinding,
        chaos_agent_failure_rate=args.chaos_agent,
        chaos_branch_corruption_rate=args.chaos_branch,
    )
    problem = SyntheticConstraintProblem(
        n_stages=args.stages, constraints_per_stage=args.constraints, seed=args.seed
    )
    result = MosaicOmega(cfg).solve(problem)
    engine = MetricsEngine(result.trace, problem)

    print(result.summary())
    if result.unresolved_constraints:
        print(f"explicitly unresolved: {result.unresolved_constraints}")
    if args.json:
        print(json.dumps(engine.compute(), indent=2, default=str))
    elif args.report:
        print()
        print(engine.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```


<a id="testsinitpy"></a>

### `tests/__init__.py`

Empty — makes `tests` a package.

```python

```


<a id="teststestmosaicomegapy"></a>

### `tests/test_mosaic_omega.py`

24 tests with a standalone runner; pytest optional.

```python
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
```


<a id="rundemopy"></a>

### `analysis/run_demo.py`

Single run, full metric report, ablation suite, comparison table.
Run it as `python analysis/run_demo.py` from the repository root.

```python
#!/usr/bin/env python3
"""MOSAIC-Omega demo: single run + full metric report + ablation benchmark."""
from __future__ import annotations

import sys

import _paths  # noqa: F401  -- puts the repository root on sys.path

from mosaic_omega import MetricsEngine, MosaicConfig, MosaicOmega, SyntheticConstraintProblem
from mosaic_omega.benchmark import ablation_suite, comparison_table

HEADLINE = [
    "outcome.ground_truth_accuracy",
    "outcome.final_composite_score",
    "outcome.score_truth_gap",
    "outcome.iterations",
    "reasoning.mean_falsification_survival",
    "consensus.mean_jury_kappa",
    "efficiency.tokens_used",
    "efficiency.producer_utilisation",
    "reliability.contract_compliance_rate",
    "reliability.containment_ratio",
    "routing.oracle_match_rate",
    "routing.confidence_ece",
    "structure.mean_modularity",
    "safety.blinding_leak_rate",
    "safety.anchoring_index",
    "safety.branch_isolation_purity",
    "consensus.premature_consensus_index",
    "control.evoi_calibration_r",
]


def main() -> int:
    print("=" * 74)
    print("MOSAIC-Omega -- single run")
    print("=" * 74)
    problem = SyntheticConstraintProblem(n_stages=3, constraints_per_stage=5)
    result = MosaicOmega(MosaicConfig()).solve(problem)
    print(result.summary())
    if result.unresolved_constraints:
        print(f"explicitly unresolved: {result.unresolved_constraints}")
    print()
    print(MetricsEngine(result.trace, problem).report())

    print("=" * 74)
    print("Ablation benchmark (3 seeds per variant)")
    print("=" * 74)
    suite = ablation_suite(seeds=(1, 2, 3))
    for name, bench in suite.items():
        print(f"\n--- {name} ---")
        print(bench.table(HEADLINE))

    print()
    print("=" * 74)
    print("Ablation comparison (means, delta vs `full`)")
    print("=" * 74)
    print(comparison_table(suite, HEADLINE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```


<a id="requirementstxt"></a>

### `requirements.txt`

Dependencies of the `analysis/` single-cell pipeline. The core `mosaic_omega`
package needs **none** of these — it is standard-library-only, which is why
`python tests/test_mosaic_omega.py` and `python -m mosaic_omega.cli --report` run
on a bare interpreter.

```text
# Core mosaic_omega package: pure standard library, no dependencies.
# The single-cell analysis scripts in analysis/ require:
numpy
pandas
scipy
scikit-learn
scanpy
anndata
leidenalg
igraph
umap-learn
matplotlib
networkx
h5py
requests
```
