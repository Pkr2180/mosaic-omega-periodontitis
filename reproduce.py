#!/usr/bin/env python3
"""One-command reproduction of the MOSAIC-Omega periodontitis results.

    python reproduce.py --help
    python reproduce.py --verify        # no data needed: tests + figure/table audit
    python reproduce.py --download      # fetch the raw GEO data (~0.9 GB)
    python reproduce.py                 # full pipeline, raw counts -> figures
    python reproduce.py --from 05       # resume at a given stage
    python reproduce.py --dry-run       # print the plan and exit

A reviewer should never have to work out which script runs in which order. The
canonical order lives here, in STAGES, and nowhere else.

Stages marked `needs_data` require the GEO downloads; the rest run from the
committed tables/ and figures/. `--verify` runs only what needs no download, which
is enough to confirm the published numbers.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "analysis"))


class Stage:
    def __init__(self, key, script, what, needs_data=True):
        self.key, self.script, self.what, self.needs_data = key, script, what, needs_data

    @property
    def path(self):
        return REPO / self.script


# The canonical pipeline order. Stage keys are stable; script names may move.
STAGES = [
    Stage("00", "tests/test_mosaic_omega.py",
          "Architecture suite (24 tests, standard library only)", needs_data=False),
    Stage("00b", "tests/test_reproducibility.py",
          "Reproducibility guards (7 tests)", needs_data=False),
    Stage("01", "analysis/disease_01_build.py",
          "Main cohort GSE171213: raw counts -> sparse AnnData + QC"),
    Stage("02", "analysis/disease_02_annotate.py",
          "Main cohort: Leiden clustering -> 11 cell types"),
    Stage("03", "analysis/disease_ext_01_build.py",
          "External cohort GSE164241: build + QC + annotate"),
    Stage("04", "analysis/disease_03_analysis.py",
          "Main cohort: differential abundance + single-cell DE + LOSO"),
    Stage("05", "analysis/disease_ext_02_analysis.py",
          "External cohort: differential abundance + DE"),
    Stage("06", "analysis/disease_ext_03_crosscohort.py",
          "Cross-cohort concordance"),
    Stage("07", "analysis/disease_05_mosaic.py",
          "MOSAIC-Omega adversarial-consensus biomarker selection"),
    Stage("08", "analysis/overfitting_correction.py",
          "CORRECTION: pseudobulk permutation DE (the 2,897 -> 0 result)"),
    Stage("09", "analysis/overfitting_correction2_programs.py",
          "CORRECTION: sample-level program test (0/7 significant)"),
    Stage("10", "analysis/ai_eval_disease.py",
          "Architecture metric suite, both cohorts"),
    Stage("11", "analysis/disease_04_figures.py",
          "Figures: main cohort atlas + corrected panels"),
    Stage("12", "analysis/disease_ext_04_figures.py",
          "Figures: external cohort + cross-cohort"),
    Stage("13", "analysis/make_banner.py",
          "Repository banner / social card", needs_data=False),
]

KEYS = [s.key for s in STAGES]


def run(stage, python=sys.executable):
    print(f"\n{'=' * 78}\n[{stage.key}] {stage.what}\n     {stage.script}\n{'=' * 78}", flush=True)
    if not stage.path.exists():
        print(f"  MISSING: {stage.script}", flush=True)
        return False, 0.0
    t0 = time.time()
    rc = subprocess.call([python, str(stage.path)], cwd=str(REPO))
    dt = time.time() - t0
    print(f"  -> {'ok' if rc == 0 else f'FAILED (exit {rc})'} in {dt:.1f}s", flush=True)
    return rc == 0, dt


def have_raw_data():
    d = REPO / "data"
    return (d / "GSE171213_AllSample.counts.tsv.gz").exists() or (d / "GSE171213_counts.tsv.gz").exists()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="run only the stages that need no raw data (tests + audit)")
    ap.add_argument("--download", action="store_true",
                    help="download the raw GEO data first (~0.9 GB)")
    ap.add_argument("--from", dest="start", metavar="KEY", choices=KEYS,
                    help=f"resume from a stage key: {', '.join(KEYS)}")
    ap.add_argument("--only", metavar="KEY", choices=KEYS, help="run a single stage")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    if args.download:
        sys.exit(subprocess.call([sys.executable, str(REPO / "data" / "download_data.py")]))

    plan = list(STAGES)
    if args.only:
        plan = [s for s in plan if s.key == args.only]
    elif args.start:
        plan = plan[KEYS.index(args.start):]
    if args.verify:
        plan = [s for s in plan if not s.needs_data]

    print(f"MOSAIC-Omega reproduction -- {len(plan)} stage(s)")
    for s in plan:
        print(f"  [{s.key}] {s.script:<45} {'(data)' if s.needs_data else ''}")
    if args.dry_run:
        return 0

    if not args.verify and any(s.needs_data for s in plan) and not have_raw_data():
        print("\nRaw GEO data not found in data/.\n"
              "  python reproduce.py --download    # fetch it (~0.9 GB)\n"
              "  python reproduce.py --verify      # or verify without it\n", flush=True)
        return 2

    failed, total = [], 0.0
    for s in plan:
        ok, dt = run(s)
        total += dt
        if not ok:
            failed.append(s.key)

    print(f"\n{'=' * 78}\n{len(plan) - len(failed)}/{len(plan)} stage(s) succeeded in {total:.1f}s")
    if failed:
        print("failed: " + ", ".join(failed))
    else:
        print("Outputs: tables/  figures/   Write-up: docs/RESULTS_periodontitis.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
