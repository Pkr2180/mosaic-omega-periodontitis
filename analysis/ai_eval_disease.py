"""Deep AI evaluation of MOSAIC-Omega on the periodontitis biomarker task.

(1) Full 9-group architecture metric suite (main + external cohort).
(2) Ablation: which NOVEL components (falsification, blinding, parallel
    universes, pruning) actually drive the biomarker robustness gain?
(3) Robust-biomarker recovery as a classification problem (MOSAIC vs naive).
Tables + figures fig14/fig15.
"""
from __future__ import annotations
import os, json, warnings
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

from mosaic_omega import MosaicConfig, MosaicOmega
from disease_05_mosaic import DiseaseBiomarkerProblem

ROOT = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1"
TAB, FIG = ROOT+r"\tables", ROOT+r"\figures"

ABLATIONS = {
    "full": {},
    "no_falsification": {"falsifiers_per_candidate": 0, "attacks_per_falsifier": 0},
    "no_blinding": {"blinding_level": "none"},
    "single_universe": {"n_universes": 1},
    "no_pruning": {"prune_utility_threshold": 0.0, "redundancy_jaccard": 2.0},
}
SEEDS = list(range(6))


def load(cohort):
    f = "disease_candidates.json" if cohort == "main" else "ext_candidates.json"
    return json.load(open(os.path.join(TAB, f)))


def run(cohort, flags, seed):
    prob = DiseaseBiomarkerProblem(load(cohort))
    cfg = MosaicConfig(max_iterations=12, seed=20260807 + seed, **flags)
    res = MosaicOmega(cfg).solve(prob)
    a = res.final_candidate.assignment if res.final_candidate else {}
    picks_robust = [prob._rob(cid, a.get(cid, "")) for cid in prob._constraints]
    # robust-recovery: among constraints where a robust option (>=0.8) exists, did it pick one?
    recov = []
    for cid in prob._constraints:
        opts = prob.info[cid]["robustness"]
        if any(v >= 0.8 for v in opts.values()):
            recov.append(1.0 if prob._rob(cid, a.get(cid, "")) >= 0.8 else 0.0)
    return {"robustness": float(np.mean(picks_robust)),
            "accuracy": res.metrics["outcome"]["ground_truth_accuracy"],
            "recovery": float(np.mean(recov)) if recov else np.nan,
            "metrics": res.metrics, "assignment": a, "problem": prob, "trace": res.trace}


def main():
    # ---- (1) full metric suite ----
    full_rows = []
    traj = {}
    for cohort in ["main", "ext"]:
        r0 = run(cohort, {}, 0)
        for grp, vals in r0["metrics"].items():
            for k, v in vals.items():
                if isinstance(v, (int, float, bool)) or v is None:
                    full_rows.append({"cohort": cohort, "group": grp, "metric": k, "value": v})
        traj[cohort] = r0["trace"]
    pd.DataFrame(full_rows).to_csv(os.path.join(TAB, "ai_disease_full_metrics.csv"), index=False)

    # ---- (2) ablation ----
    abl_rows = []
    for cohort in ["main", "ext"]:
        for name, flags in ABLATIONS.items():
            rob, acc, rec = [], [], []
            for s in SEEDS:
                r = run(cohort, flags, s)
                rob.append(r["robustness"]); acc.append(r["accuracy"]); rec.append(r["recovery"])
            abl_rows.append({"cohort": cohort, "config": name,
                             "mean_robustness": np.mean(rob), "std_robustness": np.std(rob),
                             "mean_accuracy": np.mean(acc), "robust_recovery": np.nanmean(rec)})
    abl = pd.DataFrame(abl_rows)
    abl.to_csv(os.path.join(TAB, "ai_disease_ablation.csv"), index=False)
    print("\n=== ABLATION (biomarker robustness by architecture component) ===", flush=True)
    print(abl.round(3).to_string(index=False), flush=True)

    # ---- (3) MOSAIC vs naive robust-recovery classification ----
    cls_rows = []
    for cohort in ["main", "ext"]:
        prob = DiseaseBiomarkerProblem(load(cohort))
        naive = prob.naive_signature()
        n_pick = [prob._rob(cid, naive[cid]) for cid in prob._constraints]
        n_rec = np.mean([1.0 if prob._rob(cid, naive[cid]) >= 0.8 else 0.0
                         for cid in prob._constraints
                         if any(v >= 0.8 for v in prob.info[cid]["robustness"].values())])
        m = [run(cohort, {}, s) for s in SEEDS]
        cls_rows.append({"cohort": cohort, "method": "naive_Wilcoxon",
                         "mean_robustness": np.mean(n_pick), "robust_recovery": n_rec})
        cls_rows.append({"cohort": cohort, "method": "MOSAIC-Omega",
                         "mean_robustness": np.mean([x["robustness"] for x in m]),
                         "robust_recovery": np.nanmean([x["recovery"] for x in m])})
    cls = pd.DataFrame(cls_rows)
    cls.to_csv(os.path.join(TAB, "ai_disease_classification.csv"), index=False)
    print("\n=== MOSAIC vs naive robust-biomarker recovery ===", flush=True)
    print(cls.round(3).to_string(index=False), flush=True)

    make_figs(abl, cls, traj, r0["metrics"])


