"""Biological interpretation of the periodontitis single-cell study.

Functional enrichment (hypergeometric) of the disease-up signature against
curated periodontal-relevant gene programs, a program x cell-type map, and a
per-cell-type interpretation table with cross-cohort replication status.
"""
import os, glob, warnings, json
import numpy as np, pandas as pd
from scipy import stats
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT

PROGRAMS = {
    "Humoral / Ig (plasma B)": ["IGKC","IGHG1","IGHG2","IGHG3","IGHG4","IGHA1","IGHA2","IGHM",
        "IGLC1","IGLC2","IGLC3","JCHAIN","MZB1","DERL3","XBP1","PRDM1","CD38","TNFRSF17","FKBP11","SSR4","SEC11C"],
    "Antigen presentation (MHC-II)": ["HLA-DRA","HLA-DRB1","HLA-DRB5","HLA-DRB6","HLA-DQA1","HLA-DQA2",
        "HLA-DQB1","HLA-DPA1","HLA-DPB1","CD74","HLA-DMA","HLA-DMB","CIITA"],
    "MHC-I / interferon": ["HLA-A","HLA-B","HLA-C","B2M","TAP1","ISG15","IFI6","IFITM1","IFITM3",
        "STAT1","MX1","OAS1","IRF1","GBP1"],
    "ECM / collagen remodeling": ["COL1A1","COL1A2","COL3A1","COL4A1","COL5A1","COL5A2","COL6A1",
        "COL6A2","COL6A3","COL15A1","LUM","DCN","FN1","SPARC","MMP2","MMP9","TIMP1","CALD1","POSTN","FBN1"],
    "Endothelial activation / adhesion": ["SELE","SELP","ICAM1","VCAM1","PECAM1","VWF","CLDN5",
        "CDH5","ANGPT2","CD34","ACKR1"],
    "Complement / neutrophil / innate": ["C1QA","C1QB","C1QC","C3","CFB","CFD","SERPINA1","S100A8",
        "S100A9","S100A11","S100A12","LYZ","FPR1","FPR3","FCGR3B","CSF3R","LCN2","MPO"],
    "Chemokine / TLS": ["FDCSP","CXCL9","CXCL10","CXCL13","CCL2","CCL5","CCL19","CCL21","LTB",
        "CR2","CD40LG","CXCR4"],
}


def up_degs(prefix, ct):
    f = os.path.join(TAB, f"{prefix}DE_{ct}.csv")
    if not os.path.exists(f): return set(), set()
    d = pd.read_csv(f)
    if "gene" not in d.columns: return set(), set()
    up = set(d[(d["pval_adj"] < 0.05) & (d["log2FC"] > 1)]["gene"])
    allg = set(d["gene"])
    return up, allg


def celltypes(prefix):
    out = []
    for f in glob.glob(os.path.join(TAB, f"{prefix}DE_*.csv")):
        name = os.path.basename(f)[len(prefix+"DE_"):-4]
        if name == "summary":
            continue
        out.append(name)
    return sorted(out)


def enrich(sig, background):
    M = len(background); rows = []
    for prog, genes in PROGRAMS.items():
        gp = set(genes) & background
        if not gp: continue
        ov = len(sig & gp); N = len(sig); nn = len(gp)
        exp = N * nn / M if M else 0
        p = stats.hypergeom.sf(ov-1, M, nn, N) if ov > 0 else 1.0
        rows.append({"program": prog, "overlap": ov, "expected": round(exp,1),
                     "fold": round(ov/exp,2) if exp>0 else np.nan, "p": p, "genes_in_bg": nn})
    df = pd.DataFrame(rows)
    df["FDR"] = np.minimum(1, df["p"] * len(df))
    return df.sort_values("p")


