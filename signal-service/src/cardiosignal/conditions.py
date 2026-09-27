"""The syllabus condition list, mapped to PTB-XL's SCP-ECG codes.

Every code below was verified against `scp_statements.csv` and counted in
`ptbxl_database.csv` (21,799 records, v1.0.3). The counts in the comments are
record counts, not patient counts, and they are the reason this file exists:
the brief's target condition list and what PTB-XL can actually supply are not
the same list, and the difference has to be a decision taken with the nursing
faculty rather than a gap discovered in week 12.

Two conditions on the brief's list cannot be sourced from PTB-XL at all:

  * **Ventricular tachycardia** -- PTB-XL is ten-second resting ECGs from an
    outpatient population. There is no VT statement in the SCP vocabulary used;
    the only "ventricular tachycardia" matches are SVTAC and PSVT, which are
    *supra*ventricular. Teaching VT from this dataset is not possible.
  * **Hyperkalaemia / hypokalaemia** -- there are no electrolyte statements of
    any kind. PTB-XL annotates the trace, not the serum.

Four more exist but are scarce enough that the case bank cannot be balanced
around them: atrial flutter (73), SVT (51), third-degree block (16) and
second-degree block (14).

`UNAVAILABLE` entries are kept in this file deliberately. Deleting them would
hide the gap; keeping them means the coverage report names them every time it
runs, and the conversation with faculty happens.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Condition:
    """One teachable finding, and how to recognise it in the dataset."""

    key: str
    label: str
    group: str  # syllabus grouping: rhythm | conduction | ischaemia | chamber
    scp_codes: tuple[str, ...]
    target: int = 0  # candidates to draw for the review queue
    available: bool = True
    note: str = ""
    require_all: bool = False  # every code must be present, not just one
    exclude_codes: tuple[str, ...] = field(default_factory=tuple)


# Paced rhythms are out of scope per the brief, and a pacemaker spike invalidates
# every interval the engine measures.
GLOBAL_EXCLUDE_CODES = ("PACE",)

CONDITIONS: tuple[Condition, ...] = (
    # -- rhythm ------------------------------------------------------------
    Condition("normal_sinus", "Normal sinus rhythm", "rhythm", ("NORM", "SR"),
              target=90, require_all=True,
              note="9,514 NORM / 16,748 SR. The one condition in surplus."),
    Condition("sinus_bradycardia", "Sinus bradycardia", "rhythm", ("SBRAD",), target=40,
              note="637 records."),
    Condition("sinus_tachycardia", "Sinus tachycardia", "rhythm", ("STACH",), target=40,
              note="826 records."),
    Condition("atrial_fibrillation", "Atrial fibrillation", "rhythm", ("AFIB",), target=50,
              note="1,514 records. The key 'no P wave, irregularly irregular' case."),
    Condition("atrial_flutter", "Atrial flutter", "rhythm", ("AFLT",), target=25,
              note="Only 73 records -- expect few to survive the quality gate."),
    Condition("svt", "Supraventricular tachycardia", "rhythm", ("SVTAC", "PSVT"), target=20,
              note="27 + 24 = 51 records. Scarce."),
    Condition("ventricular_tachycardia", "Ventricular tachycardia", "rhythm", (), target=0,
              available=False,
              note="NOT IN PTB-XL. No VT statement exists in this vocabulary. Needs a "
                   "second source or removal from the committed condition list."),
    # -- conduction --------------------------------------------------------
    Condition("av_block_1", "First-degree AV block", "conduction", ("1AVB",), target=35,
              note="793 records."),
    Condition("av_block_2", "Second-degree AV block", "conduction", ("2AVB",), target=14,
              note="Only 14 records in the entire dataset. Take all of them."),
    Condition("av_block_3", "Third-degree AV block", "conduction", ("3AVB",), target=16,
              note="Only 16 records. Take all of them."),
    Condition("rbbb", "Right bundle branch block", "conduction", ("CRBBB",), target=35,
              note="541 complete RBBB (IRBBB is a separate, milder finding)."),
    Condition("lbbb", "Left bundle branch block", "conduction", ("CLBBB",), target=35,
              note="536 records."),
    # -- ischaemia and infarction -----------------------------------------
    # PTB-XL's INJ* statements are *subendocardial* injury, which presents as ST
    # depression, not elevation. They are not STEMI cases and must not be
    # labelled as such -- the brief's "STEMI by territory" requirement is not
    # satisfied by these codes. See docs/decisions/002.
    Condition("injury_anterior", "Subendocardial injury, anterior/anteroseptal", "ischaemia",
              ("INJAS", "INJAL"), target=30,
              note="214 + 145 records. ST depression, not elevation."),
    Condition("injury_inferior", "Subendocardial injury, inferior", "ischaemia",
              ("INJIN", "INJIL"), target=20,
              note="18 + 15 = 33 records. ST depression, not elevation. Scarce."),
    Condition("injury_lateral", "Subendocardial injury, lateral", "ischaemia", ("INJLA",),
              target=17, note="17 records. ST depression, not elevation."),
    Condition("mi_anterior", "Myocardial infarction, anterior territory", "ischaemia",
              ("AMI", "ASMI", "ALMI"), target=40,
              note="353 + 2,357 + 288 records. Evolved infarct pattern, not acute ST elevation."),
    Condition("mi_inferior", "Myocardial infarction, inferior territory", "ischaemia",
              ("IMI", "ILMI", "IPMI", "IPLMI"), target=40, note="2,676 + 478 + 33 + 51."),
    Condition("mi_lateral", "Myocardial infarction, lateral territory", "ischaemia",
              ("LMI",), target=25, note="201 records."),
    Condition("st_depression", "ST depression", "ischaemia", ("STD_",), target=35,
              note="1,009 records."),
    Condition("t_inversion", "T-wave inversion", "ischaemia", ("INVT",), target=30,
              note="294 records."),
    Condition("long_qt", "Long QT interval", "ischaemia", ("LNGQT",), target=20,
              note="117 records. Directly exercises the QTc teaching step."),
    # -- chamber enlargement ----------------------------------------------
    Condition("lvh", "Left ventricular hypertrophy", "chamber", ("LVH",), target=35,
              note="2,132 records."),
    Condition("rvh", "Right ventricular hypertrophy", "chamber", ("RVH",), target=20,
              note="126 records."),
    Condition("atrial_enlargement", "Atrial enlargement", "chamber", ("LAO/LAE", "RAO/RAE"),
              target=25, note="426 + 99 records."),
    # -- not obtainable ----------------------------------------------------
    Condition("hyperkalaemia", "Hyperkalaemia", "electrolyte", (), target=0, available=False,
              note="NOT IN PTB-XL. No electrolyte statements exist in the SCP vocabulary."),
    Condition("hypokalaemia", "Hypokalaemia", "electrolyte", (), target=0, available=False,
              note="NOT IN PTB-XL. As above."),
)

BY_KEY = {c.key: c for c in CONDITIONS}
AVAILABLE = tuple(c for c in CONDITIONS if c.available and c.scp_codes)
UNAVAILABLE = tuple(c for c in CONDITIONS if not c.available)


def matches(condition: Condition, codes: dict[str, float]) -> bool:
    """Whether one record's SCP codes satisfy a condition."""
    if not condition.scp_codes:
        return False
    if any(code in codes for code in condition.exclude_codes):
        return False
    if condition.require_all:
        return all(code in codes for code in condition.scp_codes)
    return any(code in codes for code in condition.scp_codes)


def conditions_for(codes: dict[str, float]) -> list[str]:
    """Every syllabus condition a record satisfies.

    A record can satisfy several -- an inferior MI with first-degree block is
    both, and is a better teaching case for being both.
    """
    return [c.key for c in AVAILABLE if matches(c, codes)]


def total_target() -> int:
    return sum(c.target for c in AVAILABLE)


__all__ = [
    "AVAILABLE",
    "BY_KEY",
    "CONDITIONS",
    "GLOBAL_EXCLUDE_CODES",
    "UNAVAILABLE",
    "Condition",
    "conditions_for",
    "matches",
    "total_target",
]
