"""QT Database — the QT answer key.

105 two-lead recordings in which cardiologists manually annotated QRS onset and
T offset on a subset of beats (roughly 30 per record). It is the set the
QT-measurement literature benchmarks against, which is the reason to use it:
it makes our QT error directly comparable to published numbers rather than a
figure only we can interpret.

It is sampled at 250 Hz, not 500, so nothing here may assume `config.FS`. The
sampling rate is read from each header and threaded through.

Annotation layout is the same WFDB boundary convention LUDB uses -- `(` onset,
`p`/`N`/`t` peak, `)` offset -- so the parser is shared in shape, but the
manual annotator (`.q1c`) marks only selected beats, so absence of an
annotation means "not assessed here", never "no wave".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

from cardiosignal import config
from cardiosignal.io.ludb import WAVE_SYMBOLS, WaveAnnotation
from cardiosignal.types import Recording

# .q1c is the primary manual annotation; .q2c is the second reader where present.
MANUAL_ANNOTATORS = ("q1c", "q2c")


@dataclass(frozen=True)
class ReferenceBeat:
    """One manually annotated beat: what the cardiologist marked."""

    qrs_onset: int | None
    qrs_peak: int | None
    qrs_offset: int | None
    t_offset: int | None
    p_onset: int | None

    def qt_ms(self, fs: int) -> float | None:
        if self.qrs_onset is None or self.t_offset is None:
            return None
        return (self.t_offset - self.qrs_onset) * 1000.0 / fs


def root() -> Path:
    return config.QTDB_ROOT


def is_available() -> bool:
    return root().exists() and any(root().glob("*.dat"))


def list_records() -> list[str]:
    records_file = root() / "RECORDS"
    if records_file.exists():
        return [line.strip() for line in records_file.read_text().splitlines() if line.strip()]
    return sorted(p.stem for p in root().glob("*.dat"))


def available_annotator(record: str) -> str | None:
    """Which manual annotator this record actually carries."""
    for extension in MANUAL_ANNOTATORS:
        if (root() / f"{record}.{extension}").exists():
            return extension
    return None


def load_signal(record: str) -> Recording:
    """Read a QTDB record. Leads are named by the header, and there are two."""
    read = wfdb.rdrecord(str(root() / record))
    signal = np.asarray(read.p_signal, dtype=float)
    # QTDB carries occasional NaN samples where the digitiser dropped out.
    if np.isnan(signal).any():
        signal = np.nan_to_num(signal, nan=0.0)
    return Recording(
        ecg_id=abs(hash(record)) % 1_000_000,
        source="qtdb",
        signal=signal,
        leads=tuple(read.sig_name),
        sampling_rate=int(read.fs),
    )


def load_reference_beats(record: str) -> list[ReferenceBeat]:
    """Parse the manual annotation stream into per-beat boundary sets.

    A beat is delimited by its QRS: annotations are walked in order and a new
    beat starts at each `N` peak, so a T wave is attached to the QRS that
    precedes it.
    """
    extension = available_annotator(record)
    if extension is None:
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

    beats: list[ReferenceBeat] = []
    current: dict[str, int | None] = {}
    pending_p: int | None = None

    for wave in waves:
        if wave.wave == "P":
            pending_p = wave.onset
        elif wave.wave == "QRS":
            if current:
                beats.append(_close(current))
            current = {
                "qrs_onset": wave.onset,
                "qrs_peak": wave.peak,
                "qrs_offset": wave.offset,
                "t_offset": None,
                "p_onset": pending_p,
            }
            pending_p = None
        elif wave.wave == "T" and current:
            current["t_offset"] = wave.offset
    if current:
        beats.append(_close(current))
    return beats


def _close(data: dict[str, int | None]) -> ReferenceBeat:
    return ReferenceBeat(
        qrs_onset=data.get("qrs_onset"),
        qrs_peak=data.get("qrs_peak"),
        qrs_offset=data.get("qrs_offset"),
        t_offset=data.get("t_offset"),
        p_onset=data.get("p_onset"),
    )


__all__ = [
    "MANUAL_ANNOTATORS",
    "ReferenceBeat",
    "available_annotator",
    "is_available",
    "list_records",
    "load_reference_beats",
    "load_signal",
    "root",
]
