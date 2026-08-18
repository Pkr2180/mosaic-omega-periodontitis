"""Build + QC + annotate the EXTERNAL validation cohort GSE164241 (NIH/Moutsopoulos).

Independent of GSE171213 (different lab, patients, platform).
GM* = healthy gingiva, PD* = periodontitis gingiva. BM* (buccal mucosa) excluded.
Same QC + annotation pipeline as the main cohort.
"""
import os, glob, re, warnings
import numpy as np, pandas as pd, scipy.io, scipy.sparse as sp
import scanpy as sc
warnings.filterwarnings("ignore")

DATA = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\data"
EXT = os.path.join(DATA, "GSE164241")
OUT = os.path.join(DATA, "GSE164241_annotated.h5ad")

MARKERS = {
    "T cell (CD8)":  ["CD3D", "CD3E", "CD8A", "CD8B", "CCL5", "GZMK"],
    "T cell (CD4)":  ["CD3D", "CD3E", "CD4", "IL7R", "CD40LG"],
    "NK cell":       ["NKG7", "GNLY", "KLRD1", "NCAM1"],
    "B cell":        ["MS4A1", "CD79A", "CD79B", "CD19"],
    "Plasma cell":   ["JCHAIN", "MZB1", "IGHG1", "DERL3"],
    "Macrophage":    ["CD68", "LYZ", "CD14", "FCGR3A", "C1QA", "AIF1"],
    "Dendritic cell": ["HLA-DRA", "CD1C", "CLEC9A", "LILRA4"],
    "Mast cell":     ["TPSAB1", "CPA3", "MS4A2", "KIT"],
    "Neutrophil":    ["FCGR3B", "CSF3R", "S100A8", "S100A9", "CXCR2"],
    "Fibroblast":    ["COL1A1", "COL1A2", "LUM", "DCN", "PDGFRA"],
    "Endothelial":   ["PECAM1", "VWF", "CLDN5", "CDH5"],
    "Epithelial":    ["KRT14", "KRT5", "KRT6A", "EPCAM", "SFN", "KRT13"],
    "Pericyte/Mural": ["ACTA2", "RGS5", "PDGFRB", "MYH11"],
}


def load_sample(prefix):
    mtx = glob.glob(os.path.join(EXT, prefix + "*matrix.mtx.gz"))[0]
    bc = glob.glob(os.path.join(EXT, prefix + "*barcodes.tsv.gz"))[0]
    ft = glob.glob(os.path.join(EXT, prefix + "*features.tsv.gz")) or \
         glob.glob(os.path.join(EXT, prefix + "*genes.tsv.gz"))
    ft = ft[0]
    M = scipy.io.mmread(mtx).tocsr()                 # features x cells
    feat = pd.read_csv(ft, sep="\t", header=None)
    sym = feat[1].astype(str).values if feat.shape[1] > 1 else feat[0].astype(str).values
    barc = pd.read_csv(bc, sep="\t", header=None)[0].astype(str).values
    A = sc.AnnData(X=sp.csr_matrix(M.T), obs=pd.DataFrame(index=barc),
                   var=pd.DataFrame(index=sym))
    A.var_names_make_unique()
    return A


def build():
    if os.path.exists(os.path.join(DATA, "GSE164241_qc.h5ad")):
        print("qc exists", flush=True); return
    samples = sorted(set(re.match(r"(GSM\d+_[A-Za-z]+\d+)", os.path.basename(f)).group(1)
                         for f in glob.glob(os.path.join(EXT, "*matrix.mtx.gz"))
                         if re.match(r"(GSM\d+_[A-Za-z]+\d+)", os.path.basename(f))))
    # keep gingiva healthy (GM) and periodontitis (PD)
    keep = [s for s in samples if re.search(r"_(GM|PD)\d+", s)]
    print("using samples:", keep, flush=True)
    parts = []
    for s in keep:
        A = load_sample(s)
        sid = re.search(r"_([A-Za-z]+\d+)", s).group(1)
        A.obs["sample"] = sid
        A.obs["condition"] = "Healthy" if sid.startswith("GM") else "Periodontitis"
        A.obs_names = [f"{sid}_{b}" for b in A.obs_names]
        parts.append(A)
        print(f"  {sid}: {A.n_obs} cells", flush=True)
    A = sc.concat(parts, join="inner")
    A.obs_names_make_unique()
    print("concatenated:", A.shape, flush=True)
    A.var["mt"] = A.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(A, qc_vars=["mt"], inplace=True, percent_top=None)
    keep_cells = (A.obs["n_genes_by_counts"] >= 200) & (A.obs["n_genes_by_counts"] <= 6000) \
        & (A.obs["pct_counts_mt"] < 20)
    A = A[keep_cells].copy(); sc.pp.filter_genes(A, min_cells=3)
    print("after QC:", A.shape, flush=True)
    print(A.obs["condition"].value_counts().to_string(), flush=True)
    A.write(os.path.join(DATA, "GSE164241_qc.h5ad"))


def annotate():
    if os.path.exists(OUT):
        print("annotated exists", flush=True); return
    A = sc.read_h5ad(os.path.join(DATA, "GSE164241_qc.h5ad"))
    A.layers["counts"] = A.X.copy()
    sc.pp.normalize_total(A, target_sum=1e4); sc.pp.log1p(A); A.raw = A
    sc.pp.highly_variable_genes(A, n_top_genes=2000, flavor="seurat")
    Ah = A[:, A.var["highly_variable"]].copy()
    sc.pp.scale(Ah, max_value=10); sc.tl.pca(Ah, n_comps=30)
    sc.pp.neighbors(Ah, n_neighbors=15, n_pcs=30); sc.tl.leiden(Ah, resolution=1.0)
    sc.tl.umap(Ah)
    A.obs["leiden"] = Ah.obs["leiden"].values; A.obsm["X_umap"] = Ah.obsm["X_umap"]
    for ct, gs in MARKERS.items():
        genes = [g for g in gs if g in A.raw.var_names]
        sc.tl.score_genes(A, genes, score_name=f"sig_{ct}", use_raw=True)
    cols = [f"sig_{ct}" for ct in MARKERS]
    per = A.obs.groupby("leiden")[cols].mean()
    assign = {cl: per.loc[cl].idxmax().replace("sig_", "") for cl in per.index}
    A.obs["cell_type"] = A.obs["leiden"].map(assign).astype("category")
    print("\nexternal cell type x condition:", flush=True)
    print(pd.crosstab(A.obs["cell_type"], A.obs["condition"]).to_string(), flush=True)
    A.obs = A.obs.drop(columns=[c for c in A.obs.columns if c.startswith("sig_")])
    A.write(OUT); print("\nwrote", OUT, flush=True)


if __name__ == "__main__":
    build()
    annotate()
