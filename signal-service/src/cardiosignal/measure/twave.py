"""T-wave polarity, per lead.

The engine has always located the T wave -- it has to, in order to measure the
QT interval -- but never measured it. So step 8 of the nine-step reading had no
computed answer and could not be marked at all, while the other eight could.

What is measured here is the amplitude at the T peak against the PR-segment
baseline, the same isoelectric reference the ST measurement uses, so the two
numbers describe the same trace rather than two different ideas of zero.

Three judgements are encoded, and each is a place where the wrong call produces
a confident wrong answer:

* **Flat is a finding, not a direction.** Below a tenth of a millivolt the sign
  of the deflection is noise. Reporting that as an inversion would invent a
  finding out of a wandering baseline.
* **Biphasic requires both excursions to be real.** A T wave that crosses the
  baseline is biphasic only if both halves clear the flat threshold; otherwise
  every slightly noisy T wave becomes biphasic.
* **Inversion is not abnormal everywhere.** aVR looks at the heart from the
  opposite direction and its T wave is normally inverted; III and V1 are
  commonly inverted in healthy people. Which leads those are is a clinical
  judgement, held in config and flagged for nursing faculty rather than settled
  here.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from cardiosignal import config
from cardiosignal.measure.st import pr_baseline
from cardiosignal.types import BeatFiducials, MeasurementStatus, TWaveFinding, TWaveLeadMeasure


def _median_and_mad(values: Sequence[float]) -> tuple[float, float]:
    """Median and median absolute deviation, as everywhere else in the engine.

    One artefactual beat drags a mean and cannot move a median, and a T wave is
    exactly the part of the complex a single noisy beat distorts most.
    """
    array = np.asarray(values, dtype=float)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    return median, mad


def classify(peak_mv: float, positive_excursion_mv: float, negative_excursion_mv: float) -> TWaveFinding:
    """What this T wave is, from its peak and the extremes within its span."""
    both_present = (
        positive_excursion_mv >= config.T_BIPHASIC_MIN_MV
        and abs(negative_excursion_mv) >= config.T_BIPHASIC_MIN_MV
    )
    if both_present:
        return TWaveFinding.BIPHASIC
    if abs(peak_mv) < config.T_FLAT_MV:
        return TWaveFinding.FLAT
    return TWaveFinding.UPRIGHT if peak_mv > 0 else TWaveFinding.INVERTED


def measure_lead(
    x: np.ndarray,
    beats: Sequence[BeatFiducials],
    lead: str,
    fs: int = config.FS,
) -> TWaveLeadMeasure:
    """One lead's T wave, aggregated across the usable beats."""
    usable = [b for b in beats if not b.excluded]
    peaks: list[float] = []
    positives: list[float] = []
    negatives: list[float] = []

    window_start = int(config.T_WINDOW_START_MS * fs / 1000)

    for beat in usable:
        if beat.t_peak is None or beat.qrs_onset is None or beat.qrs_offset is None:
            continue
        baseline = pr_baseline(x, beat.qrs_onset, fs)
        if baseline is None:
            continue

        peaks.append(float(x[beat.t_peak]) - baseline)

        # The span the T wave occupies, starting clear of the ST segment so its
        # deviation does not count as part of the T wave.
        start = min(beat.qrs_offset + window_start, len(x) - 1)
        end = beat.t_offset if beat.t_offset is not None else beat.t_peak
        end = min(max(end, start + 1), len(x))
        if end <= start:
            continue
        span = np.asarray(x[start:end], dtype=float) - baseline
        positives.append(float(span.max()))
        negatives.append(float(span.min()))

    measure = TWaveLeadMeasure(lead=lead, n_beats=len(peaks))

    if not peaks or len(peaks) < config.T_MIN_BEAT_FRACTION * max(len(usable), 1):
        # Too few beats gave a T wave to describe the lead honestly.
        measure.status = MeasurementStatus.NOT_MEASURABLE
        return measure

    amplitude, mad = _median_and_mad(peaks)
    positive = float(np.median(positives)) if positives else 0.0
    negative = float(np.median(negatives)) if negatives else 0.0

    measure.amplitude_mv = amplitude
    measure.mad_mv = mad
    measure.finding = classify(amplitude, positive, negative)
    measure.normally_inverted = lead in config.T_NORMALLY_INVERTED_LEADS

    # Beat-to-beat agreement, on the same shape as the other measures: spread
    # relative to size, so a large steady T wave scores better than a small
    # erratic one.
    scale = max(abs(amplitude), config.T_FLAT_MV)
    measure.confidence = float(max(0.0, min(1.0, 1.0 - mad / scale)))
    measure.status = MeasurementStatus.OK
    return measure


def measure_all(
    signal: np.ndarray,
    beats: Sequence[BeatFiducials],
    leads: Sequence[str] = config.LEADS,
    fs: int = config.FS,
) -> list[TWaveLeadMeasure]:
    return [
        measure_lead(np.asarray(signal)[:, index], beats, lead, fs)
        for index, lead in enumerate(leads)
    ]


def abnormally_inverted(measures: Sequence[TWaveLeadMeasure]) -> list[str]:
    """Leads whose T wave is inverted where it should be upright.

    aVR, III and V1 are excluded: an inverted T wave there is not a finding.
    Everything else counts, including V2, where inversion is a recognised normal
    variant in young women -- treating it as normal by default would hide
    anterior ischaemia, which is the more costly mistake of the two.
    """
    return [
        m.lead
        for m in measures
        if m.finding is TWaveFinding.INVERTED
        and not m.normally_inverted
        and m.status is MeasurementStatus.OK
    ]


def summarise(measures: Sequence[TWaveLeadMeasure]) -> TWaveFinding | None:
    """The case-level answer for step 8.

    Inversion where it should not be is the finding that matters, so it wins
    over everything else. Otherwise the reading is whatever most leads show.
    Returns None when too few leads could be measured to say anything.
    """
    measurable = [m for m in measures if m.status is MeasurementStatus.OK]
    if len(measurable) < len(measures) / 2:
        return None

    if abnormally_inverted(measurable):
        return TWaveFinding.INVERTED

    # The normally inverted leads are left out of the count, or aVR would drag
    # every normal recording toward "inverted".
    informative = [m for m in measurable if not m.normally_inverted]
    if not informative:
        return None

    counts: dict[TWaveFinding, int] = {}
    for m in informative:
        counts[m.finding] = counts.get(m.finding, 0) + 1
    return max(counts, key=counts.get)


__all__ = ["abnormally_inverted", "classify", "measure_all", "measure_lead", "summarise"]
