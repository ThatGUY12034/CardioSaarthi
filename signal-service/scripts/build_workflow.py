"""Generate the Proposed System architecture / workflow diagram.

This is deliberately not a DFD and not a use case diagram -- those answer "what
data moves" and "who does what". This answers the question those two cannot:
*where is the boundary between what is computed and what is generated*, which is
the project's central claim.

Hence the three lanes. Everything in the top lane is deterministic arithmetic
over the waveform. The middle lane is a human approval gate. In the bottom lane
the model is confined to a single box, and even that box's output is checked by
code before a student sees it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK = "#1A1A1A"
MUTED = "#6B7680"
NAVY = "#1F3864"      # deterministic content pipeline
SLATE = "#2E5C8A"     # student runtime
BRICK = "#A3352C"     # the human gate, and the one AI box
HAIRLINE = "#D8DEE4"

# Serpentine layout: lane 1 runs left to right, lane 2 right to left, lane 3
# left to right again. Each lane therefore hands off with a short, almost
# vertical arrow at the edge, instead of a long diagonal cutting back across the
# diagram through whatever caption happens to be in the way.
W, H = 186.0, 120.0
BOX_H = 12.0


def box(ax, x, y, w, text, colour, *, filled=False, dashed=False, fontsize=8.4):
    """A rounded box centred on (x, y)."""
    face = colour if filled else "white"
    ax.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - BOX_H / 2), w, BOX_H,
            boxstyle="round,pad=0,rounding_size=1.6",
            facecolor=face, edgecolor=colour, linewidth=1.6,
            linestyle=(0, (4, 2)) if dashed else "solid", zorder=3,
        )
    )
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            color="white" if filled else INK, zorder=4, linespacing=1.45)
    return x + w / 2, x - w / 2


def arrow(ax, start, end, colour=MUTED, connect=None):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=11,
            color=colour, linewidth=1.2, zorder=2, shrinkA=2, shrinkB=2,
            connectionstyle=connect or "arc3,rad=0",
        )
    )


def lane(ax, y0, y1, colour, label, sublabel):
    """Lane band with its heading stacked above the boxes, never beside them."""
    ax.add_patch(
        mpatches.Rectangle((0, y0), W, y1 - y0, facecolor=colour, alpha=0.045,
                           edgecolor="none", zorder=0)
    )
    ax.text(3, y1 - 4.0, label, fontsize=9.4, fontweight="bold", color=colour,
            va="center", zorder=1)
    ax.text(3, y1 - 8.6, sublabel, fontsize=7.8, color=MUTED, va="center", zorder=1)


def build(out: Path, dpi: int = 200) -> Path:
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})
    fig, ax = plt.subplots(figsize=(16.5, 10.5))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    # Sublabels are kept short on purpose: a long one runs under the first box
    # of its own lane, and the hand-off arrow then crosses the text.
    lane(ax, 86, 118, NAVY, "1   CONTENT PREPARATION   (offline, run once)",
         "Deterministic signal processing — no model involved.")
    lane(ax, 52, 83, BRICK, "2   FACULTY APPROVAL GATE",
         "Nothing reaches a student unreviewed.")
    lane(ax, 4, 49, SLATE, "3   STUDENT RUNTIME   (online)",
         "Control flow is code; the model only writes text.")

    # -------------------------------------- lane 1: preparation, left→right
    y1 = 98.0
    xs = [24, 60, 96, 132, 166]
    widths = [26, 28, 28, 28, 26]
    box(ax, xs[0], y1, widths[0], "PTB-XL dataset\n21,799 records", NAVY)
    box(ax, xs[1], y1, widths[1], "Quality gate &\nstratified selection", NAVY)
    box(ax, xs[2], y1, widths[2], "Measurement engine\nPan–Tompkins, delineation", NAVY)
    box(ax, xs[3], y1, widths[3], "ECG rendering\n25 mm/s · 10 mm/mV", NAVY)
    box(ax, xs[4], y1, widths[4], "Measurements +\nclean & annotated ECG", NAVY, filled=True)
    for (a, wa), (b, wb) in zip(zip(xs, widths, strict=True), zip(xs[1:], widths[1:], strict=True),
                                strict=False):
        arrow(ax, (a + wa / 2 + 0.6, y1), (b - wb / 2 - 0.6, y1), NAVY)

    ax.text(60, 89.0, "Diagnoses are inherited from the dataset's cardiologist annotations "
                      "— never computed here.",
            ha="center", fontsize=7.8, color=MUTED, style="italic")

    # -------------------------------------- lane 2: faculty, right→left
    y2 = 63.0
    box(ax, 158, y2, 30, "Confidence gate\nC = w₁(1−MAD/median) + w₂·SQI", BRICK)
    box(ax, 108, y2, 30, "Faculty review queue\napprove · edit · reject", BRICK)
    box(ax, 58, y2, 28, "Approved case bank", BRICK, filled=True)
    arrow(ax, (142.4, y2), (123.6, y2), BRICK)
    arrow(ax, (92.4, y2), (72.6, y2), BRICK)
    arrow(ax, (166, y1 - 6.6), (158, y2 + 6.6), NAVY)   # lane 1 → lane 2, at the right edge
    ax.text(120, 54.5, "385 released · 327 withheld  (of 714 measured)",
            ha="center", fontsize=7.8, color=MUTED, style="italic")

    # -------------------------------------- lane 3: runtime, left→right
    y_top, y_bot = 30.0, 13.0
    box(ax, 44, y_top, 28, "Student reads ECG\nand answers step n of 9", SLATE)
    box(ax, 84, y_top, 26, "Deterministic grading\ntolerance-based", SLATE)
    box(ax, 130, y_top, 36, "Correct → templated confirmation\n(no model call, ~50% of turns)", SLATE)
    box(ax, 110, y_bot, 24, "Retrieve 3 passages\nfrom knowledge base", SLATE)
    box(ax, 140, y_bot, 20, "AI explanation", BRICK, dashed=True)
    box(ax, 168, y_bot, 22, "Output validator\ncode-enforced", SLATE)

    arrow(ax, (58.6, y_top), (70.4, y_top), SLATE)
    arrow(ax, (97.6, y_top), (111.4, y_top), SLATE)
    arrow(ax, (97.6, y_top - 4.0), (97.6, y_bot), SLATE, connect="arc3,rad=-0.35")
    arrow(ax, (122.6, y_bot), (129.4, y_bot), SLATE)
    arrow(ax, (150.6, y_bot), (156.4, y_bot), SLATE)
    arrow(ax, (58, y2 - 6.6), (44, y_top + 6.6), BRICK)  # lane 2 → lane 3, at the left edge

    # The upper branch is self-labelling ("Correct → …"); the lower one is not,
    # and an unlabelled fork is the commonest way a flow diagram misleads.
    ax.text(85, 19.5, "wrong →", ha="right", va="center", fontsize=7.6,
            color=SLATE, fontweight="bold")
    ax.text(168, y_bot - 8.4, "rejected → retry, then stored fallback",
            ha="center", fontsize=7.4, color=MUTED, style="italic")
    ax.text(140, y_bot + 8.2, "the only place a model generates text",
            ha="center", fontsize=7.6, color=BRICK, fontweight="bold")

    # ------------------------------------------------------------- title
    fig.text(0.05, 0.97, "CardioSaarthi — Proposed System Architecture",
             fontsize=18, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.05, 0.935,
             "Clinical facts are computed, never generated. The model writes explanations only, "
             "from faculty-approved sources.",
             fontsize=10.5, color=MUTED, ha="left", va="top")

    fig.subplots_adjust(left=0.01, right=0.99, top=0.905, bottom=0.02)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[2] / "docs" / "planning" / "architecture.png"
    parser.add_argument("--out", type=Path, default=default)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()
    print(f"written -> {build(args.out, args.dpi)}")
    build(args.out.with_suffix(".pdf"), args.dpi)
    print(f"written -> {args.out.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
