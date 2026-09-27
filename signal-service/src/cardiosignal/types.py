"""The measurement contract.

`MeasurementResult` is the single artefact everything else in CardioSaarthi
reads. In week 4 it becomes the `case_measurements` table; in week 7 it is the
input to `GradingService`; the annotated renderer draws from its fiducials. It
is versioned (`SCHEMA_VERSION`) so a stored result can always be interpreted.

Two rules hold throughout:

* Every measured quantity carries its spread and its confidence. A number
  without a confidence cannot be graded against, because a student marked wrong
  by a bad measurement is worse than no case at all.
* Absence is explicit. A missing P wave is `PWaveStatus.ABSENT`, never a
  silently omitted field and never a guessed value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from cardiosignal import config


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class MeasurementStatus(str, Enum):
    """Whether a value may be served to a student."""

    OK = "OK"
    NEEDS_REVIEW = "NEEDS_REVIEW"  # confidence below threshold — faculty must correct
    NOT_MEASURABLE = "NOT_MEASURABLE"  # e.g. PR when no P wave exists
    FAILED = "FAILED"  # the algorithm could not run at all


class PWaveStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"  # no candidate cleared threshold — a finding, not a failure
    UNCERTAIN = "UNCERTAIN"  # candidate found but below the confidence bar


class Regularity(str, Enum):
    REGULAR = "REGULAR"
    REGULARLY_IRREGULAR = "REGULARLY_IRREGULAR"  # repeating pattern, e.g. Wenckebach
    IRREGULARLY_IRREGULAR = "IRREGULARLY_IRREGULAR"  # no pattern, e.g. AF
    INDETERMINATE = "INDETERMINATE"


class AxisCategory(str, Enum):
    NORMAL = "NORMAL"  # -30 to +90
    LEFT = "LEFT"  # -30 to -90
    RIGHT = "RIGHT"  # +90 to +180
    EXTREME = "EXTREME"  # -90 to -180 (north-west)
    INDETERMINATE = "INDETERMINATE"


class STFinding(str, Enum):
    NORMAL = "NORMAL"
    ELEVATION = "ELEVATION"
    DEPRESSION = "DEPRESSION"


class TWaveFinding(str, Enum):
    """What a T wave looks like in one lead.

    FLAT is its own value rather than a small UPRIGHT: below about a tenth of a
    millivolt the sign of the deflection is noise, and calling that an inversion
    would invent a finding.
    """

    UPRIGHT = "UPRIGHT"
    INVERTED = "INVERTED"
    FLAT = "FLAT"
    BIPHASIC = "BIPHASIC"


class Flag(str, Enum):
    """Reference-range flags. Descriptive only — never a diagnosis."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Raw signal container (not serialised — holds numpy)
