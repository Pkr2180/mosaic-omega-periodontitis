"""Cross-cohort replication: GSE171213 (main) vs GSE164241 (external, independent).

Concordance of differential abundance and per-cell-type DE effect sizes, DEG
replication rate, pan-signature replication, and cross-cohort reproducibility of
the MOSAIC-Omega consensus biomarkers. Produces evaluation-metric tables.
"""
import os, glob, json, warnings
import numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

TAB = r"C:\Users\Pradeep Kumar\Downloads\latest architecture -1\tables"


def de_path(prefix, ct):
    return os.path.join(TAB, f"{prefix}DE_{ct.replace('/','_').replace(' ','_')}.csv")


def shared_celltypes():
    main = {os.path.basename(f)[len("disease_DE_"):-4] for f in glob.glob(os.path.join(TAB,"disease_DE_*.csv"))}
    ext = {os.path.basename(f)[len("ext_DE_"):-4] for f in glob.glob(os.path.join(TAB,"ext_DE_*.csv"))}
    return sorted(main & ext)


def main():
    # ---- differential abundance concordance ----
    da_m = pd.read_csv(os.path.join(TAB, "disease_differential_abundance.csv")).set_index("cell_type")
    da_e = pd.read_csv(os.path.join(TAB, "ext_differential_abundance.csv")).set_index("cell_type")
    common = da_m.index.intersection(da_e.index)
    r_da, p_da = stats.pearsonr(da_m.loc[common,"log2FC"], da_e.loc[common,"log2FC"])
    da_join = pd.DataFrame({"main_log2FC": da_m.loc[common,"log2FC"], "ext_log2FC": da_e.loc[common,"log2FC"]})
    da_join.to_csv(os.path.join(TAB, "crosscohort_abundance.csv"))
    print(f"Differential-abundance concordance (Pearson r) = {r_da:.3f}  (p={p_da:.3g})", flush=True)

    # ---- per-cell-type DE concordance + replication ----
    cts = shared_celltypes()
    rows, pooled_main_lfc, pooled_ext_up = [], [], []
    for ctf in cts:
        try:
            m = pd.read_csv(os.path.join(TAB, f"disease_DE_{ctf}.csv"))
            e = pd.read_csv(os.path.join(TAB, f"ext_DE_{ctf}.csv"))
        except Exception:
            continue
        if "gene" not in m.columns or "gene" not in e.columns or len(m) == 0 or len(e) == 0:
            continue
        j = m.merge(e, on="gene", suffixes=("_m", "_e"))
        if len(j) < 20:
            continue
        rho, _ = stats.spearmanr(j["log2FC_m"], j["log2FC_e"])
        # main DEGs (up) that replicate in ext (same direction + nominal sig)
        up = j[(j["pval_adj_m"] < 0.05) & (j["log2FC_m"] > 1)]
        rep = ((up["log2FC_e"] > 0) & (up["pval_adj_e"] < 0.05)).mean() if len(up) else np.nan
        dir_conc = ((np.sign(j["log2FC_m"]) == np.sign(j["log2FC_e"]))
                    [(j.pval_adj_m<0.05)]).mean()
        rows.append({"cell_type": ctf, "n_genes": len(j), "spearman_lfc": rho,
                     "n_main_up_DEG": int(len(up)), "replication_rate": rep,
                     "direction_concordance": dir_conc})
        pooled_main_lfc.extend(j.loc[j.pval_adj_m<0.05, "log2FC_m"].tolist())
        pooled_ext_up.extend((j.loc[j.pval_adj_m<0.05, "log2FC_e"] > 0).astype(int).tolist())
    cc = pd.DataFrame(rows)
    cc.to_csv(os.path.join(TAB, "crosscohort_de_concordance.csv"), index=False)
    print("\nPer-cell-type DE concordance:\n", cc.round(3).to_string(index=False), flush=True)

    # pooled AUROC: does main effect size predict external up-direction among main-sig genes?
    auroc = np.nan
    if len(set(pooled_ext_up)) == 2:
        auroc = roc_auc_score(pooled_ext_up, pooled_main_lfc)

    # ---- pan-signature replication ----
    pan = pd.read_csv(os.path.join(TAB, "disease_pan_signature.csv"))["gene"].tolist()
    pan_rep = []
    for g in pan:
        hits = 0; tot = 0
        for ctf in cts:
            try:
                e = pd.read_csv(os.path.join(TAB, f"ext_DE_{ctf}.csv"))
            except Exception:
                continue
            if "gene" not in e.columns:
                continue
            row = e[e["gene"] == g]
            if len(row):
                tot += 1
                if row["log2FC"].iloc[0] > 0 and row["pval_adj"].iloc[0] < 0.05:
                    hits += 1
        pan_rep.append({"gene": g, "ext_celltypes_up_sig": hits, "ext_celltypes_tested": tot})
    pan_df = pd.DataFrame(pan_rep)
    pan_df.to_csv(os.path.join(TAB, "crosscohort_pan_replication.csv"), index=False)

    # ---- MOSAIC consensus cross-cohort reproducibility ----
    mos_main = json.load(open(os.path.join(TAB, "mosaic_disease_result.json")))
    ext_cand = json.load(open(os.path.join(TAB, "ext_candidates.json"))) if os.path.exists(os.path.join(TAB,"ext_candidates.json")) else {}
    # for each main-committed biomarker, is that gene robust in the external cohort?
    mos_rep = []
    short2ct = {ct.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_"): ct
                for ct in ext_cand}
    for cid, gene in mos_main["committed"].items():
        ct = short2ct.get(cid)
        ext_rob = ext_cand.get(ct, {}).get("robustness", {}).get(gene) if ct else None
        mos_rep.append({"cell_type": cid, "mosaic_biomarker": gene,
                        "ext_robustness": ext_rob,
                        "replicates_ext": (ext_rob is not None and ext_rob >= 0.8)})
    mos_df = pd.DataFrame(mos_rep)
    mos_df.to_csv(os.path.join(TAB, "crosscohort_mosaic.csv"), index=False)

    # ---- evaluation-metric summary ----
    metrics = {
        "abundance_concordance_pearson_r": round(float(r_da), 3),
        "mean_DE_spearman": round(float(np.nanmean(cc["spearman_lfc"])), 3) if len(cc) else None,
        "mean_replication_rate": round(float(np.nanmean(cc["replication_rate"])), 3) if len(cc) else None,
        "mean_direction_concordance": round(float(np.nanmean(cc["direction_concordance"])), 3) if len(cc) else None,
        "pooled_effect_direction_AUROC": round(float(auroc), 3) if auroc==auroc else None,
        "pan_signature_genes_replicated": int((pan_df["ext_celltypes_up_sig"] > 0).sum()),
        "pan_signature_total": int(len(pan_df)),
        "mosaic_biomarkers_replicated": int(mos_df["replicates_ext"].sum()),
        "mosaic_biomarkers_testable": int(mos_df["ext_robustness"].notna().sum()),
    }
    pd.DataFrame([metrics]).T.rename(columns={0: "value"}).to_csv(os.path.join(TAB, "crosscohort_metrics.csv"))
    print("\n=== CROSS-COHORT EVALUATION METRICS ===", flush=True)
    for k, v in metrics.items():
        print(f"  {k}: {v}", flush=True)


if __name__ == "__main__":
    main()