def make_figs(abl, cls, traj, metrics_ext):
    # fig14: ablation
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle("MOSAIC-Ω ablation — which novel components produce robust biomarkers?",
                 fontsize=15, fontweight="bold")
    order = ["full", "no_falsification", "no_blinding", "single_universe", "no_pruning"]
    for i, cohort in enumerate(["main", "ext"]):
        d = abl[abl.cohort == cohort].set_index("config").reindex(order)
        colors = ["#2563eb"] + ["#dc2626"]*4
        ax[i].bar(range(len(order)), d["mean_robustness"], yerr=d["std_robustness"],
                  color=colors, capsize=4)
        ax[i].set_xticks(range(len(order))); ax[i].set_xticklabels(order, rotation=25, ha="right", fontsize=9)
        ax[i].set_ylabel("mean LOSO robustness of committed biomarkers"); ax[i].set_ylim(0, 1.05)
        full_v = d.loc["full", "mean_robustness"]
        ax[i].axhline(full_v, ls="--", color="#2563eb", lw=1)
        ax[i].set_title(f"{cohort} cohort  (full={full_v:.3f})")
        for j, v in enumerate(d["mean_robustness"]):
            ax[i].text(j, v+0.02, f"{v:.2f}", ha="center", fontsize=8)
    fig.tight_layout(rect=[0,0,1,0.95])
    p1 = os.path.join(FIG, "fig14_ai_ablation.png"); fig.savefig(p1, dpi=140); plt.close(fig)

    # fig15: FESC EVOI trajectory + recovery + metric table
    fig = plt.figure(figsize=(17, 7))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1, 1.3])
    fig.suptitle("MOSAIC-Ω on periodontitis — FESC control, recovery, full metric suite",
                 fontsize=14, fontweight="bold")
    ax = fig.add_subplot(gs[0, 0])
    for cohort, col in [("main", "#2563eb"), ("ext", "#16a34a")]:
        t = traj[cohort]; it = range(1, len(t.evoi_predicted)+1)
        ax.plot(it, t.evoi_predicted, "-o", color=col, label=f"{cohort}: EVOI predicted (ΔJ)")
    ax.set_xlabel("loop iteration"); ax.set_ylabel("FESC free-energy descent (ΔJ)")
    ax.legend(fontsize=8); ax.set_title("FESC value-of-information (novel core)"); ax.grid(alpha=0.25)
    ax = fig.add_subplot(gs[0, 1])
    piv = cls.pivot(index="cohort", columns="method", values="robust_recovery")
    x = np.arange(len(piv)); w = 0.35
    ax.bar(x-w/2, piv["naive_Wilcoxon"], w, label="naive Wilcoxon", color="#94a3b8")
    ax.bar(x+w/2, piv["MOSAIC-Omega"], w, label="MOSAIC-Ω", color="#2563eb")
    ax.set_xticks(x); ax.set_xticklabels(piv.index); ax.set_ylim(0, 1.05)
    ax.set_ylabel("robust-biomarker recovery rate"); ax.legend(); ax.set_title("Robust-gene recovery")
    ax = fig.add_subplot(gs[0, 2]); ax.axis("off")
    show = [("outcome","ground_truth_accuracy"),("outcome","score_truth_gap"),
            ("reasoning","mean_falsification_survival"),("consensus","mean_jury_kappa"),
            ("consensus","blinded_adjudication"),("control","evoi_calibration_r"),
            ("safety","blinding_leak_rate"),("safety","anchoring_index"),
            ("safety","branch_isolation_purity"),("reliability","contract_compliance_rate")]
    rows = [[f"{g}.{k}", f"{metrics_ext[g][k]:.3f}" if isinstance(metrics_ext[g][k], float)
             else str(metrics_ext[g][k])] for g, k in show]
    t = ax.table(cellText=rows, colLabels=["architecture metric (ext run)", "value"],
                 loc="center", cellLoc="left"); t.auto_set_font_size(False); t.set_fontsize(9); t.scale(1,1.55)
    for j in range(2):
        t[0,j].set_facecolor("#1e293b"); t[0,j].set_text_props(color="white", weight="bold")
    ax.set_title("Full architecture metrics")
    fig.tight_layout(rect=[0,0,1,0.94])
    p2 = os.path.join(FIG, "fig15_ai_metrics.png"); fig.savefig(p2, dpi=140); plt.close(fig)
    print("wrote", p1, p2, flush=True)


if __name__ == "__main__":
    main()
