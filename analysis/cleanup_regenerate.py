"""Regenerate fig8 honestly (mark cross-cohort concordance on differential
abundance) and create fig19 = the corrected, defensible 'what replicates'
summary. Superseded overfit figures are archived separately by PowerShell.
"""
import os, warnings
import numpy as np, pandas as pd
import scanpy as sc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
warnings.filterwarnings("ignore")

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT
COND = {"Healthy": "#2563eb", "Periodontitis": "#dc2626", "Periodontitis_treated": "#f59e0b"}


def concordance():
    m = pd.read_csv(os.path.join(TAB, "disease_differential_abundance.csv")).set_index("cell_type")
    e = pd.read_csv(os.path.join(TAB, "ext_differential_abundance.csv")).set_index("cell_type")
    common = m.index.intersection(e.index)
    df = pd.DataFrame({"main": m.loc[common, "log2FC"], "ext": e.loc[common, "log2FC"],
                       "main_p": m.loc[common, "p"], "ext_p": e.loc[common, "p"]})
    df["concordant"] = np.sign(df["main"]) == np.sign(df["ext"])
    return df


def fig8():
    A = sc.read_h5ad(os.path.join(DATA, "GSE171213_annotated.h5ad"))
    cts = list(A.obs["cell_type"].cat.categories)
    cmap = plt.cm.tab20(np.linspace(0, 1, len(cts)))
    con = concordance()
    fig = plt.figure(figsize=(17, 12))
    fig.suptitle("Periodontitis atlas — GSE171213 (main cohort, 35,323 cells)  |  abundance marked for cross-cohort concordance",
                 fontsize=13, fontweight="bold")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    ax = fig.add_subplot(gs[0, 0])
    for c, col in zip(cts, cmap):
        m = (A.obs["cell_type"] == c).values
        ax.scatter(A.obsm["X_umap"][m,0], A.obsm["X_umap"][m,1], s=1.5, color=col, label=c, alpha=0.6)
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
    ax.set_ylabel("fraction"); ax.set_title("Cell-type composition by condition"); ax.tick_params(axis="x", rotation=15)
    ax = fig.add_subplot(gs[1, 1])
    d = con.sort_values("main")
    colors = ["#16a34a" if c else "#dc2626" for c in d["concordant"]]
    ax.barh(d.index, d["main"], color=colors); ax.axvline(0, color="#334155", lw=0.8)
    for i, (ct, r) in enumerate(d.iterrows()):
        tag = "✓ same dir in ext" if r["concordant"] else "✗ discordant (artifact?)"
        ax.text(r["main"] + (0.05 if r["main"] >= 0 else -0.05), i, tag,
                va="center", ha="left" if r["main"] >= 0 else "right", fontsize=7,
                color="#16a34a" if r["concordant"] else "#dc2626")
    ax.set_xlabel("main-cohort log2FC abundance (PD/HC)")
    ax.set_title("Differential abundance — green = replicates direction in external cohort")
    fig.tight_layout(rect=[0,0,1,0.96])
    p = os.path.join(FIG, "fig8_disease_atlas.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


def fig19():
    con = concordance()
    A = sc.read_h5ad(os.path.join(DATA, "GSE171213_annotated.h5ad"))
    E = sc.read_h5ad(os.path.join(DATA, "GSE164241_annotated.h5ad"))
    fig, ax = plt.subplots(1, 2, figsize=(15, 6.5))
    fig.suptitle("What actually replicates after overfitting correction (sample-level, both cohorts)",
                 fontsize=14, fontweight="bold")
    # abundance concordance scatter
    r, _ = stats.pearsonr(con["main"], con["ext"])
    cols = ["#16a34a" if c else "#dc2626" for c in con["concordant"]]
    ax[0].scatter(con["main"], con["ext"], c=cols, s=90)
    for ct, row in con.iterrows():
        ax[0].annotate(ct, (row["main"], row["ext"]), fontsize=7)
    lim = [con[["main","ext"]].values.min()-0.4, con[["main","ext"]].values.max()+0.4]
    ax[0].plot(lim, lim, "--", color="#94a3b8"); ax[0].axhline(0, color="#e2e8f0"); ax[0].axvline(0, color="#e2e8f0")
    ax[0].set_xlabel("main log2FC abundance"); ax[0].set_ylabel("external log2FC abundance")
    ax[0].set_title(f"Cell-abundance concordance (r={r:.2f})\ngreen=same direction both cohorts")
    # plasma / fibroblast proportion — the two consistent findings
    def prop(A, ct):
        p = pd.crosstab(A.obs["sample"], A.obs["cell_type"], normalize="index")
        cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"]
        hc = [s for s in p.index if cond[s]=="Healthy"]; pd_=[s for s in p.index if cond[s]=="Periodontitis"]
        return p.loc[hc, ct].values, p.loc[pd_, ct].values
    data, labels, positions, colors = [], [], [], []
    pos = 0
    for ct, coh, A_ in [("Plasma cell","main",A),("Plasma cell","ext",E),
                        ("Fibroblast","main",A),("Fibroblast","ext",E)]:
        hc, pdv = prop(A_, ct)
        data.append(hc); data.append(pdv)
        labels += [f"{ct[:5]}\n{coh} HC", f"{ct[:5]}\n{coh} PD"]
        positions += [pos, pos+0.7]; colors += ["#2563eb", "#dc2626"]; pos += 2
    bp = ax[1].boxplot(data, positions=positions, widths=0.6, patch_artist=True, showmeans=True)
    for patch, c in zip(bp["boxes"], colors): patch.set_facecolor(c); patch.set_alpha(0.6)
    ax[1].set_xticks(positions); ax[1].set_xticklabels(labels, fontsize=7)
    ax[1].set_ylabel("cell-type proportion")
    ax[1].set_title("Robust findings: Plasma ↑ and Fibroblast ↓ in disease (both cohorts)")
    fig.tight_layout(rect=[0,0,1,0.94])
    p = os.path.join(FIG, "fig19_replicated_findings.png"); fig.savefig(p, dpi=140); plt.close(fig); return p


if __name__ == "__main__":
    print("regenerated", fig8())
    print("created", fig19())
