"""Dataset-backed tests. These are the ones that produce claimable numbers.

Each skips cleanly when its dataset is absent, so the suite still runs on a
fresh clone.
"""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import conditions as cond
from cardiosignal import config


# --- LUDB: the delineation answer key --------------------------------------
@pytest.mark.needs_ludb
def test_ludb_annotations_parse_into_ordered_waves(ludb_records):
    from cardiosignal.io import ludb

    waves = ludb.load_annotations(ludb_records[0], "II")
    assert waves
    assert {w.wave for w in waves} <= {"P", "QRS", "T"}
    for wave in waves:
        if wave.onset is not None and wave.offset is not None:
            assert wave.onset < wave.offset
            if wave.peak is not None:
                assert wave.onset <= wave.peak <= wave.offset


@pytest.mark.needs_ludb
def test_ludb_signal_matches_ptbxl_shape(ludb_records):
    from cardiosignal.io import ludb

    recording = ludb.load_signal(ludb_records[0])
    assert recording.sampling_rate == config.FS
    assert np.asarray(recording.signal).shape == (5000, 12)
    assert recording.leads == config.LEADS


@pytest.mark.needs_ludb
@pytest.mark.slow
def test_beat_detection_meets_target_on_ludb(ludb_records):
    """Sensitivity and PPV against cardiologist-marked QRS positions."""
    from cardiosignal.validation.ludb_eval import evaluate

    report = evaluate(limit=40, progress=False)
    assert report.detection.sensitivity >= 0.97
    assert report.detection.ppv >= 0.97


@pytest.mark.needs_ludb
@pytest.mark.slow
def test_boundary_errors_stay_within_target_on_ludb(ludb_records):
    """The headline accuracy claim, in milliseconds, against expert annotation.

    Thresholds are set above the measured values with headroom, so this test
    catches a regression rather than restating today's number.
    """
    from cardiosignal.validation.ludb_eval import evaluate

    report = evaluate(limit=40, progress=False)

    qrs_onset = report.boundaries["QRS onset"]
    qrs_offset = report.boundaries["QRS offset"]
    t_offset = report.boundaries["T offset"]
    p_onset = report.boundaries["P onset"]

    assert qrs_onset.coverage > 0.95
    assert qrs_offset.coverage > 0.95
    assert qrs_onset.mae_ms < 20.0
    assert qrs_offset.mae_ms < 16.0
    assert t_offset.mae_ms < 28.0
    assert p_onset.mae_ms < 20.0
    # P waves are the acknowledged weak point; coverage is the honest measure.
    assert p_onset.coverage > 0.60


# --- QTDB: the QT answer key ----------------------------------------------
@pytest.mark.needs_qtdb
@pytest.mark.slow
def test_qt_error_against_manual_annotation(qtdb_records):
    from cardiosignal.validation.qtdb_eval import evaluate

    report = evaluate(limit=20, progress=False)
    assert report.coverage > 0.80
    assert report.mae_ms < 45.0
    # Catastrophic failures are what matter for a teaching platform: a QT that
    # is out by 200 ms is a wrong answer, not an imprecise one.
    errors = np.abs(np.asarray(report.errors_ms))
    assert (errors > 200).mean() < 0.02


# --- PTB-XL: the case bank -------------------------------------------------
@pytest.mark.needs_ptbxl
def test_quality_gate_rejects_paced_and_noisy_records():
    import pandas as pd

    from cardiosignal.io import ptbxl

    if not ptbxl.is_available():
        pytest.skip("PTB-XL metadata not downloaded")

    paced = pd.Series({"pacemaker": "ja, pacemaker", "validated_by_human": True})
    noisy = pd.Series({"pacemaker": "", "validated_by_human": True, "burst_noise": "I-V6"})
    clean = pd.Series({"pacemaker": "", "validated_by_human": True})

    assert ptbxl.passes_quality_gate(paced) == (False, "paced")
    assert ptbxl.passes_quality_gate(noisy)[0] is False
    assert ptbxl.passes_quality_gate(clean)[0] is True


@pytest.mark.needs_ptbxl
def test_censored_age_is_normalised():
    """PTB-XL records every age above 89 as 300. Passed through, that reaches
    the generated patient scenario and produces a 300-year-old."""
    import pandas as pd

    from cardiosignal.io.ptbxl import _age

    assert _age(pd.Series({"age": 300.0})) == (config.AGE_CENSOR_CEILING, True)
    assert _age(pd.Series({"age": 57.0})) == (57.0, False)
    assert _age(pd.Series({"age": None})) == (None, False)


@pytest.mark.needs_ptbxl
def test_every_mapped_scp_code_exists_in_the_vocabulary():
    """Guards against a typo silently emptying a whole condition bucket."""
    from cardiosignal.io import ptbxl

    if not ptbxl.is_available():
        pytest.skip("PTB-XL metadata not downloaded")

    vocabulary = set(ptbxl.load_statements().index)
    for condition in cond.AVAILABLE:
        for code in condition.scp_codes:
            assert code in vocabulary, f"{condition.key}: unknown SCP code {code!r}"


def test_unavailable_conditions_are_declared_not_deleted():
    """VT and the electrolyte disturbances are on the brief's list and are not
    in PTB-XL. They stay in the file so the coverage report keeps naming them."""
    keys = {c.key for c in cond.UNAVAILABLE}
    assert {"ventricular_tachycardia", "hyperkalaemia", "hypokalaemia"} <= keys
    for condition in cond.UNAVAILABLE:
        assert condition.scp_codes == ()
        assert "NOT IN PTB-XL" in condition.note


def test_condition_matching_requires_all_codes_when_asked():
    assert cond.matches(cond.BY_KEY["normal_sinus"], {"NORM": 100.0, "SR": 0.0})
    assert not cond.matches(cond.BY_KEY["normal_sinus"], {"NORM": 100.0})
    assert cond.matches(cond.BY_KEY["svt"], {"PSVT": 100.0})


def test_a_record_can_satisfy_several_conditions():
    """An inferior MI with first-degree block is both, and teaches better for it."""
    keys = cond.conditions_for({"IMI": 100.0, "1AVB": 100.0})
    assert "mi_inferior" in keys and "av_block_1" in keys