# ---------------------------------------------------------------------------
class Recording(BaseModel):
    """A single 12-lead record as loaded from disk."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ecg_id: int
    source: str = "ptbxl"
    signal: Any = Field(repr=False)  # np.ndarray, shape (n_samples, n_leads), mV
    leads: tuple[str, ...] = config.LEADS
    sampling_rate: int = config.FS
    age: float | None = None
    sex: str | None = None
    scp_codes: dict[str, float] = Field(default_factory=dict)
    report: str | None = None
    quality_flags: dict[str, Any] = Field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return int(np.asarray(self.signal).shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sampling_rate

    def lead(self, name: str) -> np.ndarray:
        """Signal for one lead, in mV."""
        return np.asarray(self.signal)[:, self.leads.index(name)]


# ---------------------------------------------------------------------------
# Per-beat fiducials
# ---------------------------------------------------------------------------
class BeatFiducials(BaseModel):
    """Sample indices of the landmarks on one beat.

    Indices are into the full-length record at `sampling_rate`, so the renderer
    can annotate without recomputing anything. `None` means not located.
    """

    beat_index: int
    r_index: int

    p_onset: int | None = None
    p_peak: int | None = None
    p_offset: int | None = None
    p_status: PWaveStatus = PWaveStatus.UNCERTAIN

    qrs_onset: int | None = None
    qrs_offset: int | None = None  # this is also the J point

    t_peak: int | None = None
    t_offset: int | None = None

    rr_prev_ms: float | None = None
    template_correlation: float | None = None  # per-beat SQI
    excluded: bool = False  # dropped from aggregation as an artefact
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregated measures
# ---------------------------------------------------------------------------
class ScalarMeasure(BaseModel):
    """One number, aggregated across beats, with its spread and confidence.

    `value` is the *median* across beats and `mad` is
    `median(|x_i - median(x)|)` — not mean and standard deviation, because one
    artefactual beat drags a mean but cannot move a median.
    """

    value: float | None = None
    mad: float | None = None
    unit: str = "ms"
    n_beats: int = 0
    confidence: float = 0.0
    status: MeasurementStatus = MeasurementStatus.FAILED
    flag: Flag = Flag.UNKNOWN
    reference_range: tuple[float, float] | None = None

    @property
    def servable(self) -> bool:
        """True if this value may be shown to a student without faculty correction."""
        return self.status is MeasurementStatus.OK


class RhythmSummary(BaseModel):
    regularity: Regularity = Regularity.INDETERMINATE
    rr_mean_ms: float | None = None
    sdnn_ms: float | None = None
    rmssd_ms: float | None = None
    cv: float | None = None  # SDNN / mean(RR)
    autocorr_peak: float | None = None  # RR-series autocorrelation
    autocorr_lag: int | None = None  # in beats; 2 => bigeminal pattern
    n_beats: int = 0
    confidence: float = 0.0
    status: MeasurementStatus = MeasurementStatus.FAILED


class AxisMeasure(BaseModel):
    degrees: float | None = None
    category: AxisCategory = AxisCategory.INDETERMINATE
    area_lead_i: float | None = None  # net QRS area, mV*ms
    area_lead_avf: float | None = None
    confidence: float = 0.0
    status: MeasurementStatus = MeasurementStatus.FAILED


class STLeadMeasure(BaseModel):
    """ST deviation in one lead. Per-lead is what enables territorial localisation."""

    lead: str
    deviation_mm: float | None = None
    deviation_mv: float | None = None
    baseline_mv: float | None = None  # PR-segment isoelectric reference
    j_point_index: int | None = None
    measure_index: int | None = None  # J + 60 ms
    threshold_mm: float = config.ST_THRESH_LIMB_MM
    finding: STFinding = STFinding.NORMAL
    mad_mm: float | None = None
    n_beats: int = 0
    confidence: float = 0.0


class TWaveLeadMeasure(BaseModel):
    """The T wave in one lead.

    Per lead because that is how the finding is reported and acted on: T-wave
    inversion in V1 to V3 means something different from inversion in II, III
    and aVF, and a single overall verdict throws that away.

    @param normally_inverted whether an inverted T wave is expected here. aVR
        looks at the heart from the opposite direction; III and V1 are commonly
        inverted in healthy people.
    """

    lead: str
    amplitude_mv: float | None = None  # at the T peak, against the PR baseline
    mad_mv: float | None = None
    finding: TWaveFinding = TWaveFinding.FLAT
    normally_inverted: bool = False
    n_beats: int = 0
    confidence: float = 0.0
    status: MeasurementStatus = MeasurementStatus.FAILED


class TerritorySummary(BaseModel):
    territory: str
    leads: tuple[str, ...]
    max_elevation_mm: float | None = None
    max_depression_mm: float | None = None
    leads_meeting_threshold: list[str] = Field(default_factory=list)
    finding: STFinding = STFinding.NORMAL


class SignalQuality(BaseModel):
    sqi_per_lead: dict[str, float] = Field(default_factory=dict)
    sqi_overall: float = 0.0
    n_beats_detected: int = 0
    n_beats_excluded: int = 0
    flatline_leads: list[str] = Field(default_factory=list)
    saturated_leads: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------
class MeasurementResult(BaseModel):
    """Everything the platform knows about one ECG, all of it computed.

    Note what is *not* here: no interpretation, no diagnosis derived by us.
    `scp_codes` and `diagnostic_labels` are copied verbatim from the dataset's
    cardiologist annotations.
    """

    schema_version: str = config.SCHEMA_VERSION
    # Bumped to 0.2.0 when the P-wave evidence gates were extended to the P
    # duration and the diagnosis-conflict rule was added. Stored results from
    # 0.1.0 carry the same fields with different statuses, and a correction
    # snapshots this value so a disagreement can always be traced to the
    # behaviour that produced it.
    engine_version: str = "0.3.0"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Provenance
    ecg_id: int
    source: str = "ptbxl"
    sampling_rate: int = config.FS
    n_samples: int = config.N_SAMPLES
    leads: tuple[str, ...] = config.LEADS

    # Inherited, never computed by us
    age: float | None = None
    sex: str | None = None
    scp_codes: dict[str, float] = Field(default_factory=dict)
    diagnostic_labels: list[str] = Field(default_factory=list)
    syllabus_conditions: list[str] = Field(default_factory=list)

    # Computed
    heart_rate: ScalarMeasure = Field(default_factory=lambda: ScalarMeasure(unit="bpm"))
    rhythm: RhythmSummary = Field(default_factory=RhythmSummary)
    pr_interval: ScalarMeasure = Field(default_factory=ScalarMeasure)
    qrs_duration: ScalarMeasure = Field(default_factory=ScalarMeasure)
    qt_interval: ScalarMeasure = Field(default_factory=ScalarMeasure)
    qtc_bazett: ScalarMeasure = Field(default_factory=ScalarMeasure)
    qtc_fridericia: ScalarMeasure = Field(default_factory=ScalarMeasure)
    p_duration: ScalarMeasure = Field(default_factory=ScalarMeasure)
    axis: AxisMeasure = Field(default_factory=AxisMeasure)
    st: list[STLeadMeasure] = Field(default_factory=list)
    territories: list[TerritorySummary] = Field(default_factory=list)
    t_waves: list[TWaveLeadMeasure] = Field(default_factory=list)
    # The case-level answer for step 8. None when too few leads could be
    # measured to say anything, which the grader treats as not markable.
    t_wave_finding: TWaveFinding | None = None
    t_wave_inverted_leads: list[str] = Field(default_factory=list)

    beats: list[BeatFiducials] = Field(default_factory=list)
    quality: SignalQuality = Field(default_factory=SignalQuality)

    overall_confidence: float = 0.0
    status: MeasurementStatus = MeasurementStatus.FAILED
    warnings: list[str] = Field(default_factory=list)

    # -- convenience ---------------------------------------------------------
    @property
    def r_peaks(self) -> list[int]:
        return [b.r_index for b in self.beats]

    def st_for(self, lead: str) -> STLeadMeasure | None:
        return next((s for s in self.st if s.lead == lead), None)

    def flat_row(self) -> dict[str, Any]:
        """Scalar-only view, for the batch Parquet and for faculty spreadsheets.

        Nested structures (per-beat fiducials, per-lead ST) stay in the per-case
        JSON; this is the tabular summary.
        """
        row: dict[str, Any] = {
            "ecg_id": self.ecg_id,
            "source": self.source,
            "schema_version": self.schema_version,
            "computed_at": self.computed_at,
            "age": self.age,
            "sex": self.sex,
            "diagnostic_labels": ";".join(self.diagnostic_labels),
            "syllabus_conditions": ";".join(self.syllabus_conditions),
            "status": self.status.value,
            "overall_confidence": self.overall_confidence,
            "n_beats": len(self.beats),
            "sqi_overall": self.quality.sqi_overall,
            "rhythm_regularity": self.rhythm.regularity.value,
            "rr_mean_ms": self.rhythm.rr_mean_ms,
            "sdnn_ms": self.rhythm.sdnn_ms,
            "cv": self.rhythm.cv,
            "axis_degrees": self.axis.degrees,
            "axis_category": self.axis.category.value,
            "warnings": ";".join(self.warnings),
        }
        for name in (
            "heart_rate",
            "pr_interval",
            "qrs_duration",
            "qt_interval",
            "qtc_bazett",
            "qtc_fridericia",
            "p_duration",
        ):
            m: ScalarMeasure = getattr(self, name)
            row[f"{name}"] = m.value
            row[f"{name}_mad"] = m.mad
            row[f"{name}_conf"] = m.confidence
            row[f"{name}_status"] = m.status.value
        for s in self.st:
            row[f"st_{s.lead}_mm"] = s.deviation_mm
            row[f"st_{s.lead}_finding"] = s.finding.value
        row["t_wave_finding"] = self.t_wave_finding.value if self.t_wave_finding else None
        row["t_wave_inverted_leads"] = ";".join(self.t_wave_inverted_leads)
        for t in self.t_waves:
            row[f"t_{t.lead}_mv"] = t.amplitude_mv
            row[f"t_{t.lead}_finding"] = t.finding.value
        return row


__all__ = [
    "AxisCategory",
    "AxisMeasure",
    "BeatFiducials",
    "Flag",
    "MeasurementResult",
    "MeasurementStatus",
    "PWaveStatus",
    "Recording",
    "Regularity",
    "RhythmSummary",
    "STFinding",
    "STLeadMeasure",
    "ScalarMeasure",
    "SignalQuality",
    "TWaveFinding",
    "TWaveLeadMeasure",
    "TerritorySummary",
]
