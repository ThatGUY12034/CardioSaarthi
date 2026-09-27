"""PTB-XL ingest — the case bank.

21,799 ten-second 12-lead records from 18,869 patients, with cardiologist
SCP-ECG annotations and, importantly for us, per-record signal-quality flags.

The diagnosis attached to every case the platform serves comes from here and is
never computed. That is the second half of the founding principle: measurements
are computed, diagnoses are inherited.

The quality gate is applied before anything else. A record with burst noise or
a loose electrode will produce measurements that look confident and are wrong,
and there is no reason to spend faculty review time discovering that when the
dataset already says so.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import wfdb

from cardiosignal import config
from cardiosignal.types import Recording

# Free-text quality columns. Empty means clean; anything else names a problem.
NOISE_COLUMNS = ("baseline_drift", "static_noise", "burst_noise", "electrodes_problems")


def root() -> Path:
    return config.PTBXL_ROOT


def is_available() -> bool:
    return (root() / "ptbxl_database.csv").exists()


@lru_cache(maxsize=1)
def load_metadata() -> pd.DataFrame:
    """`ptbxl_database.csv`, with `scp_codes` parsed from its literal form."""
    path = root() / "ptbxl_database.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python scripts/download_data.py ptbxl --metadata-only"
        )
    df = pd.read_csv(path, index_col="ecg_id")
    df["scp_codes"] = df["scp_codes"].apply(ast.literal_eval)
    return df


@lru_cache(maxsize=1)
def load_statements() -> pd.DataFrame:
    """`scp_statements.csv` — the code vocabulary and its diagnostic grouping."""
    return pd.read_csv(root() / "scp_statements.csv", index_col=0)


def describe_codes(codes: dict[str, float]) -> list[str]:
    """Human-readable descriptions for a record's SCP codes.

    These strings are the inherited diagnosis. They are copied to the student,
    never regenerated or paraphrased by a model.
    """
    statements = load_statements()
    out = []
    for code in codes:
        if code in statements.index:
            out.append(str(statements.loc[code, "description"]))
        else:
            out.append(code)
    return out


def quality_flags(row: pd.Series) -> dict[str, object]:
    return {
        "validated_by_human": bool(row.get("validated_by_human", False)),
        "second_opinion": bool(row.get("second_opinion", False)),
        "pacemaker": _has_text(row.get("pacemaker")),
        "extra_beats": _text(row.get("extra_beats")),
        **{column: _text(row.get(column)) for column in NOISE_COLUMNS},
    }


def _text(value: object) -> str:
    return "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value).strip()


def _has_text(value: object) -> bool:
    return bool(_text(value))


def passes_quality_gate(
    row: pd.Series,
    require_human_validation: bool = True,
    allow_noise: bool = False,
) -> tuple[bool, str]:
    """Whether a record may enter the candidate pool, and why not if not.

    The reason string is kept because the rejection tally is itself a reported
    figure -- knowing that, say, 38% of a scarce condition was lost to baseline
    drift is what tells faculty whether the condition is obtainable at all.
    """
    if _has_text(row.get("pacemaker")):
        return False, "paced"  # out of scope, and spikes corrupt every interval
    if require_human_validation and not bool(row.get("validated_by_human", False)):
        return False, "not_human_validated"
    if not allow_noise:
        for column in NOISE_COLUMNS:
            if _has_text(row.get(column)):
                return False, column
    return True, ""


def record_path(ecg_id: int, sampling_rate: int = 500) -> Path:
    meta = load_metadata()
    column = "filename_hr" if sampling_rate == 500 else "filename_lr"
    return root() / str(meta.loc[ecg_id, column])


def is_downloaded(ecg_id: int, sampling_rate: int = 500) -> bool:
    stem = record_path(ecg_id, sampling_rate)
    return stem.with_suffix(".hea").exists() and stem.with_suffix(".dat").exists()


def load_record(ecg_id: int, sampling_rate: int = 500) -> Recording:
    """One record as a `(n_samples, 12)` array in millivolts."""
    meta = load_metadata()
    if ecg_id not in meta.index:
        raise KeyError(f"ecg_id {ecg_id} is not in PTB-XL")
    row = meta.loc[ecg_id]

    stem = record_path(ecg_id, sampling_rate)
    if not stem.with_suffix(".hea").exists():
        raise FileNotFoundError(
            f"record {ecg_id} not downloaded ({stem}). Fetch it with:\n"
            f"  python scripts/download_data.py ptbxl --records-from <candidates.parquet>"
        )

    read = wfdb.rdrecord(str(stem))
    names = [name.upper() for name in read.sig_name]
    canonical = {lead.upper(): lead for lead in config.LEADS}
    order = [names.index(lead.upper()) for lead in config.LEADS if lead.upper() in names]
    leads = tuple(canonical[names[i]] for i in order)

    age, age_censored = _age(row)
    flags = quality_flags(row)
    flags["age_censored"] = age_censored

    return Recording(
        ecg_id=int(ecg_id),
        source="ptbxl",
        signal=np.asarray(read.p_signal, dtype=float)[:, order],
        leads=leads,
        sampling_rate=int(read.fs),
        age=age,
        sex={0: "male", 1: "female"}.get(int(row["sex"])) if not pd.isna(row["sex"]) else None,
        scp_codes=dict(row["scp_codes"]),
        report=_text(row.get("report")) or None,
        quality_flags=flags,
    )


def _age(row: pd.Series) -> tuple[float | None, bool]:
    """PTB-XL anonymises every age above 89 by recording it as 300.

    Left alone this reaches the generated patient scenario and produces a
    300-year-old, so it is normalised to the ceiling and flagged as censored
    rather than passed through or silently discarded.
    """
    value = row.get("age")
    if value is None or pd.isna(value):
        return None, False
    value = float(value)
    if value >= config.AGE_CENSOR_VALUE:
        return config.AGE_CENSOR_CEILING, True
    return value, False


__all__ = [
    "NOISE_COLUMNS",
    "describe_codes",
    "is_available",
    "is_downloaded",
    "load_metadata",
    "load_record",
    "load_statements",
    "passes_quality_gate",
    "quality_flags",
    "record_path",
    "root",
]
