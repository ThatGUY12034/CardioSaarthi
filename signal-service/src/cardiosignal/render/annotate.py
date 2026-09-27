"""The annotated image, for feedback after a student has answered.

Drawn onto the same millimetre axes as the clean sheet, from the fiducial
indices already stored in `MeasurementResult`. Nothing is re-measured here and
nothing is re-detected: if the overlay and the measurement ever disagreed, the
feedback would be teaching something the grader does not believe.

That shared code path is also what makes the round-trip validation honest. The
annotation marks land at `layout.sample_to_x_mm(index)`, which is the same
function that placed the trace, so a caliper measurement taken off the image
tests the geometry rather than testing a second, parallel implementation of it.

The annotated image is never shown before the student has committed an answer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cardiosignal import config
from cardiosignal.preprocess.filters import diagnostic_filter
from cardiosignal.render.geometry import Layout, ms_to_mm
from cardiosignal.render.sheet import build_sheet, save
from cardiosignal.types import (
    BeatFiducials,
    MeasurementResult,
    PWaveStatus,
    Recording,
    STFinding,
)

_WAVE_COLOURS = config.COLOR_ANNOTATION


def _vline(ax, layout: Layout, sample: int, baseline_mm: float, colour: str, half_height: float = 7.0,
           dashed: bool = False) -> None:
    x = layout.sample_to_x_mm(sample)
    ax.plot(
        [x, x],
        [baseline_mm - half_height, baseline_mm + half_height],
        color=colour,
        linewidth=0.6,
        linestyle="--" if dashed else "-",
        zorder=5,
    )


def _span(ax, layout: Layout, start: int, end: int, y_mm: float, colour: str, label: str) -> None:
    """A measured interval, drawn as a bar with its value in milliseconds."""
    x0, x1 = layout.sample_to_x_mm(start), layout.sample_to_x_mm(end)
    ax.annotate(
        "",
        xy=(x0, y_mm),
        xytext=(x1, y_mm),
        arrowprops={"arrowstyle": "<->", "color": colour, "linewidth": 0.6, "shrinkA": 0, "shrinkB": 0},
        zorder=6,
    )
    ax.text(
        (x0 + x1) / 2.0,
        y_mm + 0.8,
        label,
        fontsize=5.5,
        color=colour,
        ha="center",
        va="bottom",
        zorder=6,
    )


def annotate_beat(ax, layout: Layout, beat: BeatFiducials, baseline_mm: float, fs: int,
                  with_labels: bool = True) -> None:
    """Mark one beat's boundaries on the rhythm strip."""
    if beat.p_status is PWaveStatus.PRESENT:
        for idx in (beat.p_onset, beat.p_offset):
            if idx is not None:
                _vline(ax, layout, idx, baseline_mm, _WAVE_COLOURS["p"], 5.0, dashed=True)
        if beat.p_peak is not None and with_labels:
            ax.text(layout.sample_to_x_mm(beat.p_peak), baseline_mm + 6.0, "P", fontsize=5.5,
                    color=_WAVE_COLOURS["p"], ha="center", zorder=6)
    elif beat.p_status is PWaveStatus.ABSENT and with_labels and beat.qrs_onset is not None:
        # Absence is stated, not left blank. "No P wave" is the finding.
        ax.text(layout.sample_to_x_mm(beat.qrs_onset) - 4.0, baseline_mm + 6.0, "no P",
                fontsize=5.0, color=_WAVE_COLOURS["p"], ha="center", style="italic", zorder=6)

    for idx in (beat.qrs_onset, beat.qrs_offset):
        if idx is not None:
            _vline(ax, layout, idx, baseline_mm, _WAVE_COLOURS["qrs"], 8.0)
    if beat.qrs_offset is not None:
        ax.plot([layout.sample_to_x_mm(beat.qrs_offset)], [baseline_mm], marker="o", markersize=1.6,
                color=_WAVE_COLOURS["j_point"], zorder=6)

    if beat.t_offset is not None:
        _vline(ax, layout, beat.t_offset, baseline_mm, _WAVE_COLOURS["t"], 5.0, dashed=True)
    if beat.t_peak is not None and with_labels:
        ax.text(layout.sample_to_x_mm(beat.t_peak), baseline_mm + 6.0, "T", fontsize=5.5,
                color=_WAVE_COLOURS["t"], ha="center", zorder=6)


