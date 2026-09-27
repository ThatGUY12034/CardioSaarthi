"""Geometry is the one thing that must be exact.

If a millimetre is not a millimetre, every interval a student measures off the
image is wrong by a factor that is invisible on screen. These tests assert the
two constants and the pixel relationship that follows from them.
"""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.render import geometry as g


def test_paper_speed_and_gain_are_the_standard():
    assert config.MM_PER_S == 25.0
    assert config.MM_PER_MV == 10.0


def test_dpi_gives_exactly_ten_pixels_per_millimetre():
    """254 dpi / 25.4 mm per inch = 10 px/mm, with no rounding."""
    assert config.DPI / g.MM_PER_INCH == 10.0
    assert g.px_per_mm(config.DPI) == 10.0


@pytest.mark.parametrize(
    ("ms", "expected_mm", "expected_px"),
    [
        (200, 5.0, 50.0),  # one large square
        (40, 1.0, 10.0),  # one small square
        (1000, 25.0, 250.0),
        (120, 3.0, 30.0),  # shortest normal PR
        (400, 10.0, 100.0),
    ],
)
def test_known_intervals_land_on_exact_pixels(ms, expected_mm, expected_px):
    assert g.ms_to_mm(ms) == expected_mm
    assert g.mm_to_px(g.ms_to_mm(ms)) == expected_px


@pytest.mark.parametrize("mv", [0.1, 0.5, 1.0, 2.0, -1.5])
def test_amplitude_conversion_round_trips(mv):
    assert g.mm_to_mv(g.mv_to_mm(mv)) == pytest.approx(mv)


def test_one_millivolt_is_ten_millimetres():
    assert g.mv_to_mm(1.0) == 10.0
    assert g.mm_to_px(g.mv_to_mm(1.0)) == 100.0


@pytest.mark.parametrize("n", [0, 1, 250, 2500, 4999])
def test_sample_to_millimetre_round_trips(n):
    assert g.mm_to_samples(g.samples_to_mm(n)) == pytest.approx(n)


def test_layout_page_size_matches_pixel_size():
    layout = g.Layout()
    width_mm, height_mm = layout.page_width_mm, layout.page_height_mm
    width_px, height_px = layout.pixel_size()
    assert width_px == round(width_mm * 10)
    assert height_px == round(height_mm * 10)


def test_layout_trace_width_is_250mm_for_ten_seconds():
    """Four columns of 2.5 s at 25 mm/s."""
    layout = g.Layout(duration_s=10.0)
    assert layout.trace_width_mm == 250.0
    assert layout.column_width_mm == 62.5
    assert layout.column_width_mm * layout.n_columns == layout.trace_width_mm


def test_layout_columns_are_consecutive_time_slices():
    layout = g.Layout(duration_s=10.0)
    windows = [layout.column_window(c) for c in range(layout.n_columns)]
    assert windows == [(0.0, 2.5), (2.5, 5.0), (5.0, 7.5), (7.5, 10.0)]
    for earlier, later in zip(windows, windows[1:], strict=False):
        assert earlier[1] == later[0]  # no gap, no overlap


def test_layout_rows_do_not_overlap_and_are_ordered_top_down():
    layout = g.Layout()
    baselines = [layout.row_baseline_mm(r) for r in range(layout.n_rows)]
    assert baselines == sorted(baselines, reverse=True)
    for upper, lower in zip(baselines, baselines[1:], strict=False):
        assert upper - lower == pytest.approx(layout.row_pitch_mm)
    assert layout.rhythm_baseline_mm() < baselines[-1]


def test_pixel_to_sample_is_the_inverse_of_sample_to_x():
    """The round-trip validator depends on this being exact."""
    layout = g.Layout()
    for n in (0, 500, 1234, 4999):
        x_mm = layout.sample_to_x_mm(n)
        x_px, _y_px = layout.mm_to_pixel(x_mm, 0.0)
        assert layout.pixel_to_sample(x_px) == pytest.approx(n, abs=1e-6)


def test_pixel_mapping_flips_y_to_image_convention():
    """Matplotlib's origin is bottom-left; an image's is top-left."""
    layout = g.Layout()
    _x, y_top = layout.mm_to_pixel(0.0, layout.page_height_mm)
    _x, y_bottom = layout.mm_to_pixel(0.0, 0.0)
    assert y_top == 0.0
    assert y_bottom == pytest.approx(layout.page_height_mm * 10)


def test_millimetre_grid_aligns_with_integer_pixels():
    """Every 1 mm gridline must fall on a whole pixel, or the grid shimmers."""
    for mm in np.arange(0, 300, config.GRID_MINOR_MM):
        assert g.mm_to_px(mm) == pytest.approx(round(g.mm_to_px(mm)))
