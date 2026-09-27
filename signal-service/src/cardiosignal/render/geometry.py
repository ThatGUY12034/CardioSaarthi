"""Millimetre coordinates, and the exact pixel relationship that follows.

Everything about ECG paper is defined by two constants:

    25 mm/s   paper speed  ->  x_mm = (n / fs) * 25
    10 mm/mV  gain         ->  y_mm = v_mV * 10 + row_offset

So the plot is drawn in millimetres, not in seconds and millivolts, and the
axes are told that one unit on x equals one unit on y. `set_aspect('equal')` is
therefore not a cosmetic choice: without it Matplotlib fits the data to the
figure box and silently rescales one axis relative to the other. The grid still
looks like ECG paper, the trace still looks like an ECG, and every interval a
student measures off the image is wrong by a factor nobody can see.

The pixel relationship falls out of the same choice. At `dpi = 254`:

    254 px/inch / 25.4 mm/inch = exactly 10 px/mm

which makes 1 small square exactly 10 px, 1 large square exactly 50 px, and a
200 ms interval exactly 50 px. Not approximately -- exactly, in integers, which
is what allows the round-trip test to measure intervals back off the rendered
PNG and compare them to the source signal with no interpolation error to argue
about.

This module is the only place any of these conversions exist. The renderer, the
annotation overlay and the round-trip validator all import from here, so an
image and the measurement of that image can never disagree about where a
millimetre is.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardiosignal import config

# ---------------------------------------------------------------------------
# Scalar conversions
# ---------------------------------------------------------------------------
MM_PER_INCH = 25.4


def seconds_to_mm(seconds: float) -> float:
    return seconds * config.MM_PER_S


def mm_to_seconds(mm: float) -> float:
    return mm / config.MM_PER_S


def ms_to_mm(ms: float) -> float:
    return ms / 1000.0 * config.MM_PER_S


def mm_to_ms(mm: float) -> float:
    return mm / config.MM_PER_S * 1000.0


def samples_to_mm(n: float, fs: int = config.FS) -> float:
    """`x_mm = (n / fs) * 25`."""
    return n / fs * config.MM_PER_S


def mm_to_samples(mm: float, fs: int = config.FS) -> float:
    return mm / config.MM_PER_S * fs


def mv_to_mm(v: float) -> float:
    """`y_mm = v_mV * 10`."""
    return v * config.MM_PER_MV


def mm_to_mv(mm: float) -> float:
    return mm / config.MM_PER_MV


def px_per_mm(dpi: int = config.DPI) -> float:
    return dpi / MM_PER_INCH


def mm_to_px(mm: float, dpi: int = config.DPI) -> float:
    """At dpi=254 this is exactly `mm * 10`.

    The scale is formed first and then multiplied, rather than dividing by 25.4
    and multiplying by the dpi. `254 / 25.4` is exactly 10.0 in binary floating
    point, so `mm * 10.0` is exact for any mm that is itself exact; the other
    ordering leaves a one-ulp residue (3 mm came out as 30.000000000000004).
    Nothing downstream would have noticed a 4e-15 px error, but "exactly 10
    pixels per millimetre" is a claim this project makes, and it costs nothing
    to make it literally true.
    """
    return mm * px_per_mm(dpi)


def px_to_mm(px: float, dpi: int = config.DPI) -> float:
    return px / px_per_mm(dpi)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Layout:
    """Every position on the sheet, in millimetres from the bottom-left corner.

    Matplotlib's origin is bottom-left while a reader thinks top-down, so rows
    are numbered from the top and converted here once.
    """

    duration_s: float = config.RECORD_SECONDS
    fs: int = config.FS
    margin_mm: float = config.MARGIN_MM
    lead_in_mm: float = config.CAL_LEAD_IN_MM
    row_pitch_mm: float = config.ROW_PITCH_MM
    column_seconds: float = config.COLUMN_SECONDS
    n_rows: int = config.N_ROWS
    n_columns: int = config.N_COLUMNS
    rhythm_strip: bool = True

    @property
    def trace_width_mm(self) -> float:
        """250 mm for a ten-second record at 25 mm/s."""
        return seconds_to_mm(self.duration_s)

    @property
    def column_width_mm(self) -> float:
        return seconds_to_mm(self.column_seconds)

    @property
    def x_origin_mm(self) -> float:
        """Where t = 0 sits, leaving room for the calibration pulse."""
        return self.margin_mm + self.lead_in_mm

    @property
    def page_width_mm(self) -> float:
        return self.x_origin_mm + self.trace_width_mm + self.margin_mm

    @property
    def n_strips(self) -> int:
        return self.n_rows + (1 if self.rhythm_strip else 0)

    @property
    def page_height_mm(self) -> float:
        return 2 * self.margin_mm + self.n_strips * self.row_pitch_mm

    def row_baseline_mm(self, row: int) -> float:
        """Isoelectric line of strip `row`, counting from the top (0-based)."""
        top = self.page_height_mm - self.margin_mm
        return top - (row + 0.5) * self.row_pitch_mm

    def rhythm_baseline_mm(self) -> float:
        return self.row_baseline_mm(self.n_rows)

    def column_window(self, column: int) -> tuple[float, float]:
        """Time window `(start_s, end_s)` shown in a column."""
        start = column * self.column_seconds
        return start, min(start + self.column_seconds, self.duration_s)

    def column_x_offset_mm(self, column: int) -> float:
        """x of the column's left edge. Columns are consecutive slices of the
        same ten seconds, so a lead's x position already encodes its time."""
        return self.x_origin_mm + column * self.column_width_mm

    def sample_to_x_mm(self, n: float) -> float:
        """Absolute x for a sample index anywhere in the record."""
        return self.x_origin_mm + samples_to_mm(n, self.fs)

    def x_mm_to_sample(self, x_mm: float) -> float:
        return mm_to_samples(x_mm - self.x_origin_mm, self.fs)

    def figsize_inches(self) -> tuple[float, float]:
        return self.page_width_mm / MM_PER_INCH, self.page_height_mm / MM_PER_INCH

    def pixel_size(self, dpi: int = config.DPI) -> tuple[int, int]:
        return round(mm_to_px(self.page_width_mm, dpi)), round(mm_to_px(self.page_height_mm, dpi))

    # -- image-space mapping, used by the round-trip validator ---------------
    def mm_to_pixel(self, x_mm: float, y_mm: float, dpi: int = config.DPI) -> tuple[float, float]:
        """Millimetres to image pixels, with y flipped to image convention."""
        return mm_to_px(x_mm, dpi), mm_to_px(self.page_height_mm - y_mm, dpi)

    def pixel_to_mm(self, x_px: float, y_px: float, dpi: int = config.DPI) -> tuple[float, float]:
        return px_to_mm(x_px, dpi), self.page_height_mm - px_to_mm(y_px, dpi)

    def pixel_to_sample(self, x_px: float, dpi: int = config.DPI) -> float:
        """Image column to sample index -- the inverse the round-trip test needs."""
        return self.x_mm_to_sample(px_to_mm(x_px, dpi))


__all__ = [
    "MM_PER_INCH",
    "Layout",
    "mm_to_ms",
    "mm_to_mv",
    "mm_to_px",
    "mm_to_samples",
    "mm_to_seconds",
    "ms_to_mm",
    "mv_to_mm",
    "px_per_mm",
    "px_to_mm",
    "samples_to_mm",
    "seconds_to_mm",
]
