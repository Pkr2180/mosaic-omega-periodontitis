"""Health vs periodontitis analysis.

(A) Differential abundance (compositional, Mann-Whitney).
(B) Single-cell Wilcoxon DE per cell type (discovery, high power).
(C) Leave-sample-out (LOSO) robustness -> separates real disease genes from
    pseudoreplication / single-sample artifacts. This robustness signal becomes
    the ground truth the MOSAIC-Omega consensus engine is scored against.
"""
import os, warnings, json
import numpy as np, pandas as pd
from scipy import stats
import scanpy as sc
warnings.filterwarnings("ignore")

from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT
A_PATH = os.path.join(DATA, "GSE171213_annotated.h5ad")
MIN_CELLS = 40


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.minimum.accumulate((p[o]*n/(np.arange(n)+1))[::-1])[::-1]
    out = np.empty(n); out[o] = np.clip(q, 0, 1); return out


def differential_abundance(A):
    prop = pd.crosstab(A.obs["sample"], A.obs["cell_type"], normalize="index")
    cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"]
    hc = [s for s in prop.index if cond[s] == "Healthy"]
    pds = [s for s in prop.index if cond[s] == "Periodontitis"]
    rows = []
    for ct in prop.columns:
        a, b = prop.loc[hc, ct].values, prop.loc[pds, ct].values
        _, p = stats.mannwhitneyu(b, a, alternative="two-sided")
        rows.append({"cell_type": ct, "mean_HC": a.mean(), "mean_PD": b.mean(),
                     "log2FC": np.log2((b.mean()+1e-4)/(a.mean()+1e-4)), "p": p})
    df = pd.DataFrame(rows); df["FDR"] = bh(df["p"])
    df.sort_values("log2FC", ascending=False).to_csv(
        os.path.join(TAB, "disease_differential_abundance.csv"), index=False)
    return df


def pseudobulk_logcpm(A, ct, samples):
    """log2 CPM pseudobulk vector per sample for one cell type."""
    counts = A.layers["counts"]; smp = A.obs["sample"].values
    mask_ct = (A.obs["cell_type"] == ct).values
    out = {}
    for s in samples:
        m = mask_ct & (smp == s)
        if m.sum() >= 5:
            v = np.asarray(counts[m].sum(0)).ravel().astype(float)
            out[s] = np.log2(v / max(v.sum(), 1) * 1e6 + 1)
    return out


def loso_robustness(pb, hc, pd_, genes_idx, min_abs=0.5):
    """For each gene, fraction of leave-one-sample-out folds preserving disease
    direction with |effect|>min_abs. pb: {sample: logcpm vector}."""
    hc = [s for s in hc if s in pb]; pd_ = [s for s in pd_ if s in pb]
    all_s = hc + pd_
    H = np.vstack([pb[s] for s in hc]); P = np.vstack([pb[s] for s in pd_])
    full = P[:, genes_idx].mean(0) - H[:, genes_idx].mean(0)
    robust = np.zeros(len(genes_idx))
    for drop in all_s:
        h = [s for s in hc if s != drop]; p = [s for s in pd_ if s != drop]
        if not h or not p:
            continue
        Hd = np.vstack([pb[s] for s in h]); Pd = np.vstack([pb[s] for s in p])
        eff = Pd[:, genes_idx].mean(0) - Hd[:, genes_idx].mean(0)
        robust += ((np.sign(eff) == np.sign(full)) & (np.abs(eff) > min_abs)).astype(float)
    return full, robust / max(len(all_s), 1)


