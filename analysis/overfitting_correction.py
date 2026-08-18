"""Overfitting check + correction.

Problem 1 (pseudoreplication): single-cell Wilcoxon DE treats cells as
independent replicates -> inflated significance. Fix: PSEUDOBULK (sample x cell
type) + exact/large PERMUTATION test (sample-level null, assumption-free).

Problem 2 (circularity/target leakage): MOSAIC robustness was computed in the
same cohort used to evaluate it. Fix: FULLY BLIND cross-cohort test -- select &
robustness-rank on cohort A only, freeze, test replication on cohort B (which
never informs selection), vs naive and vs a random-gene baseline.
"""
import os, warnings, json, itertools, math
import numpy as np, pandas as pd
import scanpy as sc
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

from mosaic_omega import MosaicConfig, MosaicOmega
from disease_05_mosaic import DiseaseBiomarkerProblem

ROOT = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1"
DATA, TAB, FIG = ROOT+r"\data", ROOT+r"\tables", ROOT+r"\figures"
MAIN = os.path.join(DATA, "GSE171213_annotated.h5ad")
EXT = os.path.join(DATA, "GSE164241_annotated.h5ad")
MIN_CELLS, MIN_SAMP, MAX_EXACT, N_RAND = 10, 3, 400, 1000
rng = np.random.default_rng(20260807)


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.minimum.accumulate((p[o]*n/(np.arange(n)+1))[::-1])[::-1]
    out = np.empty(n); out[o] = np.clip(q, 0, 1); return out


def pseudobulk(A, ct):
    """log2 CPM pseudobulk: samples x genes for one cell type."""
    counts = A.layers["counts"]; smp = A.obs["sample"].values
    cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"].to_dict()
    mask = (A.obs["cell_type"] == ct).values
    rows, samples, conds = [], [], []
    for s in pd_unique(smp):
        m = mask & (smp == s)
        if m.sum() >= MIN_CELLS and cond[s] in ("Healthy", "Periodontitis"):
            v = np.asarray(counts[m].sum(0)).ravel().astype(float)
            rows.append(np.log2(v / max(v.sum(), 1) * 1e6 + 1))
            samples.append(s); conds.append(cond[s])
    if not rows:
        return None
    genes = np.array(A.raw.var_names if A.raw is not None else A.var_names)
    return {"pb": np.vstack(rows), "cond": np.array(conds), "samples": samples, "genes": genes}


def pd_unique(x):
    seen = []; [seen.append(s) for s in x if s not in seen]; return seen


def perm_de(pbd):
    pb, cond, genes = pbd["pb"], pbd["cond"], pbd["genes"]
    hc = np.where(cond == "Healthy")[0]; pdd = np.where(cond == "Periodontitis")[0]
    n, k = len(cond), len(pdd)
    if len(hc) < MIN_SAMP or len(pdd) < MIN_SAMP:
        return None
    expr = pb.mean(0) > 1.0
    X = pb[:, expr]; g = genes[expr]
    obs = X[pdd].mean(0) - X[hc].mean(0)                      # log2FC
    idx = np.arange(n)
    total = math.comb(n, k)
    if total <= MAX_EXACT:
        perms = [np.array(c) for c in itertools.combinations(idx, k)]
    else:
        perms = [rng.choice(idx, k, replace=False) for _ in range(N_RAND)]
    ge = np.ones(len(g))                                       # count |null|>=|obs|
    aobs = np.abs(obs)
    for pset in perms:
        mask = np.zeros(n, bool); mask[pset] = True
        stat = X[mask].mean(0) - X[~mask].mean(0)
        ge += (np.abs(stat) >= aobs)
    p = ge / (len(perms) + 1)
    fdr = bh(p)
    return pd.DataFrame({"gene": g, "log2FC": obs, "p_perm": p, "FDR": fdr})


def loso(pbd, genes_idx):
    pb, cond = pbd["pb"], pbd["cond"]
    hc = np.where(cond == "Healthy")[0]; pdd = np.where(cond == "Periodontitis")[0]
    full = pb[pdd][:, genes_idx].mean(0) - pb[hc][:, genes_idx].mean(0)
    rob = np.zeros(len(genes_idx)); folds = 0
    for drop in range(len(cond)):
        h = hc[hc != drop]; p = pdd[pdd != drop]
        if len(h) < 2 or len(p) < 2:
            continue
        folds += 1
        eff = pb[p][:, genes_idx].mean(0) - pb[h][:, genes_idx].mean(0)
        rob += ((np.sign(eff) == np.sign(full)) & (np.abs(eff) > 0.5))
    return rob / max(folds, 1)


