"""Publication-grade figures for the periodontitis health-vs-disease study."""
import os, warnings, json
import numpy as np, pandas as pd
import scanpy as sc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

ROOT = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1"
DATA, TAB, FIG = ROOT+r"\data", ROOT+r"\tables", ROOT+r"\figures"
A = sc.read_h5ad(os.path.join(DATA, "GSE171213_annotated.h5ad"))
COND = {"Healthy": "#2563eb", "Periodontitis": "#dc2626", "Periodontitis_treated": "#f59e0b"}


def fig_atlas():
    fig = plt.figure(figsize=(17, 12))
    fig.suptitle("Periodontitis single-cell atlas — GSE171213 (12 donors, 35,323 cells, real data)",
                 fontsize=15, fontweight="bold")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    cts = list(A.obs["cell_type"].cat.categories)
    cmap = plt.cm.tab20(np.linspace(0, 1, len(cts)))
    ax = fig.add_subplot(gs[0, 0])
    for c, col in zip(cts, cmap):
        m = (A.obs["cell_type"] == c).values
        ax.scatter(A.obsm["X_umap"][m, 0], A.obsm["X_umap"][m, 1], s=1.5, color=col, label=c, alpha=0.6)
    ax.set_title(f"UMAP — {len(cts)} cell types"); ax.axis("off")
    ax.legend(markerscale=5, fontsize=7, loc="upper right", framealpha=0.9)
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
    ax.set_ylabel("fraction of cells"); ax.set_title("Cell-type composition by condition")
    ax.tick_params(axis="x", rotation=15)
    ax = fig.add_subplot(gs[1, 1])
    da = pd.read_csv(os.path.join(TAB, "disease_differential_abundance.csv")).sort_values("log2FC")
    cols = ["#dc2626" if (fc>0 and p<0.1) else "#2563eb" if (fc<0 and p<0.1) else "#94a3b8"
            for fc, p in zip(da["log2FC"], da["p"])]
    ax.barh(da["cell_type"], da["log2FC"], color=cols); ax.axvline(0, color="#334155", lw=0.8)
    ax.set_xlabel("log2 fold-change abundance (PD / HC)")
    ax.set_title("Differential abundance (red=up in disease, p<0.1)")
    fig.tight_layout(rect=[0,0,1,0.96])
    p = os.path.join(FIG, "fig8_disease_atlas.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


def fig_de():
    summ = pd.read_csv(os.path.join(TAB, "disease_DE_summary.csv"))
    top = summ.sort_values("n_DEG", ascending=False).head(4)["cell_type"].tolist()
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    fig.suptitle("Periodontitis vs health — single-cell DE (Wilcoxon) + LOSO robustness",
                 fontsize=15, fontweight="bold")
    for ax, ct in zip(axes.ravel()[:4], top):
        d = pd.read_csv(os.path.join(TAB, f"disease_DE_{ct.replace('/','_').replace(' ','_')}.csv"))
        d["nlp"] = -np.log10(d["pval_adj"].clip(lower=1e-300))
        sig = (d["pval_adj"] < 0.05) & (d["log2FC"].abs() > 1)
        ax.scatter(d.loc[~sig,"log2FC"], d.loc[~sig,"nlp"], s=5, color="#cbd5e1")
        ax.scatter(d.loc[sig&(d.log2FC>0),"log2FC"], d.loc[sig&(d.log2FC>0),"nlp"], s=8, color="#dc2626")
        ax.scatter(d.loc[sig&(d.log2FC<0),"log2FC"], d.loc[sig&(d.log2FC<0),"nlp"], s=8, color="#2563eb")
        d["absfc"] = d["log2FC"].abs()
        for _, r in d[sig].sort_values("nlp", ascending=False).head(6).iterrows():
            ax.annotate(r["gene"], (r["log2FC"], r["nlp"]), fontsize=7)
        ax.axhline(-np.log10(0.05), ls="--", color="#94a3b8", lw=0.8)
        ax.set_xlabel("log2FC (PD/HC)"); ax.set_ylabel("-log10 adj-p")
        ax.set_title(f"{ct}  ({int(sig.sum())} DEGs)")
    # pan robust signature heatmap
    ax = axes.ravel()[4]
    pan = pd.read_csv(os.path.join(TAB, "disease_pan_signature.csv")).head(18)
    genes = [g for g in pan["gene"] if g in A.raw.var_names]
    sub = A.raw[:, genes].X; sub = sub.toarray() if hasattr(sub,"toarray") else np.asarray(sub)
    dfm = pd.DataFrame(sub, columns=genes); dfm["c"] = A.obs["condition"].values
    mean_by = dfm.groupby("c")[genes].mean().reindex(["Healthy","Periodontitis","Periodontitis_treated"])
    z = (mean_by - mean_by.mean(0)) / (mean_by.std(0)+1e-9)
    im = ax.imshow(z.T.values, aspect="auto", cmap="RdBu_r", vmin=-1.5, vmax=1.5)
    ax.set_yticks(range(len(genes))); ax.set_yticklabels(genes, fontsize=7)
    ax.set_xticks(range(len(z.index))); ax.set_xticklabels(["HC","PD","PDT"], fontsize=9)
    ax.set_title("Pan-cell-type robust signature (z)"); fig.colorbar(im, ax=ax, fraction=0.046)
    # DEG burden
    ax = axes.ravel()[5]
    s2 = summ.sort_values("n_DEG")
    ax.barh(s2["cell_type"], s2["n_DEG"], color="#7c3aed")
    ax.set_xlabel("# DEGs (adj-p<0.05, |log2FC|>1)"); ax.set_title("Disease dysregulation burden")
    fig.tight_layout(rect=[0,0,1,0.96])
    p = os.path.join(FIG, "fig9_disease_DE.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


def fig_mosaic():
    df = pd.read_csv(os.path.join(TAB, "mosaic_disease_consensus.csv"))
    res = json.load(open(os.path.join(TAB, "mosaic_disease_result.json")))
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle("MOSAIC-Ω adversarial consensus improves biomarker reproducibility",
                 fontsize=15, fontweight="bold")
    df = df.sort_values("mosaic_robustness")
    y = np.arange(len(df)); h = 0.38
    ax[0].barh(y+h/2, df["mosaic_robustness"], h, color="#2563eb", label="MOSAIC-Ω pick")
    ax[0].barh(y-h/2, df["naive_robustness"], h, color="#94a3b8", label="naive Wilcoxon-top")
    ax[0].set_yticks(y); ax[0].set_yticklabels(df["cell_type"], fontsize=9)
    ax[0].set_xlabel("leave-sample-out robustness"); ax[0].legend(); ax[0].set_xlim(0, 1.05)
    ax[0].set_title("Per-cell-type biomarker robustness")
    for i, r in enumerate(df.itertuples()):
        ax[0].text(r.mosaic_robustness+0.01, i+h/2, r.mosaic_pick, va="center", fontsize=7)
    # summary bars
    ax[1].bar(["naive\nWilcoxon-top", "MOSAIC-Ω\nconsensus"],
              [res["naive_mean_robustness"], res["mosaic_mean_robustness"]],
              color=["#94a3b8", "#2563eb"])
    ax[1].set_ylabel("mean LOSO robustness"); ax[1].set_ylim(0, 1.0)
    ax[1].set_title(f"Signature reproducibility  (+{100*(res['mosaic_mean_robustness']-res['naive_mean_robustness']):.0f}% abs.)\n"
                    f"MOSAIC accuracy vs robust-truth = {res['mosaic_accuracy_mean']:.2f}")
    for i, v in enumerate([res["naive_mean_robustness"], res["mosaic_mean_robustness"]]):
        ax[1].text(i, v+0.01, f"{v:.3f}", ha="center", fontweight="bold")
    fig.tight_layout(rect=[0,0,1,0.95])
    p = os.path.join(FIG, "fig10_mosaic_consensus.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


if __name__ == "__main__":
    print("wrote", fig_atlas())
    print("wrote", fig_de())
    print("wrote", fig_mosaic())
