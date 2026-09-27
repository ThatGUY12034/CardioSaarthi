"""Aggregation, rate, rhythm, axis and ST — the arithmetic, in isolation."""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.measure import aggregate, axis, rate, rhythm, st
from cardiosignal.types import AxisCategory, MeasurementStatus, Regularity, STFinding


# --- robust aggregation ----------------------------------------------------
def test_mad_is_unmoved_by_a_single_wild_value():
    """The reason MAD is used instead of a standard deviation."""
    clean = [160.0, 162.0, 158.0, 161.0, 159.0]
    poisoned = [*clean, 900.0]

    median_clean, mad_clean = aggregate.median_mad(clean)
    median_bad, mad_bad = aggregate.median_mad(poisoned)

    assert abs(median_bad - median_clean) <= 1.0
    assert mad_bad <= mad_clean + 1.0
    # ...whereas mean and SD are wrecked.
    assert abs(np.mean(poisoned) - np.mean(clean)) > 100
    assert np.std(poisoned) > 10 * np.std(clean)


def test_outlier_rejection_drops_the_artefact():
    kept = aggregate.reject_outliers([160.0, 162.0, 158.0, 161.0, 159.0, 900.0])
    assert 900.0 not in kept
    assert len(kept) == 5


def test_confidence_falls_as_spread_rises():
    tight = aggregate.confidence_score(160.0, 1.0, 0.95)
    loose = aggregate.confidence_score(160.0, 40.0, 0.95)
    assert tight > loose
    assert 0.0 <= loose <= tight <= 1.0


def test_confidence_falls_as_signal_quality_falls():
    assert aggregate.confidence_score(160.0, 2.0, 0.95) > aggregate.confidence_score(160.0, 2.0, 0.2)


def test_low_confidence_measures_are_withheld_for_review():
    measure = aggregate.robust_scalar([100.0, 200.0, 50.0, 300.0, 25.0], sqi=0.1)
    assert measure.status is MeasurementStatus.NEEDS_REVIEW
    assert not measure.servable


def test_pr_with_implausible_spread_is_withheld():
    """The atrial fibrillation failure mode, in isolation.

    A conduction time does not vary by 44 ms from beat to beat. When it appears
    to, the waves being measured are fibrillatory waves rather than P waves, and
    the relative confidence score does not notice -- 44 ms of spread on a 276 ms
    interval still scores 0.90. The gate has to be absolute.
    """
    from cardiosignal.detect.delineate import _ms  # noqa: F401  (fs conversion parity)
    from cardiosignal.measure import intervals
    from cardiosignal.types import BeatFiducials
    from cardiosignal.types import PWaveStatus as P

    fs = config.FS

    def beat(i: int, pr_ms: float) -> BeatFiducials:
        r = int((i + 1) * 0.8 * fs)
        qrs_on = r - int(0.04 * fs)
        return BeatFiducials(
            beat_index=i,
            r_index=r,
            p_onset=qrs_on - int(pr_ms / 1000 * fs),
            p_peak=qrs_on - int(pr_ms / 2000 * fs),
            p_offset=qrs_on - int(0.02 * fs),
            p_status=P.PRESENT,
            qrs_onset=qrs_on,
            qrs_offset=r + int(0.05 * fs),
            rr_prev_ms=800.0 if i else None,
        )

    steady = [beat(i, pr) for i, pr in enumerate([160, 162, 158, 161, 159, 160, 161])]
    erratic = [beat(i, pr) for i, pr in enumerate([160, 240, 120, 300, 190, 110, 265])]

    assert intervals.measure_all(steady, fs, sqi=0.99)["pr_interval"].status is MeasurementStatus.OK
    assert (
        intervals.measure_all(erratic, fs, sqi=0.99)["pr_interval"].status
        is MeasurementStatus.NEEDS_REVIEW
    )


def test_pr_needs_review_when_most_beats_have_no_p_wave():
    from cardiosignal.measure import intervals
    from cardiosignal.types import BeatFiducials
    from cardiosignal.types import PWaveStatus as P

    fs = config.FS
    beats = []
    for i in range(10):
        r = int((i + 1) * 0.8 * fs)
        qrs_on = r - int(0.04 * fs)
        present = i < 3  # only 30% carry a P wave
        beats.append(
            BeatFiducials(
                beat_index=i,
                r_index=r,
                p_onset=qrs_on - int(0.16 * fs) if present else None,
                p_offset=qrs_on - int(0.02 * fs) if present else None,
                p_status=P.PRESENT if present else P.ABSENT,
                qrs_onset=qrs_on,
                qrs_offset=r + int(0.05 * fs),
            )
        )
    assert (
        intervals.measure_all(beats, fs, sqi=0.99)["pr_interval"].status
        is MeasurementStatus.NEEDS_REVIEW
    )


