"""Signal quality index, from beat-template correlation.

The idea: in a clean record every beat looks like every other beat. Build the
median beat, correlate each individual beat against it, and the average
correlation is a quality figure that needs no reference and no training data.

It answers the question the MAD term cannot. Beat-to-beat spread tells you
whether the *measurements* agree; template correlation tells you whether the
*waveform* is an ECG at all. A lead that has come loose produces beats which are
mutually inconsistent (low SQI) even where an interval happens to be measured
consistently, and the two terms together are what `CONFIDENCE_MIN` gates on.

The scoring is deliberately conservative. A case withheld for faculty review
costs a reviewer two minutes; a bad measurement served to a student marks their
correct answer wrong, and that costs their trust in the whole platform.
"""

from __future__ import annotations

import numpy as np

from cardiosignal import config
from cardiosignal.types import SignalQuality


def _beat_windows(x: np.ndarray, r_peaks: np.ndarray, fs: int) -> np.ndarray | None:
    """Stack of aligned beat windows, shape `(n_beats, window)`."""
    pre = int(abs(config.SQI_TEMPLATE_WINDOW_MS[0]) * fs / 1000.0)
    post = int(config.SQI_TEMPLATE_WINDOW_MS[1] * fs / 1000.0)
    rows = [
        x[r - pre : r + post]
        for r in r_peaks
        if r - pre >= 0 and r + post <= x.size
    ]
    rows = [r for r in rows if r.size == pre + post]
    if len(rows) < 2:
        return None
    return np.vstack(rows)


def beat_correlations(x: np.ndarray, r_peaks: np.ndarray, fs: int = config.FS) -> np.ndarray:
    """Correlation of each beat against the median beat of the record.

    The template is the *median* across beats, not the mean, for the same reason
    every aggregate here is a median: one ectopic or one motion artefact should
    not define what a normal beat looks like.
    """
    windows = _beat_windows(np.asarray(x, dtype=float), np.asarray(r_peaks, dtype=int), fs)
    if windows is None:
        return np.empty(0)

    template = np.median(windows, axis=0)
    template = template - template.mean()
    denom_t = np.linalg.norm(template)
    if denom_t == 0:
        return np.zeros(windows.shape[0])

    out = np.empty(windows.shape[0])
    for i, beat in enumerate(windows):
        beat = beat - beat.mean()
        denom_b = np.linalg.norm(beat)
        out[i] = 0.0 if denom_b == 0 else float(np.dot(beat, template) / (denom_b * denom_t))
    return out


def lead_sqi(x: np.ndarray, r_peaks: np.ndarray, fs: int = config.FS) -> float:
    """One lead's SQI: the median beat-to-template correlation, floored at 0."""
    corr = beat_correlations(x, r_peaks, fs)
    if corr.size == 0:
        return 0.0
    return float(np.clip(np.median(corr), 0.0, 1.0))


def assess(
    signal_2d: np.ndarray,
    r_peaks: np.ndarray,
    fs: int = config.FS,
    leads: tuple[str, ...] = config.LEADS,
) -> SignalQuality:
    """Whole-record quality: per-lead SQI plus flatline and saturation checks."""
    signal_2d = np.asarray(signal_2d, dtype=float)
    r_peaks = np.asarray(r_peaks, dtype=int)

    per_lead: dict[str, float] = {}
    flatline: list[str] = []
    saturated: list[str] = []

    for j, lead in enumerate(leads[: signal_2d.shape[1]]):
        column = signal_2d[:, j]
        span = float(np.ptp(column))
        if span < 0.05:  # < 0.5 mm of deflection over ten seconds
            flatline.append(lead)
        # A rail-to-rail lead spends many consecutive samples at its extreme.
        extreme = np.isclose(np.abs(column), np.max(np.abs(column)), rtol=1e-3)
        if extreme.sum() > 0.02 * column.size:
            saturated.append(lead)
        per_lead[lead] = lead_sqi(column, r_peaks, fs)

    usable = [v for lead, v in per_lead.items() if lead not in flatline]
    overall = float(np.median(usable)) if usable else 0.0

    return SignalQuality(
        sqi_per_lead=per_lead,
        sqi_overall=overall,
        n_beats_detected=int(r_peaks.size),
        flatline_leads=flatline,
        saturated_leads=saturated,
    )


def annotate_beats(beats, signal_2d: np.ndarray, r_peaks: np.ndarray, fs: int, reference_lead_index: int = 1) -> None:
    """Attach the per-beat template correlation to each `BeatFiducials`.

    Beats correlating poorly with the record's own template are marked
    `excluded` and dropped from aggregation -- this is where an ectopic or a
    movement artefact leaves the measurement path.
    """
    corr = beat_correlations(signal_2d[:, reference_lead_index], r_peaks, fs)
    if corr.size == 0:
        return
    # `beat_correlations` skips beats too close to either end of the record.
    pre = int(abs(config.SQI_TEMPLATE_WINDOW_MS[0]) * fs / 1000.0)
    post = int(config.SQI_TEMPLATE_WINDOW_MS[1] * fs / 1000.0)
    usable = [i for i, r in enumerate(r_peaks) if r - pre >= 0 and r + post <= signal_2d.shape[0]]
    for slot, beat_i in enumerate(usable):
        if slot >= corr.size or beat_i >= len(beats):
            break
        beats[beat_i].template_correlation = float(corr[slot])
        if corr[slot] < 0.7:
            beats[beat_i].excluded = True
            beats[beat_i].notes.append("low_template_correlation")


__all__ = ["annotate_beats", "assess", "beat_correlations", "lead_sqi"]
