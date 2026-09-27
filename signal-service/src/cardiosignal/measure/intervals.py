"""PR, QRS, QT and the corrected QT.

Each interval is a difference between two boundaries produced by the
delineator:

    PR  = QRS_onset - P_onset      atrial depolarisation plus AV conduction
    QRS = QRS_offset - QRS_onset   ventricular depolarisation
    QT  = T_offset  - QRS_onset    depolarisation plus repolarisation

Two things follow from that and both matter.

First, there is no PR interval when there is no P wave. In atrial fibrillation
the answer is not "PR = 0" and it is not a missing field -- it is
`NOT_MEASURABLE`, a clinical finding. Reporting a number there would teach a
student that AF has a PR interval.

Second, QT depends on heart rate: it shortens as the rate rises, so a raw QT
cannot be compared against a fixed threshold. Both standard corrections are
reported, never one:

    Bazett      QTc = QT / sqrt(RR)     over-corrects above ~90 bpm
    Fridericia  QTc = QT / RR^(1/3)     better behaved at the extremes

Bazett is what most textbooks and most nursing syllabi teach; Fridericia is
what the measurement literature prefers. Reporting both means the platform can
grade against whichever the faculty specify without recomputing anything, and
the discrepancy between them is itself a teaching point.

Each correction is applied *per beat* using that beat's own preceding R-R
interval, then aggregated -- not applied once to an already-averaged QT, which
would be wrong whenever the rhythm is irregular.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cardiosignal import config
from cardiosignal.measure.aggregate import robust_scalar
from cardiosignal.types import (
    BeatFiducials,
    MeasurementStatus,
    PWaveStatus,
    Regularity,
    ScalarMeasure,
)


def _ms(samples: float, fs: int) -> float:
    return float(samples) * 1000.0 / fs


def per_beat_pr(beats: Sequence[BeatFiducials], fs: int) -> list[float]:
    return [
        _ms(b.qrs_onset - b.p_onset, fs)
        for b in beats
        if not b.excluded
        and b.p_status is PWaveStatus.PRESENT
        and b.p_onset is not None
        and b.qrs_onset is not None
        and b.qrs_onset > b.p_onset
    ]


def per_beat_qrs(beats: Sequence[BeatFiducials], fs: int) -> list[float]:
    return [
        _ms(b.qrs_offset - b.qrs_onset, fs)
        for b in beats
        if not b.excluded and b.qrs_onset is not None and b.qrs_offset is not None
    ]


def per_beat_qt(beats: Sequence[BeatFiducials], fs: int) -> list[float]:
    return [
        _ms(b.t_offset - b.qrs_onset, fs)
        for b in beats
        if not b.excluded and b.qrs_onset is not None and b.t_offset is not None
    ]


def per_beat_p_duration(beats: Sequence[BeatFiducials], fs: int) -> list[float]:
    return [
        _ms(b.p_offset - b.p_onset, fs)
        for b in beats
        if not b.excluded
        and b.p_status is PWaveStatus.PRESENT
        and b.p_onset is not None
        and b.p_offset is not None
    ]


def per_beat_qtc(
    beats: Sequence[BeatFiducials],
    fs: int,
    median_rr_ms: float,
    formula: str = "bazett",
) -> list[float]:
    """Rate-corrected QT, beat by beat, using each beat's own preceding R-R."""
    out: list[float] = []
    for b in beats:
        if b.excluded or b.qrs_onset is None or b.t_offset is None:
            continue
        rr_ms = b.rr_prev_ms or median_rr_ms
        if not rr_ms or rr_ms <= 0:
            continue
        qt = _ms(b.t_offset - b.qrs_onset, fs)
        rr_s = rr_ms / 1000.0
        out.append(qt / np.sqrt(rr_s) if formula == "bazett" else qt / rr_s ** (1.0 / 3.0))
    return out


