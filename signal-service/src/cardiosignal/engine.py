"""The measurement engine: one record in, one `MeasurementResult` out.

This is the only place the stages are wired together, and the order is fixed by
dependency, not by preference:

    filter -> detect beats -> delineate boundaries -> assess quality
           -> rate -> rhythm -> intervals -> axis -> ST

Nothing here interprets. `diagnostic_labels` is copied verbatim from the
dataset's cardiologist annotations and is never derived from anything measured
above it. If this module ever starts inferring a diagnosis from its own
numbers, the platform's central claim has been broken.
"""

from __future__ import annotations

import numpy as np

from cardiosignal import config
from cardiosignal.detect.delineate import delineate
from cardiosignal.detect.pan_tompkins import detect_r_peaks
from cardiosignal.measure import axis as axis_module
from cardiosignal.measure import confidence as confidence_module
from cardiosignal.measure import intervals as intervals_module
from cardiosignal.measure import rate as rate_module
from cardiosignal.measure import rhythm as rhythm_module
from cardiosignal.measure import st as st_module
from cardiosignal.measure import twave as twave_module
from cardiosignal.preprocess.filters import diagnostic_filter
from cardiosignal.types import (
    MeasurementResult,
    MeasurementStatus,
    PWaveStatus,
    Recording,
)


def measure_record(recording: Recording) -> MeasurementResult:
    """Run the full deterministic pipeline over one 12-lead record."""
    fs = recording.sampling_rate
    raw = np.asarray(recording.signal, dtype=float)
    leads = tuple(recording.leads[: raw.shape[1]])

    result = MeasurementResult(
        ecg_id=recording.ecg_id,
        source=recording.source,
        sampling_rate=fs,
        n_samples=raw.shape[0],
        leads=leads,
        age=recording.age,
        sex=recording.sex,
        scp_codes=recording.scp_codes,
    )

    # 1. Filter once. Everything downstream measures from this array, so there
    #    is exactly one filtered version of the truth.
    filtered = diagnostic_filter(raw, fs)

    # 2. Beats. Detection runs on the raw signal because it applies its own
    #    QRS-emphasis band; feeding it the diagnostic band would filter twice.
    detection = detect_r_peaks(raw, fs, leads)
    if detection.n_beats < 2:
        result.warnings.append("fewer_than_two_beats_detected")
        result.status = MeasurementStatus.FAILED
        return result

    # 3. Boundaries.
    delineation = delineate(filtered, detection.r_peaks, fs, leads, already_filtered=True)
    beats = delineation.beats

    # 4. Quality, then per-beat exclusion, before anything is aggregated.
    quality = confidence_module.assess(filtered, detection.r_peaks, fs, leads)
    reference_index = leads.index("II") if "II" in leads else 0
    confidence_module.annotate_beats(beats, filtered, detection.r_peaks, fs, reference_index)
    quality.n_beats_excluded = sum(1 for b in beats if b.excluded)
    sqi = quality.sqi_overall
    result.quality = quality
    result.beats = beats

    # A record where most beats fail the template test has nothing measurable
    # left; aggregating the survivors would produce a confident wrong answer.
    usable = [b for b in beats if not b.excluded]
    if len(usable) < 2:
        result.warnings.append("no_usable_beats_after_quality_exclusion")
        result.status = MeasurementStatus.FAILED
        return result

    # 5-6. Rate and rhythm, from the R-R series alone.
    result.heart_rate = rate_module.heart_rate(detection.r_peaks, fs, sqi)
    result.rhythm = rhythm_module.analyse(detection.r_peaks, fs, sqi)

    # 7. Intervals.
    measures = intervals_module.measure_all(
        beats,
        fs,
        sqi,
        median_rr_ms=result.rhythm.rr_mean_ms,
        sex=recording.sex,
        regularity=result.rhythm.regularity,
    )
    for name, measure in measures.items():
        setattr(result, name, measure)

    # 8. Axis, using each lead's own PR-segment baseline.
    baselines = {
        lead: [d.baseline_mv for d in per_beat]
        for lead, per_beat in delineation.per_lead.items()
    }
    result.axis = axis_module.measure(filtered, beats, baselines, fs, leads, sqi)

    # 9. ST, per lead, then grouped by territory.
    result.st = st_module.measure_all(filtered, beats, fs, leads, sqi)
    result.territories = st_module.summarise_territories(result.st)

    # The T wave, per lead. The engine has always located it in order to measure
    # the QT interval and never measured it, which left step 8 of the nine-step
    # reading with no computed answer and therefore unmarkable.
    result.t_waves = twave_module.measure_all(filtered, beats, leads, fs)
    result.t_wave_finding = twave_module.summarise(result.t_waves)
    result.t_wave_inverted_leads = twave_module.abnormally_inverted(result.t_waves)

    _finalise(result, quality)
    return result


