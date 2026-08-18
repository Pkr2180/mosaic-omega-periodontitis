"""Rigorous AI evaluation of MOSAIC-Omega on the real gingival marker task.

Independence: marker truth is derived on TRAIN donors and validated on
DONOR-DISJOINT test donors, so there is no shared-donor leakage. Two protocols:
  (1) cross-study  : train=Williams et al.  test=Huang+Caetano et al. (different labs)
  (2) donor K-fold : 5 folds over the 17 gingival donors, donor-disjoint

Outputs (figures/ + tables/):
  fig4_confusion_prf1.png    confusion matrix + per-class precision/recall/F1
  fig5_accuracy_independent  accuracy distribution + independent cross-study replication
  fig6_roc_calibration.png   ROC + reliability diagram (verify-confidence)
  fig7_loss_curves.png       per-iteration accuracy & loss (epoch analog) + FESC descent
  tables/*.csv               all numbers
"""
from __future__ import annotations
import os, json, warnings
from collections import defaultdict
import numpy as np
import scanpy as sc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import KFold
from sklearn.metrics import (confusion_matrix, precision_recall_fscore_support,
                             roc_curve, auc)

from mosaic_omega import MosaicConfig, MosaicOmega, MetricsEngine
from mosaic_omega.metrics import brier_score, expected_calibration_error, auroc
from run_periodontal_real import PeriodontalMarkerProblem

warnings.filterwarnings("ignore")
from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT

SHARED = ["CD8-positive, alpha-beta T cell","CD4-positive helper T cell","B cell",
          "plasma cell","mast cell","dendritic cell","macrophage","neutrophil"]
# short ids MUST match run_periodontal_real.CAP keys
SHORT = {"CD8-positive, alpha-beta T cell":"CD8_T","CD4-positive helper T cell":"CD4_T",
         "B cell":"B_cell","plasma cell":"plasma_cell","mast cell":"mast_cell",
         "dendritic cell":"dendritic_cell","macrophage":"macrophage","neutrophil":"neutrophil"}
MIN_TRAIN, MIN_TEST, TOPK, SEED0 = 40, 20, 25, 20260807


def load():
    A = sc.read_h5ad(os.path.join(ROOT, "data", "mucosal_immune.h5ad"))
    A = A[A.obs["tissue"] == "gingiva"].copy()
    A.var_names = A.var["feature_name"].astype(str).values; A.var_names_make_unique()
    A = A[A.obs["cell_type"].isin(SHARED)].copy()
    A.obs["cell_type"] = A.obs["cell_type"].astype(str)
    A.raw = None
    return A


def rank(adata, min_cells):
    types = [c for c in SHARED if (adata.obs["cell_type"] == c).sum() >= min_cells]
    if len(types) < 2:
        return {}, {}
    sc.tl.rank_genes_groups(adata, "cell_type", method="wilcoxon", use_raw=False, groups=types)
    r = adata.uns["rank_genes_groups"]; ordered, score = {}, {}
    for g in r["names"].dtype.names:
        ordered[g] = list(r["names"][g])
        score[g] = dict(zip(list(r["names"][g]), map(float, r["scores"][g])))
    return ordered, score


