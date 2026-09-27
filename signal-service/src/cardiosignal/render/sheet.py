"""The ECG sheet itself.

Standard 3x4 layout with a lead II rhythm strip, drawn entirely in millimetre
coordinates on a page whose physical size is fixed, so the output is a real ECG
at 25 mm/s and 10 mm/mV rather than a picture of one.

One decision worth stating because it looks like a bug: traces are **not
clipped** to their row. A tall R wave in V4 will run into the row above, exactly
as it does on a real machine's printout. Clipping would be tidier and would be
wrong -- it removes part of the waveform, so a student measuring R-wave
amplitude off a clipped image measures the clip, not the patient.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in a batch pipeline or on a server

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiosignal import config
from cardiosignal.preprocess.filters import diagnostic_filter
from cardiosignal.render.geometry import Layout, mv_to_mm
from cardiosignal.types import Recording


def create_figure(layout: Layout) -> tuple[Figure, plt.Axes]:
    """A figure whose axes *are* the page, measured in millimetres.

    The axes fill the figure exactly (`add_axes([0, 0, 1, 1])`) and the data
    limits are the page dimensions in mm, so one data unit is one millimetre and
    saving at `dpi` gives a known pixel size with no cropping or padding.
    """
    fig = plt.figure(figsize=layout.figsize_inches())
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0.0, layout.page_width_mm)
    ax.set_ylim(0.0, layout.page_height_mm)
    ax.set_aspect("equal", adjustable="box")  # mandatory -- see geometry.py
    ax.set_axis_off()
    return fig, ax


def draw_grid(ax: plt.Axes, layout: Layout) -> None:
    """1 mm minor and 5 mm major squares across the whole page."""
    width, height = layout.page_width_mm, layout.page_height_mm

    for step, colour, lw in (
        (config.GRID_MINOR_MM, config.COLOR_GRID_MINOR, 0.18),
        (config.GRID_MAJOR_MM, config.COLOR_GRID_MAJOR, 0.45),
    ):
        xs = np.arange(0.0, width + step / 2, step)
        ys = np.arange(0.0, height + step / 2, step)
        ax.vlines(xs, 0.0, height, colors=colour, linewidths=lw, zorder=1)
        ax.hlines(ys, 0.0, width, colors=colour, linewidths=lw, zorder=1)


def draw_calibration_pulse(ax: plt.Axes, layout: Layout, baseline_mm: float) -> None:
    """The 1 mV reference: 10 mm tall, 5 mm (200 ms) wide.

    This is what lets a reader verify the gain from the image alone -- it is the
    printed proof that 10 mm really is 1 mV on this particular sheet.
    """
    x0 = layout.margin_mm
    x1 = x0 + config.CAL_PULSE_WIDTH_MM
    top = baseline_mm + config.CAL_PULSE_HEIGHT_MM
    ax.plot(
        [x0 - 2.0, x0, x0, x1, x1, x1 + 2.0],
        [baseline_mm, baseline_mm, top, top, baseline_mm, baseline_mm],
        color=config.COLOR_TRACE,
        linewidth=0.7,
        solid_joinstyle="miter",
        zorder=3,
    )


def _plot_segment(
    ax: plt.Axes,
    signal: np.ndarray,
    layout: Layout,
    baseline_mm: float,
    start_sample: int,
    end_sample: int,
    linewidth: float = 0.55,
) -> None:
    n = np.arange(start_sample, end_sample)
    if n.size == 0:
        return
    x_mm = layout.sample_to_x_mm(n)
    y_mm = baseline_mm + mv_to_mm(signal[start_sample:end_sample])
    ax.plot(x_mm, y_mm, color=config.COLOR_TRACE, linewidth=linewidth, zorder=3, solid_joinstyle="round")


def draw_traces(
    ax: plt.Axes,
    signal_2d: np.ndarray,
    layout: Layout,
    leads: tuple[str, ...],
    label_leads: bool = True,
) -> None:
    """The twelve leads in their 3x4 positions, plus the rhythm strip."""
    lead_index = {name: i for i, name in enumerate(leads)}
    fs = layout.fs

    for row, row_leads in enumerate(config.SHEET_LAYOUT[: layout.n_rows]):
        baseline = layout.row_baseline_mm(row)
        draw_calibration_pulse(ax, layout, baseline)

        for column, lead in enumerate(row_leads[: layout.n_columns]):
            if lead not in lead_index:
                continue
            start_s, end_s = layout.column_window(column)
            start, end = int(start_s * fs), int(end_s * fs)
            _plot_segment(ax, signal_2d[:, lead_index[lead]], layout, baseline, start, end)

            if column > 0:
                # Column boundary marker, as a real machine prints.
                x = layout.column_x_offset_mm(column)
                ax.plot([x, x], [baseline - 12.0, baseline + 12.0], color=config.COLOR_GRID_MAJOR,
                        linewidth=0.4, zorder=2)
            if label_leads:
                ax.text(
                    layout.column_x_offset_mm(column) + 1.5,
                    baseline + layout.row_pitch_mm / 2 - 4.0,
                    lead,
                    fontsize=7,
                    fontweight="bold",
                    color=config.COLOR_TRACE,
                    zorder=4,
                )

    if layout.rhythm_strip and config.RHYTHM_LEAD in lead_index:
        baseline = layout.rhythm_baseline_mm()
        draw_calibration_pulse(ax, layout, baseline)
        _plot_segment(ax, signal_2d[:, lead_index[config.RHYTHM_LEAD]], layout, baseline, 0,
                      signal_2d.shape[0])
        if label_leads:
            ax.text(
                layout.x_origin_mm + 1.5,
                baseline + layout.row_pitch_mm / 2 - 4.0,
                f"{config.RHYTHM_LEAD} (rhythm strip)",
                fontsize=7,
                fontweight="bold",
                color=config.COLOR_TRACE,
                zorder=4,
            )


def draw_caption(ax: plt.Axes, layout: Layout, text: str) -> None:
    ax.text(
        layout.margin_mm,
        layout.margin_mm / 2,
        text,
        fontsize=6,
        color="#444444",
        va="center",
        zorder=4,
    )


def build_sheet(
    signal_2d: np.ndarray,
    leads: tuple[str, ...] = config.LEADS,
    fs: int = config.FS,
    caption: str | None = None,
    layout: Layout | None = None,
) -> tuple[Figure, plt.Axes, Layout]:
    """Assemble a complete sheet and return it undrawn-to-disk.

    Returned rather than saved so the annotation overlay can draw onto exactly
    the same axes -- the clean and annotated images are then guaranteed to share
    one geometry, which is what makes the round-trip test meaningful.
    """
    signal_2d = np.asarray(signal_2d, dtype=float)
    layout = layout or Layout(duration_s=signal_2d.shape[0] / fs, fs=fs)

    fig, ax = create_figure(layout)
    draw_grid(ax, layout)
    draw_traces(ax, signal_2d, layout, leads)
    if caption:
        draw_caption(ax, layout, caption)
    return fig, ax, layout


def render_clean(
    recording: Recording,
    path: str | Path,
    filtered: np.ndarray | None = None,
    caption: str | None = None,
    dpi: int = config.DPI,
) -> Path:
    """Render the examination image -- no marks, nothing given away."""
    signal = diagnostic_filter(np.asarray(recording.signal, dtype=float), recording.sampling_rate) \
        if filtered is None else filtered
    default_caption = (
        f"{recording.source} {recording.ecg_id}  |  25 mm/s  10 mm/mV  |  "
        f"{recording.sampling_rate} Hz"
    )
    fig, _ax, _layout = build_sheet(
        signal, tuple(recording.leads[: signal.shape[1]]), recording.sampling_rate,
        caption=caption or default_caption,
    )
    return save(fig, path, dpi)


def save(fig: Figure, path: str | Path, dpi: int = config.DPI) -> Path:
    """Write the figure at a known physical size.

    `bbox_inches` is deliberately left alone. Passing `'tight'` would crop the
    figure to its content and change the physical size of the page, breaking the
    10 px/mm relationship that everything else depends on.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return path


__all__ = [
    "build_sheet",
    "create_figure",
    "draw_calibration_pulse",
    "draw_caption",
    "draw_grid",
    "draw_traces",
    "render_clean",
    "save",
]
