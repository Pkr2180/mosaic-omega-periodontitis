# MOSAIC-Ω on real periodontitis single-cell omics — results

> ## ⚠️ Read this first — most of the gene-level results below are RETRACTED
>
> This document is written **chronologically**: it records the original analysis, then
> the overfitting audit that overturned much of it. Sections 1–3, the external-validation
> DEG/biomarker claims, and the functional-program table are **superseded** by
> [OVERFITTING CHECK & CORRECTION](#overfitting-check--correction-read-this-before-trusting-anything-above)
> at the end. Do not cite them.
>
> **What survives correction:**
>
> | Claim | Status |
> |---|---|
> | Plasma-cell expansion (both cohorts; ext FDR 0.041) | ✅ holds |
> | Fibroblast relative contraction (both cohorts) | ✅ holds |
> | 2,897 single-cell DEGs | ❌ **0** by donor-level pseudobulk permutation (~2,900× inflation) |
> | "MOSAIC 3/3 biomarkers replicate" | ❌ does not survive a blind test |
> | "4 programs replicate" | ❌ **0/7** by correctly-powered sample-level test |
>
> The study is **underpowered (n=4–5 donors/group)**. Only *compositional* findings are
> defensible. `docs/FIGURE_MANIFEST.md` records which figures are active and which were
> archived to `figures/superseded_overfit/`.

**Data (real, public):** GSE171213, human periodontal tissue scRNA-seq.
12 donors — 4 healthy (HC), 5 severe chronic periodontitis (PD), 3 post-treatment (PDT).
Built from raw counts → QC → **35,323 cells × 28,339 genes** (9,820 HC / 13,817 PD / 11,686 PDT).

## Pipeline (all executed; scripts in repo)
1. `disease_01_build.py` — sparse AnnData + QC (mt<20%, 200–6000 genes/cell).
2. `disease_02_annotate.py` — Leiden (29 clusters) → 11 cell types via canonical marker panels.
3. `disease_03_analysis.py` — differential abundance + single-cell Wilcoxon DE + **leave-sample-out (LOSO) robustness**.
4. `disease_05_mosaic.py` — **MOSAIC-Ω adversarial-consensus biomarker selection**.
5. `disease_04_figures.py` — figures 8–10.

## Findings (as originally reported) — ⚠️ sections 2 and 3 RETRACTED, see correction

### 1. Differential abundance (Mann-Whitney, per-sample proportions)
- **Up in disease:** Endothelial (log2FC +4.0, FDR 0.087), Epithelial (+2.7, FDR 0.087), Mast (+1.4), Plasma (+1.1), DC (+0.6).
- **Down in disease:** NK (−1.4), CD8 T (−0.8), CD4 T (−0.7), Fibroblast (−0.6).
- Consistent with known periodontitis immunopathology (plasma/neutrophil/endothelial expansion, stromal & NK contraction).

### 2. Single-cell DE (Wilcoxon, PD vs HC) — ❌ RETRACTED (pseudoreplication, 0 DEGs corrected)
- Largest dysregulation: **Fibroblast (1,851 DEGs)** — collagen remodeling up (COL3A1/5A2/6A1/6A3, CALD1).
- **Endothelial:** SELE (E-selectin), COL4A1 up — leukocyte-adhesion / inflammation.
- **Dendritic:** MHC-II up (HLA-DRB6, HLA-DQA2), FPR3.
- Pan-cell-type robust signature: **IGKC, FDCSP, RGS1, HLA-DQA2, SELE, COL4A1** (FDCSP and SELE are established periodontitis-associated genes).

### 3. MOSAIC-Ω adversarial consensus — ❌ RETRACTED (circular oracle; fails blind test)
Task: commit to one reproducible disease biomarker per cell type from the top DE
candidates; verify/attack oracles grounded in real LOSO reproducibility.
- **Mean LOSO robustness: MOSAIC-Ω 0.922 vs naive Wilcoxon-top 0.811 (+0.11 absolute, ~14% relative).**
- Clear rescues: B cell → ACTG1 (0.56→1.00, rejected ribosomal RPL37A); Neutrophil → SERPINA1 (0.11→0.78, rejected fragile CD55).
- Accuracy vs LOSO-robust truth: 0.80 (8/10). Safety: blinding-leak 0.0, anchoring 0.0, contract compliance 1.0.
- **Interpretation:** falsification/jury preferentially reject pseudoreplication artifacts
  (mitochondrial/ribosomal/single-sample-driven genes) that inflate naive single-cell DE.

## Honest limitations (what keeps this short of a Nature submission)
- **Single cohort** *(at the time this section was written; GSE164241 was processed afterwards — see the external-validation section below).*
- **Demonstration, not blind test.** MOSAIC-Ω's oracle uses LOSO robustness, so its edge over
  naive selection is expected-by-design; the honest claim is "it integrates robustness that
  naive DE ignores," not a blinded superiority proof.
- **Data quality.** High median %mt (17.8%) from inflamed tissue; Healthy endothelial count (69)
  is low and its +4.0 log2FC should be read cautiously (possible capture artifact).
- **De-novo annotation**, not expert-curated; small n (4 vs 5) limits pseudobulk power.
- No wet-lab validation, no peer review — the non-negotiables of an actual Nature paper.

## Figure inventory
- fig8_disease_atlas.png — UMAP (cell type, condition), composition, differential abundance
- `superseded_overfit/fig9_disease_DE.png` — volcanoes, pan-signature heatmap (**archived: pseudoreplicated**)
- `superseded_overfit/fig10_mosaic_consensus.png` — MOSAIC-Ω vs naive (**archived: circular metric**)

Tables in `tables/` (differential abundance, per-cell-type DE, candidates, MOSAIC consensus).

---

# External validation — independent cohort GSE164241 (NIH)

**Independent cohort:** GSE164241 (Moutsopoulos lab, NIH) — different lab, patients,
country and platform than the main GSE171213 (Chinese) cohort. 13 healthy-gingiva +
5 periodontitis samples → **94,301 cells** after identical QC/annotation.

## What replicates (as originally reported) — ⚠️ only the compositional item survives
- **Plasma-cell expansion replicates strongly:** main log2FC +1.1 → external **+2.4 (FDR 0.041)**.
  The dominant compositional finding of periodontitis holds across cohorts.
- **DEG replication rate** is high for the strongest signals: Plasma 0.76, Endothelial 0.74,
  Fibroblast 0.72, CD4 T 0.61.
- **Pan-signature: 22/30 genes replicate** (up & significant in ≥1 external cell type);
  IGKC, KLF6, ACTG1 replicate across many cell types.
- **MOSAIC-Ω consensus biomarkers: 3/3 testable biomarkers replicate as robust** in the
  external cohort; MOSAIC external robustness 1.00 vs naive 0.985.

## What does NOT replicate (honest)
- **Genome-wide DE effect-size concordance is ~0** (mean Spearman −0.02, pooled direction
  AUROC 0.53). Most individual per-gene DE calls do **not** reproduce across cohorts — the
  well-known reproducibility ceiling of single-cell DE.
- **Differential-abundance concordance is negative (Pearson r = −0.49)**, driven by the main
  cohort's **endothelial (+4.0) and epithelial (+2.7) artifacts** (main HC endothelial n=69).
  The external cohort (robust n) shows these **down**, i.e. it *corrects* the main-cohort artifact.
- NK, CD8 T, B-cell DEGs replicate poorly (0.13–0.25).

## Interpretation
Cross-cohort replication is **partial and signal-strength-dependent** — exactly the regime
where a robustness filter matters. The compositional signal (plasma expansion), the robust
pan-signature, and the MOSAIC-selected biomarkers reproduce; naive per-gene DE largely does not.
This *motivates* the MOSAIC-Ω adversarial-consensus approach rather than proving superiority
(its oracle uses the robustness metric by design).

---

# Deep AI evaluation (novel architecture)

Full 9-group metric suite on the biomarker task (`tables/ai_disease_full_metrics.csv`).
Key architecture metrics (external run): falsification survival 0.94, blinded jury,
blinding-leak 0.0, anchoring 0.0, branch-isolation 1.0, contract compliance 0.88.

**Honest self-assessment (the novel capability, working):** on the harder external
cohort the overconfidence detector fires — `score_truth_gap = +0.34` (composite belief
0.58 exceeds ground-truth accuracy) and `evoi_calibration_r = −0.65`. The architecture
signals *by itself* that cross-cohort generalization is less reliable than its internal
confidence — exactly the property most agentic systems lack.

**MOSAIC vs naive (robust-biomarker recovery):** main robustness 0.811→**0.922**,
robust-recovery 0.875→**1.00**; external 0.985→1.00. (`tables/ai_disease_classification.csv`)

**Ablation (honest):** removing individual components (falsification / blinding /
universes / pruning) does **not** collapse robustness on this task — the robustness gain
over naive comes from the consensus *integrating* the LOSO signal, while falsification
trades a little robustness for accuracy and blinding preserves independence. So the
ablation shows the components affect accuracy/calibration more than raw robustness here;
it does not prove any single component is solely causal. (`tables/ai_disease_ablation.csv`)

Figures: `superseded_overfit/fig14_ai_ablation.png` (**archived**), fig15_ai_metrics.png (active).

# Biological findings (functional, cross-cohort)

Hypergeometric enrichment of the 1,787-gene disease-up signature against curated
periodontal programs (`tables/biology_functional_enrichment.csv`). **Four programs were reported as
enriched AND replicating in the independent cohort — ❌ RETRACTED; the correctly-powered
sample-level test returns 0/7 (see correction below):**

| Program | fold (main) | FDR | replicates ext |
|---|---|---|---|
| **ECM / collagen remodeling** | 15.1× | 2e-21 | ✓ (6.2×) |
| **Humoral / immunoglobulin (plasma/B)** | 7.9× | 7e-07 | ✓ (6.2×) |
| **Endothelial activation / adhesion** | 7.2× | 2e-03 | ✓ (4.5×) |
| **Complement / neutrophil / innate** | 7.0× | 4e-05 | ✓ (3.2×) |
| Antigen presentation (MHC-II) | 8.5× | 3e-05 | ✗ (main only) |
| Chemokine / TLS | 5.3× | 4e-02 | ✗ |

**Disease model (data-derived):** periodontitis in these cohorts is a **plasma-cell /
antibody-driven chronic lesion** — fibroblasts dominate the transcriptional response
(1,249 up-DEGs, ECM/collagen remodeling), plasma cells expand ~2–5× (humoral Ig program),
with endothelial leukocyte-adhesion activation (SELE, COL4A1) and complement/neutrophil
innate engagement. This matches the classical Page–Schroeder / Berglundh "established
lesion" (plasma-cell dominated) — recovered here de novo and replicated across two
independent cohorts. Program-by-cell-type map in `superseded_overfit/fig16_biology_programs.png` (archived).

**Novelty ↔ biology link:** the programs MOSAIC-Ω's robustness machinery retains are
exactly the ones that replicate independently (ECM, humoral, endothelial, complement);
the fragile programs it/naive-DE would over-call (MHC-II, chemokine/TLS) do **not**
replicate. And the architecture's honest overconfidence signal (`score_truth_gap` flipping
positive on the external cohort) correctly anticipates that not everything generalizes.

