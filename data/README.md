# Data

The raw and processed single-cell files are **not stored in this repository**
(they are several gigabytes and exceed GitHub file limits). They are all public
and can be re-downloaded from the original repositories. Analysis outputs
(`../figures`, `../tables`) are included, so the results can be inspected without
re-downloading. The manuscript files are intentionally not part of this repository.

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

> **No editing required.** Every script resolves its paths from the repository root
> via `analysis/_paths.py` (`ROOT = Path(__file__).resolve().parents[1]`), so the
> pipeline runs on any machine, username, or OS straight after `git clone`.
> To keep this `data/` directory on a different disk, point `MOSAIC_ROOT` at a
> directory laid out like the repository:
>
> ```bash
> export MOSAIC_ROOT=/scratch/mosaic-omega    # Windows: set MOSAIC_ROOT=D:\mosaic-omega
> ```
