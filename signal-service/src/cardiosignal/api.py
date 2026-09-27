"""FastAPI wrapper over the measurement engine.

Deliberately thin. Every endpoint is a few lines over a function that is already
tested without HTTP in front of it, so the service adds transport and nothing
else. In week 7 Spring Boot calls these endpoints; nothing in the engine needs
to change for that, which is the point of keeping the boundary this narrow.

The response is `MeasurementResult` exactly as stored — the same object the
faculty review queue will edit and the grader will read. There is no separate
API-shaped model to drift out of sync with the pipeline's.
"""

from __future__ import annotations

import base64
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cardiosignal import __version__, config
from cardiosignal.engine import measure_record
from cardiosignal.types import MeasurementResult, Recording

app = FastAPI(
    title="CardioSaarthi signal service",
    version=__version__,
    summary="Deterministic ECG measurement and standards-compliant rendering.",
    description=(
        "Every value returned is computed by signal processing. Diagnoses are "
        "inherited from the source dataset's cardiologist annotations and are never "
        "derived here. No model is consulted by this service."
    ),
)


class MeasureRequest(BaseModel):
    ecg_id: int | None = Field(None, description="PTB-XL record id.")
    sampling_rate: int = 500
    signal: list[list[float]] | None = Field(
        None, description="Optional inline waveform, shape (n_samples, n_leads), in mV."
    )
    leads: list[str] | None = None
    age: float | None = None
    sex: str | None = None


class RenderRequest(MeasureRequest):
    annotated: bool = True


class RenderResponse(BaseModel):
    ecg_id: int
    clean_png_base64: str
    annotated_png_base64: str | None = None
    width_px: int
    height_px: int
    px_per_mm: float


def _recording_from(request: MeasureRequest) -> Recording:
    """Either load a dataset record or accept an inline waveform."""
    if request.signal is not None:
        try:
            array = np.asarray(request.signal, dtype=float)
        except ValueError as exc:
            # Ragged rows: the type annotation admits them, numpy does not.
            raise HTTPException(422, f"signal rows must all be the same length: {exc}") from exc
        if array.ndim != 2:
            raise HTTPException(422, "signal must be 2-D: (n_samples, n_leads)")
        if array.size == 0:
            raise HTTPException(422, "signal is empty")
        if not np.isfinite(array).all():
            raise HTTPException(422, "signal contains NaN or infinity")
        leads = tuple(request.leads) if request.leads else config.LEADS[: array.shape[1]]
        if len(leads) != array.shape[1]:
            raise HTTPException(422, f"{len(leads)} lead names for {array.shape[1]} columns")
        return Recording(
            ecg_id=request.ecg_id or 0,
            source="inline",
            signal=array,
            leads=leads,
            sampling_rate=request.sampling_rate,
            age=request.age,
            sex=request.sex,
        )

    if request.ecg_id is None:
        raise HTTPException(422, "provide either ecg_id or signal")

    from cardiosignal.io import ptbxl

    try:
        return ptbxl.load_record(request.ecg_id, request.sampling_rate)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, f"ecg_id {request.ecg_id} not in PTB-XL") from exc


@app.get("/health")
def health() -> dict[str, object]:
    from cardiosignal.io import ludb, ptbxl, qtdb

    return {
        "status": "ok",
        "version": __version__,
        "schema_version": config.SCHEMA_VERSION,
        "datasets": {
            "ptbxl": ptbxl.is_available(),
            "ludb": ludb.is_available(),
            "qtdb": qtdb.is_available(),
        },
        "geometry": {
            "mm_per_second": config.MM_PER_S,
            "mm_per_mv": config.MM_PER_MV,
            "dpi": config.DPI,
            "px_per_mm": config.DPI / 25.4,
        },
    }


@app.post("/measure", response_model=MeasurementResult)
def measure(request: MeasureRequest) -> MeasurementResult:
    """Measure one record. Returns the full `MeasurementResult`."""
    recording = _recording_from(request)
    result = measure_record(recording)
    if recording.source == "ptbxl":
        from cardiosignal.io import ptbxl

        result.diagnostic_labels = ptbxl.describe_codes(recording.scp_codes)
    return result


@app.post("/render", response_model=RenderResponse)
def render(request: RenderRequest) -> RenderResponse:
    """Render the clean sheet, and optionally the annotated one."""
    from cardiosignal.preprocess.filters import diagnostic_filter
    from cardiosignal.render.annotate import render_annotated
    from cardiosignal.render.geometry import Layout
    from cardiosignal.render.sheet import render_clean

    recording = _recording_from(request)
    filtered = diagnostic_filter(np.asarray(recording.signal, dtype=float), recording.sampling_rate)
    layout = Layout(duration_s=recording.duration_s, fs=recording.sampling_rate)

    with TemporaryDirectory() as tmp:
        directory = Path(tmp)
        clean = render_clean(recording, directory / "clean.png", filtered=filtered)
        payload = base64.b64encode(clean.read_bytes()).decode()

        annotated_payload = None
        if request.annotated:
            result = measure_record(recording)
            annotated = render_annotated(
                recording, result, directory / "annotated.png", filtered=filtered
            )
            annotated_payload = base64.b64encode(annotated.read_bytes()).decode()

    width, height = layout.pixel_size()
    return RenderResponse(
        ecg_id=recording.ecg_id,
        clean_png_base64=payload,
        annotated_png_base64=annotated_payload,
        width_px=width,
        height_px=height,
        px_per_mm=config.DPI / 25.4,
    )


__all__ = ["app"]
