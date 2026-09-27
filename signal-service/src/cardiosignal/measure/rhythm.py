"""Rhythm regularity.

Three numbers and one test, in increasing order of what they can tell you:

    SDNN   standard deviation of the R-R intervals. Absolute, in ms, so it
           cannot be compared between a bradycardia and a tachycardia.
    CV     SDNN / mean(RR). Dimensionless, so it *can*. This is the primary
           discriminator: < 0.05 regular, > 0.15 irregular.
    RMSSD  root mean square of successive differences. Sensitive to
           beat-to-beat change rather than to slow drift, so it separates true
           beat-to-beat chaos from a rate that is merely wandering.

Then the test that CV alone cannot do. Atrial fibrillation and Wenckebach both
give a high CV, but they are not the same finding and a student must not be
taught that they are. AF is *irregularly* irregular -- there is no pattern. A
Wenckebach block is *regularly* irregular -- the R-R intervals shorten, a beat
drops, and the whole thing repeats. Autocorrelating the R-R series finds
exactly that repetition: a periodic pattern produces a peak at the group
length, and true chaos produces none.

The grey zone between CV 0.05 and 0.15 is reported as INDETERMINATE rather than
forced into one of the two answers. Sinus arrhythmia lives there legitimately,
and a case that cannot be classified is a case for faculty review, not for a
guess.
"""

from __future__ import annotations

import numpy as np

from cardiosignal import config
from cardiosignal.measure.rate import rr_intervals_ms
from cardiosignal.types import MeasurementStatus, Regularity, RhythmSummary


def rr_autocorrelation(rr: np.ndarray, max_lag: int | None = None) -> tuple[float, int]:
    """Peak of the normalised R-R autocorrelation, and the lag it occurred at.

    Lag 1 is excluded: a run of alternating long/short intervals correlates at
    lag 2, and lag 1 mostly reflects smooth drift rather than a repeating group.
    Returns `(peak, lag_in_beats)`; `(0.0, 0)` when there is nothing to test.
    """
    rr = np.asarray(rr, dtype=float)
    if rr.size < 6:
        return 0.0, 0
    centred = rr - rr.mean()
    denom = float(np.dot(centred, centred))
    if denom <= 0:
        return 0.0, 0

    full = np.correlate(centred, centred, mode="full")[centred.size - 1 :] / denom
    top = max_lag or min(centred.size // 2, 8)
    if top < 2:
        return 0.0, 0
    lags = np.arange(2, top + 1)
    values = full[2 : top + 1]
    if values.size == 0:
        return 0.0, 0
    best = int(np.argmax(values))
    return float(values[best]), int(lags[best])


def analyse(r_peaks: np.ndarray, fs: int = config.FS, sqi: float = 0.0) -> RhythmSummary:
    """Classify the rhythm's regularity from the R-R series alone."""
    rr = rr_intervals_ms(r_peaks, fs)
    summary = RhythmSummary(n_beats=int(np.asarray(r_peaks).size))

    if rr.size < config.MIN_BEATS_FOR_RHYTHM - 1:
        summary.status = MeasurementStatus.NEEDS_REVIEW
        summary.regularity = Regularity.INDETERMINATE
        return summary

    mean_rr = float(np.mean(rr))
    sdnn = float(np.std(rr, ddof=1)) if rr.size > 1 else 0.0
    rmssd = float(np.sqrt(np.mean(np.diff(rr) ** 2))) if rr.size > 1 else 0.0
    cv = sdnn / mean_rr if mean_rr else 0.0
    peak, lag = rr_autocorrelation(rr)

    summary.rr_mean_ms = mean_rr
    summary.sdnn_ms = sdnn
    summary.rmssd_ms = rmssd
    summary.cv = cv
    summary.autocorr_peak = peak
    summary.autocorr_lag = lag

    periodic = peak >= config.AUTOCORR_PERIODIC
    if cv < config.CV_REGULAR:
        summary.regularity = Regularity.REGULAR
    elif cv > config.CV_IRREGULAR:
        summary.regularity = (
            Regularity.REGULARLY_IRREGULAR if periodic else Regularity.IRREGULARLY_IRREGULAR
        )
    else:
        summary.regularity = (
            Regularity.REGULARLY_IRREGULAR if periodic else Regularity.INDETERMINATE
        )

    # Confidence here is about how far the record sits from a decision boundary.
    # A CV of 0.049 is "regular" by the letter of the rule and by nothing else.
    if summary.regularity is Regularity.REGULAR:
        margin = (config.CV_REGULAR - cv) / config.CV_REGULAR
    elif summary.regularity is Regularity.INDETERMINATE:
        margin = 0.0
    else:
        margin = min(1.0, (cv - config.CV_REGULAR) / (config.CV_IRREGULAR - config.CV_REGULAR))
    summary.confidence = float(np.clip(0.6 * np.clip(margin, 0.0, 1.0) + 0.4 * sqi, 0.0, 1.0))

    if summary.regularity is Regularity.INDETERMINATE or summary.confidence < config.CONFIDENCE_MIN:
        summary.status = MeasurementStatus.NEEDS_REVIEW
    else:
        summary.status = MeasurementStatus.OK
    return summary


__all__ = ["analyse", "rr_autocorrelation"]
