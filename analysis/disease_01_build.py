"""Build a sparse AnnData from GSE171213 periodontitis scRNA-seq counts and QC it.

12 samples: HC1-4 (healthy), PD1-5 (severe chronic periodontitis), PDT1-3 (treated).
Condition is encoded in each cell barcode (e.g. HC1_C123).
"""
import os, gzip
import numpy as np, pandas as pd, scipy.sparse as sp
import scanpy as sc

DATA = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\data"
COUNTS = os.path.join(DATA, "GSE171213_counts.tsv.gz")
OUT = os.path.join(DATA, "GSE171213.h5ad")


def build():
    import warnings; warnings.filterwarnings("ignore")
    if os.path.exists(OUT):
        print("exists", OUT, flush=True); return
    # streaming CSR build (genes x cells) via fast np.fromstring per line
    print("reading counts (streaming) ...", flush=True)
    indptr = [0]; indices_parts = []; data_parts = []; genes = []
    with gzip.open(COUNTS, "rt") as f:
        header = f.readline().rstrip("\n").split("\t")
        cells = header[1:]
        ncols = len(cells)
        for i, line in enumerate(f):
            tab = line.index("\t")
            genes.append(line[:tab])
            vals = np.fromstring(line[tab + 1:], sep="\t", dtype=np.float32)
            if vals.shape[0] != ncols:
                vals = np.resize(vals, ncols)
            nz = np.flatnonzero(vals)
            indices_parts.append(nz.astype(np.int32))
            data_parts.append(vals[nz])
            indptr.append(indptr[-1] + nz.shape[0])
            if i % 1000 == 0:
                print(f"  gene {i}", flush=True)
    G = sp.csr_matrix((np.concatenate(data_parts),
                       np.concatenate(indices_parts),
                       np.asarray(indptr)), shape=(len(genes), ncols))
    print("genes x cells:", G.shape, flush=True)
    X = G.T.tocsr()                             # cells x genes
    obs = pd.DataFrame(index=cells)
    obs["sample"] = [c.split("_")[0] for c in cells]
    grp = {"HC": "Healthy", "PD": "Periodontitis", "PDT": "Periodontitis_treated"}
    obs["condition"] = [grp["PDT" if s.startswith("PDT") else ("PD" if s.startswith("PD") else "HC")]
                        for s in obs["sample"]]
    var = pd.DataFrame(index=genes)
    A = sc.AnnData(X=X, obs=obs, var=var)
    A.var_names_make_unique()
    A.write(OUT)
    print("wrote", OUT, A.shape)


def qc():
    A = sc.read_h5ad(OUT)
    A.var["mt"] = A.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(A, qc_vars=["mt"], inplace=True, percent_top=None)
    print("\nbefore QC:", A.shape)
    print(A.obs["condition"].value_counts().to_string())
    print("\nper-sample cells:")
    print(A.obs["sample"].value_counts().sort_index().to_string())
    print("\nmedian genes/cell:", int(np.median(A.obs["n_genes_by_counts"])),
          "| median counts/cell:", int(np.median(A.obs["total_counts"])),
          "| median %mt:", round(float(np.median(A.obs["pct_counts_mt"])), 2))
    # standard QC thresholds
    keep = (A.obs["n_genes_by_counts"] >= 200) & (A.obs["n_genes_by_counts"] <= 6000) \
        & (A.obs["pct_counts_mt"] < 20)
    A = A[keep].copy()
    sc.pp.filter_genes(A, min_cells=3)
    print("\nafter QC:", A.shape)
    print(A.obs["condition"].value_counts().to_string())
    A.write(os.path.join(DATA, "GSE171213_qc.h5ad"))
    print("wrote QC object")


if __name__ == "__main__":
    build()
    qc()
