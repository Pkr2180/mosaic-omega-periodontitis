# Data

The raw and processed single-cell files are **not stored in this repository**
(they are several gigabytes and exceed GitHub file limits). They are all public
and can be re-downloaded from the original repositories. Analysis outputs
(`../figures`, `../tables`) and the manuscript (`../manuscript`) are included, so
the results can be inspected without re-downloading.

## Datasets used

| Role | Accession | Source | What to download |
|---|---|---|---|
| Main cohort (disease) | **GSE171213** | NCBI GEO | `GSE171213_AllSample.counts.tsv.gz` + series matrix |
| External cohort (disease) | **GSE164241** | NCBI GEO | `GSE164241_RAW.tar` (10x per-sample matrices) |
| Marker positive control (healthy atlas) | CZ CELLxGENE — Human Oral & Craniofacial Cell Atlas | cellxgene.cziscience.com | Mucosal Immune Atlas + Mucosal Atlas `.h5ad` (gingiva) |

## How to rebuild

From the repository root, after `pip install -e .` and `pip install -r requirements.txt`:

```bash
# disease cohorts
python analysis/disease_01_build.py        # -> data/GSE171213_qc.h5ad
python analysis/disease_02_annotate.py      # -> data/GSE171213_annotated.h5ad
python analysis/disease_ext_01_build.py     # -> data/GSE164241_annotated.h5ad
python analysis/disease_03_analysis.py
python analysis/disease_05_mosaic.py
python analysis/overfitting_correction.py
python analysis/overfitting_correction2_programs.py
python analysis/disease_04_figures.py
```

The download URLs are embedded in the build scripts. `perio_task.json`
(the marker-control task spec) is small and kept in this folder.

> Note: the analysis scripts currently use absolute paths set for the original
> machine. Update the `ROOT`/`DATA` variables at the top of each script to your
> local clone path before re-running.
