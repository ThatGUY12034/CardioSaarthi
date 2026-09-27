"""Two standard report figures: the development model, and the system flow.

Both are drawn for this project specifically rather than adapted from a generic
template. The development model shows a real iteration -- faculty corrections
feed back into the measurement engine, which is the loop that actually exists
here -- and the system flow names the components this project actually runs,
not a stack borrowed from a different report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK = "#1A1A1A"
MUTED = "#6B7680"
NAVY = "#1F3864"
SLATE = "#2E5C8A"
STEEL = "#4A7BA7"
BRICK = "#A3352C"
TINT = "#EDF1F6"


def label(ax, x, y, text, colour=MUTED, *, size=7.8, bold=False):
    """Edge label on an opaque plaque.

    Without the plaque the text sits directly on the arrow it describes and both
    become harder to read — the commonest legibility fault in a flow diagram.
    """
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color=colour,
            style="italic", fontweight="bold" if bold else "normal", zorder=5,
            bbox={"boxstyle": "round,pad=0.30", "facecolor": "white",
                  "edgecolor": "none"})


def box(ax, x, y, w, h, title, subtitle, colour, *, filled=False, dashed=False,
        title_size=9.2, sub_size=7.6, title_dy=1.9, sub_dy=-2.4):
    ax.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0,rounding_size=1.4",
            facecolor=colour if filled else "white",
            edgecolor=colour, linewidth=1.7,
            linestyle=(0, (4, 2)) if dashed else "solid", zorder=3,
        )
    )
    text_colour = "white" if filled else INK
    if subtitle:
        ax.text(x, y + title_dy, title, ha="center", va="center", fontsize=title_size,
                fontweight="bold", color=text_colour, zorder=4, linespacing=1.35)
        ax.text(x, y + sub_dy, subtitle, ha="center", va="center", fontsize=sub_size,
                color="white" if filled else MUTED, zorder=4, linespacing=1.5)
    else:
        ax.text(x, y, title, ha="center", va="center", fontsize=title_size,
                fontweight="bold", color=text_colour, zorder=4, linespacing=1.4)


def arrow(ax, start, end, colour, *, rad=0.0, width=1.6, style="-|>", scale=13):
    ax.add_patch(
        FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=scale,
                        color=colour, linewidth=width, zorder=2,
                        shrinkA=1, shrinkB=1,
                        connectionstyle=f"arc3,rad={rad}")
    )


# ---------------------------------------------------------------------------
# Figure 1 — development model
# ---------------------------------------------------------------------------
STAGES = [
    ("Planning", "scope, risks,\nweek plan"),
    ("Requirements", "syllabus needs,\nfaculty input"),
    ("Analysis & Design", "architecture,\nschema, DFD"),
    ("Implementation", "engine, runtime,\ntutor, console"),
    ("Testing & Validation", "LUDB / QTDB,\nunit + round-trip"),
    ("Faculty Evaluation", "review queue,\ncorrections"),
]


def development_model(out: Path, dpi: int) -> Path:
    """Linear phase sequence with an explicit feedback loop.

    A six-node ring was tried first and abandoned: with entry, exit and two
    feedback paths the arcs cross each other and the reader cannot tell which
    way the cycle turns. A straight run of phases with the loop drawn beneath
    says the same thing and cannot be misread.
    """
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})
    fig, ax = plt.subplots(figsize=(15.5, 7.6))
    ax.set_xlim(0, 186)
    ax.set_ylim(0, 92)
    ax.set_aspect("equal")
    ax.axis("off")

    y_row = 64.0
    bw, bh = 30, 18
    xs = [24, 58, 92, 126, 160]
    linear = STAGES[:5]
    for x, (title, sub) in zip(xs, linear, strict=True):
        box(ax, x, y_row, bw, bh, title, sub, NAVY)
    for a, b in zip(xs, xs[1:], strict=False):
        arrow(ax, (a + bw / 2 + 0.8, y_row), (b - bw / 2 - 0.8, y_row), SLATE, width=1.8)

    # The gate sits below the run, because it is not another phase in sequence —
    # it is the thing every phase's output has to pass through.
    box(ax, 92, 24.0, 52, 18, "Faculty Evaluation",
        "review queue · approve, edit, reject · corrections logged", BRICK, filled=True,
        title_size=10.0, sub_size=8.0)

    arrow(ax, (160, y_row - 9.6), (118.5, 24.0), BRICK, rad=0.20, width=1.8)
    label(ax, 152, 42.0, "every measured case")

    arrow(ax, (100, 33.4), (126, y_row - 9.6), BRICK, rad=0.22, width=1.8)
    label(ax, 108, 47.0, "corrections", BRICK, bold=True)

    arrow(ax, (66, 24.0), (24, y_row - 9.6), BRICK, rad=-0.26, width=1.8)
    label(ax, 38, 41.0, "next iteration", BRICK, bold=True)

    arrow(ax, (3, 82), (24, y_row + 9.8), MUTED, rad=-0.15, width=1.6)
    ax.text(3, 85.5, "Initial planning", fontsize=9.2, color=MUTED, fontweight="bold")

    arrow(ax, (176, y_row), (183, 30), MUTED, rad=-0.20, width=1.6)
    ax.text(183, 24.0, "Deployment —\nclassroom pilot", fontsize=9.2, color=MUTED,
            fontweight="bold", ha="right", va="top", linespacing=1.4)

    ax.text(92, 8.0,
            "One pass per layer, four layers over sixteen weeks. Faculty corrections re-enter at "
            "Implementation, so each review round\nimproves the measurement engine before the next "
            "batch of cases is generated.",
            ha="center", fontsize=8.6, color=MUTED, style="italic", linespacing=1.6)

    fig.text(0.5, 0.975, "Fig. 3.1.1  —  Development Model (Iterative, with faculty validation)",
             fontsize=13, fontweight="bold", color=INK, ha="center", va="top")

    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.01)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Figure 2 — system flow
# ---------------------------------------------------------------------------
def system_flow(out: Path, dpi: int) -> Path:
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})
    fig, ax = plt.subplots(figsize=(15.5, 8.6))
    ax.set_xlim(0, 176)
    ax.set_ylim(0, 98)
    ax.set_aspect("equal")
    ax.axis("off")

    # --- clients -----------------------------------------------------------
    box(ax, 20, 74, 32, 17, "Student", "browser · React + Tailwind\nChart.js", SLATE)
    box(ax, 20, 52, 32, 17, "Faculty", "review queue ·\nanalytics console", SLATE)
    box(ax, 20, 30, 32, 17, "Patient", "report explainer\n(text or photo)", SLATE)

    # --- application layer -------------------------------------------------
    box(ax, 74, 52, 38, 40,
        "Spring Boot\napplication server",
        "REST API · authentication\nOrchestratorService (state machine)\n"
        "GradingService (deterministic)\nMasteryService · RetrievalService",
        NAVY, title_size=10.2, sub_size=7.8, title_dy=11.0, sub_dy=-4.0)

    for y in (74, 52, 30):
        arrow(ax, (36.4, y), (54.6, y if y == 52 else 52), STEEL, rad=0.0 if y == 52 else
              (-0.12 if y > 52 else 0.12))
    label(ax, 45, 79.0, "HTTPS", size=7.4)

    # --- services ----------------------------------------------------------
    box(ax, 136, 80, 46, 19, "Python FastAPI  ·  signal service",
        "NeuroKit2 · SciPy · wfdb · Matplotlib\nmeasurement engine + ECG rendering", NAVY)
    box(ax, 136, 55, 46, 17, "LLM provider  (wrapper)",
        "explanations only — never values", BRICK, dashed=True)
    box(ax, 136, 31, 46, 17, "PostgreSQL + pgvector",
        "cases · measurements · responses\nknowledge-base embeddings", NAVY)
    box(ax, 136, 9, 46, 15, "Redis", "explanation cache · session state", NAVY)

    arrow(ax, (93.4, 62), (112.6, 78), STEEL, rad=-0.12)
    arrow(ax, (93.4, 55), (112.6, 55), STEEL)
    arrow(ax, (93.4, 48), (112.6, 33), STEEL, rad=0.12)
    arrow(ax, (93.4, 42), (112.6, 12), STEEL, rad=0.16)

    label(ax, 103, 73.0, "measure / render", size=7.2)
    label(ax, 103, 58.0, "grounded prompt", size=7.2)
    label(ax, 101, 40.0, "JPA / SQL", size=7.2)
    label(ax, 99, 25.0, "cache", size=7.2)

    ax.text(88, 90.5,
            "All clinical values originate in the signal service. The LLM receives them as "
            "context and never computes one.",
            ha="center", fontsize=8.6, color=MUTED, style="italic")

    fig.text(0.5, 0.975, "Fig. 4.2.1  —  System Flow Diagram",
             fontsize=13, fontweight="bold", color=INK, ha="center", va="top")

    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.02)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2] / "docs" / "planning"
    parser.add_argument("--out-dir", type=Path, default=root)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    print(f"written -> {development_model(args.out_dir / 'development_model.png', args.dpi)}")
    print(f"written -> {system_flow(args.out_dir / 'system_flow.png', args.dpi)}")
    development_model(args.out_dir / "development_model.pdf", args.dpi)
    system_flow(args.out_dir / "system_flow.pdf", args.dpi)
    print("PDF versions written alongside.")


if __name__ == "__main__":
    main()
