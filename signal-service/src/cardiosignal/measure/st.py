"""ST-segment deviation, per lead.

Measured at J + 60 ms against the PR-segment baseline.

Why those two choices, since both are the whole measurement:

*The reference.* "Elevation" is elevation relative to something, and the
something is the isoelectric line. The PR segment -- between the end of the P
wave and the start of the QRS -- is isoelectric by definition: the atria have
finished depolarising and the ventricles have not started. Using the record's
overall mean instead would let a large T wave or a wandering baseline set the
reference and manufacture deviation that is not in the patient.

*The point.* The J point is where the QRS ends and the ST segment begins, and
it is where deviation is defined -- but it also sits on the steep tail of the
QRS, so a delineation error of a few milliseconds there translates into a large
amplitude error. Stepping 60 ms further along lands on the flat part of the ST
segment, where the same delineation error costs almost nothing.

*Per lead.* This is what makes the measurement teachable. A single "ST is
elevated" figure says nothing; elevation in II, III and aVF is an inferior
infarct and elevation in V1-V4 is an anterior one. Territorial localisation
requires the deviation to be kept lead by lead, so it is never collapsed.

Thresholds follow the standard: 1 mm in the limb leads, 2 mm in V2-V3, where
normal early repolarisation is larger. Nothing here names a diagnosis -- the
module reports millimetres and a direction, and the diagnosis stays inherited
from the dataset.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cardiosignal import config
from cardiosignal.measure.aggregate import median_mad, reject_outliers
from cardiosignal.types import BeatFiducials, STFinding, STLeadMeasure, TerritorySummary


def threshold_for(lead: str) -> float:
    """Elevation threshold in mm. V2-V3 get a higher bar; normal early
    repolarisation in those leads routinely reaches 1.5 mm in healthy people."""
    return config.ST_THRESH_V2V3_MM if lead in ("V2", "V3") else config.ST_THRESH_LIMB_MM


def pr_baseline(x: np.ndarray, qrs_onset: int, fs: int = config.FS) -> float | None:
    """Isoelectric level from the PR segment immediately before the QRS."""
    hi = qrs_onset - int(6 * fs / 1000)  # step back off the QRS upstroke
    lo = hi - int(config.PR_BASELINE_WINDOW_MS * fs / 1000)
    if lo < 0 or hi <= lo:
        return None
    return float(np.median(x[lo:hi]))


def measure_lead(
    x: np.ndarray,
    lead: str,
    beats: Sequence[BeatFiducials],
    fs: int = config.FS,
    sqi: float = 0.0,
) -> STLeadMeasure:
    """ST deviation in one lead, aggregated across beats."""
    x = np.asarray(x, dtype=float)
    offset = int(config.J_OFFSET_MS * fs / 1000)

    deviations: list[float] = []
    j_index: int | None = None
    measure_index: int | None = None
    baseline_used: float | None = None

    for beat in beats:
        if beat.excluded or beat.qrs_onset is None or beat.qrs_offset is None:
            continue
        j = beat.qrs_offset
        point = j + offset
        if point >= x.size:
            continue
        baseline = pr_baseline(x, beat.qrs_onset, fs)
        if baseline is None:
            continue
        deviations.append(float(x[point]) - baseline)
        if j_index is None:
            j_index, measure_index, baseline_used = j, point, baseline

    result = STLeadMeasure(lead=lead, threshold_mm=threshold_for(lead))
    if not deviations:
        return result

    kept = reject_outliers(deviations)
    if kept.size == 0:
        kept = np.asarray(deviations)
    median_mv, mad_mv = median_mad(kept)
    if median_mv is None:
        return result

    result.deviation_mv = median_mv
    result.deviation_mm = median_mv * config.MM_PER_MV
    result.mad_mm = (mad_mv or 0.0) * config.MM_PER_MV
    result.baseline_mv = baseline_used
    result.j_point_index = j_index
    result.measure_index = measure_index
    result.n_beats = int(kept.size)

    if result.deviation_mm >= result.threshold_mm:
        result.finding = STFinding.ELEVATION
    elif result.deviation_mm <= -config.ST_DEPRESSION_THRESH_MM:
        result.finding = STFinding.DEPRESSION
    else:
        result.finding = STFinding.NORMAL

    # Spread is judged in absolute millimetres here, not as a fraction of the
    # value: ST deviation is legitimately near zero in a normal record, and a
    # relative spread would score every healthy ECG as unmeasurable.
    spread_term = float(np.clip(1.0 - (result.mad_mm or 0.0) / 0.5, 0.0, 1.0))
    result.confidence = float(np.clip(0.6 * spread_term + 0.4 * sqi, 0.0, 1.0))
    return result


def measure_all(
    signal_2d: np.ndarray,
    beats: Sequence[BeatFiducials],
    fs: int = config.FS,
    leads: tuple[str, ...] = config.LEADS,
    sqi: float = 0.0,
) -> list[STLeadMeasure]:
    signal_2d = np.asarray(signal_2d, dtype=float)
    return [
        measure_lead(signal_2d[:, j], lead, beats, fs, sqi)
        for j, lead in enumerate(leads[: signal_2d.shape[1]])
    ]


def summarise_territories(st: Sequence[STLeadMeasure]) -> list[TerritorySummary]:
    """Group per-lead deviation into coronary territories.

    Two contiguous leads meeting threshold is the standard requirement -- a
    single lead is far more likely to be a lead placement or contact problem
    than a regional finding.
    """
    by_lead = {s.lead: s for s in st}
    out: list[TerritorySummary] = []

    for name, group in config.TERRITORIES.items():
        members = [by_lead[ld] for ld in group if ld in by_lead]
        summary = TerritorySummary(territory=name, leads=group)
        if not members:
            out.append(summary)
            continue

        values = [m.deviation_mm for m in members if m.deviation_mm is not None]
        if values:
            summary.max_elevation_mm = max(values)
            summary.max_depression_mm = min(values)

        elevated = [m.lead for m in members if m.finding is STFinding.ELEVATION]
        depressed = [m.lead for m in members if m.finding is STFinding.DEPRESSION]
        if len(elevated) >= 2:
            summary.finding = STFinding.ELEVATION
            summary.leads_meeting_threshold = elevated
        elif len(depressed) >= 2:
            summary.finding = STFinding.DEPRESSION
            summary.leads_meeting_threshold = depressed
        out.append(summary)
    return out


__all__ = ["measure_all", "measure_lead", "pr_baseline", "summarise_territories", "threshold_for"]
