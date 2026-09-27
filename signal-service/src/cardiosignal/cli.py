"""Command line for the Layer 1 pipeline.

    cardiosignal select                       stratified candidate pool + coverage report
    cardiosignal measure --ecg-id 12345       one case, printed
    cardiosignal render  --ecg-id 12345       clean and annotated images
    cardiosignal run     --batch <file>       the whole batch
    cardiosignal validate --report            regenerate the validation report
    cardiosignal calibration-sheet            the printable caliper check
    cardiosignal status                       what data is present
"""

from __future__ import annotations

from pathlib import Path

import typer

from cardiosignal import __version__, config

app = typer.Typer(add_completion=False, help=__doc__, no_args_is_help=True)


@app.command()
def select(
    out: Path = typer.Option(config.ARTIFACT_ROOT, help="Where to write candidates."),
    docs: Path = typer.Option(config.DOCS_ROOT / "validation", help="Where to write the coverage report."),
    allow_noise: bool = typer.Option(False, help="Keep records the dataset flags as noisy."),
    no_human_validation: bool = typer.Option(
        False, "--no-human-validation", help="Include records not validated by a human."
    ),
) -> None:
    """Draw a stratified candidate pool from PTB-XL metadata."""
    from cardiosignal.pipeline.select_cases import format_coverage, write_outputs
    from cardiosignal.pipeline.select_cases import select as run_select

    result = run_select(
        require_human_validation=not no_human_validation, allow_noise=allow_noise
    )
    candidates_path, coverage_path = write_outputs(result, out, docs)
    typer.echo(format_coverage(result))
    typer.echo("")
    typer.echo(f"candidates -> {candidates_path}")
    typer.echo(f"coverage   -> {coverage_path}")
    typer.echo("")
    typer.echo("Next: fetch just these waveforms with")
    typer.echo(f"  python scripts/download_data.py ptbxl --records-from {candidates_path}")


@app.command()
def measure(
    ecg_id: int = typer.Option(..., "--ecg-id", help="PTB-XL record id."),
    sampling_rate: int = typer.Option(500, help="500 or 100 Hz."),
    json_out: Path | None = typer.Option(None, "--json", help="Write the full result here."),
) -> None:
    """Measure one record and print the result."""
    from cardiosignal.engine import measure_record
    from cardiosignal.io import ptbxl

    recording = ptbxl.load_record(ecg_id, sampling_rate)
    result = measure_record(recording)
    result.diagnostic_labels = ptbxl.describe_codes(recording.scp_codes)

    def show(label: str, measure_obj) -> None:
        if measure_obj.value is None:
            typer.echo(f"  {label:<16} {measure_obj.status.value}")
            return
        typer.echo(
            f"  {label:<16} {measure_obj.value:7.1f} {measure_obj.unit:<4} "
            f"(MAD {measure_obj.mad or 0:5.1f}, conf {measure_obj.confidence:.2f}, "
            f"{measure_obj.flag.value})"
        )

    typer.echo(f"\nPTB-XL {ecg_id}  age {recording.age}  sex {recording.sex}")
    typer.echo(f"status {result.status.value}   overall confidence {result.overall_confidence:.2f}")
    typer.echo(f"beats {len(result.beats)}   SQI {result.quality.sqi_overall:.2f}\n")

    show("Heart rate", result.heart_rate)
    typer.echo(
        f"  {'Rhythm':<16} {result.rhythm.regularity.value}  "
        f"(CV {result.rhythm.cv or 0:.3f}, conf {result.rhythm.confidence:.2f})"
    )
    show("PR", result.pr_interval)
    show("QRS", result.qrs_duration)
    show("QT", result.qt_interval)
    show("QTc (Bazett)", result.qtc_bazett)
    show("QTc (Fridericia)", result.qtc_fridericia)
    typer.echo(
        f"  {'Axis':<16} "
        + (f"{result.axis.degrees:7.1f} deg  {result.axis.category.value}"
           if result.axis.degrees is not None else result.axis.status.value)
    )

    deviating = [s for s in result.st if s.finding.value != "NORMAL"]
    if deviating:
        typer.echo("\n  ST deviation:")
        for s in deviating:
            typer.echo(f"    {s.lead:<4} {s.deviation_mm:+5.2f} mm  {s.finding.value}")
    for territory in result.territories:
        if territory.finding.value != "NORMAL":
            typer.echo(
                f"    territory {territory.territory}: {territory.finding.value} "
                f"in {', '.join(territory.leads_meeting_threshold)}"
            )

    typer.echo("\n  Inherited diagnosis (from the dataset, not computed):")
    for label in result.diagnostic_labels:
        typer.echo(f"    - {label}")
    if result.warnings:
        typer.echo("\n  Warnings: " + "; ".join(result.warnings))

    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"\nwritten -> {json_out}")


