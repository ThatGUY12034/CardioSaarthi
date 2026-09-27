"""Clinical scenario generation -- the one place a model authors content.

Section 4.5 of the brief: one call per case produces the patient around the
tracing. Age, sex, presenting complaint, history, vitals, relevant labs. It runs
once, offline, and nothing it writes reaches a student before a reviewer has
approved it.

Everything in this module is pure: prompt construction and output validation,
no network. `scripts/generate_narratives.py` does the calling and the storing,
so the part with the rules in it can be tested without an API key.

What the model is not allowed to do
-----------------------------------
It does not state a single clinical fact about the ECG. Not the heart rate, not
an interval, not the diagnosis. Those are computed, and a model restating a
computed number is a model that can restate it wrong.

So the facts are *injected*, never requested: the vitals block gets its heart
rate from the measurement engine after generation, and `validate` rejects any
narrative whose prose states an ECG measurement of its own. A scenario that
says "ECG shows a PR interval of 240 ms" is refused even when 240 happens to be
the right answer, because the next one will not be.
"""

from __future__ import annotations

import re
from typing import Any

# Sections the model must produce. Nothing here is a clinical measurement.
REQUIRED_FIELDS = ("presenting_complaint", "history", "vitals", "examination")

OPTIONAL_FIELDS = ("relevant_labs", "medications")

# Caps keep the narrative readable on a case card and the cost predictable.
MAX_FIELD_CHARS = 700
MAX_TOTAL_CHARS = 2200

# Vitals the model may supply. Heart rate is deliberately absent: it is measured
# from the tracing and injected afterwards, so the scenario cannot contradict
# the ECG it is attached to.
ALLOWED_VITALS = ("blood_pressure", "respiratory_rate", "temperature_c", "spo2_percent")

# Prose that states an ECG measurement. The model is told not to; this is what
# catches it when it does anyway.
ECG_CLAIM_PATTERNS = (
    re.compile(r"\b(pr|qrs|qt|qtc|rr|p wave)\s*(interval|duration|segment)?\s*(of|is|was|:|=)?\s*\d", re.I),
    re.compile(r"\b\d+\s*(ms|msec|millisecond)", re.I),
    re.compile(r"\b(heart rate|rate|pulse)\s*(of|is|was|:|=)?\s*\d+\s*(bpm|beats)", re.I),
    re.compile(r"\becg\s+(shows|reveals|demonstrates|indicates)", re.I),
    re.compile(r"\b(st)\s*(segment|elevation|depression)\s*(of|is|was|:|=)?\s*\d", re.I),
    re.compile(r"\b\d+(\.\d+)?\s*(mm|mv)\b", re.I),
)

SYSTEM_PROMPT = """You write short clinical vignettes for a nursing ECG teaching platform.

You are given a confirmed cardiologist diagnosis for a real, de-identified ECG \
recording, plus the patient's real age and sex. You write the patient around it: \
why they presented, their relevant history, their observations on arrival.

Absolute rules:

1. Never state any ECG measurement or finding. No heart rate, no PR/QRS/QT \
interval, no ST deviation, no axis, no rhythm description. The platform computes \
those from the signal and a student's task is to read them off the tracing \
themselves. A vignette that gives them away destroys the exercise.

2. Never name or hint at the diagnosis. Write a presentation consistent with it, \
not a description of it. "Palpitations since this morning" is right; "presented \
with atrial fibrillation" is not.

3. Use the age and sex you are given exactly. Do not invent a different patient.

4. Stay plausible and ordinary. Most patients are unremarkable. Do not write \
dramatic or unusual presentations unless the diagnosis demands it.

5. British English, plain clinical prose, no markdown, no headings inside fields.

Return a single JSON object and nothing else, with these keys:

  presenting_complaint  one or two sentences, the reason for the encounter
  history               relevant past history, risk factors, current medications
  examination           general examination findings excluding anything cardiac \
rhythm related
  vitals                object with blood_pressure (e.g. "138/86"), \
respiratory_rate (integer), temperature_c (number), spo2_percent (integer)
  relevant_labs         object of test name to value, or an empty object
  medications           array of strings, may be empty

Keep each text field under 500 characters."""


