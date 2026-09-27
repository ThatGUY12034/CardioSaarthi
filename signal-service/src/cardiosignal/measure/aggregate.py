"""Robust aggregation across beats.

A ten-second record gives between about eight and twenty beats. Some of them
will be wrong -- a mis-delineated boundary, a beat clipped by the end of the
record, an ectopic. The aggregate has to survive that.

Hence median and MAD rather than mean and standard deviation:

    MAD = median(|x_i - median(x)|)

One artefactual beat drags a mean arbitrarily far and inflates a standard
deviation without limit. It cannot move a median at all, and moves a MAD only
as far as the honest beats allow. The same property is what makes MAD usable as
a *confidence* signal: if the beats disagree, the value is not trustworthy, and
that is exactly what we need to know before showing it to a student.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cardiosignal import config
from cardiosignal.types import Flag, MeasurementStatus, ScalarMeasure

MAD_TO_SIGMA = 1.4826  # scale factor making MAD comparable to a standard deviation


def median_mad(values: Sequence[float] | np.ndarray) -> tuple[float | None, float | None]:
    """Median and median absolute deviation, ignoring NaN."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None, None
    median = float(np.median(arr))
    return median, float(np.median(np.abs(arr - median)))


def reject_outliers(values: Sequence[float] | np.ndarray, n_mad: float = 3.0) -> np.ndarray:
    """Drop beats more than `n_mad` scaled MADs from the median.

    Used before aggregation so a single wild beat neither sets the value nor
    poisons the spread that the confidence score is derived from.
    """
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 3:
        return arr
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    if mad <= 0:
        return arr
    return arr[np.abs(arr - median) <= n_mad * mad * MAD_TO_SIGMA]


def confidence_score(median: float | None, mad: float | None, sqi: float) -> float:
    """`C = w1 * (1 - MAD/median) + w2 * SQI`, clipped to [0, 1].

    The first term is beat-to-beat agreement: a measure whose spread is a large
    fraction of its own value is not a measurement. The second is signal
    quality, so that a record whose beats agree only because every beat is
    equally corrupted does not score well.
    """
    if median is None or mad is None or median == 0:
        return 0.0
    consistency = 1.0 - abs(mad / median)
    consistency = float(np.clip(consistency, 0.0, 1.0))
    sqi = float(np.clip(sqi, 0.0, 1.0))
    score = config.CONFIDENCE_W_SPREAD * consistency + config.CONFIDENCE_W_SQI * sqi
    return float(np.clip(score, 0.0, 1.0))


def _flag_for(value: float | None, reference: tuple[float, float] | None) -> Flag:
    if value is None or reference is None:
        return Flag.UNKNOWN
    low, high = reference
    if value < low:
        return Flag.LOW
    if value > high:
        return Flag.HIGH
    return Flag.NORMAL


def robust_scalar(
    values: Sequence[float] | np.ndarray,
    unit: str = "ms",
    sqi: float = 0.0,
    reference_range: tuple[float, float] | None = None,
    min_beats: int = config.MIN_BEATS_FOR_MEASURE,
    not_measurable: bool = False,
) -> ScalarMeasure:
    """Aggregate per-beat values into one servable measure.

    `not_measurable=True` is for quantities that legitimately do not exist for
    this record -- a PR interval when there is no P wave. That is a clinical
    finding and must never be confused with a measurement that failed.
    """
    if not_measurable:
        return ScalarMeasure(unit=unit, status=MeasurementStatus.NOT_MEASURABLE, n_beats=0)

    kept = reject_outliers(values)
    if kept.size == 0:
        return ScalarMeasure(unit=unit, status=MeasurementStatus.FAILED, n_beats=0)

    median, mad = median_mad(kept)
    confidence = confidence_score(median, mad, sqi)

    if kept.size < min_beats or confidence < config.CONFIDENCE_MIN:
        status = MeasurementStatus.NEEDS_REVIEW
    else:
        status = MeasurementStatus.OK

    return ScalarMeasure(
        value=median,
        mad=mad,
        unit=unit,
        n_beats=int(kept.size),
        confidence=confidence,
        status=status,
        flag=_flag_for(median, reference_range),
        reference_range=reference_range,
    )


__all__ = [
    "MAD_TO_SIGMA",
    "confidence_score",
    "median_mad",
    "reject_outliers",
    "robust_scalar",
]
