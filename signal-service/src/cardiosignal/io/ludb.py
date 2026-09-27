"""LUDB — the delineation answer key.

The Lobachevsky University Database: 200 records, 12 leads, ten seconds each at
500 Hz — structurally identical to PTB-XL — in which cardiologists have marked
the onset, peak and offset of every P wave, QRS complex and T wave, separately
in every lead.

That is the only thing in this project that can answer "how accurate is the
delineator, in milliseconds?" PTB-XL carries diagnoses, not boundaries, so
against PTB-XL alone the engine could only be checked by eye or by waiting
weeks for faculty corrections. LUDB gives a number per wave, per lead, today —
and it puts a figure on the P wave specifically, which is the risk the brief
names as the engine's weakest point.

Annotation format: each wave is a triple of consecutive annotations,

    '('   onset
    'p' | 'N' | 't'   peak, and which wave it is
    ')'   offset

so the file is parsed by walking the symbol stream and grouping triples. A wave
whose onset or offset is missing is kept with `None` in that slot rather than
dropped: an annotator declining to mark a boundary is information, and silently
discarding those waves would flatter the error statistics.

LUDB is a *test set*. It never enters the student case bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

from cardiosignal import config
from cardiosignal.types import Recording

WAVE_SYMBOLS = {"p": "P", "N": "QRS", "t": "T"}

# LUDB names leads in lower case; the annotation file extension is the lead name.
LEAD_TO_EXTENSION = {lead: lead.lower() for lead in config.LEADS}


@dataclass(frozen=True)
class WaveAnnotation:
    """One expert-marked wave. Indices are samples into the record."""

    wave: str  # "P" | "QRS" | "T"
    onset: int | None
    peak: int | None
    offset: int | None

    def duration_ms(self, fs: int = config.FS) -> float | None:
        if self.onset is None or self.offset is None:
            return None
        return (self.offset - self.onset) * 1000.0 / fs


def root() -> Path:
    return config.LUDB_ROOT


def is_available() -> bool:
    return (root() / "data").exists() and any((root() / "data").glob("*.dat"))


def list_records() -> list[str]:
    """Record stems, e.g. `['data/1', 'data/2', ...]`, in numeric order."""
    records_file = root() / "RECORDS"
    if records_file.exists():
        names = [line.strip() for line in records_file.read_text().splitlines() if line.strip()]
    else:
        names = [f"data/{p.stem}" for p in sorted((root() / "data").glob("*.dat"))]
    return sorted(names, key=lambda s: int(s.rsplit("/", 1)[-1]))


def load_signal(record: str) -> Recording:
    """Read one LUDB record into the same `Recording` shape as PTB-XL."""
    read = wfdb.rdrecord(str(root() / record))
    order = [read.sig_name.index(lead.lower()) for lead in config.LEADS if lead.lower() in read.sig_name]
    leads = tuple(lead for lead in config.LEADS if lead.lower() in read.sig_name)
    signal = np.asarray(read.p_signal, dtype=float)[:, order]
    return Recording(
        ecg_id=int(record.rsplit("/", 1)[-1]),
        source="ludb",
        signal=signal,
        leads=leads,
        sampling_rate=int(read.fs),
    )


def load_annotations(record: str, lead: str) -> list[WaveAnnotation]:
    """Expert boundaries for one lead, as a list of waves in time order."""
    extension = LEAD_TO_EXTENSION.get(lead)
    if extension is None:
        return []
    path = root() / f"{record}.{extension}"
    if not path.exists():
        return []

    ann = wfdb.rdann(str(root() / record), extension)
    samples, symbols = list(ann.sample), list(ann.symbol)

    waves: list[WaveAnnotation] = []
    for i, symbol in enumerate(symbols):
        if symbol not in WAVE_SYMBOLS:
            continue
        onset = samples[i - 1] if i > 0 and symbols[i - 1] == "(" else None
        offset = samples[i + 1] if i + 1 < len(symbols) and symbols[i + 1] == ")" else None
        waves.append(
            WaveAnnotation(
                wave=WAVE_SYMBOLS[symbol],
                onset=int(onset) if onset is not None else None,
                peak=int(samples[i]),
                offset=int(offset) if offset is not None else None,
            )
        )
    return waves


def load_all_annotations(record: str) -> dict[str, list[WaveAnnotation]]:
    """Every lead's annotations for one record."""
    return {lead: load_annotations(record, lead) for lead in config.LEADS}


def reference_r_peaks(record: str, lead: str = "II") -> np.ndarray:
    """QRS peak positions, for scoring the detector's sensitivity and PPV.

    Falls back through leads because a few records are missing the odd
    annotation file, and an absent file must not be read as "no beats here".
    """
    for candidate in (lead, "II", "I", "V5", "V2"):
        waves = [w for w in load_annotations(record, candidate) if w.wave == "QRS" and w.peak is not None]
        if waves:
            return np.asarray([w.peak for w in waves], dtype=int)
    return np.empty(0, dtype=int)


__all__ = [
    "LEAD_TO_EXTENSION",
    "WAVE_SYMBOLS",
    "WaveAnnotation",
    "is_available",
    "list_records",
    "load_all_annotations",
    "load_annotations",
    "load_signal",
    "reference_r_peaks",
    "root",
]
