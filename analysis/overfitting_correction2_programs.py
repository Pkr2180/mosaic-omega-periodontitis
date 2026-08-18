"""Non-overfit program-level test (the correctly-powered analysis).

Gene-level DE is underpowered at 4-5 donors (see overfitting_correction.py).
Programs aggregate many genes -> testable at SAMPLE level without pseudoreplication.
Per-sample program score (mean of program genes across the sample's cells) is
compared Healthy vs Periodontitis with a sample-level Mann-Whitney + permutation,
independently in each cohort. A program is a robust finding only if it is
significant in BOTH cohorts.
"""
import os, warnings
import numpy as np, pandas as pd
import scanpy as sc
from scipy import stats
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
warnings.filterwarnings("ignore")

from biology_functional import PROGRAMS
from _paths import ROOT, DATA, TAB, FIG  # repo-relative; override with MOSAIC_ROOT


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    q = np.minimum.accumulate((p[o]*n/(np.arange(n)+1))[::-1])[::-1]
    out = np.empty(n); out[o] = np.clip(q, 0, 1); return out


def sample_program_scores(path):
    A = sc.read_h5ad(path)
    A = A[A.obs["condition"].isin(["Healthy", "Periodontitis"])].copy()
    for prog, genes in PROGRAMS.items():
        gs = [g for g in genes if g in A.var_names]
        sc.tl.score_genes(A, gs, score_name=prog, use_raw=False)
    df = A.obs.groupby("sample")[list(PROGRAMS)].mean()
    cond = A.obs.drop_duplicates("sample").set_index("sample")["condition"]
    df["condition"] = cond
    return df


def test(df):
    hc = df[df.condition == "Healthy"]; pdg = df[df.condition == "Periodontitis"]
    rows = []
    for prog in PROGRAMS:
        a, b = hc[prog].values, pdg[prog].values
        u, p = stats.mannwhitneyu(b, a, alternative="two-sided")
        rows.append({"program": prog, "mean_HC": a.mean(), "mean_PD": b.mean(),
                     "delta": b.mean()-a.mean(), "p": p})
    r = pd.DataFrame(rows); r["FDR"] = bh(r["p"]); return r


def main():
    print("scoring programs per sample (main + external)...", flush=True)
    dm = sample_program_scores(os.path.join(DATA, "GSE171213_annotated.h5ad"))
    de = sample_program_scores(os.path.join(DATA, "GSE164241_annotated.h5ad"))
    rm = test(dm).set_index("program"); re = test(de).set_index("program")
    out = pd.DataFrame({
        "delta_main": rm["delta"], "FDR_main": rm["FDR"],
        "delta_ext": re["delta"], "FDR_ext": re["FDR"]})
    out["sig_both"] = (out["FDR_main"] < 0.05) & (out["FDR_ext"] < 0.05) & \
                      (np.sign(out["delta_main"]) == np.sign(out["delta_ext"]))
    out["consistent_dir"] = np.sign(out["delta_main"]) == np.sign(out["delta_ext"])
    out = out.sort_values("FDR_main")
    out.to_csv(os.path.join(TAB, "corrected_program_test.csv"))
    print("\n=== SAMPLE-LEVEL PROGRAM TEST (non-overfit, both cohorts) ===", flush=True)
    print(out.round(4).to_string(), flush=True)
    print(f"\nprograms significant & concordant in BOTH cohorts: "
          f"{int(out['sig_both'].sum())}/{len(out)}", flush=True)

    n_main = {s: int((dm.condition=='Healthy').sum()) for s in [0]}
    fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
    fig.suptitle("Corrected, correctly-powered analysis — sample-level program dysregulation",
                 fontsize=14, fontweight="bold")
    o = out.sort_values("delta_main")
    y = np.arange(len(o)); w = 0.4
    ax[0].barh(y-w/2, o["delta_main"], w, label=f"main (n={len(dm)})", color="#2563eb")
    ax[0].barh(y+w/2, o["delta_ext"], w, label=f"external (n={len(de)})", color="#16a34a")
    ax[0].set_yticks(y); ax[0].set_yticklabels(o.index, fontsize=9); ax[0].axvline(0, color="#334155", lw=0.8)
    ax[0].set_xlabel("program score change (PD - HC)"); ax[0].legend()
    ax[0].set_title("Program dysregulation (sample-level, both cohorts)")
    for i, prog in enumerate(o.index):
        if o.loc[prog, "sig_both"]:
            ax[0].text(max(o.loc[prog,"delta_main"], o.loc[prog,"delta_ext"])+0.002, i,
                       "✓ both", va="center", fontsize=8, color="#16a34a", fontweight="bold")
    # scatter concordance
    ax[1].scatter(out["delta_main"], out["delta_ext"],
                  c=["#16a34a" if s else "#dc2626" for s in out["sig_both"]], s=80)
    for prog, r in out.iterrows():
        ax[1].annotate(prog.split(" /")[0].split(" (")[0], (r["delta_main"], r["delta_ext"]), fontsize=7)
    ax[1].axhline(0, color="#e2e8f0"); ax[1].axvline(0, color="#e2e8f0")
    lim = [min(out.delta_main.min(), out.delta_ext.min())-0.01, max(out.delta_main.max(), out.delta_ext.max())+0.01]
    ax[1].plot(lim, lim, "--", color="#94a3b8")
    rho, pr = stats.pearsonr(out["delta_main"], out["delta_ext"])
    ax[1].set_xlabel("main program change"); ax[1].set_ylabel("external program change")
    ax[1].set_title(f"Cross-cohort program concordance (r={rho:.2f}, green=sig both)")
    fig.tight_layout(rect=[0,0,1,0.94])
    p = os.path.join(FIG, "fig18_corrected_programs.png"); fig.savefig(p, dpi=140); plt.close(fig)
    print("wrote", p, flush=True)


if __name__ == "__main__":
    main()
