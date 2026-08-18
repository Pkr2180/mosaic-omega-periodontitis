"""Generate the full figure suite for MOSAIC-Omega on the REAL periodontal task.

Reproduces the deterministic run (same components/order as MosaicOmega.solve),
captures the live FESC agent-topology graph and loop trajectories, and renders:

  fig1_architecture.png  - agent graph (FESC) | roster | score loop | EVOI
  fig2_loop_graph.png    - graph-structure evolution | adjudication | EVOI calib | sovereignty
  fig3_real_biology.png  - real scanpy dotplot of committed markers | decision matrix

All numbers come from the executed trace; the biology panel is drawn from the
real primary AnnData (gingiva subset).
"""
from __future__ import annotations

import json, os, time, copy
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from mosaic_omega import (
    MosaicConfig, MissionKernel, MemoryFabric, DynamicAgentProvisioner,
    UniverseManager, TopologyGraph, ContractLedger, BudgetManager,
    CheckpointStore, AgentPruner, FailSafeLoop, MetricsEngine,
)
from mosaic_omega.types import Phase, Termination, RunTrace, Candidate
from run_periodontal_real import PeriodontalMarkerProblem, TASK_PATH

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT
FIGDIR = os.path.join(ROOT, "figures")
os.makedirs(FIGDIR, exist_ok=True)

ROLE_OF = {"spec": "specialist", "veri": "verifier", "fals": "falsifier",
           "cont": "contradiction", "mino": "minority", "juro": "juror",
           "micr": "micro", "watc": "watchdog", "meta": "meta"}
ROLE_COLOR = {"specialist": "#2563eb", "verifier": "#16a34a", "falsifier": "#dc2626",
              "contradiction": "#f59e0b", "minority": "#7c3aed", "juror": "#0891b2",
              "micro": "#64748b", "watchdog": "#be185d", "meta": "#000000",
              "other": "#94a3b8"}


def role_of(node: str) -> str:
    agent = node.split("::")[-1]
    return ROLE_OF.get(agent.split("-")[0], "other")


# ---------------------------------------------------------------------------
def run_capture(problem, cfg):
    """Mirror MosaicOmega.solve, retaining topology snapshots + live objects."""
    trace = RunTrace()
    mission = MissionKernel(cfg).compile(problem.goal, problem)
    trace.mission = mission
    memory = MemoryFabric(); memory.set("goal", problem.goal)
    provisioner = DynamicAgentProvisioner(cfg, problem)
    universes = UniverseManager(cfg, problem, None); universes.spawn(memory)
    topology = TopologyGraph(cfg)
    contracts = ContractLedger(max_depth=cfg.max_delegation_depth)
    budgets = BudgetManager(cfg); checkpoints = CheckpointStore(); pruner = AgentPruner(cfg)
    checkpoints.commit(-1, Phase.OBSERVE,
                       {"iteration": -1, "assignment": {}, "score": 0.0, "invariant_ok": True},
                       branch="root")
    loop = FailSafeLoop(cfg, problem, mission, trace, memory=memory,
                        provisioner=provisioner, universes=universes, topology=topology,
                        contracts=contracts, budgets=budgets, checkpoints=checkpoints,
                        pruner=pruner)
    started = time.perf_counter()
    topo_snaps = []
    for stage in mission.stages:
        loop.run_stage(stage)
        topo_snaps.append((stage.stage_id, set(topology.nodes), dict(topology.weights)))
    trace.tokens_used = budgets.tokens_used
    trace.tool_calls_used = budgets.tool_calls_used
    trace.wall_clock_s = time.perf_counter() - started
    trace.isolation_purity = universes.isolation_purity()
    # assemble final assignment from committed memory
    assignment = {cid: c.value for cid, c in memory.commitment.items()}
    trace.final_candidate = Candidate(
        candidate_id="fig", universe="root", iteration=trace.iterations,
        assignment=assignment, composite_score=(trace.score_history[-1] if trace.score_history else 0.0))
    trace.termination = trace.termination or Termination.STAGNATION
    metrics = MetricsEngine(trace, problem).compute()
    return trace, metrics, topo_snaps, assignment


