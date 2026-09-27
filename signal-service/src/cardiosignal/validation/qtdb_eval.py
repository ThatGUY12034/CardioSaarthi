"""QT interval accuracy against the QT Database's manual annotations.

QT is the hardest of the taught intervals, because its end is the end of the T
wave and a T wave approaches baseline asymptotically -- there is no instant at
which it objectively stops. That is exactly why the tangent construction is
used, and exactly why it needs an external check: two reasonable methods can
disagree by 20 ms on the same beat.

What is scored is the *interval*, not the boundary. A T-offset error and a
QRS-onset error in the same direction cancel in the QT, and it is the QT that
gets taught and graded, so that is the number reported.

Only manually annotated beats are scored, matched to our beats by QRS position.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cardiosignal.detect.delineate import delineate_lead
from cardiosignal.detect.pan_tompkins import detect_r_peaks
from cardiosignal.io import qtdb
from cardiosignal.preprocess.filters import diagnostic_filter

# A QT of 26 seconds is not a long QT, it is a parsing artefact. The manual
# annotator marks only selected beats, so where a T wave is marked with no QRS
# marked before it, the T attaches to a QRS thousands of samples earlier. Two
# such beats out of 3,473 were enough on their own to move the pooled error from
# 31 ms to 117 ms and the standard deviation to 3.8 seconds.
#
# The upper bound is set at 1,200 ms rather than at something tighter so that
# genuinely long QT intervals -- which are exactly the records worth testing
# against -- are kept. Only the physically impossible is discarded, and the
# count of discards is reported.
REFERENCE_QT_RANGE_MS = (150.0, 1200.0)


@dataclass
class QtdbReport:
    n_records: int = 0
    n_records_with_annotations: int = 0
    errors_ms: list[float] = field(default_factory=list)
    n_reference_beats: int = 0
    n_reference_rejected: int = 0
    per_record_bias: list[float] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return len(self.errors_ms) / self.n_reference_beats if self.n_reference_beats else 0.0

    @property
    def mae_ms(self) -> float | None:
        return float(np.mean(np.abs(self.errors_ms))) if self.errors_ms else None

    @property
    def bias_ms(self) -> float | None:
        return float(np.mean(self.errors_ms)) if self.errors_ms else None

    @property
    def sd_ms(self) -> float | None:
        return float(np.std(self.errors_ms)) if len(self.errors_ms) > 1 else None

    @property
    def median_ae_ms(self) -> float | None:
        return float(np.median(np.abs(self.errors_ms))) if self.errors_ms else None

    def share_over(self, threshold_ms: float) -> float:
        """Fraction of beats wrong by more than `threshold_ms`.

        For a teaching platform this matters more than the mean: a QT out by
        200 ms is a wrong answer, not an imprecise one.
        """
        if not self.errors_ms:
            return 0.0
        return float((np.abs(np.asarray(self.errors_ms)) > threshold_ms).mean())


def evaluate(limit: int | None = None, progress: bool = True, match_ms: float = 100.0) -> QtdbReport:
    if not qtdb.is_available():
        raise FileNotFoundError("QTDB not found. Run: python scripts/download_data.py qtdb")

    records = qtdb.list_records()
    if limit:
        records = records[:limit]

    report = QtdbReport(n_records=len(records))
    iterator = records
    if progress:
        from tqdm import tqdm

        iterator = tqdm(records, unit="record")

    for record in iterator:
        try:
            reference = qtdb.load_reference_beats(record)
            marked = [b for b in reference if b.qrs_onset is not None and b.t_offset is not None]
            if not marked:
                continue

            recording = qtdb.load_signal(record)
            fs = recording.sampling_rate

            low, high = REFERENCE_QT_RANGE_MS
            usable = []
            for beat in marked:
                qt = beat.qt_ms(fs)
                if qt is not None and low <= qt <= high:
                    usable.append(beat)
                else:
                    report.n_reference_rejected += 1
            if not usable:
                continue

            report.n_records_with_annotations += 1
            report.n_reference_beats += len(usable)
            raw = np.asarray(recording.signal, dtype=float)
            detection = detect_r_peaks(raw, fs, recording.leads, reference_lead=recording.leads[0])
            if detection.n_beats == 0:
                report.failures.append(f"{record}: no beats detected")
                continue

            filtered = diagnostic_filter(raw, fs)
            # Score on the lead that yields the most measurable QT intervals --
            # QTDB's two leads are not a fixed pair across records, and the
            # annotators used whichever showed the T wave best.
            best: list[float] = []
            for j, lead in enumerate(recording.leads):
                beats = delineate_lead(filtered[:, j], detection.r_peaks, fs, lead)
                errors = _match(beats, usable, fs, match_ms)
                if len(errors) > len(best):
                    best = errors
            report.errors_ms.extend(best)
            if best:
                report.per_record_bias.append(float(np.mean(best)))
        except Exception as exc:
            report.failures.append(f"{record}: {type(exc).__name__}: {exc}")

    return report


def _match(beats, reference, fs: int, match_ms: float) -> list[float]:
    """Pair reference beats with ours by QRS onset, and difference the QTs."""
    tolerance = match_ms * fs / 1000.0
    ours = [b for b in beats if b.qrs_onset is not None and b.t_offset is not None]
    if not ours:
        return []
    onsets = np.asarray([b.qrs_onset for b in ours], dtype=float)

    errors: list[float] = []
    for ref in reference:
        distances = np.abs(onsets - ref.qrs_onset)
        nearest = int(np.argmin(distances))
        if distances[nearest] > tolerance:
            continue
        mine = ours[nearest]
        our_qt = (mine.t_offset - mine.qrs_onset) * 1000.0 / fs
        ref_qt = ref.qt_ms(fs)
        if ref_qt is None:
            continue
        errors.append(our_qt - ref_qt)
    return errors


def format_report(report: QtdbReport) -> str:
    def fmt(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "—"

    lines = [
        "### QT interval (QT Database, manual annotations)",
        "",
        "| metric | value |",
        "|---|---|",
        f"| Records with manual annotation | {report.n_records_with_annotations} of {report.n_records} |",
        f"| Annotated beats used | {report.n_reference_beats} |",
        f"| Annotated beats rejected as implausible | {report.n_reference_rejected} |",
        f"| Beats matched and measured | {len(report.errors_ms)} ({report.coverage * 100:.1f}%) |",
        f"| QT mean absolute error | {fmt(report.mae_ms)} ms |",
        f"| QT median absolute error | {fmt(report.median_ae_ms)} ms |",
        f"| QT bias (signed) | {fmt(report.bias_ms)} ms |",
        f"| QT SD of error | {fmt(report.sd_ms)} ms |",
        f"| Beats with error > 100 ms | {report.share_over(100.0) * 100:.1f}% |",
        "",
        "QTDB is sampled at 250 Hz, so one sample is 4 ms — a floor of roughly "
        f"±2 ms is inherent to the reference itself. Reference beats whose annotated "
        f"QT falls outside {REFERENCE_QT_RANGE_MS[0]:.0f}-{REFERENCE_QT_RANGE_MS[1]:.0f} ms "
        "are excluded: the manual annotator marks only selected beats, so a T wave "
        "marked without a preceding QRS attaches to a beat thousands of samples earlier "
        "and yields a 'QT' of tens of seconds. The count is reported above rather than "
        "quietly dropped.",
        "",
        "The median is given alongside the mean because the mean is sensitive to the "
        "small number of beats where the T wave is genuinely unmeasurable.",
    ]
    if report.failures:
        lines += ["", f"Failures: {len(report.failures)}."]
    return "\n".join(lines)


__all__ = ["QtdbReport", "evaluate", "format_report"]
