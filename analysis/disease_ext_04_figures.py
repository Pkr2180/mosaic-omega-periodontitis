"""Figures for the external validation cohort + cross-cohort replication."""
import os, json, warnings
import numpy as np, pandas as pd
import scanpy as sc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
warnings.filterwarnings("ignore")

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT
COND = {"Healthy": "#2563eb", "Periodontitis": "#dc2626"}


def fig_ext_atlas():
    A = sc.read_h5ad(os.path.join(DATA, "GSE164241_annotated.h5ad"))
    cts = list(A.obs["cell_type"].cat.categories)
    cmap = plt.cm.tab20(np.linspace(0, 1, len(cts)))
    fig = plt.figure(figsize=(17, 11))
    fig.suptitle(f"External validation cohort — GSE164241 (NIH, independent; {A.n_obs:,} gingival cells)",
                 fontsize=15, fontweight="bold")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    ax = fig.add_subplot(gs[0, 0])
    for c, col in zip(cts, cmap):
        m = (A.obs["cell_type"] == c).values
        ax.scatter(A.obsm["X_umap"][m,0], A.obsm["X_umap"][m,1], s=1.5, color=col, label=c, alpha=0.6)
    ax.set_title(f"UMAP — {len(cts)} cell types"); ax.axis("off"); ax.legend(markerscale=5, fontsize=7)
    ax = fig.add_subplot(gs[0, 1])
    for c, col in COND.items():
        m = (A.obs["condition"] == c).values
        if m.sum(): ax.scatter(A.obsm["X_umap"][m,0], A.obsm["X_umap"][m,1], s=1.5, color=col, label=c, alpha=0.5)
    ax.set_title("UMAP — condition"); ax.axis("off"); ax.legend(markerscale=5, fontsize=8)
    ax = fig.add_subplot(gs[1, 0])
    comp = pd.crosstab(A.obs["condition"], A.obs["cell_type"], normalize="index")[cts]
    bottom = np.zeros(len(comp))
    for c, col in zip(cts, cmap):
        ax.bar(comp.index, comp[c].values, bottom=bottom, color=col); bottom += comp[c].values
    ax.set_ylabel("fraction"); ax.set_title("Composition by condition"); ax.tick_params(axis="x", rotation=10)
    ax = fig.add_subplot(gs[1, 1])
    da = pd.read_csv(os.path.join(TAB, "ext_differential_abundance.csv")).sort_values("log2FC")
    cols = ["#dc2626" if (fc>0 and p<0.1) else "#2563eb" if (fc<0 and p<0.1) else "#94a3b8"
            for fc, p in zip(da["log2FC"], da["p"])]
    ax.barh(da["cell_type"], da["log2FC"], color=cols); ax.axvline(0, color="#334155", lw=0.8)
    ax.set_xlabel("log2FC abundance (PD/HC)"); ax.set_title("Differential abundance (external)")
    fig.tight_layout(rect=[0,0,1,0.96])
    p = os.path.join(FIG, "fig11_external_atlas.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


def fig_crosscohort():
    fig, ax = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle("Cross-cohort replication — main (GSE171213) vs external (GSE164241)",
                 fontsize=15, fontweight="bold")
    # (a) differential abundance concordance
    ab = pd.read_csv(os.path.join(TAB, "crosscohort_abundance.csv"), index_col=0)
    r, _ = stats.pearsonr(ab["main_log2FC"], ab["ext_log2FC"])
    ax[0,0].scatter(ab["main_log2FC"], ab["ext_log2FC"], color="#2563eb", s=60)
    for ct, row in ab.iterrows():
        ax[0,0].annotate(ct, (row["main_log2FC"], row["ext_log2FC"]), fontsize=7)
    lim = [ab.values.min()-0.5, ab.values.max()+0.5]
    ax[0,0].plot(lim, lim, "--", color="#94a3b8"); ax[0,0].axhline(0, color="#e2e8f0"); ax[0,0].axvline(0, color="#e2e8f0")
    ax[0,0].set_xlabel("main log2FC abundance"); ax[0,0].set_ylabel("external log2FC abundance")
    ax[0,0].set_title(f"Differential abundance concordance (r={r:.2f})")
    # (b) per-cell-type DE concordance
    cc = pd.read_csv(os.path.join(TAB, "crosscohort_de_concordance.csv")).sort_values("spearman_lfc")
    ax[0,1].barh(cc["cell_type"], cc["spearman_lfc"], color="#7c3aed")
    ax[0,1].set_xlabel("Spearman r of per-gene log2FC (main vs ext)")
    ax[0,1].set_title("DE effect-size concordance per cell type"); ax[0,1].set_xlim(-0.2, 1)
    # (c) replication rate
    ax[1,0].barh(cc["cell_type"], cc["replication_rate"], color="#16a34a")
    ax[1,0].set_xlabel("fraction of main DEGs replicating in external (same dir + sig)")
    ax[1,0].set_title("DEG replication rate"); ax[1,0].set_xlim(0, 1)
    # (d) pan-signature replication
    pan = pd.read_csv(os.path.join(TAB, "crosscohort_pan_replication.csv")).head(15)
    ax[1,1].barh(pan["gene"], pan["ext_celltypes_up_sig"], color="#dc2626")
    ax[1,1].set_xlabel("# external cell types where gene is up & significant")
    ax[1,1].set_title("Pan-signature replication in external cohort")
    fig.tight_layout(rect=[0,0,1,0.96])
    p = os.path.join(FIG, "fig12_crosscohort_replication.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


def fig_ext_mosaic_metrics():
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle("MOSAIC-Ω in external cohort + cross-cohort evaluation metrics",
                 fontsize=15, fontweight="bold")
    # external MOSAIC vs naive
    res = json.load(open(os.path.join(TAB, "ext_mosaic_result.json")))
    ax[0].bar(["naive\nWilcoxon-top", "MOSAIC-Ω\nconsensus"],
              [res["naive_mean_robustness"], res["mosaic_mean_robustness"]],
              color=["#94a3b8", "#2563eb"])
    for i, v in enumerate([res["naive_mean_robustness"], res["mosaic_mean_robustness"]]):
        ax[0].text(i, v+0.01, f"{v:.3f}", ha="center", fontweight="bold")
    ax[0].set_ylabel("mean LOSO robustness"); ax[0].set_ylim(0, 1)
    ax[0].set_title(f"External-cohort biomarker reproducibility\nMOSAIC accuracy={res['mosaic_accuracy_mean']:.2f}")
    # metrics table
    ax[1].axis("off")
    m = pd.read_csv(os.path.join(TAB, "crosscohort_metrics.csv"), index_col=0)
    cells = [[k.replace("_", " "), str(v["value"] if hasattr(v,'__getitem__') else v)] for k, v in m.iterrows()]
    cells = [[idx.replace("_"," "), str(m.loc[idx, m.columns[0]])] for idx in m.index]
    t = ax[1].table(cellText=cells, colLabels=["cross-cohort metric", "value"],
                    loc="center", cellLoc="left")
    t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.7)
    for j in range(2):
        t[0, j].set_facecolor("#1e293b"); t[0, j].set_text_props(color="white", weight="bold")
    ax[1].set_title("Cross-cohort evaluation metrics")
    fig.tight_layout(rect=[0,0,1,0.94])
    p = os.path.join(FIG, "fig13_crosscohort_mosaic_metrics.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


if __name__ == "__main__":
    print("wrote", fig_ext_atlas())
    print("wrote", fig_crosscohort())
    print("wrote", fig_ext_mosaic_metrics())