@app.command()
def render(
    ecg_id: int = typer.Option(..., "--ecg-id"),
    out: Path = typer.Option(config.ARTIFACT_ROOT / "images"),
    sampling_rate: int = typer.Option(500),
    annotated: bool = typer.Option(True, help="Also render the feedback image."),
) -> None:
    """Render the clean (and optionally annotated) sheet for one record."""
    from cardiosignal.engine import measure_record
    from cardiosignal.io import ptbxl
    from cardiosignal.preprocess.filters import diagnostic_filter
    from cardiosignal.render.annotate import render_annotated
    from cardiosignal.render.sheet import render_clean

    recording = ptbxl.load_record(ecg_id, sampling_rate)
    filtered = diagnostic_filter(recording.signal, recording.sampling_rate)
    typer.echo(f"clean     -> {render_clean(recording, out / f'{ecg_id}_clean.png', filtered=filtered)}")
    if annotated:
        result = measure_record(recording)
        typer.echo(
            f"annotated -> "
            f"{render_annotated(recording, result, out / f'{ecg_id}_annotated.png', filtered=filtered)}"
        )


@app.command()
def run(
    batch: Path = typer.Option(..., "--batch", help="candidates.parquet or .csv"),
    out: Path = typer.Option(config.ARTIFACT_ROOT),
    limit: int | None = typer.Option(None, help="Process only the first N."),
    no_render: bool = typer.Option(False, "--no-render", help="Measurements only, no images."),
) -> None:
    """Measure and render an entire candidate batch."""
    from cardiosignal.pipeline.run import format_summary, load_candidates, run_batch

    candidates = load_candidates(batch)
    _table, summary = run_batch(candidates, out, render=not no_render, limit=limit)
    typer.echo(format_summary(summary))
    typer.echo(f"\nwritten -> {out}")


@app.command()
def validate(
    report: bool = typer.Option(True, "--report/--no-report", help="Write the report file."),
    ludb_limit: int | None = typer.Option(None, help="Evaluate only the first N LUDB records."),
    qtdb_limit: int | None = typer.Option(None, help="Evaluate only the first N QTDB records."),
) -> None:
    """Run the full validation suite and regenerate the report."""
    from cardiosignal.validation.report import build

    path = build(ludb_limit=ludb_limit, qtdb_limit=qtdb_limit)
    if report:
        typer.echo(f"\nreport -> {path}")
        typer.echo(path.read_text(encoding="utf-8"))


@app.command("calibration-sheet")
def calibration_sheet(
    out: Path = typer.Option(config.DOCS_ROOT / "validation" / "calibration_sheet.pdf"),
) -> None:
    """Printable caliper check. Print at 100% scale — no 'fit to page'."""
    from cardiosignal.render.annotate import render_calibration_sheet

    typer.echo(f"written -> {render_calibration_sheet(out)}")
    typer.echo("Print at 100% scale, then confirm 200 ms measures exactly 5 mm.")


@app.command()
def status() -> None:
    """What data is present, and what the engine is configured to do."""
    from cardiosignal.io import ludb, ptbxl, qtdb

    typer.echo(f"cardiosignal {__version__}  (schema {config.SCHEMA_VERSION})")
    typer.echo(f"data root      {config.DATA_ROOT}")
    typer.echo(f"artifacts      {config.ARTIFACT_ROOT}")
    typer.echo("")
    typer.echo(f"  PTB-XL metadata  {'yes' if ptbxl.is_available() else 'no'}")
    typer.echo(f"  LUDB             {'yes' if ludb.is_available() else 'no'}")
    typer.echo(f"  QTDB             {'yes' if qtdb.is_available() else 'no'}")
    typer.echo("")
    typer.echo(f"  paper speed      {config.MM_PER_S} mm/s")
    typer.echo(f"  gain             {config.MM_PER_MV} mm/mV")
    typer.echo(f"  render dpi       {config.DPI}  ({config.DPI / 25.4:.1f} px/mm)")
    typer.echo(f"  filter           {config.BANDPASS_HZ[0]}-{config.BANDPASS_HZ[1]} Hz, zero phase")
    typer.echo(f"  confidence gate  {config.CONFIDENCE_MIN}")


if __name__ == "__main__":
    app()
