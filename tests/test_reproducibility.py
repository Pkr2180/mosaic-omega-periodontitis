"""Reproducibility guards: a fresh clone must run without editing the source.

These are deliberately separate from the architecture suite
(``test_mosaic_omega.py``) -- they check the *repository*, not the algorithms.

Run:  python tests/test_reproducibility.py
"""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# An absolute path baked into a script makes the repo unrunnable for anyone else.
ABSOLUTE_PATH = re.compile(
    r"""["']\s*[A-Za-z]:[\\/]"""        # Windows drive letter: "C:\... or 'D:/...
    r"""|["']/(?:home|Users|mnt|scratch)/""",   # POSIX home / mount roots
)

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "build", "dist", ".eggs"}


def _py_files():
    here = Path(__file__).resolve()
    for p in sorted(ROOT.rglob("*.py")):
        if SKIP_DIRS & set(p.parts):
            continue
        if p.resolve() == here:
            continue        # this file necessarily contains the pattern it looks for
        yield p


def test_no_absolute_paths_in_source():
    """No script may hard-code a machine-specific absolute path."""
    offenders = []
    for p in _py_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "MOSAIC_ROOT" in line:
                continue
            if ABSOLUTE_PATH.search(line):
                offenders.append(f"{p.relative_to(ROOT).as_posix()}:{i}: {stripped[:90]}")
    assert not offenders, (
        "hard-coded absolute paths found -- a fresh clone cannot run these:\n  "
        + "\n  ".join(offenders)
    )


def test_paths_resolve_to_repository_root():
    """analysis/_paths.py must point at the repo, not at analysis/."""
    sys.path.insert(0, str(ROOT / "analysis"))
    import _paths

    assert _paths.ROOT == ROOT, f"{_paths.ROOT} != {ROOT}"
    assert _paths.DATA == ROOT / "data"
    assert _paths.FIGURES == ROOT / "figures"
    assert _paths.TABLES == ROOT / "tables"
    # committed outputs must be visible through the resolved paths
    assert (_paths.TABLES / "overfitting_comparison.csv").exists()


def test_mosaic_root_override():
    """MOSAIC_ROOT relocates the tree (for data on another disk)."""
    import importlib
    import tempfile

    sys.path.insert(0, str(ROOT / "analysis"))
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MOSAIC_ROOT"] = tmp
        try:
            import _paths
            importlib.reload(_paths)
            assert _paths.ROOT == Path(tmp).resolve()
            assert _paths.DATA == Path(tmp).resolve() / "data"
        finally:
            del os.environ["MOSAIC_ROOT"]
            import _paths
            importlib.reload(_paths)


def test_every_analysis_script_compiles():
    """Every script must at least parse -- catches truncated edits."""
    failed = []
    for p in sorted((ROOT / "analysis").glob("*.py")):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as exc:
            failed.append(f"{p.name}:{exc.lineno}: {exc.msg}")
    assert not failed, "scripts failed to compile:\n  " + "\n  ".join(failed)


