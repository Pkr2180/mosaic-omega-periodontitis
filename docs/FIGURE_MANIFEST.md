# Figure manifest & consistency audit

Audited all figures (2026-08-09 and 08-10) for internal consistency after the
overfitting correction. Overfit/superseded figures were archived to
`figures/superseded_overfit/`; affected figures were regenerated honestly.

## ACTIVE figures (valid, mutually consistent)

### A. Architecture demonstration (MOSAIC-Ω mechanics)
| Figure | Shows | Status |
|---|---|---|
| fig1_architecture.png | FESC agent graph, dynamic roster, fail-safe loop, EVOI | valid |
| fig2_loop_graph.png | topology rewiring, blinded jury, calibration, sovereignty | valid |
| fig15_ai_metrics.png | FESC EVOI, full architecture metric suite, `score_truth_gap`=+0.34 (overconfidence detector firing) | valid (honest self-assessment) |

### B. Cell-type marker-recovery sub-study (healthy oral atlas, CELLxGENE)
This is a SEPARATE task from the disease study: does the architecture recover
canonical cell-type markers, validated across independent studies.
| Figure | Shows | Status |
|---|---|---|
| fig3_real_biology.png | committed markers dotplot; **on-figure caveat: shared-donor validation** | valid (caveated) |
| fig4_confusion_prf1.png | confusion matrix + per-class P/R/F1 (donor-disjoint CV) | valid |
| fig5_accuracy_independent.png | donor-KFold 0.92, **cross-study 0.95**; plasma marker honestly fails cross-study | valid |
| fig6_roc_calibration.png | verifier ROC + reliability diagram | valid |
| fig7_loss_curves.png | per-iteration accuracy/loss (epoch analog) | valid |

Note: fig3 uses shared-donor validation (flagged on the figure); fig5 provides the
proper cross-study test (7/8 markers replicate; plasma-cell marker does not). Consistent.

### C. Periodontitis disease study (real, 2 cohorts)
| Figure | Shows | Status |
|---|---|---|
| fig8_disease_atlas.png | main-cohort atlas + composition + **abundance marked for cross-cohort concordance** | regenerated honest |
| fig11_external_atlas.png | external cohort (GSE164241) atlas + composition + abundance | valid |
| fig19_replicated_findings.png | **what survives correction**: Plasma↑ & Fibroblast↓ in both cohorts | valid |

### D. Overfitting corrections (the authoritative disease verdict)
| Figure | Shows | Status |
|---|---|---|
| fig17_overfitting_correction.png | single-cell vs pseudobulk DEGs (~2900× inflation), blind test | valid |
| fig18_corrected_programs.png | sample-level program test: 0/7 significant-both | valid |

## ARCHIVED — superseded / overfit (`figures/superseded_overfit/`)
| Figure | Why removed |
|---|---|
| fig9_disease_DE.png | single-cell DE volcanoes (1,851 DEGs) — pseudoreplicated; contradicted by fig17 (0 DEGs corrected) |
| fig10_mosaic_consensus.png | MOSAIC robustness win — circular (oracle used the eval metric); superseded by blind test (fig17) |
| fig12_crosscohort_replication.png | replication rates computed from overfit single-cell DE; superseded by fig17/fig19 |
| fig13_crosscohort_mosaic_metrics.png | included invalid "MOSAIC 3/3 biomarkers replicate" claim |
| fig14_ai_ablation.png | ablation of the circular robustness metric — not a valid biomarker claim |
| fig16_biology_programs.png | "4 programs replicate" via hypergeometric on overfit DEG lists; **directly contradicted by fig18 (0/7)** |

## Consistency resolution — the single source of truth
- **Gene-level DE and MOSAIC biomarker results are NOT valid** (pseudoreplication + circularity). See fig17/fig18.
- **Only sample-level compositional findings replicate**: Plasma↑, Fibroblast↓ (fig19, fig8).
- The architecture-mechanics (fig1,2,15) and marker-recovery (fig3–7) figures are a separate,
  honest demonstration and remain valid.