def main():
    cts_m = celltypes("disease_")
    bg = set()
    sig_by_ct = {}
    for ct in cts_m:
        up, allg = up_degs("disease_", ct)
        bg |= allg; sig_by_ct[ct] = up
    sig = set().union(*sig_by_ct.values()) if sig_by_ct else set()
    print(f"disease-up signature: {len(sig)} genes; background {len(bg)}", flush=True)

    en = enrich(sig, bg)
    # replication in external
    cts_e = celltypes("ext_")
    bg_e = set(); sig_e = set()
    for ct in cts_e:
        up, allg = up_degs("ext_", ct); bg_e |= allg; sig_e |= up
    en_e = enrich(sig_e, bg_e).set_index("program")
    en["ext_fold"] = en["program"].map(en_e["fold"])
    en["ext_FDR"] = en["program"].map(en_e["FDR"])
    en["replicated"] = (en["FDR"] < 0.05) & (en["ext_FDR"] < 0.05)
    en.to_csv(os.path.join(TAB, "biology_functional_enrichment.csv"), index=False)
    print("\n=== FUNCTIONAL ENRICHMENT of disease-up signature ===", flush=True)
    print(en[["program","overlap","expected","fold","FDR","ext_fold","ext_FDR","replicated"]].round(3).to_string(index=False), flush=True)

    # program x cell-type map (fraction of each cell type's up-DEGs in each program)
    prog_names = list(PROGRAMS.keys())
    Mtx = np.zeros((len(prog_names), len(cts_m)))
    for j, ct in enumerate(cts_m):
        up = sig_by_ct[ct]
        for i, prog in enumerate(prog_names):
            gp = set(PROGRAMS[prog]) & bg
            Mtx[i, j] = len(up & gp)
    heat = pd.DataFrame(Mtx, index=prog_names, columns=[c.replace('_',' ') for c in cts_m])
    heat.to_csv(os.path.join(TAB, "biology_program_by_celltype.csv"))

    # abundance directions
    da = pd.read_csv(os.path.join(TAB, "disease_differential_abundance.csv")).set_index("cell_type")
    da_e = pd.read_csv(os.path.join(TAB, "ext_differential_abundance.csv")).set_index("cell_type")

    # per-cell-type interpretation
    interp = []
    for ct in cts_m:
        ctn = ct.replace('_', ' ')
        up = sig_by_ct[ct]
        prog_hits = {p: len(up & (set(g) & bg)) for p, g in PROGRAMS.items()}
        dom = max(prog_hits, key=prog_hits.get) if any(prog_hits.values()) else "-"
        da_dir = "up" if da["log2FC"].get(ctn, 0) > 0 else "down"
        da_e_dir = "up" if da_e["log2FC"].get(ctn, 0) > 0 else "down"
        top = pd.read_csv(os.path.join(TAB, f"disease_DE_{ct}.csv"))
        topup = top[(top.pval_adj<0.05)&(top.log2FC>1)].sort_values("score", ascending=False)["gene"].head(5).tolist()
        interp.append({"cell_type": ctn, "abundance_main": da_dir, "abundance_ext": da_e_dir,
                       "n_up_DEG": len(up), "dominant_program": dom, "top_up_genes": ",".join(topup)})
    interp = pd.DataFrame(interp).sort_values("n_up_DEG", ascending=False)
    interp.to_csv(os.path.join(TAB, "biology_celltype_interpretation.csv"), index=False)
    print("\n=== PER-CELL-TYPE BIOLOGICAL INTERPRETATION ===", flush=True)
    print(interp.to_string(index=False), flush=True)

    make_fig(en, heat)


def make_fig(en, heat):
    fig = plt.figure(figsize=(18, 8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.25])
    fig.suptitle("Biological programs dysregulated in periodontitis (real data, 2 cohorts)",
                 fontsize=15, fontweight="bold")
    ax = fig.add_subplot(gs[0, 0])
    e = en.sort_values("fold")
    colors = ["#16a34a" if r else "#94a3b8" for r in e["replicated"]]
    ax.barh(e["program"], e["fold"], color=colors)
    for i, (_, r) in enumerate(e.iterrows()):
        ax.text(r["fold"]+0.05, i, f"FDR={r['FDR']:.0e}" + (" ✓ext" if r["replicated"] else ""),
                va="center", fontsize=8)
    ax.axvline(1, ls="--", color="#334155")
    ax.set_xlabel("enrichment fold (disease-up signature)")
    ax.set_title("Functional enrichment (green = replicates in external cohort)")
    ax = fig.add_subplot(gs[0, 1])
    im = ax.imshow(heat.values, aspect="auto", cmap="Reds")
    ax.set_yticks(range(len(heat.index))); ax.set_yticklabels(heat.index, fontsize=9)
    ax.set_xticks(range(len(heat.columns))); ax.set_xticklabels(heat.columns, rotation=45, ha="right", fontsize=8)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            if heat.values[i, j] > 0:
                ax.text(j, i, int(heat.values[i, j]), ha="center", va="center", fontsize=7,
                        color="white" if heat.values[i,j] > heat.values.max()/2 else "black")
    ax.set_title("Program dysregulation by cell type (# up-DEGs)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout(rect=[0,0,1,0.95])
    p = os.path.join(FIG, "fig16_biology_programs.png"); fig.savefig(p, dpi=140); plt.close(fig)
    print("wrote", p, flush=True)


if __name__ == "__main__":
    main()