def build_task(train, test, seed):
    """Task with truth from TRAIN, candidates, and val_topk from DONOR-DISJOINT TEST."""
    tr_ord, tr_score = rank(train, MIN_TRAIN)
    te_ord, _ = rank(test, MIN_TEST)
    types = [c for c in SHARED if c in tr_ord]
    truth = {c: tr_ord[c][0] for c in types}
    rng = np.random.default_rng(seed)
    candidates, train_score, train_sig, val_topk, val_rank, n_test = {}, {}, {}, {}, {}, {}
    for c in types:
        distract = [truth[o] for o in types if o != c and truth[o] != truth[c]]
        distract = list(dict.fromkeys(distract)); rng.shuffle(distract)
        opts = list(dict.fromkeys([truth[c]] + distract[:3]))
        for g in tr_ord[c]:
            if len(opts) >= 4: break
            if g not in opts: opts.append(g)
        rng.shuffle(opts); candidates[c] = opts
        smax = max(tr_score[c].values())
        train_score[c] = {g: tr_score[c].get(g, 0.0) for g in opts}
        train_sig[c] = {g: bool(tr_score[c].get(g, 0.0) > 0.30 * smax and tr_score[c].get(g,0)>0)
                        for g in opts}
        vlist = te_ord.get(c, [])
        val_topk[c] = vlist[:TOPK]
        val_rank[c] = vlist.index(truth[c]) if truth[c] in vlist else -1
        n_test[c] = int((test.obs["cell_type"] == c).sum())
    task = {"provenance": {"seed": int(seed)}, "types": types,
            "short": {c: SHORT[c] for c in types}, "truth": truth,
            "candidates": candidates, "train_score": train_score, "train_sig": train_sig,
            "val_topk": val_topk}
    return task, {"val_rank": val_rank, "n_test": n_test, "truth": truth, "types": types}


def per_iteration_accuracy(trace, problem):
    """Real accuracy trajectory: best candidate's true_score at each iteration."""
    by_it = defaultdict(list)
    for cand in trace.candidates:
        by_it[cand.iteration].append(cand)
    traj = []
    for it in sorted(by_it):
        best = max(by_it[it], key=lambda c: c.composite_score)
        traj.append(problem.true_score(best.assignment))
    return traj


def run_once(task, cfg_seed):
    problem = PeriodontalMarkerProblem(task)
    res = MosaicOmega(MosaicConfig(max_iterations=12, seed=cfg_seed)).solve(problem)
    assign = res.final_candidate.assignment if res.final_candidate else {}
    metrics = res.metrics
    conf_pairs = [(cl.confidence, bool(cl.verified)) for cl in res.trace.claims
                  if cl.verified is not None]
    acc_traj = per_iteration_accuracy(res.trace, problem)
    return problem, assign, metrics, conf_pairs, acc_traj, res