def main():
    A = sc.read_h5ad(A_PATH)
    print("loaded", A.shape, flush=True)
    cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"].to_dict()
    hc = [s for s, c in cond.items() if c == "Healthy"]
    pd_ = [s for s, c in cond.items() if c == "Periodontitis"]

    print("\n=== (A) DIFFERENTIAL ABUNDANCE ===")
    da = differential_abundance(A)
    print(da.round(4).sort_values("log2FC", ascending=False).to_string(index=False), flush=True)

    print("\n=== (B/C) SINGLE-CELL DE + LOSO ROBUSTNESS per cell type ===")
    genes = np.array(A.raw.var_names if A.raw is not None else A.var_names)
    gidx = {g: i for i, g in enumerate(genes)}
    summary, candidates = [], {}
    two = A[A.obs["condition"].isin(["Healthy", "Periodontitis"])].copy()
    for ct in two.obs["cell_type"].cat.categories:
        sub = two[two.obs["cell_type"] == ct].copy()
        if (sub.obs["condition"] == "Healthy").sum() < MIN_CELLS or \
           (sub.obs["condition"] == "Periodontitis").sum() < MIN_CELLS:
            continue
        sc.tl.rank_genes_groups(sub, "condition", groups=["Periodontitis"],
                                reference="Healthy", method="wilcoxon", use_raw=True)
        r = sub.uns["rank_genes_groups"]
        d = pd.DataFrame({
            "gene": list(r["names"]["Periodontitis"]),
            "log2FC": list(map(float, r["logfoldchanges"]["Periodontitis"])),
            "score": list(map(float, r["scores"]["Periodontitis"])),
            "pval_adj": list(map(float, r["pvals_adj"]["Periodontitis"])),
        })
        # LOSO robustness on the top disease-up candidates
        up = d[(d["pval_adj"] < 0.05) & (d["log2FC"] > 1)].sort_values("score", ascending=False)
        cand_genes = [g for g in up["gene"].head(12) if g in gidx][:8]
        rob_map = {}
        if len(cand_genes) >= 2:
            pb = pseudobulk_logcpm(A, ct, hc + pd_)
            gi = [gidx[g] for g in cand_genes]
            _, rob = loso_robustness(pb, hc, pd_, gi)
            rob_map = {g: float(r_) for g, r_ in zip(cand_genes, rob)}
        d["loso_robustness"] = d["gene"].map(rob_map)
        d.to_csv(os.path.join(TAB, f"disease_DE_{ct.replace('/','_').replace(' ','_')}.csv"), index=False)
        nsig = int(((d["pval_adj"] < 0.05) & (d["log2FC"].abs() > 1)).sum())
        summary.append({"cell_type": ct,
                        "n_DEG": nsig,
                        "n_up": int(((d.pval_adj<0.05)&(d.log2FC>1)).sum()),
                        "n_down": int(((d.pval_adj<0.05)&(d.log2FC<-1)).sum()),
                        "top_up": ",".join(up["gene"].head(6)),
                        "robust_up": ",".join([g for g in cand_genes if rob_map.get(g,0) >= 0.8][:6])})
        if len(cand_genes) >= 4:
            robust_sorted = sorted(cand_genes, key=lambda g: -rob_map.get(g, 0))
            candidates[ct] = {"candidates": cand_genes,
                              "robustness": rob_map,
                              "truth": robust_sorted[0],
                              "logFC": {g: float(d.loc[d.gene==g,"log2FC"].iloc[0]) for g in cand_genes}}
    sdf = pd.DataFrame(summary).sort_values("n_DEG", ascending=False)
    sdf.to_csv(os.path.join(TAB, "disease_DE_summary.csv"), index=False)
    print(sdf.to_string(index=False), flush=True)

    json.dump(candidates, open(os.path.join(TAB, "disease_candidates.json"), "w"), indent=1)
    print(f"\nsaved MOSAIC-Omega candidate task for {len(candidates)} cell types", flush=True)

    # pan-cell-type robust disease signature
    from collections import Counter
    c = Counter()
    for ct, info in candidates.items():
        for g, rb in info["robustness"].items():
            if rb >= 0.8 and info["logFC"][g] > 1:
                c[g] += 1
    pan = pd.DataFrame(c.most_common(30), columns=["gene", "n_celltypes_robust_up"])
    pan.to_csv(os.path.join(TAB, "disease_pan_signature.csv"), index=False)
    print("\n=== PAN robust disease signature ===")
    print(pan.head(20).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
