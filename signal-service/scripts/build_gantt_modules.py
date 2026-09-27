"""Coloured version of the module-oriented Gantt chart.

Same eleven tasks and the same week spans as the black-and-white original --
nothing has been re-planned. Colour is added only where it carries information:
each bar is coloured by the phase it belongs to, so the chart shows at a glance
that Content Preparation, Student Runtime, Faculty Console and Patient Explainer
are four separate workstreams rather than one long sequence.

Colour that does not encode anything is decoration, so the duration labels,
gridlines and axis stay monochrome.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

INK = "#1A1A1A"
MUTED = "#6B7680"
HAIRLINE = "#DDE3E8"

# Groups match the phases used in the methodology diagram, so the two slides
# tell one story. Planning and closure get neutral tones because they are
# scaffolding around the four phases rather than phases themselves.
GROUPS = {
    "plan": ("Planning & Design", "#6B7680"),
    "p1": ("Phase 1 · Content Preparation", "#2F5FA6"),
    "p2": ("Phase 2 · Student Runtime", "#3E8E5A"),
    "p3": ("Phase 3 · Patient Explainer", "#E08A2E"),
    "p4": ("Phase 4 · Faculty Console", "#7B5EA7"),
    "close": ("Integration, Testing & Closure", "#1F3864"),
}

N_WEEKS = 17


@dataclass(frozen=True)
class Task:
    label: str
    start: int  # first week, inclusive
    end: int  # last week, inclusive
    group: str

    @property
    def weeks(self) -> int:
        return self.end - self.start + 1


TASKS: list[Task] = [
    Task("Requirements Gathering & Literature Review", 1, 2, "plan"),
    Task("System Design (Architecture / DFD / UML)", 2, 4, "plan"),
    Task("Content Preparation Module\n(ECG ingest, clean, render, case gen)", 4, 7, "p1"),
    Task("Faculty Review Workflow Setup", 6, 7, "p1"),
    Task("Student Runtime Module\n(Study UI, orchestrator, grading, AI explanation)", 6, 11, "p2"),
    Task("Faculty Console Module\n(Review queue, cohort analytics)", 10, 12, "p4"),
    Task("Patient Report Explainer Module\n(OCR, glossary, safety checks)", 11, 13, "p3"),
    Task("System Integration", 13, 14, "close"),
    Task("Testing & Validation", 14, 15, "close"),
    Task("Documentation & Report Writing", 15, 16, "close"),
    Task("Final Presentation & Panel Review", 16, 16, "close"),
]

MILESTONE_WEEK = 16  # panel review


def build(out: Path, dpi: int = 200) -> Path:
    plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"]})
    fig, ax = plt.subplots(figsize=(16.0, 8.6))

    y_positions = list(range(len(TASKS) - 1, -1, -1))
    bar_h = 0.56

    for w in range(1, N_WEEKS + 1):
        ax.axvline(w, color=HAIRLINE, linewidth=1.0, zorder=0)

    for task, y in zip(TASKS, y_positions, strict=True):
        colour = GROUPS[task.group][1]
        ax.barh(y, task.weeks, left=task.start, height=bar_h,
                facecolor=colour, edgecolor=colour, linewidth=1.4, zorder=3)
        ax.text(task.start + task.weeks / 2, y, f"{task.weeks}w",
                ha="center", va="center", fontsize=9, fontweight="bold",
                color="white", zorder=4)

    ax.plot(MILESTONE_WEEK, y_positions[-1], marker="D", markersize=11,
            color=INK, markeredgecolor="white", markeredgewidth=1.2, zorder=5)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([t.label for t in TASKS], fontsize=10.5, color=INK)
    ax.tick_params(axis="y", length=0, pad=8)

    ax.set_xticks(range(1, N_WEEKS + 1))
    ax.set_xticklabels([f"W{w}" for w in range(1, N_WEEKS + 1)], fontsize=10, color=MUTED)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_xlim(0.7, N_WEEKS + 0.3)
    ax.set_ylim(-1.5, len(TASKS) - 0.3)
    ax.set_xlabel("Project Week", fontsize=11.5, fontweight="bold", color=INK, labelpad=10)

    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(HAIRLINE)

    handles = [mpatches.Patch(facecolor=c, edgecolor=c, label=n) for n, c in GROUPS.values()]
    handles.append(
        plt.Line2D([], [], marker="D", color=INK, markersize=8, linestyle="none",
                   label="Milestone")
    )
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.10),
              ncol=4, frameon=False, fontsize=9.5, handlelength=1.4, columnspacing=2.0)

    fig.suptitle("PROJECT GANTT CHART — AI-ECG TUTOR", fontsize=17, fontweight="bold",
                 color=INK, y=0.975)

    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[2] / "docs" / "planning" / "gantt_modules.png"
    parser.add_argument("--out", type=Path, default=default)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()
    print(f"written -> {build(args.out, args.dpi)}")
    build(args.out.with_suffix(".pdf"), args.dpi)
    print(f"written -> {args.out.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