def test_pr_is_withheld_when_the_rhythm_is_irregularly_irregular():
    """The spread gate alone is not enough.

    Fibrillatory waves can sit a *consistent* distance before each QRS purely by
    chance, producing a steady and entirely fictional PR interval that passes
    every consistency check. An irregularly irregular ventricular response says
    nothing is conducting at a fixed delay, so no PR interval may be served.
    """
    from cardiosignal.measure import intervals
    from cardiosignal.types import BeatFiducials
    from cardiosignal.types import PWaveStatus as P

    fs = config.FS
    beats = []
    for i in range(8):
        r = int((i + 1) * 0.8 * fs)
        qrs_on = r - int(0.04 * fs)
        beats.append(
            BeatFiducials(
                beat_index=i,
                r_index=r,
                p_onset=qrs_on - int(0.16 * fs),  # rock-steady 160 ms
                p_offset=qrs_on - int(0.02 * fs),
                p_status=P.PRESENT,
                qrs_onset=qrs_on,
                qrs_offset=r + int(0.05 * fs),
            )
        )

    steady = intervals.measure_all(beats, fs, sqi=0.99, regularity=Regularity.REGULAR)
    fibrillating = intervals.measure_all(
        beats, fs, sqi=0.99, regularity=Regularity.IRREGULARLY_IRREGULAR
    )

    assert steady["pr_interval"].status is MeasurementStatus.OK
    assert fibrillating["pr_interval"].status is MeasurementStatus.NEEDS_REVIEW


def test_qt_longer_than_most_of_the_cycle_is_withheld():
    """Repolarisation must finish before the next beat depolarises.

    A QT beyond ~65% of the R-R interval is an over-extended T offset, not a
    long QT — typically the tangent carried into the following P wave at faster
    rates. The corrections derived from it are withheld with it, because a QTc
    computed from a bad QT is just as wrong.
    """
    from cardiosignal.measure import intervals
    from cardiosignal.types import BeatFiducials
    from cardiosignal.types import PWaveStatus as P

    fs = config.FS

    def beats_with_qt(qt_ms: float, rr_ms: float) -> list[BeatFiducials]:
        out = []
        for i in range(8):
            r = int((i + 1) * rr_ms / 1000 * fs)
            qrs_on = r - int(0.04 * fs)
            out.append(
                BeatFiducials(
                    beat_index=i,
                    r_index=r,
                    p_onset=qrs_on - int(0.16 * fs),
                    p_offset=qrs_on - int(0.02 * fs),
                    p_status=P.PRESENT,
                    qrs_onset=qrs_on,
                    qrs_offset=r + int(0.05 * fs),
                    t_offset=qrs_on + int(qt_ms / 1000 * fs),
                    rr_prev_ms=rr_ms if i else None,
                )
            )
        return out

    rr = 630.0  # ~95 bpm, where the over-extension actually showed up
    sane = intervals.measure_all(beats_with_qt(300.0, rr), fs, sqi=0.99, median_rr_ms=rr)
    over = intervals.measure_all(beats_with_qt(525.0, rr), fs, sqi=0.99, median_rr_ms=rr)

    assert sane["qt_interval"].status is MeasurementStatus.OK
    assert over["qt_interval"].status is MeasurementStatus.NEEDS_REVIEW
    assert over["qtc_bazett"].status is MeasurementStatus.NEEDS_REVIEW
    assert over["qtc_fridericia"].status is MeasurementStatus.NEEDS_REVIEW
    # The value is still reported — a reviewer needs to see what was measured.
    assert over["qt_interval"].value is not None


def test_not_measurable_is_distinct_from_failed():
    """No P wave is a finding. It must never look like a broken algorithm."""
    absent = aggregate.robust_scalar([], not_measurable=True)
    broken = aggregate.robust_scalar([])
    assert absent.status is MeasurementStatus.NOT_MEASURABLE
    assert broken.status is MeasurementStatus.FAILED
    assert absent.status is not broken.status


# --- rate ------------------------------------------------------------------
def test_heart_rate_uses_mean_interval_not_mean_rate():
    """60 / mean(RR): the two differ whenever the rhythm is irregular."""
    fs = config.FS
    rr_ms = np.array([1000.0, 500.0])
    peaks = np.cumsum(np.r_[0.0, rr_ms]) * fs / 1000.0

    measured = rate.heart_rate(peaks.astype(int), fs, sqi=1.0)
    assert measured.value == pytest.approx(60000.0 / 750.0, rel=1e-6)
    assert measured.value != pytest.approx(np.mean([60.0, 120.0]))


