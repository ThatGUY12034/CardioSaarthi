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


# ---------------------------------------------------------------------------
# diagnosis leakage
# ---------------------------------------------------------------------------
def test_naming_the_diagnosis_is_refused():
    """The vignette is read before the tracing.

    A history saying "previous silent inferior myocardial infarction" answers
    the case before the student has looked at anything, which is what section
    5.4 of the brief forbids.
    """
    leaked = _good(
        history="Previous silent inferior myocardial infarction diagnosed on screening."
    )
    problems = narrative.validate(
        leaked, age=56, sex="male", diagnostic_labels=["inferior myocardial infarction"]
    )
    assert any("gives the diagnosis away" in p for p in problems), problems


def test_an_abbreviation_of_the_diagnosis_is_refused():
    """A model told not to write "atrial fibrillation" will happily write "AF"."""
    leaked = _good(presenting_complaint="Known AF, now with palpitations.")
    problems = narrative.validate(
        leaked, age=70, sex="male", diagnostic_labels=["atrial fibrillation"]
    )
    assert any("gives the diagnosis away" in p for p in problems), problems


def test_a_consistent_presentation_that_names_nothing_passes():
    """Family history of sudden death is a legitimate clue for long QT. It is
    consistent with the diagnosis without naming it, which is exactly right."""
    subtle = _good(
        presenting_complaint="Intermittent palpitations and lightheadedness for three weeks.",
        history="Hypertension on amlodipine. Hypothyroidism on levothyroxine. Mother died suddenly at 52.",
    )
    assert narrative.validate(
        subtle, age=48, sex="female", diagnostic_labels=["long QT-interval", "sinus rhythm"]
    ) == []


@pytest.mark.parametrize(
    "prose",
    [
        "Symptoms began 20 minutes after lunch.",
        "Seen in the minor injuries unit after a fall.",
        "Afterwards the discomfort settled without treatment.",
    ],
)
def test_the_leak_check_respects_word_boundaries(prose):
    """'mi' must not fire inside 'minutes', nor 'af' inside 'after'.

    Without word boundaries this check rejects ordinary prose, which costs a
    repair call on almost every case.
    """
    assert narrative.diagnosis_leaks(prose, ["inferior myocardial infarction"]) == []


def test_leakage_is_only_checked_against_this_case_s_diagnosis():
    """Mentioning a condition the case does not have is not a leak."""
    assert narrative.diagnosis_leaks(
        "Long-standing hypertrophy of the left ventricle on a previous scan.",
        ["atrial fibrillation"],
    ) == []


# ---------------------------------------------------------------------------
# the substring bug
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "prose",
    [
        "The patient attended today and this began yesterday.",
        "She is a woman of 48 with no cardiac history.",
        "Her observations were stable throughout.",
    ],
)
def test_ordinary_prose_about_a_female_patient_is_not_flagged(prose):
    """Substring matching saw "he" inside "the", "man" inside "woman" and
    "male" inside "female", which rejected almost every vignette written about a
    female patient. Word boundaries are not optional here."""
    assert narrative._pronoun_problems(prose, "female") == []


@pytest.mark.parametrize(
    "prose",
    [
        "The patient attended with further discomfort; his mother drove him.",
        "He is a man of 60 with a smoking history.",
    ],
)
def test_ordinary_prose_about_a_male_patient_is_not_flagged(prose):
    assert narrative._pronoun_problems(prose, "male") == []


def test_a_vignette_written_about_the_wrong_sex_is_still_caught():
    assert narrative._pronoun_problems("He attended with his wife.", "female")
    assert narrative._pronoun_problems("She attended with her husband.", "male")


def test_a_relative_of_the_other_sex_does_not_trip_the_check():
    """Counted rather than searched for, so a mentioned relative is fine as long
    as the vignette is predominantly about the right patient."""
    prose = "She attended with her husband, who said he had noticed her looking pale."
    assert narrative._pronoun_problems(prose, "female") == []


# ---------------------------------------------------------------------------
# the prompt
# ---------------------------------------------------------------------------
def test_the_prompt_gives_no_example_observations_to_copy():
    """Three vignettes in a row came back with identical vitals -- 138/86, 36.8,
    98% -- because the example value in the prompt became the answer every
    time."""
    assert "138/86" not in narrative.SYSTEM_PROMPT
    assert "identical values across different patients" in narrative.SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# reply parsing
# ---------------------------------------------------------------------------
def _extract():
    import sys
    sys.path.insert(0, str(REPO_ROOT_SCRIPTS))
    from generate_narratives import _extract_json
    return _extract_json


REPO_ROOT_SCRIPTS = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"


def test_plain_json_parses():
    assert _extract()('{"a": 1}') == {"a": 1}


def test_a_fenced_block_parses():
    assert _extract()('```json\n{"a": 1}\n```') == {"a": 1}


def test_a_preamble_before_the_object_parses():
    """A weaker model sometimes writes a sentence first. The object is there, so
    discarding the whole reply would waste a call for nothing."""
    assert _extract()('Here is the vignette:\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_an_empty_reply_is_transient_not_fatal():
    from generate_narratives import TransientError

    with pytest.raises(TransientError):
        _extract()("   ")


def test_a_reply_with_no_object_is_transient():
    from generate_narratives import TransientError

    with pytest.raises(TransientError):
        _extract()("I cannot help with that request.")


# ---------------------------------------------------------------------------
# telling the model, rather than only catching it
# ---------------------------------------------------------------------------
def test_the_prompt_names_the_words_that_would_give_this_case_away():
    """Every rejection in the first large run was the same failure: a vignette
    for an infarction case opening its history with "previous myocardial
    infarction". A model told "never name the diagnosis" does not reliably work
    out which words those are, so it is told."""
    prompt = narrative.build_user_prompt(
        age=70, sex="male", age_censored=False,
        diagnostic_labels=["inferior myocardial infarction"],
    )
    for term in ("infarction", "infarct", "stemi", "heart attack"):
        assert term in prompt, term
    assert "in any tense, including as past medical history" in prompt


def test_the_instruction_and_the_validator_cannot_drift_apart():
    """Whatever the model is told not to write is exactly what it would be
    rejected for writing, because both read the same alias table."""
    labels = ["atrial fibrillation", "left ventricular hypertrophy"]
    for term in narrative.forbidden_terms(labels):
        assert narrative.diagnosis_leaks(f"history of {term} noted", labels), term


def test_a_case_with_nothing_to_hide_gets_no_forbidden_list():
    prompt = narrative.build_user_prompt(
        age=40, sex="female", age_censored=False, diagnostic_labels=["normal ECG"],
    )
    assert "must not appear anywhere" not in prompt
