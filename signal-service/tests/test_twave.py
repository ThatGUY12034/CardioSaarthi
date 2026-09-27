"""Tests for T-wave polarity.

The failure that matters is a confident wrong direction: a flat T wave reported
as inverted, or an inversion in aVR reported as a finding, both of which would
mark a correct student answer wrong at step 8.
"""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.measure import twave
from cardiosignal.types import BeatFiducials, MeasurementStatus, TWaveFinding, TWaveLeadMeasure


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------
def test_a_clearly_positive_t_wave_is_upright():
    assert twave.classify(0.35, 0.35, -0.01) is TWaveFinding.UPRIGHT


def test_a_clearly_negative_t_wave_is_inverted():
    assert twave.classify(-0.30, 0.01, -0.30) is TWaveFinding.INVERTED


def test_a_small_deflection_is_flat_rather_than_given_a_direction():
    """Below a tenth of a millivolt the sign is noise. Calling that an inversion
    would invent a finding out of a wandering baseline."""
    assert twave.classify(0.04, 0.04, -0.02) is TWaveFinding.FLAT
    assert twave.classify(-0.06, 0.02, -0.06) is TWaveFinding.FLAT


def test_the_flat_threshold_is_a_boundary_not_a_range():
    just_under = config.T_FLAT_MV - 0.001
    just_over = config.T_FLAT_MV + 0.001
    assert twave.classify(just_under, just_under, 0.0) is TWaveFinding.FLAT
    assert twave.classify(just_over, just_over, 0.0) is TWaveFinding.UPRIGHT


def test_biphasic_needs_both_halves_to_be_real():
    """A T wave that dips slightly below the baseline is not biphasic. Requiring
    both excursions to clear the threshold stops every noisy T wave becoming
    one."""
    assert twave.classify(0.30, 0.30, -0.02) is TWaveFinding.UPRIGHT
    assert twave.classify(0.30, 0.30, -0.25) is TWaveFinding.BIPHASIC


# ---------------------------------------------------------------------------
# which inversions are abnormal
# ---------------------------------------------------------------------------
def _lead(name: str, finding: TWaveFinding) -> TWaveLeadMeasure:
    return TWaveLeadMeasure(
        lead=name,
        amplitude_mv=-0.3 if finding is TWaveFinding.INVERTED else 0.3,
        finding=finding,
        normally_inverted=name in config.T_NORMALLY_INVERTED_LEADS,
        n_beats=10,
        status=MeasurementStatus.OK,
    )


def test_inversion_in_avr_is_not_a_finding():
    """aVR looks at the heart from the opposite direction, so its T wave is
    normally inverted. Reporting it would flag almost every recording."""
    measures = [_lead("aVR", TWaveFinding.INVERTED), _lead("II", TWaveFinding.UPRIGHT)]
    assert twave.abnormally_inverted(measures) == []


@pytest.mark.parametrize("lead", config.T_NORMALLY_INVERTED_LEADS)
def test_the_normally_inverted_leads_are_all_excluded(lead):
    assert twave.abnormally_inverted([_lead(lead, TWaveFinding.INVERTED)]) == []


def test_inversion_where_it_should_be_upright_is_a_finding():
    measures = [
        _lead("I", TWaveFinding.INVERTED),
        _lead("aVL", TWaveFinding.INVERTED),
        _lead("aVR", TWaveFinding.INVERTED),
        _lead("II", TWaveFinding.UPRIGHT),
    ]
    # The lateral leads, and not aVR alongside them.
    assert twave.abnormally_inverted(measures) == ["I", "aVL"]


def test_v2_is_not_excluded():
    """Inversion in V2 is a recognised normal variant in young women, and is
    deliberately still reported: treating it as normal by default would hide
    anterior ischaemia, which is the more costly of the two mistakes."""
    assert twave.abnormally_inverted([_lead("V2", TWaveFinding.INVERTED)]) == ["V2"]


