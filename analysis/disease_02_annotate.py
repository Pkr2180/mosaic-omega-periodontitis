"""Normalise, cluster (Leiden), and annotate periodontal cell types de novo.

Cell-type calls use canonical periodontal/immune marker panels scored per cluster.
"""
import os, warnings
import numpy as np, pandas as pd
import scanpy as sc
warnings.filterwarnings("ignore")
sc.settings.verbosity = 1

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT
QC = os.path.join(DATA, "GSE171213_qc.h5ad")
OUT = os.path.join(DATA, "GSE171213_annotated.h5ad")

MARKERS = {
    "T cell (CD8)":  ["CD3D", "CD3E", "CD8A", "CD8B", "CCL5", "GZMK"],
    "T cell (CD4)":  ["CD3D", "CD3E", "CD4", "IL7R", "CD40LG"],
    "NK cell":       ["NKG7", "GNLY", "KLRD1", "NCAM1"],
    "B cell":        ["MS4A1", "CD79A", "CD79B", "CD19"],
    "Plasma cell":   ["JCHAIN", "MZB1", "IGHG1", "DERL3"],
    "Macrophage": ["CD68", "LYZ", "CD14", "FCGR3A", "C1QA", "AIF1"],
    "Dendritic cell": ["HLA-DRA", "CD1C", "CLEC9A", "LILRA4"],
    "Mast cell":     ["TPSAB1", "CPA3", "MS4A2", "KIT"],
    "Neutrophil":    ["FCGR3B", "CSF3R", "S100A8", "S100A9", "CXCR2"],
    "Fibroblast":    ["COL1A1", "COL1A2", "LUM", "DCN", "PDGFRA"],
    "Endothelial":   ["PECAM1", "VWF", "CLDN5", "CDH5"],
    "Epithelial":    ["KRT14", "KRT5", "KRT6A", "EPCAM", "SFN", "KRT13"],
    "Pericyte/Mural": ["ACTA2", "RGS5", "PDGFRB", "MYH11"],
}


def main():
    A = sc.read_h5ad(QC)
    print("loaded", A.shape, flush=True)
    A.layers["counts"] = A.X.copy()
    sc.pp.normalize_total(A, target_sum=1e4)
    sc.pp.log1p(A)
    A.raw = A
    sc.pp.highly_variable_genes(A, n_top_genes=2000, flavor="seurat")
    Ah = A[:, A.var["highly_variable"]].copy()
    sc.pp.scale(Ah, max_value=10)
    sc.tl.pca(Ah, n_comps=30)
    sc.pp.neighbors(Ah, n_neighbors=15, n_pcs=30)
    sc.tl.leiden(Ah, resolution=1.0, key_added="leiden")
    sc.tl.umap(Ah)
    A.obs["leiden"] = Ah.obs["leiden"].values
    A.obsm["X_umap"] = Ah.obsm["X_umap"]
    print("clusters:", A.obs["leiden"].nunique(), flush=True)

    # score marker panels, assign each Leiden cluster its argmax cell type
    for ct, gs in MARKERS.items():
        genes = [g for g in gs if g in A.raw.var_names]
        sc.tl.score_genes(A, genes, score_name=f"sig_{ct}", use_raw=True)
    score_cols = [f"sig_{ct}" for ct in MARKERS]
    per_cluster = A.obs.groupby("leiden")[score_cols].mean()
    assign = {}
    for cl in per_cluster.index:
        best = per_cluster.loc[cl].idxmax().replace("sig_", "")
        assign[cl] = best
    A.obs["cell_type"] = A.obs["leiden"].map(assign).astype("category")
    print("\ncluster -> cell type:")
    for cl in sorted(assign, key=int):
        print(f"  {cl:>2} -> {assign[cl]:<18} (n={int((A.obs['leiden']==cl).sum())})", flush=True)
    print("\ncell type composition:")
    print(A.obs["cell_type"].value_counts().to_string(), flush=True)
    print("\ncell type x condition:")
    print(pd.crosstab(A.obs["cell_type"], A.obs["condition"]).to_string(), flush=True)
    A.obs = A.obs.drop(columns=[c for c in A.obs.columns if c.startswith("sig_")])
    A.write(OUT)
    print("\nwrote", OUT, flush=True)


if __name__ == "__main__":
    main()
