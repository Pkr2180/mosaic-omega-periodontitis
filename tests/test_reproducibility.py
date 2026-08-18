"""Reproducibility guards: a fresh clone must run without editing the source.

These are deliberately separate from the architecture suite
(``test_mosaic_omega.py``) -- they check the *repository*, not the algorithms.

Run:  python tests/test_reproducibility.py
"""
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