def measure_all(
    beats: Sequence[BeatFiducials],
    fs: int = config.FS,
    sqi: float = 0.0,
    median_rr_ms: float | None = None,
    sex: str | None = None,
    regularity: Regularity | None = None,
) -> dict[str, ScalarMeasure]:
    """Every interval measure for one record."""
    usable = [b for b in beats if not b.excluded]
    n_present = sum(1 for b in usable if b.p_status is PWaveStatus.PRESENT)
    p_present = n_present > 0
    p_fraction = n_present / len(usable) if usable else 0.0

    pr_values = per_beat_pr(beats, fs)
    pr = robust_scalar(
        pr_values,
        unit="ms",
        sqi=sqi,
        reference_range=config.PR_NORMAL_MS,
        not_measurable=not p_present,
    )
    if p_present and not pr_values:
        # P waves exist but no beat gave a usable onset pair -- a delineation
        # failure, which is not the same statement as "there is no P wave".
        pr = ScalarMeasure(unit="ms", status=MeasurementStatus.FAILED)

    # Two absolute gates on top of the relative confidence score. Without them
    # an atrial fibrillation record yields a confident PR interval measured off
    # fibrillatory waves -- the exact failure that would mark a student's
    # correct answer ("no PR interval, this is AF") wrong.
    if pr.status is not MeasurementStatus.NOT_MEASURABLE:
        if p_present and p_fraction < config.PR_MIN_P_FRACTION:
            pr.status = MeasurementStatus.NEEDS_REVIEW
        if pr.mad is not None and pr.mad > config.PR_MAX_MAD_MS:
            pr.status = MeasurementStatus.NEEDS_REVIEW
        if regularity is Regularity.IRREGULARLY_IRREGULAR:
            # A PR interval presumes P waves conducting to the ventricles at a
            # fixed delay. An irregularly irregular ventricular response says
            # they are not. The spread gate alone misses this: fibrillatory
            # waves can land at a *consistent* distance before each QRS purely
            # by chance, and six atrial fibrillation records in the case bank
            # produced exactly that -- a steady, entirely fictional PR interval.
            pr.status = MeasurementStatus.NEEDS_REVIEW

    qrs = robust_scalar(per_beat_qrs(beats, fs), "ms", sqi, config.QRS_NORMAL_MS)
    qt = robust_scalar(per_beat_qt(beats, fs), "ms", sqi)
    p_dur = robust_scalar(
        per_beat_p_duration(beats, fs), "ms", sqi, (60.0, 120.0), not_measurable=not p_present
    )

    # A QT longer than ~65% of the cycle is an over-extended T offset, not a
    # long QT. Withheld rather than served, and the corrections derived from it
    # are withheld with it -- a QTc computed from a bad QT is just as wrong.
    if qt.value and median_rr_ms and (qt.value / median_rr_ms) > config.QT_MAX_RR_FRACTION:
        qt.status = MeasurementStatus.NEEDS_REVIEW

    rr_fallback = median_rr_ms or 0.0
    qtc_upper = config.QTC_UPPER_MS.get((sex or "").lower(), 450.0)
    qtc_b = robust_scalar(
        per_beat_qtc(beats, fs, rr_fallback, "bazett"), "ms", sqi, (350.0, qtc_upper)
    )
    qtc_f = robust_scalar(
        per_beat_qtc(beats, fs, rr_fallback, "fridericia"), "ms", sqi, (350.0, qtc_upper)
    )
    if qt.status is MeasurementStatus.NEEDS_REVIEW:
        for correction in (qtc_b, qtc_f):
            if correction.status is MeasurementStatus.OK:
                correction.status = MeasurementStatus.NEEDS_REVIEW

    return {
        "pr_interval": pr,
        "qrs_duration": qrs,
        "qt_interval": qt,
        "qtc_bazett": qtc_b,
        "qtc_fridericia": qtc_f,
        "p_duration": p_dur,
    }


__all__ = [
    "measure_all",
    "per_beat_p_duration",
    "per_beat_pr",
    "per_beat_qrs",
    "per_beat_qt",
    "per_beat_qtc",
]
