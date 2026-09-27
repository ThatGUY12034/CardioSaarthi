"""Tests for scenario generation.

All of these run without an API key, because the rules worth testing are in the
validation, not in the call. The one thing this module exists to prevent is a
generated vignette stating a clinical fact that the engine is supposed to
compute -- so that is what most of these check.
"""

from __future__ import annotations

import pytest

from cardiosignal import narrative


def _good(**overrides):
    base = {
        "presenting_complaint": "Attended after two days of feeling generally unwell and short of breath on stairs.",
        "history": "Hypertension for eight years, on amlodipine. Ex-smoker. No previous cardiac admissions.",
        "examination": "Comfortable at rest, chest clear, no peripheral oedema.",
        "vitals": {"blood_pressure": "142/88", "respiratory_rate": 18, "temperature_c": 36.8, "spo2_percent": 97},
        "relevant_labs": {},
        "medications": ["amlodipine 5 mg"],
    }
    base.update(overrides)
    return base


def test_a_well_formed_narrative_passes():
    assert narrative.validate(_good(), age=64, sex="male") == []


@pytest.mark.parametrize("field", narrative.REQUIRED_FIELDS)
def test_every_required_field_is_required(field):
    incomplete = _good()
    del incomplete[field]
    problems = narrative.validate(incomplete, age=64, sex="male")
    assert any(field in p for p in problems)


@pytest.mark.parametrize(
    "prose",
    [
        "The ECG shows a prolonged PR interval.",
        "Referred after a rate of 130 bpm was noted at triage.",
        "Ambulance strip showed QRS 140 ms.",
        "There was 2 mm of ST elevation on the paramedic recording.",
        "QTc was 480 ms on the previous admission.",
    ],
)
def test_a_vignette_stating_an_ecg_finding_is_refused(prose):
    """Refused even when the number is right.

    A student's task is to read the measurement off the tracing. A vignette that
    hands it to them destroys the exercise, and one that hands over a wrong
    number is worse: the platform would then mark a correct reading wrong.
    """
    problems = narrative.validate(_good(presenting_complaint=prose), age=64, sex="male")
    assert any("ECG finding" in p for p in problems), problems


def test_ordinary_clinical_prose_is_not_mistaken_for_an_ecg_claim():
    """The guard must not be so broad that it rejects normal writing."""
    fine = _good(
        history="Three previous admissions. Takes 5 mg amlodipine daily and 75 mg aspirin.",
        presenting_complaint="Two hours of central chest discomfort radiating to the left arm.",
    )
    assert narrative.validate(fine, age=64, sex="male") == []


def test_heart_rate_may_not_be_supplied_as_a_vital():
    supplied = _good(vitals={"blood_pressure": "120/80", "heart_rate_bpm": 72})
    problems = narrative.validate(supplied, age=64, sex="male")
    assert any("heart rate is measured" in p for p in problems), problems


def test_a_stated_age_must_match_the_record():
    wrong = _good(presenting_complaint="A 40-year-old presented with fatigue.")
    problems = narrative.validate(wrong, age=64, sex="male")
    assert any("states age" in p for p in problems), problems

    right = _good(presenting_complaint="A 64-year-old presented with fatigue.")
    assert narrative.validate(right, age=64, sex="male") == []


def test_the_wrong_sex_is_caught():
    problems = narrative.validate(
        _good(history="She has hypertension and takes amlodipine."), age=64, sex="male"
    )
    assert any("male" in p for p in problems), problems


def test_measured_heart_rate_replaces_whatever_the_model_wrote():
    """The line between the two halves of the system.

    The model wrote the patient; the engine measured the heart. Where the
    vignette needs a number the tracing already answers, it comes from the
    tracing.
    """
    tampered = _good(vitals={"blood_pressure": "120/80", "heart_rate_bpm": 60, "pulse": 60})
    merged = narrative.inject_computed_vitals(tampered, heart_rate=93.4)

    assert merged["vitals"]["heart_rate_bpm"] == 93
    assert merged["vitals"]["heart_rate_source"] == "measured from the recording"
    assert "pulse" not in merged["vitals"], "fields outside the allowed set must be dropped"
    assert merged["vitals"]["blood_pressure"] == "120/80"


def test_injection_leaves_heart_rate_out_when_there_is_none():
    merged = narrative.inject_computed_vitals(_good(), heart_rate=None)
    assert "heart_rate_bpm" not in merged["vitals"]


def test_censored_age_is_described_as_a_floor_not_a_number():
    """PTB-XL stores ages above 89 as 300. Writing "89" would invent a
    precision the data does not have."""
    prompt = narrative.build_user_prompt(
        age=89.0, sex="female", age_censored=True, diagnostic_labels=["sinus rhythm"]
    )
    assert "89 or older" in prompt


def test_the_prompt_carries_the_diagnosis_but_the_rules_forbid_naming_it():
    prompt = narrative.build_user_prompt(
        age=70, sex="male", age_censored=False, diagnostic_labels=["atrial fibrillation"]
    )
    assert "atrial fibrillation" in prompt
    assert "Never name or hint at the diagnosis" in narrative.SYSTEM_PROMPT


def test_the_german_clinician_note_is_passed_as_context_with_a_warning():
    prompt = narrative.build_user_prompt(
        age=56,
        sex="male",
        age_censored=False,
        diagnostic_labels=["atrial flutter"],
        clinical_report="2:1 Überleitung bei vorhofflattern, jetzt unter cordichin",
    )
    assert "Überleitung" in prompt
    assert "do not repeat" in prompt


def test_a_missing_clinician_note_simply_omits_the_section():
    prompt = narrative.build_user_prompt(
        age=56, sex="male", age_censored=False, diagnostic_labels=["sinus rhythm"], clinical_report=None
    )
    assert "Contemporaneous clinician note" not in prompt