def test_heart_rate_flags_bradycardia_and_tachycardia():
    fs = config.FS
    slow = rate.heart_rate(np.arange(0, 10) * int(1.5 * fs), fs, sqi=1.0)
    fast = rate.heart_rate(np.arange(0, 30) * int(0.4 * fs), fs, sqi=1.0)
    assert slow.value < config.HR_NORMAL_BPM[0]
    assert fast.value > config.HR_NORMAL_BPM[1]


# --- rhythm ----------------------------------------------------------------
def _peaks_from_rr(rr_ms: list[float], fs: int = config.FS) -> np.ndarray:
    return np.cumsum(np.r_[0.0, rr_ms] * fs / 1000.0).astype(int)


def test_metronomic_rhythm_is_regular():
    summary = rhythm.analyse(_peaks_from_rr([800.0] * 12), sqi=1.0)
    assert summary.regularity is Regularity.REGULAR
    assert summary.cv < config.CV_REGULAR


def test_chaotic_intervals_are_irregularly_irregular():
    rng = np.random.default_rng(3)
    rr = list(800 + rng.uniform(-250, 250, 16))
    summary = rhythm.analyse(_peaks_from_rr(rr), sqi=1.0)
    assert summary.regularity is Regularity.IRREGULARLY_IRREGULAR


def test_repeating_pattern_is_regularly_irregular():
    """Wenckebach: intervals shorten, a beat drops, the group repeats."""
    group = [700.0, 760.0, 820.0, 1400.0]
    summary = rhythm.analyse(_peaks_from_rr(group * 5), sqi=1.0)
    assert summary.regularity is Regularity.REGULARLY_IRREGULAR
    assert summary.autocorr_peak >= config.AUTOCORR_PERIODIC


def test_autocorrelation_separates_pattern_from_chaos():
    """The single test that distinguishes AF from Wenckebach."""
    patterned = np.asarray([700.0, 760.0, 820.0, 1400.0] * 5)
    rng = np.random.default_rng(5)
    chaotic = 800 + rng.uniform(-250, 250, 20)
    assert rhythm.rr_autocorrelation(patterned)[0] > rhythm.rr_autocorrelation(chaotic)[0]


# --- axis ------------------------------------------------------------------
def test_axis_uses_area_so_a_deep_s_wave_counts():
    """Peak height would call this positive; net area correctly calls it negative."""
    beat = np.zeros(100)
    beat[40:45] = 1.0  # tall, narrow R
    beat[45:70] = -0.4  # shallow, wide S -- larger in area
    area = axis.net_qrs_area(beat, 30, 90, baseline=0.0)
    assert area < 0
    assert beat.max() > abs(beat.min())  # peak height points the other way


@pytest.mark.parametrize(
    ("degrees", "category"),
    [
        (0.0, AxisCategory.NORMAL),
        (60.0, AxisCategory.NORMAL),
        (-45.0, AxisCategory.LEFT),
        (120.0, AxisCategory.RIGHT),
        (-120.0, AxisCategory.EXTREME),
    ],
)
def test_axis_quadrants(degrees, category):
    assert axis.categorise(degrees) is category


def test_axis_normal_range_matches_the_standard():
    assert config.AXIS_NORMAL_DEG == (-30.0, 90.0)


# --- ST --------------------------------------------------------------------
def test_v2_v3_carry_a_higher_elevation_threshold():
    """Normal early repolarisation is larger in V2-V3."""
    assert st.threshold_for("V2") == config.ST_THRESH_V2V3_MM
    assert st.threshold_for("V3") == config.ST_THRESH_V2V3_MM
    assert st.threshold_for("II") == config.ST_THRESH_LIMB_MM
    assert st.threshold_for("V2") > st.threshold_for("II")


def test_pr_segment_is_the_isoelectric_reference():
    x = np.zeros(1000)
    x[:400] = 0.25  # a baseline offset before the QRS
    assert st.pr_baseline(x, qrs_onset=390) == pytest.approx(0.25)


def test_territory_needs_two_contiguous_leads():
    """A single deviating lead is far more likely a contact problem."""
    from cardiosignal.types import STLeadMeasure

    one = [STLeadMeasure(lead="II", deviation_mm=2.0, finding=STFinding.ELEVATION)]
    two = [*one, STLeadMeasure(lead="III", deviation_mm=2.0, finding=STFinding.ELEVATION)]

    assert st.summarise_territories(one)[0].finding is STFinding.NORMAL
    inferior = next(t for t in st.summarise_territories(two) if t.territory == "inferior")
    assert inferior.finding is STFinding.ELEVATION
    assert set(inferior.leads_meeting_threshold) == {"II", "III"}


def test_territories_cover_the_expected_leads():
    assert config.TERRITORIES["inferior"] == ("II", "III", "aVF")
    assert config.TERRITORIES["anterior"] == ("V1", "V2", "V3", "V4")