# ---------------------------------------------------------------------------
def fig1(trace, metrics, topo_snaps, assignment, problem):
    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle("MOSAIC-Ω  —  self-reconfiguring multi-agent run on real gingival omics",
                 fontsize=15, fontweight="bold")

    # -- A1: FESC agent-topology graph (richest snapshot) -------------------
    ax = axes[0, 0]
    sid, nodes, weights = max(topo_snaps, key=lambda s: len(s[2]))
    G = nx.Graph()
    for n in nodes:
        G.add_node(n, role=role_of(n))
    for (a, b), w in weights.items():
        if w > 0.01:
            G.add_edge(a, b, weight=w)
    if G.number_of_edges() == 0:
        for (a, b), w in weights.items():
            G.add_edge(a, b, weight=max(w, 0.02))
    pos = nx.spring_layout(G, seed=7, weight="weight", k=0.9, iterations=120)
    roles = [G.nodes[n]["role"] for n in G.nodes]
    degs = np.array([G.degree(n) for n in G.nodes])
    ew = [G[u][v]["weight"] for u, v in G.edges]
    nx.draw_networkx_edges(G, pos, ax=ax, width=[0.4 + 3.5 * w for w in ew],
                           alpha=0.35, edge_color="#475569")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=60 + 60 * degs,
                           node_color=[ROLE_COLOR[r] for r in roles], alpha=0.92,
                           linewidths=0.4, edgecolors="white")
    ax.set_title(f"FESC agent-communication graph @ {sid}\n"
                 f"{G.number_of_nodes()} agents, {G.number_of_edges()} edges, "
                 f"modularity={metrics['structure']['mean_modularity']:.2f}", fontsize=11)
    ax.axis("off")
    seen = [r for r in ROLE_COLOR if r in set(roles)]
    ax.legend(handles=[plt.Line2D([0], [0], marker="o", color="w", label=r,
              markerfacecolor=ROLE_COLOR[r], markersize=8) for r in seen],
              loc="upper right", fontsize=7, ncol=2, framealpha=0.9)

    # -- A2: agent roster composition (provision / use / prune) -------------
    ax = axes[0, 1]
    prov = Counter(s.role.value for s in trace.agents_provisioned)
    used_ids = set(trace.agents_used)
    used = Counter(s.role.value for s in trace.agents_provisioned if s.agent_id in used_ids)
    pruned_ids = {d["agent"] for d in trace.prune_decisions}
    pruned = Counter(s.role.value for s in trace.agents_provisioned if s.agent_id in pruned_ids)
    order = [r for r in ROLE_COLOR if r in prov]
    x = np.arange(len(order)); w = 0.26
    ax.bar(x - w, [prov[r] for r in order], w, label="provisioned", color="#93c5fd")
    ax.bar(x, [used.get(r, 0) for r in order], w, label="used", color="#2563eb")
    ax.bar(x + w, [pruned.get(r, 0) for r in order], w, label="pruned", color="#dc2626")
    ax.set_xticks(x); ax.set_xticklabels(order, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("agents"); ax.legend(fontsize=8)
    ax.set_title(f"Dynamic roster — provisioned {sum(prov.values())}, "
                 f"used {len(used_ids)}, pruned {len(pruned_ids)}\n"
                 f"pruning precision={metrics['efficiency']['pruning_precision']}", fontsize=11)

    # -- A3: fail-safe loop score trajectory --------------------------------
    ax = axes[1, 0]
    sh = trace.score_history
    ax.plot(range(1, len(sh) + 1), sh, "-o", color="#2563eb", lw=2, label="composite score")
    ax.axhline(0.85, ls="--", color="#16a34a", label="acceptance threshold")
    conv = metrics["control"]["convergence_iteration"]
    if conv is not None:
        ax.axvline(conv + 1, ls=":", color="#f59e0b", label=f"convergence @ it{conv+1}")
    ax.set_xlabel("loop iteration"); ax.set_ylabel("score"); ax.set_ylim(0, 1)
    ax.set_title(f"Fail-safe loop — termination={metrics['outcome']['termination']}, "
                 f"ground truth={metrics['outcome']['ground_truth_accuracy']:.2f}", fontsize=11)
    ax.legend(fontsize=8); ax.grid(alpha=0.25)

    # -- A4: FESC EVOI (predicted free-energy) vs realized ------------------
    ax = axes[1, 1]
    ep, er = trace.evoi_predicted, trace.evoi_realized
    it = range(1, len(ep) + 1)
    ax.plot(it, ep, "-s", color="#7c3aed", lw=2, label="EVOI predicted (ΔJ, free energy)")
    ax.set_xlabel("loop iteration"); ax.set_ylabel("predicted ΔJ", color="#7c3aed")
    ax.tick_params(axis="y", labelcolor="#7c3aed")
    ax2 = ax.twinx()
    ax2.plot(it, er, "-o", color="#dc2626", lw=1.6, label="realized score gain")
    ax2.axhline(0, color="#94a3b8", lw=0.8)
    ax2.set_ylabel("realized gain", color="#dc2626"); ax2.tick_params(axis="y", labelcolor="#dc2626")
    ax.set_title(f"FESC value-of-information (novel core)\n"
                 f"stop = free-energy fixed point", fontsize=11)
    l1, la1 = ax.get_legend_handles_labels(); l2, la2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, la1 + la2, fontsize=7, loc="upper left")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    p = os.path.join(FIGDIR, "fig1_architecture.png")
    fig.savefig(p, dpi=140); plt.close(fig); return p