# ---------------------------------------------------------------------------
def main():
    A = load()
    donors = np.array(sorted(A.obs["donor_id"].astype(str).unique()))
    print(f"gingival immune cells: {A.n_obs} | donors: {len(donors)}")

    owner_global = {}   # per-run maps kept locally; aggregate CM by short type
    short_types = [SHORT[c] for c in SHARED]
    CM = np.zeros((len(SHARED), len(SHARED)), dtype=int)
    ti = {SHORT[c]: i for i, c in enumerate(SHARED)}

    all_conf = []
    fold_acc = []           # accuracy vs train-truth per run (donor-disjoint CV)
    acc_curves = []         # per-iteration accuracy trajectories
    rows_indep = []         # independent replication rows

    # ---------- (2) donor-disjoint K-fold CV ----------
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED0)
    seeds = [SEED0 + s for s in range(5)]
    for fold, (tr_idx, te_idx) in enumerate(kf.split(donors)):
        tr_d, te_d = set(donors[tr_idx]), set(donors[te_idx])
        train = A[A.obs["donor_id"].astype(str).isin(tr_d)].copy()
        test = A[A.obs["donor_id"].astype(str).isin(te_d)].copy()
        task, info = build_task(train, test, SEED0 + fold)
        owner = {info["truth"][c]: c for c in info["types"]}   # gene -> long type
        for s in seeds:
            problem, assign, metrics, conf, acc_traj, res = run_once(task, s)
            fold_acc.append(metrics["outcome"]["ground_truth_accuracy"])
            all_conf.extend(conf); acc_curves.append(acc_traj)
            for c in info["types"]:
                sid = SHORT[c]; pred = assign.get(sid)
                owner_type = owner.get(pred)          # which cell type's marker was picked
                if owner_type in SHORT:
                    CM[ti[SHORT[c]], ti[SHORT[owner_type]]] += 1
        print(f"fold {fold}: train {len(tr_d)}d/{train.n_obs}c  test {len(te_d)}d/{test.n_obs}c  types {len(info['types'])}")

    # ---------- (1) cross-study independent validation ----------
    study = A.obs["study"].astype(str)
    train_x = A[study == "Williams et al."].copy()
    test_x = A[study.isin(["Huang et al.", "Caetano et al."])].copy()
    taskx, infox = build_task(train_x, test_x, SEED0)
    xacc = []
    for s in seeds:
        problem, assign, metrics, conf, acc_traj, res = run_once(taskx, s)
        xacc.append(metrics["outcome"]["ground_truth_accuracy"])
        rep = problem.external_replication(assign)
        if s == seeds[0]:
            committed = assign
    for c in infox["types"]:
        sid = SHORT[c]
        rows_indep.append({
            "cell_type": sid, "train_marker(Williams)": infox["truth"][c],
            "committed": committed.get(sid), "correct": committed.get(sid) == infox["truth"][c],
            "indep_test_rank": infox["val_rank"][c], "n_test_cells": infox["n_test"][c],
            "replicates(indep)": bool(0 <= infox["val_rank"][c] < TOPK),
        })

    # ---------- aggregate metrics ----------
    y_true, y_pred = [], []
    for i in range(len(SHARED)):
        for j in range(len(SHARED)):
            y_true += [i] * CM[i, j]; y_pred += [j] * CM[i, j]
    P, Rc, F1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(SHARED))), zero_division=0)
    acc_cv = np.trace(CM) / CM.sum()
    brier = brier_score(all_conf); ece = expected_calibration_error(all_conf)
    au = auroc(all_conf)

    # ---------- TABLES ----------
    import csv
    with open(os.path.join(TAB, "independent_cross_study.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_indep[0].keys())); w.writeheader()
        w.writerows(rows_indep)
    with open(os.path.join(TAB, "classification_report.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["cell_type","precision","recall","f1","support"])
        for i, c in enumerate(SHARED):
            w.writerow([SHORT[c], f"{P[i]:.3f}", f"{Rc[i]:.3f}", f"{F1[i]:.3f}", int(CM[i].sum())])
        w.writerow(["ACCURACY(CV)", "", "", f"{acc_cv:.3f}", int(CM.sum())])
    with open(os.path.join(TAB, "ai_metrics_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric","value"])
        for k, v in [("cv_accuracy_mean", np.mean(fold_acc)),
                     ("cv_accuracy_std", np.std(fold_acc)),
                     ("cross_study_accuracy_mean", np.mean(xacc)),
                     ("cross_study_accuracy_std", np.std(xacc)),
                     ("macro_precision", np.mean(P)), ("macro_recall", np.mean(Rc)),
                     ("macro_f1", np.mean(F1)), ("confusion_accuracy", acc_cv),
                     ("verify_brier", brier), ("verify_ece", ece), ("verify_auroc", au),
                     ("n_runs", len(fold_acc)), ("n_conf_pairs", len(all_conf))]:
            w.writerow([k, f"{v:.4f}" if isinstance(v, float) else v])

    print("\n=== AI EVALUATION SUMMARY ===")
    print(f"CV accuracy (donor-disjoint):   {np.mean(fold_acc):.3f} ± {np.std(fold_acc):.3f}  (n={len(fold_acc)} runs)")
    print(f"Cross-study accuracy (indep):   {np.mean(xacc):.3f} ± {np.std(xacc):.3f}")
    print(f"Confusion-matrix accuracy:      {acc_cv:.3f}")
    print(f"Macro P / R / F1:               {np.mean(P):.3f} / {np.mean(Rc):.3f} / {np.mean(F1):.3f}")
    print(f"Verify Brier / ECE / AUROC:     {brier:.3f} / {ece:.3f} / {au:.3f}")
    print(f"Independent cross-study replication: "
          f"{sum(r['replicates(indep)'] for r in rows_indep)}/{len(rows_indep)}")

    make_figs(CM, P, Rc, F1, fold_acc, xacc, rows_indep, all_conf, acc_curves,
              brier, ece, au, acc_cv)


# ---------------------------------------------------------------------------
def make_figs(CM, P, Rc, F1, fold_acc, xacc, rows_indep, all_conf, acc_curves,
              brier, ece, au, acc_cv):
    labels = [SHORT[c] for c in SHARED]

    # fig4: confusion matrix + PRF1
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle("MOSAIC-Ω — classification evaluation (donor-disjoint CV, 25 runs)",
                 fontsize=14, fontweight="bold")
    im = ax[0].imshow(CM, cmap="Blues")
    ax[0].set_xticks(range(len(labels))); ax[0].set_xticklabels(labels, rotation=45, ha="right")
    ax[0].set_yticks(range(len(labels))); ax[0].set_yticklabels(labels)
    ax[0].set_xlabel("predicted (marker's owner cell type)"); ax[0].set_ylabel("true cell type")
    for i in range(len(labels)):
        for j in range(len(labels)):
            if CM[i, j]:
                ax[0].text(j, i, CM[i, j], ha="center", va="center",
                           color="white" if CM[i, j] > CM.max()/2 else "black", fontsize=9)
    ax[0].set_title(f"Confusion matrix (accuracy={acc_cv:.2f})")
    fig.colorbar(im, ax=ax[0], fraction=0.046)
    x = np.arange(len(labels)); w = 0.26
    ax[1].bar(x - w, P, w, label="precision", color="#2563eb")
    ax[1].bar(x, Rc, w, label="recall", color="#16a34a")
    ax[1].bar(x + w, F1, w, label="F1", color="#f59e0b")
    ax[1].set_xticks(x); ax[1].set_xticklabels(labels, rotation=45, ha="right")
    ax[1].set_ylim(0, 1.05); ax[1].legend(); ax[1].grid(alpha=0.25, axis="y")
    ax[1].set_title(f"Per-class metrics (macro-F1={np.mean(F1):.2f})")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "fig4_confusion_prf1.png"), dpi=140); plt.close(fig)

    # fig5: accuracy distribution + independent replication
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("MOSAIC-Ω — accuracy & independent (donor-disjoint) validation",
                 fontsize=14, fontweight="bold")
    ax[0].boxplot([fold_acc, xacc], labels=["donor K-fold CV", "cross-study\n(Williams→Huang+Caetano)"],
                  showmeans=True)
    ax[0].scatter(np.ones(len(fold_acc)) + np.random.uniform(-0.05,0.05,len(fold_acc)), fold_acc,
                  alpha=0.5, color="#2563eb", zorder=3)
    ax[0].scatter(np.ones(len(xacc))*2 + np.random.uniform(-0.05,0.05,len(xacc)), xacc,
                  alpha=0.5, color="#dc2626", zorder=3)
    ax[0].set_ylabel("ground-truth accuracy"); ax[0].set_ylim(0, 1.05); ax[0].grid(alpha=0.25, axis="y")
    ax[0].set_title(f"CV {np.mean(fold_acc):.2f}±{np.std(fold_acc):.2f} | "
                    f"cross-study {np.mean(xacc):.2f}±{np.std(xacc):.2f}")
    labs = [r["cell_type"] for r in rows_indep]
    ranks = [r["indep_test_rank"] for r in rows_indep]
    cols = ["#16a34a" if r["replicates(indep)"] else "#dc2626" for r in rows_indep]
    ax[1].bar(range(len(labs)), [rk if rk >= 0 else TOPK+3 for rk in ranks], color=cols)
    ax[1].axhline(TOPK, ls="--", color="#334155", label=f"top-{TOPK} threshold")
    for i, r in enumerate(rows_indep):
        ax[1].text(i, 1, f"n={r['n_test_cells']}", ha="center", fontsize=7, rotation=90, color="white")
    ax[1].set_xticks(range(len(labs))); ax[1].set_xticklabels(labs, rotation=45, ha="right")
    ax[1].set_ylabel("rank of Williams marker in independent test\n(lower=better)")
    ax[1].legend(); ax[1].set_title("Cross-study marker rank in held-out labs (green=replicates)")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "fig5_accuracy_independent.png"), dpi=140); plt.close(fig)

    # fig6: ROC + reliability
    fig, ax = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("MOSAIC-Ω — verifier calibration on real DE labels",
                 fontsize=14, fontweight="bold")
    yc = np.array([o for _, o in all_conf], dtype=int); pc = np.array([p for p, _ in all_conf])
    fpr, tpr, _ = roc_curve(yc, pc); roc_auc = auc(fpr, tpr)
    ax[0].plot(fpr, tpr, color="#2563eb", lw=2, label=f"AUROC={roc_auc:.2f}")
    ax[0].plot([0,1],[0,1], "--", color="#94a3b8")
    ax[0].set_xlabel("false positive rate"); ax[0].set_ylabel("true positive rate")
    ax[0].legend(); ax[0].set_title(f"ROC — verify confidence → correct (n={len(all_conf)})")
    ax[0].grid(alpha=0.25)
    bins = np.linspace(0, 1, 11); idx = np.clip(np.digitize(pc, bins)-1, 0, 9)
    bx, by, bn = [], [], []
    for b in range(10):
        m = idx == b
        if m.sum():
            bx.append(pc[m].mean()); by.append(yc[m].mean()); bn.append(m.sum())
    ax[1].plot([0,1],[0,1], "--", color="#94a3b8", label="perfect")
    ax[1].plot(bx, by, "-o", color="#7c3aed", lw=2, label=f"observed (ECE={ece:.2f})")
    ax[1].set_xlabel("predicted confidence"); ax[1].set_ylabel("empirical accuracy")
    ax[1].legend(); ax[1].set_title(f"Reliability diagram (Brier={brier:.2f})")
    ax[1].grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "fig6_roc_calibration.png"), dpi=140); plt.close(fig)

    # fig7: per-iteration accuracy & loss (epoch analog) + mean band
    fig, ax = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("MOSAIC-Ω — per-iteration learning curves (epoch analog; no NN training)",
                 fontsize=14, fontweight="bold")
    maxlen = max(len(c) for c in acc_curves)
    M = np.full((len(acc_curves), maxlen), np.nan)
    for i, c in enumerate(acc_curves):
        M[i, :len(c)] = c
    it = np.arange(1, maxlen+1)
    acc_mean = np.nanmean(M, axis=0); acc_sd = np.nanstd(M, axis=0)
    ax[0].plot(it, acc_mean, "-o", color="#16a34a", label="accuracy")
    ax[0].fill_between(it, acc_mean-acc_sd, acc_mean+acc_sd, alpha=0.2, color="#16a34a")
    ax[0].axhline(0.85, ls="--", color="#334155", label="acceptance")
    ax[0].set_xlabel("loop iteration (≈epoch)"); ax[0].set_ylabel("ground-truth accuracy")
    ax[0].set_ylim(0, 1.05); ax[0].legend(); ax[0].grid(alpha=0.25)
    ax[0].set_title("Accuracy trajectory (mean ± sd over 25 runs)")
    loss_mean = 1 - acc_mean
    ax[1].plot(it, loss_mean, "-o", color="#dc2626", label="loss = 1 − accuracy")
    ax[1].fill_between(it, np.clip(loss_mean-acc_sd,0,1), np.clip(loss_mean+acc_sd,0,1),
                       alpha=0.2, color="#dc2626")
    ax[1].set_xlabel("loop iteration (≈epoch)"); ax[1].set_ylabel("loss")
    ax[1].set_ylim(0, 1.05); ax[1].legend(); ax[1].grid(alpha=0.25)
    ax[1].set_title("Loss curve (error trajectory)")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG, "fig7_loss_curves.png"), dpi=140); plt.close(fig)


if __name__ == "__main__":
    main()