def _finalise(result: MeasurementResult, quality) -> None:
    """Overall confidence, servable status, and the warning list."""
    components = [
        result.heart_rate.confidence,
        result.qrs_duration.confidence,
        result.qt_interval.confidence,
        result.rhythm.confidence,
        quality.sqi_overall,
    ]
    if result.pr_interval.status is not MeasurementStatus.NOT_MEASURABLE:
        components.append(result.pr_interval.confidence)
    result.overall_confidence = float(np.median(components))

    if quality.flatline_leads:
        result.warnings.append(f"flatline_leads:{','.join(quality.flatline_leads)}")
    if quality.saturated_leads:
        result.warnings.append(f"saturated_leads:{','.join(quality.saturated_leads)}")
    if quality.n_beats_excluded:
        result.warnings.append(f"beats_excluded:{quality.n_beats_excluded}")

    absent = sum(1 for b in result.beats if b.p_status is PWaveStatus.ABSENT)
    uncertain = sum(1 for b in result.beats if b.p_status is PWaveStatus.UNCERTAIN)
    if absent:
        # Stated as a finding, not an error: no P wave is what atrial
        # fibrillation looks like, and the case bank needs those cases.
        result.warnings.append(f"p_wave_absent_in_{absent}_of_{len(result.beats)}_beats")
    if uncertain:
        result.warnings.append(f"p_wave_uncertain_in_{uncertain}_beats")

    if (
        result.pr_interval.status is MeasurementStatus.NEEDS_REVIEW
        and result.pr_interval.mad is not None
        and result.pr_interval.mad > config.PR_MAX_MAD_MS
    ):
        # Colon-separated so the batch summary groups these into one row: the
        # detail belongs in the per-case record, not in the tally.
        result.warnings.append(
            f"pr_unstable_waves_may_not_be_p_waves:mad_{result.pr_interval.mad:.0f}ms"
        )

    if result.t_wave_inverted_leads:
        # A finding, not a fault: reported so a reviewer sees it without opening
        # the per-lead detail.
        result.warnings.append(
            "t_wave_inverted_in:" + ",".join(result.t_wave_inverted_leads)
        )

    if (
        result.qt_interval.status is MeasurementStatus.NEEDS_REVIEW
        and result.qt_interval.value
        and result.rhythm.rr_mean_ms
    ):
        ratio = result.qt_interval.value / result.rhythm.rr_mean_ms
        if ratio > config.QT_MAX_RR_FRACTION:
            result.warnings.append(f"qt_over_extended:qt_is_{ratio:.0%}_of_rr")

    # Where the computed signal and the inherited diagnosis disagree.
    #
    # Atrial fibrillation and flutter are defined by the absence of organised P
    # waves, so a PR interval or P duration measured on such a record is a claim
    # the cardiologist's label contradicts. Three atrial fibrillation records in
    # the case bank produced exactly that, and two of them had a clean P wave
    # before nearly every QRS -- the engine was not malfunctioning, it was
    # measuring something real that the label says should not be there.
    #
    # So neither side wins automatically. The value is left exactly as computed
    # and withheld for a human to settle. Rewriting the measurement to match the
    # label would let an inherited diagnosis overwrite a computed fact, which is
    # the one thing this system is built not to do.
    conflicting_diagnoses = [
        code for code in config.P_ABSENT_DIAGNOSES if code in result.scp_codes
    ]
    if conflicting_diagnoses:
        withheld = [
            name
            for name in ("pr_interval", "p_duration")
            if getattr(result, name).status is MeasurementStatus.OK
        ]
        for name in withheld:
            getattr(result, name).status = MeasurementStatus.NEEDS_REVIEW
        if withheld:
            result.warnings.append(
                "diagnosis_conflict:{}_with_{}".format(
                    "_".join(code.lower() for code in conflicting_diagnoses),
                    "_and_".join(withheld),
                )
            )

    # The gate. Anything below the bar is withheld from the student bank until a
    # faculty reviewer has corrected it -- see the review queue in week 4.
    # PR and QT count here because they are graded steps: an unreliable value
    # would have the platform mark a correct student answer wrong.
    review_needed = (
        result.overall_confidence < config.CONFIDENCE_MIN
        or result.heart_rate.status is not MeasurementStatus.OK
        or result.qrs_duration.status is not MeasurementStatus.OK
        or result.pr_interval.status is MeasurementStatus.NEEDS_REVIEW
        or result.p_duration.status is MeasurementStatus.NEEDS_REVIEW
        or result.qt_interval.status is MeasurementStatus.NEEDS_REVIEW
    )
    result.status = MeasurementStatus.NEEDS_REVIEW if review_needed else MeasurementStatus.OK


__all__ = ["measure_record"]