Figures: `superseded_overfit/fig16_biology_programs.png` (**archived**). Tables: biology_functional_enrichment.csv,
biology_program_by_celltype.csv, biology_celltype_interpretation.csv.

---

# OVERFITTING CHECK & CORRECTION (read this before trusting anything above)

The single-cell DE and the gene-level MOSAIC results **were overfit**. Corrected analyses:

**1. Pseudoreplication (single-cell Wilcoxon DE) — massive inflation.**
Replacing single-cell Wilcoxon with **pseudobulk (sample-level) + exact permutation** DE:

| level | fibroblast DEGs | total DEGs (10 cell types) |
|---|---|---|
| single-cell Wilcoxon (overfit) | 1,851 | 2,897 |
| pseudobulk permutation (corrected) | 0 | **0** |

**Inflation factor ≈ 2,900×.** With 4–5 donors/group there is no donor-level power to call
individual genes (the exact-permutation p-floor ≈ 1/126 cannot survive genome-wide FDR).
The "1,851 fibroblast DEGs" were pseudoreplication artifacts. (`tables/overfitting_comparison.csv`)

**2. Circularity — gene-level biomarkers do not survive a blind test.**
Fully blind cross-cohort test (select+rank on cohort A, freeze, test on held-out cohort B):
no robust gene-level candidates could even be selected after correction. The earlier
"MOSAIC 3/3 replicate" rested on the overfit DE and does **not** hold up. (`tables/blind_biomarker_test.csv`)