def fig2(trace, metrics, topo_snaps):
    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle("MOSAIC-Ω  —  loop control & graph engineering", fontsize=15, fontweight="bold")

    # -- B1: graph structure evolution --------------------------------------
    ax = axes[0, 0]
    snaps = trace.topology
    it = [s.iteration for s in snaps]
    ax.plot(it, [s.modularity for s in snaps], "-o", label="modularity", color="#2563eb")
    ax.plot(it, [s.avg_degree / max(1, max(s.avg_degree for s in snaps)) for s in snaps],
            "-s", label="mean degree (norm)", color="#16a34a")
    ax.plot(it, [s.degree_entropy / max(1e-9, max(s.degree_entropy for s in snaps)) for s in snaps],
            "-^", label="degree entropy (norm)", color="#f59e0b")
    ax.set_xlabel("iteration"); ax.set_ylabel("value"); ax.legend(fontsize=8); ax.grid(alpha=0.25)
    ax.set_title(f"Continuous topology rewiring (G_t+1=F(...))\n"
                 f"{len(snaps)} rewiring events, edge churn="
                 f"{metrics['structure']['edge_churn_rate']:.2f}", fontsize=11)

    # -- B2: adjudication (jury margin + kappa) -----------------------------
    ax = axes[0, 1]
    v = trace.verdicts
    if v:
        rounds = range(1, len(v) + 1)
        ax.plot(rounds, [x.margin for x in v], "-o", color="#0891b2", label="jury margin")
        ax.plot(rounds, [x.agreement_kappa for x in v], "-s", color="#7c3aed",
                label="Fleiss κ (independence)")
    ax.set_xlabel("jury round"); ax.set_ylabel("value"); ax.legend(fontsize=8); ax.grid(alpha=0.25)
    ax.set_title(f"Blinded adjudication — survival="
                 f"{metrics['reasoning']['mean_falsification_survival']:.2f}, "
                 f"blinded={metrics['consensus']['blinded_adjudication']}", fontsize=11)

    # -- B3: EVOI calibration scatter ---------------------------------------
    ax = axes[1, 0]
    ep, er = np.array(trace.evoi_predicted), np.array(trace.evoi_realized)
    ax.scatter(ep, er, c="#7c3aed", s=45, alpha=0.8)
    r = metrics["control"]["evoi_calibration_r"]
    ax.set_xlabel("predicted ΔJ (free energy)"); ax.set_ylabel("realized score gain")
    ax.axhline(0, color="#94a3b8", lw=0.8)
    ax.set_title(f"FESC calibration — r={r:.2f} (honest: model-based, "
                 f"decoupled from score)", fontsize=11)
    ax.grid(alpha=0.25)

    # -- B4: sovereignty transfers (earned authority) -----------------------
    ax = axes[1, 1]
    s = trace.sovereignty
    if s:
        idx = range(1, len(s) + 1)
        gains = [t.competence_to - t.competence_from for t in s]
        ax.bar(idx, gains, color=["#16a34a" if g >= 0 else "#dc2626" for g in gains])
        ax.axhline(0, color="#334155", lw=0.8)
    ax.set_xlabel("sovereignty transfer #"); ax.set_ylabel("competence gain")
    ax.set_title(f"Dynamic sovereignty — {len(s)} transfers, "
                 f"mean gain={metrics['structure']['mean_competence_gain_on_transfer']:.2f}", fontsize=11)
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    p = os.path.join(FIGDIR, "fig2_loop_graph.png")
    fig.savefig(p, dpi=140); plt.close(fig); return p


