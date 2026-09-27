"""End-to-end: the engine's contract, the rendered sheet, and the round trip."""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.render.geometry import Layout
from cardiosignal.types import MeasurementStatus, PWaveStatus


# --- the contract ----------------------------------------------------------
def test_engine_produces_a_versioned_result(measured):
    assert measured.schema_version == config.SCHEMA_VERSION
    assert measured.status in set(MeasurementStatus)
    assert 0.0 <= measured.overall_confidence <= 1.0


def test_every_measure_carries_spread_and_confidence(measured):
    """A number without a confidence cannot be graded against."""
    for name in ("heart_rate", "qrs_duration", "qt_interval"):
        measure = getattr(measured, name)
        assert 0.0 <= measure.confidence <= 1.0
        if measure.value is not None:
            assert measure.mad is not None
            assert measure.n_beats > 0


def test_fiducials_are_ordered_within_each_beat(measured):
    for beat in measured.beats:
        if beat.qrs_onset is not None and beat.qrs_offset is not None:
            assert beat.qrs_onset < beat.qrs_offset
        if beat.p_status is PWaveStatus.PRESENT and beat.p_onset and beat.p_offset:
            assert beat.p_onset < beat.p_offset <= beat.qrs_onset
        if beat.t_offset is not None and beat.qrs_offset is not None:
            assert beat.t_offset > beat.qrs_offset


def test_engine_never_invents_a_diagnosis(measured):
    """Diagnoses are inherited. The engine measures and stops."""
    assert measured.diagnostic_labels == []
    assert measured.syllabus_conditions == []


def test_st_is_reported_per_lead(measured):
    """Per-lead is what makes territorial localisation possible."""
    assert {s.lead for s in measured.st} == set(config.LEADS)
    assert {t.territory for t in measured.territories} == set(config.TERRITORIES)


def test_qtc_reports_both_corrections(measured):
    """Bazett is what the syllabus teaches; Fridericia is what the literature
    prefers. Reporting one only would force a choice on the faculty."""
    assert measured.qtc_bazett is not None
    assert measured.qtc_fridericia is not None


def test_result_serialises_and_flattens(measured):
    payload = measured.model_dump_json()
    assert len(payload) > 500
    row = measured.flat_row()
    assert row["ecg_id"] == measured.ecg_id
    assert "heart_rate" in row and "st_V2_mm" in row


def test_absent_p_wave_gives_not_measurable_pr(recording):
    """Atrial fibrillation has no PR interval — not a PR interval of zero."""
    from cardiosignal.engine import measure_record

    rng = np.random.default_rng(4)
    signal = np.asarray(recording.signal).copy()
    # Erase everything before each QRS so no P wave can be found.
    from cardiosignal.detect.pan_tompkins import detect_r_peaks

    for peak in detect_r_peaks(signal, config.FS).r_peaks:
        lo, hi = max(0, peak - 150), max(0, peak - 40)
        signal[lo:hi, :] = rng.normal(0, 0.002, size=(hi - lo, signal.shape[1]))

    result = measure_record(recording.model_copy(update={"signal": signal}))
    assert result.pr_interval.status in (
        MeasurementStatus.NOT_MEASURABLE,
        MeasurementStatus.NEEDS_REVIEW,
        MeasurementStatus.FAILED,
    )
    assert result.pr_interval.value is None or result.pr_interval.value > 0


def test_flat_recording_fails_rather_than_guessing(recording):
    from cardiosignal.engine import measure_record

    dead = recording.model_copy(update={"signal": np.zeros((5000, 12))})
    result = measure_record(dead)
    assert result.status is MeasurementStatus.FAILED
    assert result.warnings


# --- rendering -------------------------------------------------------------
def test_rendered_sheet_has_the_exact_pixel_size(recording, tmp_path):
    from PIL import Image

    from cardiosignal.render.sheet import render_clean

    path = render_clean(recording, tmp_path / "clean.png")
    layout = Layout()
    assert Image.open(path).size == layout.pixel_size()


def test_axes_aspect_is_equal(recording):
    """Without this Matplotlib rescales one axis and every interval is wrong."""
    from cardiosignal.render.sheet import build_sheet

    fig, ax, _layout = build_sheet(np.asarray(recording.signal))
    assert ax.get_aspect() == 1.0
    import matplotlib.pyplot as plt

    plt.close(fig)


def test_annotated_and_clean_share_one_geometry(recording, measured, tmp_path):
    from PIL import Image

    from cardiosignal.render.annotate import render_annotated
    from cardiosignal.render.sheet import render_clean

    clean = render_clean(recording, tmp_path / "clean.png")
    annotated = render_annotated(recording, measured, tmp_path / "annotated.png")
    assert Image.open(clean).size == Image.open(annotated).size


def test_calibration_sheet_renders(tmp_path):
    from cardiosignal.render.annotate import render_calibration_sheet

    assert render_calibration_sheet(tmp_path / "cal.pdf").exists()


# --- round trip ------------------------------------------------------------
def test_intervals_measured_off_the_image_match_the_signal(recording, tmp_path):
    """The claim: a caliper on the image agrees with the engine."""
    from cardiosignal.detect.pan_tompkins import detect_r_peaks
    from cardiosignal.render.sheet import render_clean
    from cardiosignal.validation import roundtrip

    signal = np.asarray(recording.signal)
    path = render_clean(recording, tmp_path / "sheet.png")
    detection = detect_r_peaks(signal, config.FS)

    report = roundtrip.evaluate(
        path, signal[:, config.LEADS.index(config.RHYTHM_LEAD)], detection.r_peaks, config.FS
    )

    assert report.geometry_exact
    assert report.large_square_px == 50.0
    assert report.n_beats_recovered == pytest.approx(report.n_beats_source, abs=1)
    assert report.rr_mae_ms is not None
    # One pixel is 0.1 mm is 4 ms, so a few ms is the floor set by line width.
    assert report.rr_mae_ms < 12.0
    assert report.peak_mae_ms < 12.0
