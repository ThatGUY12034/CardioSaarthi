"""Filtering.

Zero phase is the whole point of this module.

PR, QRS and QT are not amplitudes — they are *differences between boundaries*.
A conventional (forward-only) IIR filter delays different frequencies by
different amounts, which moves the onset of the P wave and the onset of the QRS
by different distances. The interval between them then changes by an amount
that depends on the waveform, silently, with no way to detect it downstream.

`scipy.signal.filtfilt` runs the filter forwards, reverses the result, runs it
again and reverses back. The two passes have equal and opposite phase response,
so the net phase is exactly zero at every frequency. The cost is that the
effective filter order doubles (a 4th-order design behaves as 8th-order in
magnitude), which is why `FILTER_ORDER` is 4 and not 8.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sps

from cardiosignal import config


def _butter_sos(
    low_hz: float | None,
    high_hz: float | None,
    fs: int,
    order: int = config.FILTER_ORDER,
) -> np.ndarray:
    """Second-order sections for a Butterworth band/low/high-pass.

    SOS rather than transfer-function coefficients: a 4th-order band-pass
    expressed as `b, a` is numerically fragile at these low corner frequencies
    relative to a 500 Hz sample rate.
    """
    nyq = fs / 2.0
    if low_hz and high_hz:
        return sps.butter(order, [low_hz / nyq, high_hz / nyq], btype="bandpass", output="sos")
    if low_hz:
        return sps.butter(order, low_hz / nyq, btype="highpass", output="sos")
    if high_hz:
        return sps.butter(order, high_hz / nyq, btype="lowpass", output="sos")
    raise ValueError("at least one corner frequency is required")


def _apply(sos: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Zero-phase application along axis 0, tolerant of short records.

    The pad is deliberately much longer than SciPy's default. A 0.5 Hz corner
    has a two-second period, so a ten-second record filtered with SciPy's
    ~27-sample pad rings visibly at both ends -- and both ends of a ten-second
    strip contain beats we intend to measure. Padding with a third of the record
    roughly halves that edge transient. It costs nothing but arithmetic.
    """
    x = np.asarray(x, dtype=float)
    minimum = 3 * (sos.shape[0] * 2)
    padlen = max(minimum, x.shape[0] // 3)
    padlen = max(0, min(padlen, x.shape[0] - 1))
    return sps.sosfiltfilt(sos, x, axis=0, padlen=padlen)


def bandpass(
    x: np.ndarray,
    fs: int = config.FS,
    low_hz: float = config.BANDPASS_HZ[0],
    high_hz: float = config.BANDPASS_HZ[1],
    order: int = config.FILTER_ORDER,
) -> np.ndarray:
    """Diagnostic band-pass, zero phase.

    Works on a 1-D lead or a 2-D `(n_samples, n_leads)` array.
    """
    return _apply(_butter_sos(low_hz, high_hz, fs, order), x)


def diagnostic_filter(x: np.ndarray, fs: int = config.FS) -> np.ndarray:
    """The 0.5-40 Hz band every measurement is taken from.

    0.5 Hz removes baseline wander (respiration, electrode drift) without
    distorting the ST segment, which is the reason the corner is not higher:
    a 1 Hz high-pass visibly bends the ST segment and would manufacture ST
    depression that is not in the patient.

    40 Hz removes muscle noise and mains interference (50 Hz here) while
    leaving the QRS, whose energy is concentrated below ~30 Hz.
    """
    return bandpass(x, fs, config.BANDPASS_HZ[0], config.BANDPASS_HZ[1])


def qrs_emphasis_filter(x: np.ndarray, fs: int = config.FS) -> np.ndarray:
    """The 5-15 Hz band Pan-Tompkins detects beats in.

    This signal is used *only* to locate beats. Nothing is measured from it —
    a 5 Hz high-pass badly distorts the ST segment and T wave, which is exactly
    why the diagnostic band above is kept separate.
    """
    return bandpass(x, fs, config.QRS_BAND_HZ[0], config.QRS_BAND_HZ[1])


def notch(x: np.ndarray, fs: int = config.FS, freq: float = config.POWERLINE_HZ, q: float = 30.0) -> np.ndarray:
    """Optional mains notch. Rarely needed — the 40 Hz low-pass already covers 50 Hz."""
    b, a = sps.iirnotch(freq / (fs / 2.0), q)
    return sps.filtfilt(b, a, np.asarray(x, dtype=float), axis=0)


def group_delay_samples(sos: np.ndarray, fs: int = config.FS) -> float:
    """Group delay of a *single* forward pass, for documentation and tests.

    Applied through `filtfilt` the net delay is zero; this function exists so a
    test can show what the delay would have been had we used `lfilter`, which is
    the mistake this module is built to prevent.
    """
    w, gd = sps.group_delay(sps.sos2tf(sos), w=512, fs=fs)
    band = (w >= 1.0) & (w <= 30.0)
    return float(np.median(gd[band]))


__all__ = [
    "bandpass",
    "diagnostic_filter",
    "group_delay_samples",
    "notch",
    "qrs_emphasis_filter",
]
