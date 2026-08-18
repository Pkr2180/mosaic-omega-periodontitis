"""Repository-relative paths shared by every analysis script.

The pipeline previously hard-coded an absolute path from the machine the analysis
was first run on, so a fresh clone could not execute anything without editing the
source. Paths are now derived from the location of this file, which makes the
repository runnable on any machine and under any username::

    git clone https://github.com/Pkr2180/mosaic-omega-periodontitis.git
    cd mosaic-omega-periodontitis
    pip install -e .
    pip install -r requirements.txt
    python analysis/disease_01_build.py

The single-cell matrices are several GB and are not committed (see
``data/README.md``). To keep them on another disk, point ``MOSAIC_ROOT`` at a
directory laid out like the repository::

    export MOSAIC_ROOT=/scratch/mosaic-omega     # Windows: set MOSAIC_ROOT=D:\\mosaic
"""
import os
import sys
from pathlib import Path

#: The checkout itself -- where the code lives. Always the real repository.
REPO = Path(__file__).resolve().parents[1]

#: Where data and generated outputs live. Same as REPO unless MOSAIC_ROOT moves them.
ROOT = Path(os.environ["MOSAIC_ROOT"]).resolve() if os.environ.get("MOSAIC_ROOT") else REPO

DATA = ROOT / "data"
FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"

# Short aliases used throughout the analysis scripts.
FIG = FIGURES
TAB = TABLES

# Make `import mosaic_omega` work when a script is run directly out of a clone,
# without requiring `pip install -e .` first.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

for _d in (DATA, FIGURES, TABLES):
    _d.mkdir(parents=True, exist_ok=True)

__all__ = ["REPO", "ROOT", "DATA", "FIGURES", "TABLES", "FIG", "TAB"]
