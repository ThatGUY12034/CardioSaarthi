"""The HTTP surface Spring Boot will call in week 7.

Endpoints are exercised through the functions rather than a live server: the
service is deliberately thin, so what is worth testing is that the contract and
the error handling are right, not that FastAPI can route.
"""

from __future__ import annotations

import base64

import numpy as np
import pytest
from fastapi import HTTPException

from cardiosignal import api, config


def test_health_reports_geometry_and_datasets():
    payload = api.health()
    assert payload["status"] == "ok"
    assert payload["geometry"]["px_per_mm"] == 10.0
    assert payload["geometry"]["mm_per_second"] == config.MM_PER_S
    assert set(payload["datasets"]) == {"ptbxl", "ludb", "qtdb"}


def test_measure_accepts_an_inline_waveform(twelve_lead):
    request = api.MeasureRequest(
        signal=twelve_lead.tolist(), sampling_rate=config.FS, age=61, sex="female"
    )
    result = api.measure(request)
    assert result.schema_version == config.SCHEMA_VERSION
    assert result.heart_rate.value is not None
    # Inline signals carry no dataset annotation, so no diagnosis is attached.
    assert result.diagnostic_labels == []


def test_measure_requires_an_identifier_or_a_signal():
    with pytest.raises(HTTPException) as excinfo:
        api.measure(api.MeasureRequest())
    assert excinfo.value.status_code == 422


def test_measure_rejects_a_one_dimensional_signal():
    """Caught by the schema itself: `list[list[float]]` cannot be 1-D."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        api.MeasureRequest(signal=[1.0, 2.0])  # type: ignore[arg-type]


def test_measure_rejects_ragged_and_non_finite_signals():
    """The schema admits both; numpy does not, and a 500 would be the wrong answer."""
    for bad in ([[1.0, 2.0], [3.0]], [[float("nan"), 1.0], [2.0, 3.0]]):
        with pytest.raises(HTTPException) as excinfo:
            api.measure(api.MeasureRequest(signal=bad))
        assert excinfo.value.status_code == 422


def test_measure_rejects_mismatched_lead_names(twelve_lead):
    with pytest.raises(HTTPException) as excinfo:
        api.measure(
            api.MeasureRequest(signal=twelve_lead.tolist(), leads=["I", "II"])
        )
    assert excinfo.value.status_code == 422


def test_render_returns_a_png_of_the_expected_size(twelve_lead):
    response = api.render(
        api.RenderRequest(signal=twelve_lead.tolist(), annotated=True)
    )
    assert response.px_per_mm == 10.0
    assert (response.width_px, response.height_px) == (2800, 1800)

    payload = base64.b64decode(response.clean_png_base64)
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert response.annotated_png_base64 is not None


def test_render_can_skip_the_annotated_image(twelve_lead):
    response = api.render(
        api.RenderRequest(signal=twelve_lead.tolist(), annotated=False)
    )
    assert response.annotated_png_base64 is None


def test_unknown_ptbxl_record_is_a_404():
    from cardiosignal.io import ptbxl

    if not ptbxl.is_available():
        pytest.skip("PTB-XL metadata not downloaded")
    with pytest.raises(HTTPException) as excinfo:
        api.measure(api.MeasureRequest(ecg_id=99_999_999))
    assert excinfo.value.status_code == 404


def test_measure_response_is_the_stored_model(twelve_lead):
    """No API-shaped duplicate of MeasurementResult that could drift from it."""
    import typing

    from cardiosignal.types import MeasurementResult

    assert typing.get_type_hints(api.measure)["return"] is MeasurementResult
    result = api.measure(api.MeasureRequest(signal=twelve_lead.tolist()))
    assert isinstance(result, MeasurementResult)
    assert np.isfinite(result.overall_confidence)
