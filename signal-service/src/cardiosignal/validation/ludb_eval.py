"""Score the detector and the delineator against LUDB's expert annotations.

Two questions, answered separately because a failure in the first invalidates
any answer to the second:

  1. Does the detector find the beats?      sensitivity and PPV
  2. Are the boundaries in the right place?  mean absolute error, in ms

Matching rules matter as much as the errors themselves, so they are explicit:

  * A detected R peak counts as a true positive if an expert QRS peak lies
    within `RPEAK_MATCH_WINDOW_MS`, and each expert peak may be claimed once.
    Without the one-to-one constraint a detector that fires twice per beat
    would score 100% sensitivity.

  * A boundary error is only computed for beats the detector actually found and
    the expert actually marked. Boundaries we failed to produce are counted
    separately as *coverage*, never averaged in as zero error. A delineator
    that reports nothing would otherwise score a perfect MAE.

Both numbers are reported. Coverage without accuracy is worthless, and accuracy
without coverage is a lie of omission.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

from cardiosignal import config
from cardiosignal.detect.delineate import LeadBeatDelineation, delineate_lead
from cardiosignal.detect.pan_tompkins import detect_r_peaks
from cardiosignal.io import ludb
from cardiosignal.preprocess.filters import diagnostic_filter


# ---------------------------------------------------------------------------
# Beat detection
# ---------------------------------------------------------------------------
@dataclass
class DetectionScore:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def sensitivity(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def ppv(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    def __iadd__(self, other: DetectionScore) -> DetectionScore:
        self.true_positives += other.true_positives
        self.false_positives += other.false_positives
        self.false_negatives += other.false_negatives
        return self


def annotated_span(annotations: dict[str, list[ludb.WaveAnnotation]]) -> tuple[int, int] | None:
    """First and last annotated sample across all leads.

    LUDB's experts did not annotate the full ten seconds -- typically the middle
    ~7.5 s, leaving the first and last beats unmarked. Scoring the detector over
    the whole record therefore counts perfectly correct beats outside that span
    as false positives, which is a defect in the scoring, not in the detector.
    Evaluation is confined to the annotated interval.
    """
    samples = [
        value
        for waves in annotations.values()
        for wave in waves
        for value in (wave.onset, wave.peak, wave.offset)
        if value is not None
    ]
    return (min(samples), max(samples)) if samples else None


def score_detection(
    detected: np.ndarray,
    reference: np.ndarray,
    fs: int = config.FS,
    window_ms: float = config.RPEAK_MATCH_WINDOW_MS,
    span: tuple[int, int] | None = None,
) -> DetectionScore:
    """One-to-one greedy matching within the tolerance window."""
    tolerance = window_ms * fs / 1000.0
    detected = np.sort(np.asarray(detected, dtype=float))
    reference = np.sort(np.asarray(reference, dtype=float))
    if span is not None:
        lo, hi = span[0] - tolerance, span[1] + tolerance
        detected = detected[(detected >= lo) & (detected <= hi)]
        reference = reference[(reference >= lo) & (reference <= hi)]
    claimed = np.zeros(reference.size, dtype=bool)
    score = DetectionScore()

    for d in detected:
        if reference.size == 0:
            score.false_positives += 1
            continue
        distances = np.abs(reference - d)
        distances[claimed] = np.inf
        nearest = int(np.argmin(distances))
        if distances[nearest] <= tolerance:
            claimed[nearest] = True
            score.true_positives += 1
        else:
            score.false_positives += 1

    score.false_negatives = int((~claimed).sum())
    return score


# ---------------------------------------------------------------------------
# Boundary delineation
# ---------------------------------------------------------------------------
@dataclass
class BoundaryErrors:
    """Signed errors in ms for one boundary type, pooled over beats and leads."""

    name: str
    errors_ms: list[float] = field(default_factory=list)
    n_reference: int = 0  # expert marked it
    n_produced: int = 0  # and we produced something to compare

    @property
    def coverage(self) -> float:
        return self.n_produced / self.n_reference if self.n_reference else 0.0

    @property
    def mae_ms(self) -> float | None:
        return float(np.mean(np.abs(self.errors_ms))) if self.errors_ms else None

    @property
    def bias_ms(self) -> float | None:
        """Mean *signed* error. A large bias is a systematic offset and is
        fixable; a large MAE with zero bias is scatter and is not."""
        return float(np.mean(self.errors_ms)) if self.errors_ms else None

    @property
    def sd_ms(self) -> float | None:
        return float(np.std(self.errors_ms)) if len(self.errors_ms) > 1 else None

    @property
    def p95_ms(self) -> float | None:
        return float(np.percentile(np.abs(self.errors_ms), 95)) if self.errors_ms else None


BOUNDARY_KEYS = (
    ("P onset", "P", "onset", "p_onset"),
    ("P offset", "P", "offset", "p_offset"),
    ("QRS onset", "QRS", "onset", "qrs_onset"),
    ("QRS offset", "QRS", "offset", "qrs_offset"),
    ("T offset", "T", "offset", "t_offset"),
)


def _nearest_beat(beats: list[LeadBeatDelineation], sample: int) -> LeadBeatDelineation | None:
    if not beats:
        return None
    return min(beats, key=lambda b: abs(b.r_index - sample))


def score_boundaries(
    beats: list[LeadBeatDelineation],
    annotations: Iterable[ludb.WaveAnnotation],
    into: dict[str, BoundaryErrors],
    fs: int = config.FS,
    window_ms: float = config.BOUNDARY_MATCH_WINDOW_MS,
) -> None:
    """Pair each expert boundary with our estimate on the same beat."""
    tolerance = window_ms * fs / 1000.0

    for wave in annotations:
        for label, wave_type, edge, attribute in BOUNDARY_KEYS:
            if wave.wave != wave_type:
                continue
            reference = getattr(wave, edge)
            if reference is None:
                continue
            bucket = into.setdefault(label, BoundaryErrors(label))
            bucket.n_reference += 1

            anchor = wave.peak if wave.peak is not None else reference
            beat = _nearest_beat(beats, anchor)
            if beat is None:
                continue
            estimate = getattr(beat, attribute)
            if estimate is None:
                continue
            # Guard against pairing our boundary with a different beat's wave.
            if abs(estimate - reference) > tolerance:
                continue
            bucket.n_produced += 1
            bucket.errors_ms.append((estimate - reference) * 1000.0 / fs)


# ---------------------------------------------------------------------------
# Whole-dataset run
# ---------------------------------------------------------------------------
@dataclass
class LudbReport:
    n_records: int = 0
    detection: DetectionScore = field(default_factory=DetectionScore)
    boundaries: dict[str, BoundaryErrors] = field(default_factory=dict)
    per_lead: dict[str, dict[str, BoundaryErrors]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def evaluate(
    records: list[str] | None = None,
    leads: tuple[str, ...] = config.LEADS,
    limit: int | None = None,
    progress: bool = True,
) -> LudbReport:
    """Run detection and delineation over LUDB and score both."""
    if not ludb.is_available():
        raise FileNotFoundError(
            "LUDB not found. Run: python scripts/download_data.py ludb"
        )

    records = records or ludb.list_records()
    if limit:
        records = records[:limit]

    report = LudbReport(n_records=len(records))
    iterator = records
    if progress:
        from tqdm import tqdm

        iterator = tqdm(records, unit="record")

    for record in iterator:
        try:
            recording = ludb.load_signal(record)
            raw = np.asarray(recording.signal, dtype=float)
            fs = recording.sampling_rate

            detection = detect_r_peaks(raw, fs, recording.leads)
            annotations = ludb.load_all_annotations(record)
            report.detection += score_detection(
                detection.r_peaks,
                ludb.reference_r_peaks(record),
                fs,
                span=annotated_span(annotations),
            )
            if detection.n_beats == 0:
                report.failures.append(f"{record}: no beats detected")
                continue

            filtered = diagnostic_filter(raw, fs)
            for j, lead in enumerate(recording.leads):
                if lead not in leads or not annotations.get(lead):
                    continue
                beats = delineate_lead(filtered[:, j], detection.r_peaks, fs, lead)
                score_boundaries(beats, annotations[lead], report.boundaries, fs)
                score_boundaries(
                    beats, annotations[lead], report.per_lead.setdefault(lead, {}), fs
                )
        except Exception as exc:
            report.failures.append(f"{record}: {type(exc).__name__}: {exc}")

    return report


def format_report(report: LudbReport) -> str:
    """Markdown, ready to paste into the validation chapter."""
    lines = [
        "### Beat detection (LUDB)",
        "",
        "| metric | value | target |",
        "|---|---|---|",
        f"| Sensitivity | {report.detection.sensitivity * 100:.2f}% | "
        f"{config.TARGET_RPEAK_SENSITIVITY * 100:.0f}% |",
        f"| PPV | {report.detection.ppv * 100:.2f}% | {config.TARGET_RPEAK_PPV * 100:.0f}% |",
        f"| True positives | {report.detection.true_positives} | |",
        f"| False positives | {report.detection.false_positives} | |",
        f"| False negatives | {report.detection.false_negatives} | |",
        "",
        "### Boundary delineation (LUDB, all leads pooled)",
        "",
        "| boundary | n | coverage | MAE ms | bias ms | SD ms | p95 ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, _wave, _edge, _attr in BOUNDARY_KEYS:
        bucket = report.boundaries.get(label)
        if bucket is None:
            lines.append(f"| {label} | 0 | — | — | — | — | — |")
            continue

        def fmt(value: float | None) -> str:
            return f"{value:.1f}" if value is not None else "—"

        lines.append(
            f"| {label} | {bucket.n_produced} | {bucket.coverage * 100:.1f}% | "
            f"{fmt(bucket.mae_ms)} | {fmt(bucket.bias_ms)} | {fmt(bucket.sd_ms)} | "
            f"{fmt(bucket.p95_ms)} |"
        )

    lines += [
        "",
        f"Records evaluated: {report.n_records}. Failures: {len(report.failures)}.",
        "",
        "*Coverage* is the share of expert-marked boundaries for which the engine "
        "produced a comparable estimate. Boundaries the engine declined to produce "
        "are counted here, not averaged into the error as zeros.",
    ]
    if report.failures:
        lines += ["", "<details><summary>Failures</summary>", ""]
        lines += [f"- {f}" for f in report.failures[:20]]
        lines += ["", "</details>"]
    return "\n".join(lines)


__all__ = [
    "BOUNDARY_KEYS",
    "BoundaryErrors",
    "DetectionScore",
    "LudbReport",
    "evaluate",
    "format_report",
    "score_boundaries",
    "score_detection",
]