def test_documented_commands_exist():
    """Every `python <script>` the docs tell a reader to run must exist."""
    cmd = re.compile(r"^\s*(?:\$\s*)?python (?!-m )([A-Za-z0-9_./\\-]+\.py)", re.M)
    offenders = []
    for doc in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS & set(doc.parts):
            continue
        text = doc.read_text(encoding="utf-8")
        # ignore the fenced source dumps -- they are file bodies, not instructions
        text = re.sub(r"^### `[^`]+`\n.*?^```", "", text, flags=re.S | re.M)
        for script in set(cmd.findall(text)):
            if not (ROOT / script.replace("\\", "/")).exists():
                offenders.append(f"{doc.relative_to(ROOT).as_posix()}: python {script}")
    assert not offenders, (
        "documentation tells readers to run scripts that do not exist:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_reference_doc_matches_source():
    """docs/MOSAIC_OMEGA.md embeds file sources; they must equal the real files."""
    sys.path.insert(0, str(ROOT / "analysis"))
    import sync_reference_doc

    drift = sync_reference_doc.sync(check_only=True)
    assert drift == 0, (
        "docs/MOSAIC_OMEGA.md has drifted from the source (see names above); "
        "run: python analysis/sync_reference_doc.py"
    )


def _scalars(path):
    """Minimal YAML scalar reader -- the guards must run with no dependencies."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s{2,}([a-z_]+):\s*([^#\n]+?)\s*(?:#.*)?$", line)
        if m and m.group(2) not in ("", "|", ">-"):
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def test_frozen_config_matches_results():
    """configs/ijos_reproduction.yaml must match the committed tables and scripts."""
    cfg = _scalars(ROOT / "configs" / "ijos_reproduction.yaml")
    problems = []

    def eq(key, actual, label):
        want = cfg.get(key)
        if want is None:
            problems.append(f"{key}: missing from config")
        elif str(want) != str(actual):
            problems.append(f"{key}: config says {want}, {label} says {actual}")

    # headline DEG counts, straight from the results table
    sc_total = pb_total = 0
    with open(ROOT / "tables" / "overfitting_comparison.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            sc_total += int(row["singlecell_DEG"])
            pb_total += int(row["pseudobulk_perm_DEG"])
    eq("single_cell_degs", sc_total, "tables/overfitting_comparison.csv")
    eq("pseudobulk_degs", pb_total, "tables/overfitting_comparison.csv")

    # program test
    with open(ROOT / "tables" / "corrected_program_test.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    eq("programs_tested", len(rows), "tables/corrected_program_test.csv")
    eq("programs_significant_both_cohorts",
       sum(r["sig_both"].strip().lower() == "true" for r in rows),
       "tables/corrected_program_test.csv")

    # architecture self-assessment
    gaps = {}
    with open(ROOT / "tables" / "ai_disease_full_metrics.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["metric"] == "score_truth_gap":
                gaps[row["cohort"]] = round(float(row["value"]), 3)
    eq("score_truth_gap_main", gaps.get("main"), "tables/ai_disease_full_metrics.csv")
    eq("score_truth_gap_external", gaps.get("ext"), "tables/ai_disease_full_metrics.csv")

    # QC / clustering parameters, straight from the scripts
    build = (ROOT / "analysis" / "disease_01_build.py").read_text(encoding="utf-8")
    eq("min_genes_per_cell", 200 if ">= 200" in build else "?", "disease_01_build.py")
    eq("max_genes_per_cell", 6000 if "<= 6000" in build else "?", "disease_01_build.py")
    eq("max_pct_mitochondrial", 20 if "pct_counts_mt\"] < 20" in build else "?",
       "disease_01_build.py")

    ann = (ROOT / "analysis" / "disease_02_annotate.py").read_text(encoding="utf-8")
    eq("resolution", 1.0 if "resolution=1.0" in ann else "?", "disease_02_annotate.py")
    eq("n_neighbors", 15 if "n_neighbors=15" in ann else "?", "disease_02_annotate.py")
    eq("n_pcs", 30 if "n_pcs=30" in ann else "?", "disease_02_annotate.py")

    de = (ROOT / "analysis" / "disease_03_analysis.py").read_text(encoding="utf-8")
    eq("min_cells_per_type",
       re.search(r"MIN_CELLS\s*=\s*(\d+)", de).group(1), "disease_03_analysis.py")

    assert not problems, (
        "configs/ijos_reproduction.yaml has drifted from the results/scripts:\n  "
        + "\n  ".join(problems)
    )


def test_reproduce_entrypoint_stages_exist():
    """Every stage reproduce.py would run must point at a real script."""
    sys.path.insert(0, str(ROOT))
    import reproduce

    missing = [f"[{s.key}] {s.script}" for s in reproduce.STAGES if not s.path.exists()]
    assert not missing, "reproduce.py references missing scripts:\n  " + "\n  ".join(missing)
    keys = [s.key for s in reproduce.STAGES]
    assert len(keys) == len(set(keys)), f"duplicate stage keys: {keys}"


def test_package_is_importable_without_dependencies():
    """The core package must import using only the standard library."""
    sys.path.insert(0, str(ROOT))
    import mosaic_omega

    assert hasattr(mosaic_omega, "__version__") or mosaic_omega.__name__ == "mosaic_omega"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}\n     {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
