"""Precompute a real differential-expression marker task from two periodontal
spatial/single-cell datasets. Cached to data/perio_task.json so the MOSAIC-Omega
adapter stays pure and fast.

Task: for each gingival immune cell type, the correct canonical marker gene.
- Ground truth + verify/attack oracles come from Wilcoxon DE on the PRIMARY set.
- Independent replication is measured on the VALIDATION set.
"""
import json, os
import numpy as np
import scanpy as sc

DATA = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\data"
PRIMARY = os.path.join(DATA, "mucosal_immune.h5ad")     # 23k, gingiva+immune (train/truth)
VALID   = os.path.join(DATA, "mucosal.h5ad")            # 87k, gingiva (external validation)
OUT     = os.path.join(DATA, "perio_task.json")
SEED = 20260807
TOPK_VAL = 25                 # a marker "replicates" if in validation top-K for its type
MIN_CELLS = 40                # min cells per type to trust DE

# 8 immune cell types shared, exact-label, between the two atlases
SHARED = [
    "CD8-positive, alpha-beta T cell", "CD4-positive helper T cell", "B cell",
    "plasma cell", "mast cell", "dendritic cell", "macrophage", "neutrophil",
]
SHORT = {
    "CD8-positive, alpha-beta T cell": "CD8_T",
    "CD4-positive helper T cell": "CD4_T",
    "B cell": "B_cell", "plasma cell": "plasma_cell", "mast cell": "mast_cell",
    "dendritic cell": "dendritic_cell", "macrophage": "macrophage",
    "neutrophil": "neutrophil",
}


def load_gingiva(path):
    A = sc.read_h5ad(path)
    A = A[A.obs["tissue"] == "gingiva"].copy()
    A.var_names = A.var["feature_name"].astype(str).values
    A.var_names_make_unique()
    A = A[A.obs["cell_type"].isin(SHARED)].copy()
    A.obs["cell_type"] = A.obs["cell_type"].astype(str)
    return A


def rank(A):
    """Return {cell_type: {gene: wilcoxon_z}} and ordered marker lists."""
    sc.tl.rank_genes_groups(A, groupby="cell_type", method="wilcoxon", use_raw=False,
                            groups=[c for c in SHARED if (A.obs['cell_type'] == c).sum() >= MIN_CELLS])
    res = A.uns["rank_genes_groups"]
    groups = list(res["names"].dtype.names)
    scores, ordered, padj, lfc = {}, {}, {}, {}
    for g in groups:
        names = list(res["names"][g])
        sc_ = list(map(float, res["scores"][g]))
        pv = list(map(float, res["pvals_adj"][g]))
        fc = list(map(float, res["logfoldchanges"][g]))
        scores[g] = dict(zip(names, sc_))
        padj[g] = dict(zip(names, pv))
        lfc[g] = dict(zip(names, fc))
        ordered[g] = names
    return scores, ordered, padj, lfc


def main():
    rng = np.random.default_rng(SEED)
    print("loading primary (train/truth) ...")
    P = load_gingiva(PRIMARY)
    print("  gingiva cells:", P.n_obs, "types:", dict(P.obs['cell_type'].value_counts()))
    print("loading validation (external) ...")
    V = load_gingiva(VALID)
    print("  gingiva cells:", V.n_obs)

    # common gene universe so truths/candidates exist in both
    common = sorted(set(P.var_names) & set(V.var_names))
    P = P[:, common].copy(); V = V[:, common].copy()
    print("common genes:", len(common))

    pscore, pordered, ppadj, plfc = rank(P)
    vscore, vordered, vpadj, vlfc = rank(V)

    types = [c for c in SHARED if c in pordered and c in vordered]

    # truth = primary rank-1 significant, specific gene for each type
    truth = {}
    for c in types:
        for gene in pordered[c]:
            if ppadj[c].get(gene, 1) < 0.01 and plfc[c].get(gene, 0) > 1.0:
                truth[c] = gene
                break
        truth.setdefault(c, pordered[c][0])

    # distractor pool = other types' rank-1 markers (plausible confusables)
    pool = {c: truth[c] for c in types}
    candidates, train_score, train_sig = {}, {}, {}
    for c in types:
        distract = [pool[o] for o in types if o != c and pool[o] != truth[c]]
        distract = list(dict.fromkeys(distract))
        rng.shuffle(distract)
        opts = [truth[c]] + distract[:3]
        opts = list(dict.fromkeys(opts))
        while len(opts) < 4:  # backfill from primary top genes if needed
            for g in pordered[c]:
                if g not in opts:
                    opts.append(g); break
        rng.shuffle(opts)
        candidates[c] = opts
        # enrichment (Wilcoxon z) of each candidate FOR THIS type, in train
        train_score[c] = {g: float(pscore[c].get(g, 0.0)) for g in opts}
        train_sig[c] = {g: bool(ppadj[c].get(g, 1) < 0.05 and plfc[c].get(g, 0) > 0.25)
                        for g in opts}

    # validation: does the truth marker replicate (top-K in external set)?
    val_top = {c: vordered[c][:TOPK_VAL] for c in types}
    val_rank = {}
    val_replicated = {}
    for c in types:
        vlist = vordered[c]
        r = vlist.index(truth[c]) if truth[c] in vlist else -1
        val_rank[c] = int(r)
        val_replicated[c] = bool(0 <= r < TOPK_VAL)

    task = {
        "provenance": {
            "primary": "CZ CELLxGENE Human Oral & Craniofacial Cell Atlas - Mucosal Immune Atlas (gingiva subset)",
            "validation": "CZ CELLxGENE Human Oral & Craniofacial Cell Atlas - Mucosal Atlas (gingiva subset)",
            "n_primary_gingiva": int(P.n_obs), "n_valid_gingiva": int(V.n_obs),
            "common_genes": len(common), "topk_val": TOPK_VAL, "seed": SEED,
        },
        "types": types, "short": {c: SHORT[c] for c in types},
        "truth": truth, "candidates": candidates,
        "train_score": train_score, "train_sig": train_sig,
        "val_topk": val_top, "val_rank": val_rank, "val_replicated": val_replicated,
        "n_train": {c: int((P.obs['cell_type'] == c).sum()) for c in types},
        "n_val": {c: int((V.obs['cell_type'] == c).sum()) for c in types},
    }
    with open(OUT, "w") as f:
        json.dump(task, f, indent=2)
    print("\nwrote", OUT)
    print("\ncell_type            truth_marker      candidates                         val_rank replicated")
    for c in types:
        print(f"{SHORT[c]:<20}{truth[c]:<18}{str(candidates[c]):<36}{val_rank[c]:>7}   {val_replicated[c]}")


if __name__ == "__main__":
    main()
