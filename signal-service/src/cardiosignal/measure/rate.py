"""Heart rate.

`HR = 60 / mean(RR)`, as specified.

Note that this is deliberately *not* the mean of the instantaneous rates. The
two differ whenever the rhythm is irregular, because averaging rates weights
short beats more heavily than long ones (a rate is a reciprocal). The
ventricular rate a clinician counts off a ten-second strip is beats per unit
time -- that is the mean-interval form, and it is the number a student will be
graded against.

The instantaneous rates are still computed, but only to give the spread: if the
beat-to-beat rate varies wildly, the single reported rate deserves a lower
confidence even though the arithmetic is exact.
"""

from __future__ import annotations

import numpy as np

from cardiosignal import config
from cardiosignal.measure.aggregate import confidence_score, median_mad, reject_outliers
from cardiosignal.types import Flag, MeasurementStatus, ScalarMeasure


def rr_intervals_ms(r_peaks: np.ndarray, fs: int = config.FS) -> np.ndarray:
    r_peaks = np.asarray(r_peaks, dtype=float)
    if r_peaks.size < 2:
        return np.empty(0)
    return np.diff(r_peaks) * 1000.0 / fs


def heart_rate(r_peaks: np.ndarray, fs: int = config.FS, sqi: float = 0.0) -> ScalarMeasure:
    """Ventricular rate in bpm from the R-R series."""
    rr = rr_intervals_ms(r_peaks, fs)
    if rr.size == 0:
        return ScalarMeasure(unit="bpm", status=MeasurementStatus.FAILED)

    kept = reject_outliers(rr)
    if kept.size == 0:
        kept = rr

    value = 60000.0 / float(np.mean(kept))

    # Spread comes from the instantaneous rates, which is what a reader sees as
    # "the rate varies across the strip".
    instantaneous = 60000.0 / kept
    _, mad = median_mad(instantaneous)
    confidence = confidence_score(value, mad, sqi)

    if kept.size + 1 < config.MIN_BEATS_FOR_MEASURE or confidence < config.CONFIDENCE_MIN:
        status = MeasurementStatus.NEEDS_REVIEW
    else:
        status = MeasurementStatus.OK

    low, high = config.HR_NORMAL_BPM
    flag = Flag.LOW if value < low else Flag.HIGH if value > high else Flag.NORMAL

    return ScalarMeasure(
        value=value,
        mad=mad,
        unit="bpm",
        n_beats=int(kept.size) + 1,
        confidence=confidence,
        status=status,
        flag=flag,
        reference_range=config.HR_NORMAL_BPM,
    )


__all__ = ["heart_rate", "rr_intervals_ms"]
