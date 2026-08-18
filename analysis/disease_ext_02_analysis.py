"""External cohort (GSE164241): differential abundance + single-cell DE + LOSO
robustness + MOSAIC-Omega consensus. Same methods as the main cohort.
Tables written with ext_ prefix.
"""
import os, warnings, json
import numpy as np, pandas as pd
from scipy import stats
import scanpy as sc
warnings.filterwarnings("ignore")

from disease_03_analysis import bh, pseudobulk_logcpm, loso_robustness
from disease_05_mosaic import DiseaseBiomarkerProblem
from mosaic_omega import MosaicConfig, MosaicOmega

DATA = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\data"
TAB = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\tables"
A_PATH = os.path.join(DATA, "GSE164241_annotated.h5ad")
MIN_CELLS = 40


def main():
    A = sc.read_h5ad(A_PATH); print("external loaded", A.shape, flush=True)
    cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"].to_dict()
    hc = [s for s, c in cond.items() if c == "Healthy"]
    pd_ = [s for s, c in cond.items() if c == "Periodontitis"]
    print(f"HC samples={len(hc)}  PD samples={len(pd_)}", flush=True)

    # differential abundance
    prop = pd.crosstab(A.obs["sample"], A.obs["cell_type"], normalize="index")
    rows = []
    for ct in prop.columns:
        a, b = prop.loc[[s for s in prop.index if s in hc], ct].values, \
               prop.loc[[s for s in prop.index if s in pd_], ct].values
        _, p = stats.mannwhitneyu(b, a, alternative="two-sided")
        rows.append({"cell_type": ct, "mean_HC": a.mean(), "mean_PD": b.mean(),
                     "log2FC": np.log2((b.mean()+1e-4)/(a.mean()+1e-4)), "p": p})
    da = pd.DataFrame(rows); da["FDR"] = bh(da["p"])
    da.sort_values("log2FC", ascending=False).to_csv(os.path.join(TAB, "ext_differential_abundance.csv"), index=False)
    print("\next differential abundance:\n", da.round(3).sort_values("log2FC", ascending=False).to_string(index=False), flush=True)

    # DE + LOSO
    genes = np.array(A.raw.var_names); gidx = {g: i for i, g in enumerate(genes)}
    two = A[A.obs["condition"].isin(["Healthy", "Periodontitis"])].copy()
    summary, candidates = [], {}
    for ct in two.obs["cell_type"].cat.categories:
        sub = two[two.obs["cell_type"] == ct].copy()
        if (sub.obs["condition"] == "Healthy").sum() < MIN_CELLS or \
           (sub.obs["condition"] == "Periodontitis").sum() < MIN_CELLS:
            continue
        sc.tl.rank_genes_groups(sub, "condition", groups=["Periodontitis"],
                                reference="Healthy", method="wilcoxon", use_raw=True)
        r = sub.uns["rank_genes_groups"]
        d = pd.DataFrame({"gene": list(r["names"]["Periodontitis"]),
                          "log2FC": list(map(float, r["logfoldchanges"]["Periodontitis"])),
                          "score": list(map(float, r["scores"]["Periodontitis"])),
                          "pval_adj": list(map(float, r["pvals_adj"]["Periodontitis"]))})
        up = d[(d["pval_adj"] < 0.05) & (d["log2FC"] > 1)].sort_values("score", ascending=False)
        cand_genes = [g for g in up["gene"].head(12) if g in gidx][:8]
        rob_map = {}
        if len(cand_genes) >= 2:
            pb = pseudobulk_logcpm(A, ct, hc + pd_)
            gi = [gidx[g] for g in cand_genes]
            hcp = [s for s in hc if s in pb]; pdp = [s for s in pd_ if s in pb]
            if len(hcp) >= 2 and len(pdp) >= 2:
                _, rob = loso_robustness(pb, hcp, pdp, gi)
                rob_map = {g: float(x) for g, x in zip(cand_genes, rob)}
        d["loso_robustness"] = d["gene"].map(rob_map)
        d.to_csv(os.path.join(TAB, f"ext_DE_{ct.replace('/','_').replace(' ','_')}.csv"), index=False)
        nsig = int(((d.pval_adj < 0.05) & (d.log2FC.abs() > 1)).sum())
        summary.append({"cell_type": ct, "n_DEG": nsig,
                        "n_up": int(((d.pval_adj<0.05)&(d.log2FC>1)).sum()),
                        "n_down": int(((d.pval_adj<0.05)&(d.log2FC<-1)).sum()),
                        "top_up": ",".join(up["gene"].head(6))})
        if len(cand_genes) >= 4 and rob_map:
            best = sorted(cand_genes, key=lambda g: -rob_map.get(g, 0))[0]
            candidates[ct] = {"candidates": cand_genes, "robustness": rob_map, "truth": best,
                              "logFC": {g: float(d.loc[d.gene==g,"log2FC"].iloc[0]) for g in cand_genes}}
    pd.DataFrame(summary).sort_values("n_DEG", ascending=False).to_csv(
        os.path.join(TAB, "ext_DE_summary.csv"), index=False)
    json.dump(candidates, open(os.path.join(TAB, "ext_candidates.json"), "w"), indent=1)
    print(f"\next DE done: {len(candidates)} cell types with candidates", flush=True)

    # MOSAIC-Omega consensus on external candidates
    if candidates:
        problem = DiseaseBiomarkerProblem(candidates)
        accs, robs = [], []; committed = None
        for s in range(5):
            res = MosaicOmega(MosaicConfig(max_iterations=12, seed=20260807+s)).solve(problem)
            a = res.final_candidate.assignment if res.final_candidate else {}
            accs.append(res.metrics["outcome"]["ground_truth_accuracy"]); robs.append(problem.mean_robustness(a))
            if s == 0: committed = a
        naive = problem.naive_signature()
        out = {"mosaic_accuracy_mean": float(np.mean(accs)), "mosaic_mean_robustness": float(np.mean(robs)),
               "naive_mean_robustness": float(problem.mean_robustness(naive)),
               "committed": committed, "naive": naive,
               "picks": {problem.info[cid]["cell_type"]: {"mosaic": committed[cid],
                          "mosaic_rob": problem._rob(cid, committed[cid]),
                          "naive": naive[cid], "naive_rob": problem._rob(cid, naive[cid])}
                         for cid in problem._constraints}}
        json.dump(out, open(os.path.join(TAB, "ext_mosaic_result.json"), "w"), indent=1)
        print(f"\next MOSAIC: robustness {out['mosaic_mean_robustness']:.3f} vs naive {out['naive_mean_robustness']:.3f}, "
              f"accuracy {out['mosaic_accuracy_mean']:.3f}", flush=True)


if __name__ == "__main__":
    main()