def build_user_prompt(
    *,
    age: float | None,
    sex: str | None,
    age_censored: bool,
    diagnostic_labels: list[str],
    clinical_report: str | None = None,
) -> str:
    """The per-case half of the prompt.

    The dataset's own cardiologist report is included when present. It is German
    free text written at the time of recording, and it carries clinical context
    -- medication, prior events, why the study was ordered -- that nothing else
    in the record has. The model is told to use it for context only, because it
    frequently states the ECG findings outright.
    """
    if age is None:
        age_line = "Age: not recorded"
    elif age_censored:
        # The source dataset stores ages above 89 as 300 to prevent
        # re-identification. Saying "89" flatly would invent a precision the
        # data does not have.
        age_line = "Age: 89 or older (exact age withheld by the source dataset)"
    else:
        age_line = f"Age: {age:.0f}"

    parts = [
        "Write the clinical vignette for this patient.",
        "",
        age_line,
        f"Sex: {sex or 'not recorded'}",
        "",
        "Confirmed cardiologist diagnosis for this recording:",
    ]
    parts.extend(f"  - {label}" for label in diagnostic_labels or ["no diagnostic statement recorded"])

    if clinical_report and clinical_report.strip():
        parts += [
            "",
            "Contemporaneous clinician note, in German, from the original recording.",
            "Use it only for background such as medication, prior events or the reason",
            "for the study. It often states the ECG findings directly; do not repeat",
            "any of those, and do not translate it verbatim:",
            f"  {clinical_report.strip()[:600]}",
        ]

    parts += ["", "Return only the JSON object."]
    return "\n".join(parts)


def validate(narrative: dict[str, Any], *, age: float | None, sex: str | None) -> list[str]:
    """Problems that make a narrative unusable. Empty list means it passed.

    Returns every problem rather than the first, so one repair pass can address
    all of them instead of discovering them one call at a time.
    """
    problems: list[str] = []

    if not isinstance(narrative, dict):
        return ["narrative is not a JSON object"]

    for field in REQUIRED_FIELDS:
        if field not in narrative:
            problems.append(f"missing required field '{field}'")

    text_fields = {
        key: value
        for key, value in narrative.items()
        if key != "vitals" and isinstance(value, str)
    }

    for key, value in text_fields.items():
        if len(value) > MAX_FIELD_CHARS:
            problems.append(f"'{key}' is {len(value)} characters, over the {MAX_FIELD_CHARS} limit")

    prose = " ".join(text_fields.values())
    if len(prose) > MAX_TOTAL_CHARS:
        problems.append(f"narrative is {len(prose)} characters, over the {MAX_TOTAL_CHARS} limit")

    # The rule the whole module exists to enforce.
    for pattern in ECG_CLAIM_PATTERNS:
        match = pattern.search(prose)
        if match:
            problems.append(
                f"states an ECG finding in prose: {match.group(0).strip()!r}. "
                "Measurements are computed from the signal and must not appear in the vignette."
            )
            break

    vitals = narrative.get("vitals")
    if vitals is not None and not isinstance(vitals, dict):
        problems.append("'vitals' is not an object")
    elif isinstance(vitals, dict):
        for key in vitals:
            if key not in ALLOWED_VITALS:
                problems.append(
                    f"vitals contains '{key}'. Only {', '.join(ALLOWED_VITALS)} may be supplied; "
                    "heart rate is measured from the tracing and injected afterwards."
                )

    problems.extend(_age_problems(prose, age))

    if sex:
        wrong = {"male": ("she ", "her ", "woman", "female"), "female": ("he ", "his ", "man", "male")}
        for token in wrong.get(sex.lower(), ()):
            if token in prose.lower():
                problems.append(f"narrative refers to a {sex} patient as {token.strip()!r}")
                break

    return problems


def _age_problems(prose: str, age: float | None) -> list[str]:
    """Ages stated in the prose must match the record's real age."""
    if age is None:
        return []
    stated = {int(m) for m in re.findall(r"\b(\d{1,3})[- ]?year[- ]old", prose, re.I)}
    wrong = {value for value in stated if abs(value - age) > 1}
    if wrong:
        return [f"prose states age {sorted(wrong)} but the record says {age:.0f}"]
    return []


def inject_computed_vitals(narrative: dict[str, Any], *, heart_rate: float | None) -> dict[str, Any]:
    """Put the measured heart rate into the vitals, replacing anything there.

    This is the line between the two halves of the system. The model wrote the
    patient; the engine measured the heart. Where the vignette needs a number
    the tracing already answers, it comes from the tracing.
    """
    vitals = dict(narrative.get("vitals") or {})
    vitals = {key: value for key, value in vitals.items() if key in ALLOWED_VITALS}
    if heart_rate is not None:
        vitals["heart_rate_bpm"] = round(float(heart_rate))
        vitals["heart_rate_source"] = "measured from the recording"
    return {**narrative, "vitals": vitals}


__all__ = [
    "ALLOWED_VITALS",
    "MAX_FIELD_CHARS",
    "MAX_TOTAL_CHARS",
    "REQUIRED_FIELDS",
    "SYSTEM_PROMPT",
    "build_user_prompt",
    "inject_computed_vitals",
    "validate",
]
