"""Pan-Tompkins stages, and the refractory rules that make it a detector
rather than a peak finder."""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.detect import pan_tompkins as pt


def test_derivative_kernel_matches_the_specification():
    """y[n] = (2x[n] + x[n-1] - x[n-3] - 2x[n-4]) / 8"""
    assert np.allclose(pt.DERIVATIVE_KERNEL * 8, [2.0, 1.0, 0.0, -1.0, -2.0])


def test_derivative_is_zero_on_a_constant_signal():
    assert np.allclose(pt.stage_derivative(np.full(100, 3.7))[10:-10], 0.0, atol=1e-12)


def test_derivative_is_constant_on_a_ramp():
    ramp = np.arange(200, dtype=float)
    derivative = pt.stage_derivative(ramp)[20:-20]
    assert np.allclose(derivative, derivative[0])
    assert derivative[0] > 0


def test_squaring_removes_sign_and_emphasises_large_slopes():
    x = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    squared = pt.stage_square(x)
    assert (squared >= 0).all()
    # A slope twice as large contributes four times as much.
    assert squared[4] / squared[3] == pytest.approx(4.0)


def test_integration_window_is_one_qrs_wide_and_adds_no_delay():
    """A moving average of an impulse is a plateau one window wide. What matters
    is that the plateau is *centred* on the impulse: an off-centre response is a
    delay, and a delay moves every fiducial the detector goes on to place."""
    x = np.zeros(1000)
    x[500] = 1.0
    integrated = pt.stage_integrate(x, config.FS)
    width = int(config.INTEGRATION_MS * config.FS / 1000)

    support = np.flatnonzero(integrated > 0)
    assert (support[0] + support[-1]) / 2 == pytest.approx(500, abs=1)  # centred, no lag
    assert support.size == pytest.approx(width, abs=2)


@pytest.mark.parametrize("heart_rate", [45, 60, 75, 90, 120, 150])
def test_rate_is_recovered_from_a_simulated_signal(simulate, heart_rate):
    detection = pt.detect_single_lead(simulate(heart_rate), config.FS)
    rr = detection.rr_intervals_ms()
    assert rr.size >= 5
    measured = 60000.0 / float(np.mean(rr))
    assert measured == pytest.approx(heart_rate, rel=0.05)


def test_no_two_beats_inside_the_refractory_period(single_lead):
    detection = pt.detect_single_lead(single_lead, config.FS)
    gaps = np.diff(detection.r_peaks) * 1000.0 / config.FS
    assert (gaps >= config.REFRACTORY_MS).all()


def test_flat_lead_yields_no_beats():
    detection = pt.detect_single_lead(np.zeros(5000), config.FS)
    assert detection.n_beats == 0


def test_multilead_detection_survives_one_dead_lead(twelve_lead):
    """The QRS is in every lead at once; losing one must not lose the beat."""
    good = pt.detect_r_peaks(twelve_lead, config.FS)

    damaged = twelve_lead.copy()
    damaged[:, 1] = 0.0  # lead II flatlined
    damaged[:, 7] = 50.0 * np.random.default_rng(0).standard_normal(damaged.shape[0])  # V2 noise

    degraded = pt.detect_r_peaks(damaged, config.FS)
    assert abs(degraded.n_beats - good.n_beats) <= 1


def test_multilead_preprocess_combines_after_squaring(twelve_lead):
    """Leads must be combined as energy, not band-passed as an envelope."""
    integrated, derivative = pt.preprocess_multilead(twelve_lead, config.FS)
    assert integrated.shape == (twelve_lead.shape[0],)
    assert (integrated >= 0).all()
    assert derivative.shape == integrated.shape


def test_refined_peaks_land_on_the_waveform_extremum(single_lead):
    """Detection runs on a 5-15 Hz signal; the reported index must sit on the
    real R peak, not on the filter's peak."""
    from cardiosignal.preprocess.filters import diagnostic_filter

    detection = pt.detect_single_lead(single_lead, config.FS)
    filtered = diagnostic_filter(single_lead, config.FS)
    for peak in detection.r_peaks[1:-1]:
        window = filtered[peak - 10 : peak + 11]
        assert abs(filtered[peak] - window[np.argmax(np.abs(window))]) < 1e-9
