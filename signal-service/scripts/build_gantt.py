"""Generate the project Gantt chart.

Phases and colours match the methodology diagram exactly, so the two slides read
as one system rather than two unrelated pictures.

Two things this chart does that a generic Gantt does not:

  * It shows what is actually finished, rather than what was planned to be.
    Completed work is drawn solid; everything else is drawn pale. A plan that
    cannot show slippage is decoration.
  * It marks the critical path as faculty review throughput, not code. The
    brief says so explicitly (risk 2), and a chart that puts the risk on the
    engineering tasks would be telling a comfortable lie.

Edit START_MONDAY if the schedule shifts, then re-run. Nothing is hand-placed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba

PLANNED_ALPHA = 0.30

# Week 1 Monday. Phase 1 measurement + rendering completed at the end of week 3.
START_MONDAY = date(2026, 7, 20)
TODAY = date(2026, 8, 9)

# Palette lifted from the methodology diagram so the deck stays coherent.
PHASE_COLOURS = {
    1: "#2F5FA6",  # blue   — ECG content preparation
    2: "#3E8E5A",  # green  — student learning workflow
    3: "#E08A2E",  # orange — AI-assisted learning & report explanation
    4: "#7B5EA7",  # purple — faculty monitoring & validation
}
PHASE_TITLES = {
    1: "PHASE 1 — ECG CONTENT PREPARATION",
    2: "PHASE 2 — STUDENT LEARNING WORKFLOW",
    3: "PHASE 3 — AI-ASSISTED LEARNING & REPORT EXPLANATION",
    4: "PHASE 4 — FACULTY MONITORING & VALIDATION",
}


@dataclass(frozen=True)
class Task:
    phase: int
    name: str
    start_week: int  # 1-based, inclusive
    end_week: int  # 1-based, inclusive
    done: bool = False
    critical: bool = False


@dataclass(frozen=True)
class Milestone:
    week: int  # marker sits at the end of this week
    label: str
    done: bool = False


TASKS: list[Task] = [
    # -- Phase 1 --------------------------------------------------------
    Task(1, "Dataset acquisition & quality screening", 1, 1, done=True),
    Task(1, "Measurement engine (detection, delineation, intervals)", 1, 3, done=True),
    Task(1, "Standards-compliant ECG rendering", 2, 3, done=True),
    Task(1, "Technical validation vs LUDB & QTDB", 3, 3, done=True),
    Task(1, "Clinical scenario generation (offline LLM batch)", 4, 5),
    Task(1, "Faculty review interface", 4, 5),
    Task(1, "Faculty review cycles → approved case bank", 5, 8, critical=True),
    # -- Phase 2 --------------------------------------------------------
    Task(2, "Session state machine & step-lock orchestration", 7, 7),
    Task(2, "Deterministic grading + error taxonomy", 7, 8),
    Task(2, "Knowledge base ingestion & embeddings (pgvector)", 8, 8),
    Task(2, "Student interface — nine-step case player", 8, 10),
    Task(2, "Competency model & spaced repetition", 9, 10),
    # -- Phase 3 --------------------------------------------------------
    Task(3, "LLM wrapper + CardioSaarthi persona configuration", 9, 9),
    Task(3, "RAG retrieval & citation pipeline", 9, 10),
    Task(3, "Output validation, fallback library, caching", 10, 11),
    Task(3, "Persona fixture suite (40 error scenarios)", 11, 11),
    Task(3, "Patient report explainer", 12, 13),
    # -- Phase 4 --------------------------------------------------------
    Task(4, "Faculty analytics console", 11, 12),
    Task(4, "Technical validation report (final)", 13, 13),
    Task(4, "Study setup — ethics, consent, cohort scheduling", 12, 14, critical=True),
    Task(4, "Pre-test / post-test with nursing cohort", 14, 15),
    Task(4, "Analysis, documentation & final report", 15, 16),
]

MILESTONES: list[Milestone] = [
    Milestone(3, "M1  Engine validated", done=True),
    Milestone(4, "M2  Faculty review #1"),
    Milestone(8, "M3  60 approved cases"),
    Milestone(10, "M4  Student runtime live"),
    Milestone(13, "M5  Layers 3 & 4 complete"),
    Milestone(16, "M6  Final submission"),
]

N_WEEKS = 16


def week_start(week: int) -> date:
    return START_MONDAY + timedelta(weeks=week - 1)


def week_end(week: int) -> date:
    return START_MONDAY + timedelta(weeks=week, days=-1)


def build(out: Path, dpi: int = 200) -> Path:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#c9d2da",
    })

    rows: list[tuple[str, Task | None, int]] = []  # (label, task, phase)
    for phase in (1, 2, 3, 4):
        rows.append((PHASE_TITLES[phase], None, phase))
        rows.extend((t.name, t, phase) for t in TASKS if t.phase == phase)

    height = 0.42 * len(rows) + 3.6
    fig, ax = plt.subplots(figsize=(16.5, height))

    y_positions = list(range(len(rows) - 1, -1, -1))
    bar_h = 0.58

    # Phase background bands, so the eye groups the rows without extra lines.
    for phase in (1, 2, 3, 4):
        indices = [i for i, (_l, _t, p) in enumerate(rows) if p == phase]
        top = y_positions[indices[0]] + 0.72
        bottom = y_positions[indices[-1]] - 0.55
        ax.add_patch(
            mpatches.Rectangle(
                (mdates.date2num(week_start(1)) - 3, bottom),
                mdates.date2num(week_end(N_WEEKS)) - mdates.date2num(week_start(1)) + 6,
                top - bottom,
                facecolor=PHASE_COLOURS[phase],
                alpha=0.055,
                edgecolor="none",
                zorder=0,
            )
        )

    labels: list[str] = []
    for (label, task, phase), y in zip(rows, y_positions, strict=True):
        if task is None:
            labels.append(label)
            continue
        labels.append("      " + label)

        start = mdates.date2num(week_start(task.start_week))
        finish = mdates.date2num(week_end(task.end_week)) + 1
        colour = PHASE_COLOURS[phase]

        # Face and edge are set in one call with an explicit RGBA face, so the
        # planned bars get a pale fill *and* a full-strength outline. Drawing
        # the fill as a second, lower-zorder bar does not work -- the opaque
        # bar on top hides it, which is exactly what the first version did.
        ax.barh(
            y,
            finish - start,
            left=start,
            height=bar_h,
            facecolor=to_rgba(colour, 1.0 if task.done else PLANNED_ALPHA),
            edgecolor=colour,
            linewidth=1.6,
            zorder=3,
        )
        if task.done:
            ax.text(finish + 1.5, y, "✓", color=colour, fontsize=11,
                    fontweight="bold", va="center", zorder=4)
        if task.critical:
            ax.text(finish + 5, y, "critical path",
                    color="#b3341f", fontsize=8, style="italic", va="center", zorder=4)

    # Milestones, on their own strip beneath the tasks. Labels alternate between
    # two rows: M1 and M2 are one week apart and their captions are wider than
    # that, so a single row makes them overlap into unreadability.
    milestone_y = -1.4
    for i, m in enumerate(MILESTONES):
        x = mdates.date2num(week_end(m.week)) + 1
        offset = 0.75 if i % 2 == 0 else 1.65
        ax.plot(x, milestone_y, marker="D", markersize=9,
                color="#12232e" if m.done else "#ffffff",
                markeredgecolor="#12232e", markeredgewidth=1.5, zorder=5, clip_on=False)
        ax.plot([x, x], [milestone_y - 0.12, milestone_y - offset + 0.16],
                color="#9aa7b1", linewidth=0.8, zorder=4, clip_on=False)
        ax.text(x, milestone_y - offset, m.label, fontsize=8.5, ha="center", va="top",
                color="#12232e", fontweight="bold" if m.done else "normal", clip_on=False,
                bbox={"boxstyle": "round,pad=0.28", "facecolor": "white",
                      "edgecolor": "#d8e0e6", "linewidth": 0.8})

    # "Today" marker.
    today_x = mdates.date2num(TODAY)
    ax.axvline(today_x, color="#b3341f", linestyle="--", linewidth=1.8, zorder=6)
    ax.text(today_x, len(rows) - 0.15, f"  today  {TODAY:%d %b %Y}", color="#b3341f",
            fontsize=9.5, fontweight="bold", va="bottom", ha="left", zorder=6)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=10)
    for tick, (_label, task, phase) in zip(ax.get_yticklabels(), rows, strict=True):
        if task is None:
            tick.set_fontweight("bold")
            tick.set_fontsize(10.5)
            tick.set_color(PHASE_COLOURS[phase])

    ax.set_ylim(milestone_y - 3.2, len(rows) + 0.6)
    ax.set_xlim(mdates.date2num(week_start(1)) - 3, mdates.date2num(week_end(N_WEEKS)) + 16)

    # Week numbers on top, calendar dates underneath — supervisors think in
    # weeks, calendars think in dates, and the chart has to serve both.
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.tick_params(axis="x", labelsize=9)

    secondary = ax.secondary_xaxis("top")
    secondary.set_xticks([mdates.date2num(week_start(w)) + 3.5 for w in range(1, N_WEEKS + 1)])
    secondary.set_xticklabels([f"W{w}" for w in range(1, N_WEEKS + 1)], fontsize=9)
    secondary.tick_params(length=0)

    for w in range(1, N_WEEKS + 2):
        ax.axvline(mdates.date2num(week_start(w)), color="#e6ecf1", linewidth=0.8, zorder=1)

    ax.grid(False)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    fig.suptitle("CardioSaarthi — AI-ECG Tutor System   |   16-week project schedule",
                 fontsize=17, fontweight="bold", color="#12232e", y=0.985)
    ax.set_title(
        "Solid bars are delivered and validated. Pale bars are planned. "
        "Faculty review throughput — not code — is the critical path.",
        fontsize=10.5, color="#5b6b78", pad=26,
    )

    legend = [
        mpatches.Patch(facecolor="#2F5FA6", edgecolor="#2F5FA6", label="Completed"),
        mpatches.Patch(facecolor=to_rgba("#2F5FA6", PLANNED_ALPHA), edgecolor="#2F5FA6",
                       label="Planned"),
        plt.Line2D([], [], marker="D", color="#12232e", markersize=8, linestyle="none",
                   label="Milestone"),
        plt.Line2D([], [], color="#b3341f", linestyle="--", label="Today"),
    ]
    ax.legend(handles=legend, loc="lower right", bbox_to_anchor=(1.0, -0.085),
              ncol=4, frameon=False, fontsize=9.5)

    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


SIMPLE_PHASE_NAMES = {
    1: "ECG content preparation",
    2: "Student learning workflow",
    3: "AI-assisted learning & explanation",
    4: "Faculty monitoring & validation",
}
SIMPLE_MILESTONES = [
    Milestone(3, "Engine validated", done=True),
    Milestone(8, "60 cases approved"),
    Milestone(10, "Runtime live"),
    Milestone(16, "Final submission"),
]


INK = "#1a1a1a"
MUTED = "#6b7680"
HAIRLINE = "#e4e8eb"


def build_simple(out: Path, dpi: int = 200) -> Path:
    """One bar per phase.

    Restraint is the whole design here. The row label already names the phase,
    so the bar does not repeat it. Colour appears only in the bars, so it marks
    something rather than decorating everything. The status column is aligned on
    one left edge rather than trailing each bar, so the eye reads it as a column.
    The one editorial point -- that the critical path is faculty review, not
    engineering -- sits in a footnote instead of the subtitle, because a
    subtitle should describe the chart and a footnote can carry an argument.

    Phase spans and completion are derived from the same task list as the
    detailed chart, so the two versions cannot drift apart and tell a room two
    different stories.
    """
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "axes.edgecolor": HAIRLINE,
    })

    fig, ax = plt.subplots(figsize=(13.0, 5.8))
    y_positions = [3, 2, 1, 0]
    bar_h = 0.44
    status_x = mdates.date2num(week_end(N_WEEKS)) + 8

    for phase, y in zip((1, 2, 3, 4), y_positions, strict=True):
        tasks = [t for t in TASKS if t.phase == phase]
        first, last = min(t.start_week for t in tasks), max(t.end_week for t in tasks)
        colour = PHASE_COLOURS[phase]

        start = mdates.date2num(week_start(first))
        finish = mdates.date2num(week_end(last)) + 1
        ax.barh(y, finish - start, left=start, height=bar_h,
                facecolor=to_rgba(colour, 0.22), edgecolor=to_rgba(colour, 0.55),
                linewidth=1.0, zorder=3)

        done = [t for t in tasks if t.done]
        if done:
            done_end = mdates.date2num(week_end(max(t.end_week for t in done))) + 1
            ax.barh(y, done_end - start, left=start, height=bar_h,
                    facecolor=colour, edgecolor="none", zorder=4)

        status = f"{len(done)} of {len(tasks)} complete" if done else "not started"
        ax.text(status_x, y, f"Weeks {first}–{last}", va="center", fontsize=10.5,
                color=INK, zorder=5)
        ax.text(status_x + 46, y, status, va="center", fontsize=10.5, color=MUTED, zorder=5)

    # Milestones on a baseline strip. Two of the four fall only two weeks apart
    # and their captions are wider than that gap, so alternate rows are needed
    # however short the labels are made.
    milestone_y = -1.15
    for i, m in enumerate(SIMPLE_MILESTONES):
        x = mdates.date2num(week_end(m.week)) + 1
        ax.plot(x, milestone_y, marker="D", markersize=7,
                color=INK if m.done else "white", markeredgecolor=INK,
                markeredgewidth=1.2, zorder=6, clip_on=False)
        ax.text(x, milestone_y - (0.32 if i % 2 == 0 else 0.70), m.label, fontsize=9.5,
                ha="center", va="top", color=INK if m.done else MUTED, clip_on=False)

    today_x = mdates.date2num(TODAY)
    ax.axvline(today_x, ymin=0.34, ymax=0.94, color=MUTED, linestyle=(0, (4, 3)),
               linewidth=1.2, zorder=7)
    ax.text(today_x, 3.42, " Today", color=MUTED, fontsize=10, va="bottom", ha="left",
            zorder=7)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([SIMPLE_PHASE_NAMES[p] for p in (1, 2, 3, 4)], fontsize=12,
                       color=INK)
    ax.tick_params(axis="y", length=0, pad=10)

    ax.set_ylim(milestone_y - 1.15, 3.75)
    ax.set_xlim(mdates.date2num(week_start(1)) - 3, status_x + 100)

    ax.set_xticks([mdates.date2num(week_start(w)) + 3.5 for w in range(1, N_WEEKS + 1, 3)])
    ax.set_xticklabels([f"Week {w}" for w in range(1, N_WEEKS + 1, 3)], fontsize=10,
                       color=MUTED)
    ax.tick_params(axis="x", length=0, pad=8)
    for w in range(1, N_WEEKS + 2, 3):
        ax.axvline(mdates.date2num(week_start(w)), color=HAIRLINE, linewidth=1.0, zorder=1)
    ax.axhline(milestone_y + 0.42, color=HAIRLINE, linewidth=1.0, zorder=1,
               xmax=(mdates.date2num(week_end(N_WEEKS)) + 1 - ax.get_xlim()[0])
               / (ax.get_xlim()[1] - ax.get_xlim()[0]))

    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(False)

    fig.text(0.055, 0.955, "CardioSaarthi — Project Schedule", fontsize=17,
             fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.055, 0.885,
             "Sixteen weeks · Semester VII, 2026–27 · status as at end of week 3",
             fontsize=10.5, color=MUTED, ha="left", va="top")

    legend = [
        mpatches.Patch(facecolor=PHASE_COLOURS[1], edgecolor="none", label="Delivered"),
        mpatches.Patch(facecolor=to_rgba(PHASE_COLOURS[1], 0.22),
                       edgecolor=to_rgba(PHASE_COLOURS[1], 0.55), label="Planned"),
        plt.Line2D([], [], marker="D", color=INK, markersize=6, linestyle="none",
                   label="Milestone"),
    ]
    ax.legend(handles=legend, loc="upper right", bbox_to_anchor=(1.0, 1.16),
              ncol=3, frameon=False, fontsize=10, handlelength=1.3,
              columnspacing=1.6, labelcolor=INK)

    fig.text(0.055, 0.035,
             "Critical path: faculty review throughput in weeks 5–8, not engineering.",
             fontsize=9.5, color=MUTED, ha="left", va="bottom")

    # Left margin sized for the longest phase name, which would otherwise be
    # clipped by the figure edge.
    fig.subplots_adjust(left=0.245, right=0.985, top=0.80, bottom=0.15)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2] / "docs" / "planning"
    parser.add_argument("--out", type=Path, default=root / "gantt.png")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--detailed-only", action="store_true")
    parser.add_argument("--simple-only", action="store_true")
    args = parser.parse_args()

    if not args.detailed_only:
        simple = args.out.with_name("gantt_simple.png")
        build_simple(simple, args.dpi)
        build_simple(simple.with_suffix(".pdf"), args.dpi)
        print(f"written -> {simple}   (slide version — use this one)")
        print(f"written -> {simple.with_suffix('.pdf')}")

    if not args.simple_only:
        build(args.out, args.dpi)
        build(args.out.with_suffix(".pdf"), args.dpi)
        print(f"written -> {args.out}   (detailed version, for the report)")
        print(f"written -> {args.out.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
