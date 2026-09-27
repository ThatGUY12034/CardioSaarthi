"""Mean frontal QRS axis.

Leads I and aVF are orthogonal in the frontal plane -- I points at 0 degrees,
aVF at +90 -- so the net QRS deflection in those two leads is a vector in
component form, and the axis is simply its angle:

    alpha = atan2(A_aVF, A_I)

The component used is the *net area* under the QRS, not the height of the R
wave. Area is the integral of the deflection over the complex, so a tall narrow
R and a deep wide S contribute in proportion to how much depolarisation each
represents. Peak height ignores the S wave entirely, which puts the axis in the
wrong quadrant on any complex with a significant negative component -- exactly
the complexes where the axis is clinically interesting.

Areas are taken from the isoelectric PR-segment baseline, so a wandering
baseline shifts both leads together and cancels in the angle.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cardiosignal import config
from cardiosignal.measure.aggregate import median_mad, reject_outliers
from cardiosignal.types import AxisCategory, AxisMeasure, BeatFiducials, MeasurementStatus


def net_qrs_area(
    x: np.ndarray,
    qrs_onset: int,
    qrs_offset: int,
    baseline: float,
    fs: int = config.FS,
) -> float:
    """Signed area under one QRS complex, in mV.ms."""
    if qrs_offset <= qrs_onset:
        return 0.0
    segment = np.asarray(x[qrs_onset : qrs_offset + 1], dtype=float) - baseline
    dt_ms = 1000.0 / fs
    return float(np.sum(segment) * dt_ms)


def categorise(degrees: float) -> AxisCategory:
    """Quadrant naming, on the convention where aVF is +90 and aVL is -30."""
    low, high = config.AXIS_NORMAL_DEG
    if low <= degrees <= high:
        return AxisCategory.NORMAL
    if -90.0 <= degrees < low:
        return AxisCategory.LEFT
    if high < degrees <= 180.0:
        return AxisCategory.RIGHT
    if -180.0 <= degrees < -90.0:
        return AxisCategory.EXTREME
    return AxisCategory.INDETERMINATE


def measure(
    signal_2d: np.ndarray,
    beats: Sequence[BeatFiducials],
    per_lead_baselines: dict[str, list[float | None]] | None = None,
    fs: int = config.FS,
    leads: tuple[str, ...] = config.LEADS,
    sqi: float = 0.0,
) -> AxisMeasure:
    """Frontal axis from the net QRS areas in leads I and aVF."""
    result = AxisMeasure()
    if "I" not in leads or "aVF" not in leads:
        return result

    x_i = np.asarray(signal_2d[:, leads.index("I")], dtype=float)
    x_avf = np.asarray(signal_2d[:, leads.index("aVF")], dtype=float)

    areas_i: list[float] = []
    areas_avf: list[float] = []
    angles: list[float] = []

    for n, beat in enumerate(beats):
        if beat.excluded or beat.qrs_onset is None or beat.qrs_offset is None:
            continue
        base_i = _baseline(per_lead_baselines, "I", n, x_i, beat, fs)
        base_avf = _baseline(per_lead_baselines, "aVF", n, x_avf, beat, fs)
        a_i = net_qrs_area(x_i, beat.qrs_onset, beat.qrs_offset, base_i, fs)
        a_avf = net_qrs_area(x_avf, beat.qrs_onset, beat.qrs_offset, base_avf, fs)
        if a_i == 0.0 and a_avf == 0.0:
            continue
        areas_i.append(a_i)
        areas_avf.append(a_avf)
        angles.append(float(np.degrees(np.arctan2(a_avf, a_i))))

    if not angles:
        return result

    kept = reject_outliers(angles)
    if kept.size == 0:
        kept = np.asarray(angles)
    degrees, mad = median_mad(kept)

    result.degrees = degrees
    result.area_lead_i = float(np.median(areas_i))
    result.area_lead_avf = float(np.median(areas_avf))
    result.category = categorise(degrees) if degrees is not None else AxisCategory.INDETERMINATE

    # A 10-degree spread across beats is unremarkable; 40 degrees means the
    # complexes are not being delineated consistently.
    spread_term = float(np.clip(1.0 - (mad or 0.0) / 30.0, 0.0, 1.0))
    result.confidence = float(np.clip(0.6 * spread_term + 0.4 * sqi, 0.0, 1.0))

    # An isoelectric QRS in both leads has no meaningful direction.
    magnitude = np.hypot(result.area_lead_i, result.area_lead_avf)
    if magnitude < 1.0:
        result.category = AxisCategory.INDETERMINATE
        result.confidence *= 0.5

    result.status = (
        MeasurementStatus.OK
        if result.confidence >= config.CONFIDENCE_MIN and result.category is not AxisCategory.INDETERMINATE
        else MeasurementStatus.NEEDS_REVIEW
    )
    return result


def _baseline(
    per_lead_baselines: dict[str, list[float | None]] | None,
    lead: str,
    beat_index: int,
    x: np.ndarray,
    beat: BeatFiducials,
    fs: int,
) -> float:
    """PR-segment baseline for this lead and beat, with a local fallback."""
    if per_lead_baselines and lead in per_lead_baselines:
        values = per_lead_baselines[lead]
        if beat_index < len(values) and values[beat_index] is not None:
            return float(values[beat_index])
    if beat.qrs_onset is not None:
        hi = max(0, beat.qrs_onset - int(6 * fs / 1000))
        lo = max(0, hi - int(config.PR_BASELINE_WINDOW_MS * fs / 1000))
        if hi > lo:
            return float(np.median(x[lo:hi]))
    return float(np.median(x))


__all__ = ["categorise", "measure", "net_qrs_area"]