# ---------------------------------------------------------------------------
# the case-level answer
# ---------------------------------------------------------------------------
def test_abnormal_inversion_decides_the_summary():
    measures = [_lead(name, TWaveFinding.UPRIGHT) for name in ("II", "V4", "V5", "V6", "aVF", "III")]
    measures.append(_lead("V3", TWaveFinding.INVERTED))
    assert twave.summarise(measures) is TWaveFinding.INVERTED


def test_avr_alone_does_not_make_a_recording_inverted():
    measures = [_lead(name, TWaveFinding.UPRIGHT) for name in ("I", "II", "V4", "V5", "V6")]
    measures.append(_lead("aVR", TWaveFinding.INVERTED))
    assert twave.summarise(measures) is TWaveFinding.UPRIGHT


def test_too_few_measurable_leads_gives_no_answer():
    """Half the leads unmeasurable is not an answer of "flat", it is no answer,
    and the grader must not mark a student against it."""
    measures = [
        TWaveLeadMeasure(lead=name, status=MeasurementStatus.NOT_MEASURABLE)
        for name in config.LEADS
    ]
    assert twave.summarise(measures) is None


# ---------------------------------------------------------------------------
# measuring a synthetic trace
# ---------------------------------------------------------------------------
def _trace(t_amplitude_mv: float, fs: int = config.FS, beats: int = 8):
    """A flat baseline with a QRS and a T wave of known amplitude on each beat."""
    length = int(beats * 0.8 * fs) + fs
    x = np.zeros(length)
    fiducials = []
    for i in range(beats):
        r = int((i + 0.5) * 0.8 * fs)
        qrs_on, qrs_off = r - int(0.04 * fs), r + int(0.05 * fs)
        x[r - 5 : r + 5] += 1.0
        t_peak = qrs_off + int(0.20 * fs)
        width = int(0.06 * fs)
        x[t_peak - width : t_peak + width] += t_amplitude_mv * np.hanning(2 * width)
        fiducials.append(
            BeatFiducials(
                beat_index=i, r_index=r, qrs_onset=qrs_on, qrs_offset=qrs_off,
                t_peak=t_peak, t_offset=t_peak + width,
            )
        )
    return x, fiducials


def test_an_upright_t_wave_is_measured_at_about_its_true_amplitude():
    x, beats = _trace(0.40)
    measure = twave.measure_lead(x, beats, "II")

    assert measure.status is MeasurementStatus.OK
    assert measure.finding is TWaveFinding.UPRIGHT
    assert measure.amplitude_mv == pytest.approx(0.40, abs=0.05)
    assert measure.confidence > 0.9, "identical beats should agree closely"


def test_an_inverted_t_wave_is_measured_negative():
    x, beats = _trace(-0.35)
    measure = twave.measure_lead(x, beats, "V3")

    assert measure.finding is TWaveFinding.INVERTED
    assert measure.amplitude_mv == pytest.approx(-0.35, abs=0.05)


def test_a_lead_with_no_located_t_waves_is_not_measurable():
    x, beats = _trace(0.4)
    stripped = [b.model_copy(update={"t_peak": None}) for b in beats]
    assert twave.measure_lead(x, stripped, "II").status is MeasurementStatus.NOT_MEASURABLE


def test_the_st_segment_is_not_counted_as_part_of_the_t_wave():
    """ST deviation is a separate finding measured separately. Starting the T
    window at the J point would let an elevated ST segment read as a tall T."""
    x, beats = _trace(0.15)
    for beat in beats:
        # A large ST elevation immediately after the J point.
        x[beat.qrs_offset : beat.qrs_offset + int(0.04 * config.FS)] += 0.5

    measure = twave.measure_lead(x, beats, "V2")
    assert measure.amplitude_mv == pytest.approx(0.15, abs=0.06), (
        "the T amplitude should come from the T peak, not the ST segment"
    )