def build_cohort(path):
    A = sc.read_h5ad(path)
    cts = [c for c in A.obs["cell_type"].cat.categories]
    out = {}
    for ct in cts:
        pbd = pseudobulk(A, ct)
        if pbd is None:
            continue
        de = perm_de(pbd)
        if de is None:
            continue
        out[ct] = {"pbd": pbd, "de": de}
    return out


def main():
    print("building pseudobulk + permutation DE (main)...", flush=True)
    M = build_cohort(MAIN)
    print("building pseudobulk + permutation DE (external)...", flush=True)
    E = build_cohort(EXT)

    # ---- (A) overfitting comparison: single-cell vs pseudobulk DEG counts ----
    cmp_rows = []
    for ct in M:
        ctf = ct.replace('/', '_').replace(' ', '_')
        scf = os.path.join(TAB, f"disease_DE_{ctf}.csv")
        sc_deg = 0
        if os.path.exists(scf):
            d = pd.read_csv(scf)
            sc_deg = int(((d.pval_adj < 0.05) & (d.log2FC.abs() > 1)).sum())
        pb_deg = int(((M[ct]["de"].FDR < 0.05) & (M[ct]["de"].log2FC.abs() > 1)).sum())
        cmp_rows.append({"cell_type": ct, "singlecell_DEG": sc_deg, "pseudobulk_perm_DEG": pb_deg})
        M[ct]["de"].to_csv(os.path.join(TAB, f"corrected_DE_main_{ctf}.csv"), index=False)
    cmp = pd.DataFrame(cmp_rows).sort_values("singlecell_DEG", ascending=False)
    cmp.to_csv(os.path.join(TAB, "overfitting_comparison.csv"), index=False)
    print("\n=== OVERFITTING: single-cell (pseudoreplicated) vs pseudobulk-permutation DEGs ===", flush=True)
    print(cmp.to_string(index=False), flush=True)
    infl = cmp["singlecell_DEG"].sum() / max(cmp["pseudobulk_perm_DEG"].sum(), 1)
    print(f"\ninflation factor (single-cell / pseudobulk) = {infl:.1f}x", flush=True)

    # ---- (B) corrected cross-cohort concordance (pseudobulk effect sizes) ----
    conc = []
    for ct in set(M) & set(E):
        j = M[ct]["de"].merge(E[ct]["de"], on="gene", suffixes=("_m", "_e"))
        if len(j) < 20:
            continue
        from scipy.stats import spearmanr
        rho, _ = spearmanr(j.log2FC_m, j.log2FC_e)
        up = j[(j.FDR_m < 0.1) & (j.log2FC_m > 0.5)]
        rep = ((up.log2FC_e > 0) & (up.FDR_e < 0.25)).mean() if len(up) else np.nan
        conc.append({"cell_type": ct, "n_genes": len(j), "spearman_pb": rho,
                     "n_up": len(up), "replication_rate": rep})
    conc = pd.DataFrame(conc)
    conc.to_csv(os.path.join(TAB, "corrected_crosscohort.csv"), index=False)
    print("\n=== CORRECTED cross-cohort concordance (pseudobulk) ===", flush=True)
    print(conc.round(3).to_string(index=False), flush=True)

    # ---- (C) fully blind biomarker test (select A, freeze, test B) ----
    def candidates_from(cohort):
        cand = {}
        for ct, d in cohort.items():
            de = d["de"]; pbd = d["pbd"]
            up = de[(de.FDR < 0.1) & (de.log2FC > 0.5)].sort_values("p_perm").head(8)
            genes = up["gene"].tolist()
            if len(genes) < 4:
                continue
            gi = [np.where(pbd["genes"] == g)[0][0] for g in genes]
            rob = loso(pbd, gi)
            rob_map = {g: float(r) for g, r in zip(genes, rob)}
            cand[ct] = {"candidates": genes, "robustness": rob_map,
                        "truth": max(rob_map, key=rob_map.get),
                        "logFC": {g: float(de.loc[de.gene==g,"log2FC"].iloc[0]) for g in genes}}
        return cand

    def replicates_in(cohort, ct, gene):
        if ct not in cohort:
            return None
        de = cohort[ct]["de"]; row = de[de.gene == gene]
        if not len(row):
            return None
        return bool(row.log2FC.iloc[0] > 0 and row.p_perm.iloc[0] < 0.05)

    blind_rows = []
    for src, dst, sc_c, ds_c in [("main", "ext", M, E), ("ext", "main", E, M)]:
        cand = candidates_from(sc_c)
        if not cand:
            continue
        prob = DiseaseBiomarkerProblem(cand)
        res = MosaicOmega(MosaicConfig(max_iterations=12, seed=20260807)).solve(prob)
        a = res.final_candidate.assignment if res.final_candidate else {}
        naive = prob.naive_signature()
        short2ct = {ct.replace(" ","_").replace("(","").replace(")","").replace("/","_"): ct for ct in cand}
        mos_rep, nai_rep, rnd_rep, tested = 0, 0, 0, 0
        for cid in prob._constraints:
            ct = short2ct[cid]
            mg, ng = a.get(cid), naive[cid]
            r_m = replicates_in(ds_c, ct, mg); r_n = replicates_in(ds_c, ct, ng)
            # random baseline: a random expressed gene tested in dst
            if ct in ds_c:
                rg = ds_c[ct]["de"]["gene"].sample(1, random_state=int(tested)+1).iloc[0]
                r_r = replicates_in(ds_c, ct, rg)
            else:
                r_r = None
            if r_m is not None:
                tested += 1; mos_rep += int(r_m)
                nai_rep += int(r_n) if r_n is not None else 0
                rnd_rep += int(r_r) if r_r is not None else 0
        blind_rows.append({"direction": f"{src}->{dst}", "n_tested": tested,
                           "MOSAIC_replicated": mos_rep, "naive_replicated": nai_rep,
                           "random_replicated": rnd_rep,
                           "MOSAIC_rate": mos_rep/max(tested,1),
                           "naive_rate": nai_rep/max(tested,1),
                           "random_rate": rnd_rep/max(tested,1)})
    blind = pd.DataFrame(blind_rows)
    blind.to_csv(os.path.join(TAB, "blind_biomarker_test.csv"), index=False)
    print("\n=== FULLY BLIND cross-cohort biomarker replication (non-circular) ===", flush=True)
    print(blind.round(3).to_string(index=False), flush=True)

    make_fig(cmp, conc, blind)


