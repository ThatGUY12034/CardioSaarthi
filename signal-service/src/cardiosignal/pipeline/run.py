"""Batch pipeline: candidates in, measurements and images out.

Output goes to `artifacts/` as files rather than to a database. The database
schema is derived from `MeasurementResult` in week 4, once the engine's output
shape has stopped changing -- writing it now would mean writing it twice.

Layout::

    artifacts/
      measurements/<ecg_id>.json     one MeasurementResult per case
      images/<ecg_id>_clean.png      the examination image
      images/<ecg_id>_annotated.png  the feedback image
      measurements.parquet           flat table of every case
      run_summary.md                 what happened

Every case is attempted; a failure is recorded and the run continues. A batch
that stops on the first bad record is useless for a dataset this size.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from cardiosignal import config
from cardiosignal.engine import measure_record
from cardiosignal.io import ptbxl
from cardiosignal.preprocess.filters import diagnostic_filter
from cardiosignal.render.annotate import render_annotated
from cardiosignal.render.sheet import render_clean
from cardiosignal.types import MeasurementResult, MeasurementStatus


@dataclass
class RunSummary:
    n_requested: int = 0
    n_measured: int = 0
    n_ok: int = 0
    n_needs_review: int = 0
    n_failed: int = 0
    n_missing_file: int = 0
    failures: list[tuple[int, str]] = field(default_factory=list)
    warning_counts: dict[str, int] = field(default_factory=dict)

    def note_warnings(self, result: MeasurementResult) -> None:
        """Tally by warning *kind*, discarding the per-case detail.

        Warnings carry their specifics after a colon (or as an embedded count),
        so the raw strings are nearly all distinct. Grouping is what makes the
        summary readable: "328 cases had an absent P wave" is actionable,
        328 separate rows are not.
        """
        for warning in result.warnings:
            key = warning.split(":")[0].split("_in_")[0]
            self.warning_counts[key] = self.warning_counts.get(key, 0) + 1


def process_one(
    ecg_id: int,
    out_dir: Path,
    syllabus_conditions: list[str] | None = None,
    render: bool = True,
    sampling_rate: int = 500,
) -> MeasurementResult:
    """Measure and render a single case."""
    recording = ptbxl.load_record(ecg_id, sampling_rate)
    result = measure_record(recording)
    result.diagnostic_labels = ptbxl.describe_codes(recording.scp_codes)
    result.syllabus_conditions = syllabus_conditions or []

    measurements_dir = out_dir / "measurements"
    measurements_dir.mkdir(parents=True, exist_ok=True)
    (measurements_dir / f"{ecg_id}.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )

    if render:
        images = out_dir / "images"
        # Filter once and hand the same array to both renderers, so the clean
        # and annotated images are pixel-identical apart from the overlay.
        filtered = diagnostic_filter(recording.signal, recording.sampling_rate)
        render_clean(recording, images / f"{ecg_id}_clean.png", filtered=filtered)
        render_annotated(recording, result, images / f"{ecg_id}_annotated.png", filtered=filtered)

    return result


def run_batch(
    candidates: pd.DataFrame,
    out_dir: Path = config.ARTIFACT_ROOT,
    render: bool = True,
    limit: int | None = None,
    progress: bool = True,
    sampling_rate: int = 500,
) -> tuple[pd.DataFrame, RunSummary]:
    """Process a candidate table end to end."""
    if limit:
        candidates = candidates.head(limit)

    summary = RunSummary(n_requested=len(candidates))
    rows: list[dict] = []

    iterator = candidates.itertuples(index=False)
    if progress:
        from tqdm import tqdm

        iterator = tqdm(iterator, total=len(candidates), unit="case")

    for row in iterator:
        ecg_id = int(row.ecg_id)
        try:
            if not ptbxl.is_downloaded(ecg_id, sampling_rate):
                summary.n_missing_file += 1
                summary.failures.append((ecg_id, "waveform not downloaded"))
                continue

            conditions = [c for c in str(getattr(row, "syllabus_conditions", "")).split(";") if c]
            result = process_one(ecg_id, out_dir, conditions, render, sampling_rate)

            summary.n_measured += 1
            summary.note_warnings(result)
            if result.status is MeasurementStatus.OK:
                summary.n_ok += 1
            elif result.status is MeasurementStatus.NEEDS_REVIEW:
                summary.n_needs_review += 1
            else:
                summary.n_failed += 1
            rows.append(result.flat_row())
        except Exception as exc:
            summary.n_failed += 1
            summary.failures.append((ecg_id, f"{type(exc).__name__}: {exc}"))
            if len(summary.failures) <= 3:
                traceback.print_exc()

    table = pd.DataFrame(rows)
    if not table.empty:
        out_dir.mkdir(parents=True, exist_ok=True)
        table.to_parquet(out_dir / "measurements.parquet", index=False)
        table.to_csv(out_dir / "measurements.csv", index=False)
    (out_dir / "run_summary.md").write_text(format_summary(summary), encoding="utf-8")
    return table, summary


def format_summary(summary: RunSummary) -> str:
    lines = [
        "# Pipeline run summary",
        "",
        f"- requested: **{summary.n_requested}**",
        f"- measured: **{summary.n_measured}**",
        f"- servable now (`OK`): **{summary.n_ok}**",
        f"- withheld for faculty review (`NEEDS_REVIEW`): **{summary.n_needs_review}**",
        f"- failed: **{summary.n_failed}**",
        f"- waveform not downloaded: **{summary.n_missing_file}**",
        "",
        "`NEEDS_REVIEW` is not an error. It is the confidence gate doing its job: the "
        "measurement exists but is not trusted enough to grade a student against until a "
        "reviewer has confirmed or corrected it.",
    ]
    if summary.warning_counts:
        lines += ["", "## Warnings", "", "| warning | cases |", "|---|---:|"]
        lines += [
            f"| {k} | {v} |"
            for k, v in sorted(summary.warning_counts.items(), key=lambda kv: -kv[1])
        ]
    if summary.failures:
        lines += ["", "## Failures", "", "| ecg_id | reason |", "|---|---|"]
        lines += [f"| {i} | {reason} |" for i, reason in summary.failures[:40]]
        if len(summary.failures) > 40:
            lines.append(f"| ... | {len(summary.failures) - 40} more |")
    return "\n".join(lines)


def load_candidates(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".json":
        return pd.DataFrame(json.loads(path.read_text()))
    raise ValueError(f"unsupported candidate file: {path}")


__all__ = ["RunSummary", "format_summary", "load_candidates", "process_one", "run_batch"]
