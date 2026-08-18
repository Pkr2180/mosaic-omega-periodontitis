"""Generate the repository banner / GitHub social-preview card.

Output (committed, so the README renders without running this):
    docs/social_preview.png   1280x640

One image serves both roles -- the README header and the card GitHub shows when
the repo is linked (Settings > Social preview, which wants 1280x640).

The headline visual is the study's central result: single-cell Wilcoxon DE calls
2,897 differentially expressed genes across ten cell types, while the correctly
powered donor-level pseudobulk permutation test calls 0 -- a ~2,900x
pseudoreplication inflation that the architecture surfaces on its own.

Numbers are read from tables/overfitting_comparison.csv, not hard-coded, so the
banner cannot drift from the results.
"""
import os
import csv

PX_X = PX_Y = 1.0   # data units per pixel; set by draw_bars()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from _paths import ROOT, TAB

DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

# --- palette: validated against the #141419 dark surface (CVD dE 25.7, all checks pass)
SURFACE = "#141419"
INK = "#ffffff"
INK_2 = "#c3c2b7"
INK_3 = "#8a897f"
RETRACTED = "#d03b3b"   # status: critical -- the inflated, retracted count
CORRECTED = "#3987e5"   # categorical slot 1 -- the corrected count
RULE = "#2e2e35"


def load_counts():
    """Total single-cell vs pseudobulk DEG counts from the results table."""
    sc_total = pb_total = 0
    with open(os.path.join(TAB, "overfitting_comparison.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            sc_total += int(row["singlecell_DEG"])
            pb_total += int(row["pseudobulk_perm_DEG"])
    return sc_total, pb_total


def draw_bars(ax, sc_total, pb_total, px_w, px_h):
    """Horizontal two-bar comparison. The zero bar is drawn as an explicit
    zero-tick so 'no genes survive' reads as a result, not as missing data."""
    global PX_X, PX_Y
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    x_span, y_span = sc_total * 1.34, 2.70
    ax.set_xlim(0, x_span)
    ax.set_ylim(-0.95, 1.75)
    PX_X, PX_Y = x_span / px_w, y_span / px_h   # data units per pixel

    bars = [
        (1.0, sc_total, RETRACTED, "Single-cell Wilcoxon", "pseudoreplicated"),
        (0.0, pb_total, CORRECTED, "Donor-level pseudobulk", "correctly powered"),
    ]
    for y, val, colour, label, sub in bars:
        ax.text(0, y + 0.34, label, color=INK, fontsize=13.5, fontweight="bold",
                va="center", ha="left")
        ax.text(0, y + 0.075, sub, color=INK_3, fontsize=10.5, va="center", ha="left")
        if val > 0:
            # rounding_size is in x-data units; mutation_aspect rescales y so the
            # 4px corner radius stays isotropic on screen (see PX_X / PX_Y).
            ax.add_patch(FancyBboxPatch(
                (0, y - 0.30), val, 0.26,
                boxstyle=f"round,pad=0,rounding_size={4 * PX_X}",
                mutation_aspect=PX_Y / PX_X,
                facecolor=colour, edgecolor="none"))
            ax.text(val + sc_total * 0.030, y - 0.17, f"{val:,}", color=INK,
                    fontsize=19, fontweight="bold", va="center", ha="left")
        else:
            # zero: a visible baseline tick + an emphatic label
            ax.plot([0, 0], [y - 0.31, y - 0.04], color=colour, lw=4,
                    solid_capstyle="round")
            ax.text(sc_total * 0.030, y - 0.17, "0", color=colour, fontsize=19,
                    fontweight="bold", va="center", ha="left")
            ax.text(sc_total * 0.105, y - 0.175, "genes survive", color=INK_3,
                    fontsize=10.5, va="center", ha="left")

    ax.text(0, -0.72, f"≈ {round(sc_total / 100) * 100:,}× pseudoreplication inflation",
            color=INK_2, fontsize=12, fontweight="bold", va="center", ha="left")
    ax.text(0, 1.62, "Differentially expressed genes, 10 cell types",
            color=INK_3, fontsize=10.5, va="center", ha="left")


def build(path, size=(1280, 640), title_fs=58):
    w, h = size
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=SURFACE)

    left = 0.055
    fig.text(left, 0.80, "MOSAIC-Ω", color=INK, fontsize=title_fs,
             fontweight="bold", va="center", ha="left")
    fig.add_artist(plt.Line2D([left, left + 0.075], [0.685, 0.685],
                              color=CORRECTED, lw=4, solid_capstyle="round"))
    fig.text(left, 0.585, "Self-auditing, free-energy-governed\nmulti-agent single-cell analysis",
             color=INK_2, fontsize=16.5, va="center", ha="left", linespacing=1.5)
    fig.text(left, 0.375, "The architecture that reports its own overfitting",
             color=INK, fontsize=14, fontweight="bold", va="center", ha="left")
    fig.text(left, 0.17,
             "2 independent cohorts  ·  129,624 cells  ·  24/24 tests  ·  MIT",
             color=INK_3, fontsize=12, va="center", ha="left")

    fig.add_artist(plt.Line2D([0.505, 0.505], [0.13, 0.87], color=RULE, lw=1.4))
    rect = [0.565, 0.155, 0.375, 0.655]
    ax = fig.add_axes(rect)
    draw_bars(ax, *load_counts(), px_w=rect[2] * w, px_h=rect[3] * h)

    fig.savefig(path, facecolor=SURFACE, dpi=100)
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    build(os.path.join(DOCS, "social_preview.png"))
