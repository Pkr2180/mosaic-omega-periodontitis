# MOSAIC-Ω — Self-Auditing, Free-Energy-Governed Multi-Agent Analysis

A self-reconfiguring multi-agent architecture that governs a team of analytic
agents through a single convex **Free-Energy Structural Control (FESC)**
objective and carries an explicit **self-assessment layer** (adversarial
falsification, blinded adjudication, and an overconfidence detector).

This repository contains the architecture and a full application to
**single-cell periodontitis**: an analysis of two independent human gingival
cohorts that shows only a **plasma-cell compositional remodelling** replicates
across cohorts, while cell-level gene signatures are dominated by
**pseudoreplication** — a limitation the architecture flags from within the
analysis.

## Repository layout

```
mosaic_omega/     Core architecture (pure standard library, no dependencies)
tests/            Test suite for the architecture (23 tests)
analysis/         Single-cell periodontitis pipeline
figures/          Generated figures (active set + superseded_overfit/ archive)
tables/           Generated result tables (CSV)
docs/             Results write-up, figure manifest, architecture reference
data/             Large data — NOT committed; see data/README.md to download
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .                 # makes `import mosaic_omega` work everywhere
pip install -r requirements.txt  # analysis dependencies (scanpy, etc.)
```

The core `mosaic_omega` package has **no third-party dependencies**; only the
single-cell analysis in `analysis/` needs the packages in `requirements.txt`.

## Reproduce

- **Architecture tests:** `python tests/test_mosaic_omega.py`
- **Single-cell analysis:** download the data (see `data/README.md`), then run the
  `analysis/disease_*.py` and `analysis/overfitting_correction*.py` scripts in
  order, followed by `analysis/disease_04_figures.py`.

The manuscript files and the manuscript-writing code are intentionally not part of
this repository.

> Reproducibility note: the analysis scripts use absolute paths set for the
> original machine. Edit the `ROOT`/`DATA` variables at the top of each script to
> your local clone before re-running. Generated `figures/` and `tables/` are
> included so results can be inspected without re-running.

## Key result

| Layer | Finding |
|---|---|
| Cell composition | Plasma cells ↑ and fibroblasts ↓ in disease — replicates in both cohorts |
| Cell-level DE | 2,897 genes by single-cell test → **0** by donor-level pseudobulk permutation (~2,900× pseudoreplication inflation) |
| Programs | 0 / 7 significant with consistent direction in both cohorts |
| Architecture | Overconfidence detector rose out of cohort (+0.10 → +0.34), agreeing with the loss of gene-level reproducibility; zero blinding leakage, zero anchoring, full branch isolation |

See `docs/RESULTS_periodontitis.md` for the full write-up and
`docs/FIGURE_MANIFEST.md` for figure provenance.

## Data

Public datasets: **GSE171213** and **GSE164241** (NCBI GEO), and the CZ CELLxGENE
Human Oral & Craniofacial Cell Atlas. Download instructions are in
`data/README.md`.

## License

MIT — see `LICENSE`.