def make_fig(cmp, conc, blind):
    fig, ax = plt.subplots(1, 3, figsize=(19, 6))
    fig.suptitle("Overfitting correction — pseudobulk permutation DE + blind cross-cohort test",
                 fontsize=15, fontweight="bold")
    x = np.arange(len(cmp)); w = 0.4
    ax[0].bar(x-w/2, cmp["singlecell_DEG"], w, label="single-cell (overfit)", color="#dc2626")
    ax[0].bar(x+w/2, cmp["pseudobulk_perm_DEG"], w, label="pseudobulk perm (corrected)", color="#2563eb")
    ax[0].set_xticks(x); ax[0].set_xticklabels(cmp["cell_type"], rotation=45, ha="right", fontsize=8)
    ax[0].set_ylabel("# DEGs"); ax[0].legend(); ax[0].set_yscale("symlog")
    ax[0].set_title("Pseudoreplication inflation removed")
    c = conc.dropna(subset=["spearman_pb"]).sort_values("spearman_pb")
    ax[1].barh(c["cell_type"], c["spearman_pb"], color="#7c3aed")
    ax[1].set_xlabel("cross-cohort Spearman (pseudobulk log2FC)")
    ax[1].set_title("Corrected effect-size concordance"); ax[1].axvline(0, color="#334155", lw=0.8)
    if len(blind):
        b = blind.iloc[0]
        cats = ["random", "naive\nWilcoxon", "MOSAIC-Ω"]
        vals = [b["random_rate"], b["naive_rate"], b["MOSAIC_rate"]]
        ax[2].bar(cats, vals, color=["#94a3b8", "#f59e0b", "#2563eb"])
        for i, v in enumerate(vals):
            ax[2].text(i, v+0.02, f"{v:.2f}", ha="center", fontweight="bold")
        ax[2].set_ylim(0, 1.05); ax[2].set_ylabel("blind replication rate in held-out cohort")
        ax[2].set_title(f"Blind biomarker test ({b['direction']}, n={int(b['n_tested'])})")
    fig.tight_layout(rect=[0,0,1,0.95])
    p = os.path.join(FIG, "fig17_overfitting_correction.png"); fig.savefig(p, dpi=140); plt.close(fig)
    print("wrote", p, flush=True)


if __name__ == "__main__":
    main()