def _representative_beat(result: MeasurementResult) -> BeatFiducials | None:
    """The beat whose intervals sit closest to the reported medians.

    The image should illustrate the number the student was graded against, so
    the annotated beat is the one that actually looks like the aggregate rather
    than simply the first one in the record.
    """
    usable = [b for b in result.beats if not b.excluded and b.qrs_onset and b.qrs_offset]
    if not usable:
        return None
    target = result.qrs_duration.value
    if target is None:
        return usable[len(usable) // 2]
    fs = result.sampling_rate
    return min(usable, key=lambda b: abs((b.qrs_offset - b.qrs_onset) * 1000.0 / fs - target))


def draw_measurement_overlay(ax, layout: Layout, result: MeasurementResult) -> None:
    """Boundaries on every beat, plus the measured intervals on one of them."""
    baseline = layout.rhythm_baseline_mm()
    fs = result.sampling_rate

    for beat in result.beats:
        if not beat.excluded:
            annotate_beat(ax, layout, beat, baseline, fs, with_labels=False)

    focus = _representative_beat(result)
    if focus is None:
        return
    annotate_beat(ax, layout, focus, baseline, fs, with_labels=True)

    # Stacked below the strip, widest interval lowest, so the labels read as a
    # nested set rather than three overlapping arrows.
    y = baseline - 10.5
    step = 4.2
    if focus.p_onset is not None and focus.qrs_onset is not None and result.pr_interval.value:
        _span(ax, layout, focus.p_onset, focus.qrs_onset, y, _WAVE_COLOURS["p"],
              f"PR {result.pr_interval.value:.0f} ms")
    if focus.qrs_onset is not None and focus.qrs_offset is not None and result.qrs_duration.value:
        _span(ax, layout, focus.qrs_onset, focus.qrs_offset, y - step, _WAVE_COLOURS["qrs"],
              f"QRS {result.qrs_duration.value:.0f} ms")
    if focus.qrs_onset is not None and focus.t_offset is not None and result.qt_interval.value:
        _span(ax, layout, focus.qrs_onset, focus.t_offset, y - 2 * step, _WAVE_COLOURS["t"],
              f"QT {result.qt_interval.value:.0f} ms")


def draw_st_markers(ax, layout: Layout, result: MeasurementResult, leads: tuple[str, ...]) -> None:
    """Mark the J+60 ms measurement point in each lead that deviates.

    Only deviating leads are marked. Marking all twelve turns the sheet into
    noise and hides the territorial pattern, which is the thing worth seeing.
    """
    lead_row_col = {
        lead: (row, col)
        for row, row_leads in enumerate(config.SHEET_LAYOUT)
        for col, lead in enumerate(row_leads)
    }
    for st in result.st:
        if st.finding is STFinding.NORMAL or st.measure_index is None:
            continue
        position = lead_row_col.get(st.lead)
        if position is None:
            continue
        row, col = position
        start_s, end_s = layout.column_window(col)
        t_s = st.measure_index / result.sampling_rate
        if not (start_s <= t_s < end_s):
            continue  # that beat is not inside this lead's 2.5 s window
        baseline = layout.row_baseline_mm(row)
        x = layout.sample_to_x_mm(st.measure_index)
        y = baseline + (st.deviation_mv or 0.0) * config.MM_PER_MV
        elevated = st.finding is STFinding.ELEVATION
        colour = "#c62828" if elevated else "#1565c0"
        ax.plot([x], [y], marker="v" if elevated else "^", markersize=2.4, color=colour, zorder=6)
        # Label offset away from the trace, in the direction of the deviation,
        # so it never sits on top of the waveform it is describing.
        ax.text(
            x + 1.2,
            y + (3.0 if elevated else -3.0),
            f"{st.lead} {st.deviation_mm:+.1f} mm",
            fontsize=5.0,
            color=colour,
            va="center",
            zorder=6,
        )


def draw_legend(ax, layout: Layout, result: MeasurementResult) -> None:
    """A compact summary block, including the confidence the value carries."""
    lines = [
        f"Rate {result.heart_rate.value:.0f} bpm" if result.heart_rate.value else "Rate --",
        f"Rhythm {result.rhythm.regularity.value.replace('_', ' ').lower()}",
        f"Axis {result.axis.degrees:.0f}°" if result.axis.degrees is not None else "Axis --",
        f"QTcB {result.qtc_bazett.value:.0f} ms" if result.qtc_bazett.value else "QTcB --",
        f"confidence {result.overall_confidence:.2f}  [{result.status.value}]",
    ]
    ax.text(
        layout.page_width_mm - layout.margin_mm,
        layout.margin_mm / 2,
        "   ".join(lines),
        fontsize=5.5,
        color="#333333",
        ha="right",
        va="center",
        zorder=6,
    )


def render_annotated(
    recording: Recording,
    result: MeasurementResult,
    path: str | Path,
    filtered: np.ndarray | None = None,
    dpi: int = config.DPI,
) -> Path:
    """Render the feedback image for one measured record."""
    signal = (
        diagnostic_filter(np.asarray(recording.signal, dtype=float), recording.sampling_rate)
        if filtered is None
        else filtered
    )
    leads = tuple(recording.leads[: signal.shape[1]])
    caption = (
        f"{recording.source} {recording.ecg_id}  |  25 mm/s  10 mm/mV  |  annotated  |  "
        f"measured, not interpreted"
    )
    fig, ax, layout = build_sheet(signal, leads, recording.sampling_rate, caption=caption)
    draw_measurement_overlay(ax, layout, result)
    draw_st_markers(ax, layout, result, leads)
    draw_legend(ax, layout, result)
    return save(fig, path, dpi)


def render_calibration_sheet(path: str | Path, dpi: int = config.DPI) -> Path:
    """The print check sheet.

    Printed at 100% scale, a caliper laid across the marked span must read
    exactly 5 mm for 200 ms and 10 mm for 1 mV. That is the physical evidence
    that the geometry is right, independent of any code.
    """
    layout = Layout(duration_s=2.0, rhythm_strip=False, n_rows=1)
    from cardiosignal.render.sheet import create_figure, draw_grid

    fig, ax = create_figure(layout)
    draw_grid(ax, layout)
    baseline = layout.row_baseline_mm(0)

    x0 = layout.x_origin_mm
    for label, width_mm, offset in (
        ("200 ms = 5 mm (1 large square)", ms_to_mm(200), 0.0),
        ("1000 ms = 25 mm (5 large squares)", ms_to_mm(1000), -12.0),
    ):
        y = baseline + offset
        ax.annotate(
            "",
            xy=(x0, y),
            xytext=(x0 + width_mm, y),
            arrowprops={"arrowstyle": "<->", "color": "#111111", "linewidth": 0.8, "shrinkA": 0,
                        "shrinkB": 0},
            zorder=6,
        )
        ax.text(x0, y + 1.2, label, fontsize=7, zorder=6)

    y = baseline - 24.0
    ax.annotate(
        "",
        xy=(x0, y),
        xytext=(x0, y + config.CAL_PULSE_HEIGHT_MM),
        arrowprops={"arrowstyle": "<->", "color": "#111111", "linewidth": 0.8, "shrinkA": 0,
                    "shrinkB": 0},
        zorder=6,
    )
    ax.text(x0 + 2.0, y + 5.0, "1 mV = 10 mm (2 large squares)", fontsize=7, va="center", zorder=6)

    ax.text(
        layout.margin_mm,
        layout.margin_mm / 2,
        "CardioSaarthi print check — print at 100% scale (no 'fit to page'), then measure with an "
        "ECG caliper.",
        fontsize=6,
        color="#444444",
        va="center",
        zorder=6,
    )
    return save(fig, path, dpi)


__all__ = [
    "annotate_beat",
    "draw_legend",
    "draw_measurement_overlay",
    "draw_st_markers",
    "render_annotated",
    "render_calibration_sheet",
]