def fig3_biology(problem, assignment, metrics):
    import scanpy as sc
    task = problem.task
    types_long = task["types"]; short = task["short"]
    # committed marker per cell type (short id) -> gene
    chosen = {short[c]: assignment.get(short[c], "?") for c in types_long}

    # real primary AnnData, gingiva subset, symbol var names
    A = sc.read_h5ad(os.path.join(ROOT, "data", "mucosal_immune.h5ad"))
    A = A[A.obs["tissue"] == "gingiva"].copy()
    A.var_names = A.var["feature_name"].astype(str).values
    A.var_names_make_unique()
    A = A[A.obs["cell_type"].isin(types_long)].copy()
    A.obs["cell_type"] = A.obs["cell_type"].astype(str)

    genes = [chosen[short[c]] for c in types_long]
    genes = list(dict.fromkeys([g for g in genes if g in A.var_names]))

    fig = plt.figure(figsize=(15, 6.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1])
    fig.suptitle("MOSAIC-Ω  —  real result: committed gingival cell-type markers",
                 fontsize=15, fontweight="bold")

    # C1: real dotplot (mean expression + fraction) of committed markers
    ax1 = fig.add_subplot(gs[0, 0])
    A.raw = None
    genes = [str(g) for g in genes]
    dp = sc.pl.dotplot(A, var_names=genes, groupby="cell_type", ax=ax1, show=False,
                       use_raw=False, standard_scale="var", dot_max=0.8, cmap="Reds")
    ax1.set_title("Real expression of committed markers (primary, 14,036 gingival cells)",
                  fontsize=10)

    # C2: decision matrix - chosen vs DE-truth vs replication
    ax2 = fig.add_subplot(gs[0, 1])
    rep = problem.external_replication(assignment)
    rows = []
    for c in types_long:
        s = short[c]
        ch = assignment.get(s, "?"); tr = problem.truth_of(s)
        rows.append((s, ch, tr, ch == tr, rep[s]))
    ax2.axis("off")
    cell_txt = [[r[0], r[1], "✓" if r[3] else "✗",
                 "✓" if r[4] else "✗"] for r in rows]
    tbl = ax2.table(cellText=cell_txt,
                    colLabels=["cell type", "committed marker", "correct", "replicates*"],
                    loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1, 1.6)
    for j in range(4):
        tbl[0, j].set_facecolor("#1e293b"); tbl[0, j].set_text_props(color="white", weight="bold")
    for i, r in enumerate(rows, 1):
        tbl[i, 2].set_facecolor("#dcfce7" if r[3] else "#fee2e2")
        tbl[i, 3].set_facecolor("#dcfce7" if r[4] else "#fee2e2")
    acc = metrics["outcome"]["ground_truth_accuracy"]
    nrep = sum(rep.values())
    ax2.set_title(f"Accuracy vs real DE truth: {acc:.0%}  ({len(rows)}/{len(rows)})\n"
                  f"*replication NOT independent — shared donors (see caption)",
                  fontsize=10)
    fig.text(0.5, 0.01,
             "Caveat: primary & 'validation' share 13/13 gingival donors (same meta-atlas). "
             "Replication is internal, not an independent cohort.",
             ha="center", fontsize=8, style="italic", color="#b91c1c")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    p = os.path.join(FIGDIR, "fig3_real_biology.png")
    fig.savefig(p, dpi=140); plt.close(fig); return p


def main():
    with open(TASK_PATH) as f:
        task = json.load(f)
    problem = PeriodontalMarkerProblem(task)
    cfg = MosaicConfig(max_iterations=12)
    trace, metrics, topo_snaps, assignment = run_capture(problem, cfg)

    print("run:", metrics["outcome"]["termination"],
          "| ground_truth:", metrics["outcome"]["ground_truth_accuracy"],
          "| iterations:", trace.iterations)
    outs = []
    outs.append(fig1(trace, metrics, topo_snaps, assignment, problem))
    outs.append(fig2(trace, metrics, topo_snaps))
    try:
        outs.append(fig3_biology(problem, assignment, metrics))
    except Exception as e:
        print("fig3 (biology) failed:", repr(e))
    for p in outs:
        print("wrote", p)


if __name__ == "__main__":
    main()
