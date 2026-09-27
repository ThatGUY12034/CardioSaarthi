"""Zero phase is the property the whole measurement chain rests on.

PR, QRS and QT are differences between boundaries. A filter that delays
different frequencies by different amounts moves those boundaries by different
distances and changes the interval between them, invisibly. These tests assert
that the filter as applied introduces no delay, and demonstrate the delay it
*would* have had if applied forward-only — which is the mistake being guarded
against.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import signal as sps

from cardiosignal import config
from cardiosignal.preprocess import filters


@pytest.mark.parametrize("frequency", [1.0, 5.0, 10.0, 20.0, 30.0])
def test_filtfilt_introduces_no_phase_shift(frequency):
    """A sinusoid in the passband must come out aligned with itself."""
    t = np.arange(0, 4.0, 1.0 / config.FS)
    x = np.sin(2 * np.pi * frequency * t)
    y = filters.diagnostic_filter(x)

    trim = config.FS  # ignore edge transients
    correlation = np.correlate(y[trim:-trim], x[trim:-trim], mode="full")
    lag = int(np.argmax(correlation)) - (len(x[trim:-trim]) - 1)
    assert lag == 0


def test_forward_only_filtering_would_have_delayed_the_signal():
    """The failure mode this module exists to prevent, made explicit."""
    sos = filters._butter_sos(*config.BANDPASS_HZ, config.FS)
    t = np.arange(0, 4.0, 1.0 / config.FS)
    x = np.sin(2 * np.pi * 10.0 * t)

    forward = sps.sosfilt(sos, x)
    trim = config.FS
    correlation = np.correlate(forward[trim:-trim], x[trim:-trim], mode="full")
    lag = int(np.argmax(correlation)) - (len(x[trim:-trim]) - 1)
    assert lag != 0, "a forward-only filter should delay; if not, the test is meaningless"
    assert abs(lag) * 1000 / config.FS > 2.0  # more than a millisecond of error


def test_impulse_response_is_symmetric():
    """Zero phase means a symmetric impulse response — the direct statement."""
    impulse = np.zeros(2001)
    impulse[1000] = 1.0
    response = filters.diagnostic_filter(impulse)
    window = response[1000 - 200 : 1000 + 201]
    # Symmetry is exact in theory; sosfiltfilt's edge handling leaves a small
    # residue, so the assertion is on asymmetry relative to response amplitude.
    assert np.max(np.abs(window - window[::-1])) / np.ptp(response) < 1e-3


def test_baseline_wander_is_removed():
    """0.05 Hz drift is respiration and electrode movement, not the patient."""
    t = np.arange(0, 10.0, 1.0 / config.FS)
    drift = 0.8 * np.sin(2 * np.pi * 0.05 * t)
    signal = 0.5 * np.sin(2 * np.pi * 10.0 * t)
    cleaned = filters.diagnostic_filter(signal + drift)

    trim = config.FS
    assert np.ptp(cleaned[trim:-trim]) < np.ptp((signal + drift)[trim:-trim])
    assert np.abs(np.mean(cleaned[trim:-trim])) < 0.05


def test_high_frequency_noise_is_attenuated():
    """Measured in the frequency domain, which is where attenuation is defined.

    A time-domain amplitude test would instead be dominated by the 0.5 Hz
    high-pass ringing that the noise burst excites when it starts and stops --
    an edge effect, not a statement about the stopband.
    """
    t = np.arange(0, 8.0, 1.0 / config.FS)
    noise = 0.4 * np.sin(2 * np.pi * 120.0 * t)
    filtered = filters.diagnostic_filter(noise)
    trim = config.FS

    def magnitude_at(signal: np.ndarray, frequency: float) -> float:
        segment = signal[trim:-trim]
        spectrum = np.abs(np.fft.rfft(segment * np.hanning(segment.size)))
        freqs = np.fft.rfftfreq(segment.size, 1.0 / config.FS)
        return float(spectrum[int(np.argmin(np.abs(freqs - frequency)))])

    attenuation = magnitude_at(filtered, 120.0) / magnitude_at(noise, 120.0)
    assert attenuation < 1e-3  # the design gives ~3e-5


def test_qrs_band_is_separate_from_the_diagnostic_band():
    """The 5-15 Hz signal locates beats; nothing is ever measured from it."""
    assert config.QRS_BAND_HZ != config.BANDPASS_HZ
    assert config.QRS_BAND_HZ[0] > config.BANDPASS_HZ[0]


def test_filters_work_on_twelve_lead_arrays(twelve_lead):
    filtered = filters.diagnostic_filter(twelve_lead)
    assert filtered.shape == twelve_lead.shape
    assert np.isfinite(filtered).all()