**3. Correctly-powered sample-level program test — 0/7 significant in both cohorts.**
Per-sample program scores, Mann-Whitney per cohort: **0 of 7 programs reach FDR<0.05 with
concordant direction in both cohorts.** Only Humoral/Ig is consistent-direction (up/up) and
near-significant externally (FDR 0.068). The earlier "4 programs replicate" used the overfit
single-cell DEG lists (hypergeometric on inflated gene sets) and does not survive. (`tables/corrected_program_test.csv`)

## What actually survives correction (honest, defensible)
- **Plasma-cell expansion** — consistent direction in both cohorts (main +2.2×, external +5.3×,
  external FDR 0.041), large effect; matches established periodontitis biology.
- **Fibroblast relative contraction** — down in both cohorts.
- These are **compositional** (sample-level, not pseudoreplicated) and directionally reproducible.
- Everything gene-level and program-level is **underpowered / not reproducible** at this sample size.

## Corrected bottom line
The study is **underpowered (n=4–5 donors/group)**; most "findings" were overfit. After correction,
only the **plasma-cell/humoral axis** is directionally robust across cohorts — consistent with the
classical plasma-cell-dominated lesion, but formally significant in only one cohort. Reaching
publishable gene/biomarker conclusions requires **many more donors** + proper pseudobulk
(DESeq2/edgeR) + batch/ambient correction. Corrected figures: fig17, fig18.

## Validation figure/table inventory
- fig11_external_atlas.png — external UMAP, composition, differential abundance
- `superseded_overfit/fig12_crosscohort_replication.png` — replication rates (**archived: built on overfit DE**)
- `superseded_overfit/fig13_crosscohort_mosaic_metrics.png` — external MOSAIC metrics (**archived: invalid claim**)
- tables/: ext_differential_abundance.csv, ext_DE_*.csv, ext_candidates.json, ext_mosaic_result.json,
  crosscohort_abundance.csv, crosscohort_de_concordance.csv, crosscohort_pan_replication.csv,
  crosscohort_mosaic.csv, crosscohort_metrics.csv
