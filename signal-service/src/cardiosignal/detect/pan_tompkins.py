"""Pan-Tompkins QRS detection.

Implemented as five separately testable stages rather than one opaque function,
because every stage has to be defensible on its own:

    1. band-pass 5-15 Hz      isolate QRS energy from P/T (low) and muscle (high)
    2. derivative             QRS is the steepest thing on the trace
    3. squaring               make everything positive, emphasise large slopes
    4. 150 ms integration     one QRS complex wide, so the complex becomes one hump
    5. adaptive threshold     amplitude drifts across a record; a fixed bar fails

The refractory rules are where most naive detectors fail:

    * nothing within 200 ms of an accepted beat can be a separate beat --
      that is shorter than the shortest physiological refractory period;
    * a candidate 200-360 ms after a beat is most likely a tall T wave, so it
      must clear a stricter bar before it is accepted as a QRS.

Note on delay: the integrator here is *centred* (`uniform_filter1d`), and the
band-pass is zero phase, so the integrated signal is time-aligned with the
input. The 5-point derivative introduces a 2-sample lag, which is corrected
explicitly. Even so, the returned R index is always refined by searching the
diagnostic-band signal for the local extremum, so no filter delay can reach the
measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sps
from scipy.ndimage import uniform_filter1d

from cardiosignal import config
from cardiosignal.preprocess.filters import diagnostic_filter, qrs_emphasis_filter

# y[n] = (2x[n] + x[n-1] - x[n-3] - 2x[n-4]) / 8
DERIVATIVE_KERNEL = np.array([2.0, 1.0, 0.0, -1.0, -2.0]) / 8.0
DERIVATIVE_LAG = 2  # samples, compensated below


@dataclass
class RPeakDetection:
    """R-peak indices plus the intermediate signals, kept for validation plots."""

    r_peaks: np.ndarray
    integrated: np.ndarray = field(repr=False)
    derivative: np.ndarray = field(repr=False)
    threshold_trace: np.ndarray = field(repr=False)
    n_searchback: int = 0
    n_rejected_refractory: int = 0
    n_rejected_twave: int = 0
    lead_used: str = "composite"

    @property
    def n_beats(self) -> int:
        return int(self.r_peaks.size)

    def rr_intervals_ms(self, fs: int = config.FS) -> np.ndarray:
        if self.r_peaks.size < 2:
            return np.empty(0)
        return np.diff(self.r_peaks) * 1000.0 / fs


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage_bandpass(x: np.ndarray, fs: int = config.FS) -> np.ndarray:
    """Stage 1 -- 5-15 Hz. Detection only; nothing is ever measured from this."""
    return qrs_emphasis_filter(np.asarray(x, dtype=float), fs)


def stage_derivative(x: np.ndarray) -> np.ndarray:
    """Stage 2 -- the 5-point derivative, lag-compensated.

    Convolution gives `y[n] = sum_k h[k] x[n-k]`, which is the formula exactly,
    but the kernel is causal and so lags by 2 samples. Shifting back keeps the
    derivative aligned with the waveform it describes, which matters because the
    same derivative is reused for T-wave discrimination.
    """
    x = np.asarray(x, dtype=float)
    y = np.convolve(x, DERIVATIVE_KERNEL, mode="full")[: x.size]
    return np.roll(y, -DERIVATIVE_LAG)


def stage_square(x: np.ndarray) -> np.ndarray:
    """Stage 3 -- pointwise squaring. Non-linear: it suppresses small slopes far
    more than large ones, which is what separates QRS from P and T."""
    return np.asarray(x, dtype=float) ** 2


def stage_integrate(x: np.ndarray, fs: int = config.FS, window_ms: int = config.INTEGRATION_MS) -> np.ndarray:
    """Stage 4 -- moving-window integration, window ~ one QRS wide.

    Centred, so it adds no delay. A window much shorter than a QRS leaves the
    complex as several humps; much longer and adjacent P/T waves merge into it.
    """
    width = max(1, int(round(window_ms * fs / 1000.0)))
    return uniform_filter1d(np.asarray(x, dtype=float), size=width, mode="nearest")


def preprocess(x: np.ndarray, fs: int = config.FS) -> tuple[np.ndarray, np.ndarray]:
    """Stages 1-4. Returns `(integrated, derivative)`."""
    banded = stage_bandpass(x, fs)
    deriv = stage_derivative(banded)
    return stage_integrate(stage_square(deriv), fs), deriv


# ---------------------------------------------------------------------------
# Stage 5 -- adaptive thresholding with refractory rules
# ---------------------------------------------------------------------------
def _local_slope(deriv: np.ndarray, index: int, fs: int) -> float:
    """Maximum |slope| in a 60 ms window around a candidate.

    This is the T-wave discriminant: a T wave carries far less slope than a QRS
    even when its integrated amplitude is comparable.
    """
    half = max(1, int(0.03 * fs))
    lo, hi = max(0, index - half), min(deriv.size, index + half + 1)
    return float(np.max(np.abs(deriv[lo:hi]))) if hi > lo else 0.0


def detect_from_integrated(
    integrated: np.ndarray,
    derivative: np.ndarray,
    fs: int = config.FS,
) -> RPeakDetection:
    """Stage 5. Walks the candidate peaks once, maintaining running estimates of
    signal and noise level exactly as Pan and Tompkins describe."""
    refractory = int(config.REFRACTORY_MS * fs / 1000.0)
    twave_window = int(config.TWAVE_SEARCH_MS * fs / 1000.0)

    candidates, _ = sps.find_peaks(integrated, distance=max(1, refractory // 2))
    if candidates.size == 0:
        return RPeakDetection(
            r_peaks=np.empty(0, dtype=int),
            integrated=integrated,
            derivative=derivative,
            threshold_trace=np.zeros_like(integrated),
        )

    learn_n = min(integrated.size, int(config.LEARNING_SECONDS * fs))
    spki = float(np.max(integrated[:learn_n])) * 0.25
    npki = float(np.mean(integrated[:learn_n])) * 0.5
    if spki <= npki:  # flat or pathological lead
        spki = npki * 2.0 + 1e-12

    accepted: list[int] = []
    accepted_slopes: list[float] = []
    threshold_trace = np.zeros_like(integrated)
    n_refractory = n_twave = n_searchback = 0

    def thresholds() -> tuple[float, float]:
        t1 = npki + 0.25 * (spki - npki)
        return t1, 0.5 * t1

    last_recorded = 0
    for idx in candidates:
        t1, t2 = thresholds()
        threshold_trace[last_recorded : idx + 1] = t1
        last_recorded = idx + 1
        peak = float(integrated[idx])

        if peak <= t1:
            npki = 0.125 * peak + 0.875 * npki
            continue

        if accepted:
            gap = idx - accepted[-1]
            if gap < refractory:
                # Physiologically impossible as a separate beat.
                n_refractory += 1
                continue
            if gap < twave_window:
                # Most likely the T wave of the previous beat. Accept only if it
                # carries at least half the slope of that beat's QRS.
                slope = _local_slope(derivative, idx, fs)
                if slope < config.TWAVE_THRESHOLD_FACTOR * accepted_slopes[-1]:
                    n_twave += 1
                    npki = 0.125 * peak + 0.875 * npki
                    continue

        accepted.append(int(idx))
        accepted_slopes.append(_local_slope(derivative, idx, fs))
        spki = 0.125 * peak + 0.875 * spki

        # Search back: a missed beat shows as an RR gap well beyond the running
        # mean. Rescan that gap at the lower threshold.
        if len(accepted) >= 3:
            rr_mean = float(np.mean(np.diff(accepted[-min(9, len(accepted)) :])))
            if rr_mean > 0:
                limit = int(config.SEARCHBACK_FACTOR * rr_mean)
                prev, cur = accepted[-2], accepted[-1]
                if cur - prev > limit:
                    window = candidates[(candidates > prev + refractory) & (candidates < cur - refractory)]
                    window = window[integrated[window] > t2]
                    if window.size:
                        best = int(window[np.argmax(integrated[window])])
                        accepted.insert(-1, best)
                        accepted_slopes.insert(-1, _local_slope(derivative, best, fs))
                        spki = 0.25 * float(integrated[best]) + 0.75 * spki
                        n_searchback += 1

    threshold_trace[last_recorded:] = thresholds()[0]
    return RPeakDetection(
        r_peaks=np.asarray(sorted(set(accepted)), dtype=int),
        integrated=integrated,
        derivative=derivative,
        threshold_trace=threshold_trace,
        n_searchback=n_searchback,
        n_rejected_refractory=n_refractory,
        n_rejected_twave=n_twave,
    )


def refine_r_peaks(
    detection_indices: np.ndarray,
    reference_signal: np.ndarray,
    fs: int = config.FS,
    window_ms: float = 50.0,
) -> np.ndarray:
    """Snap each index to the true R peak in the *diagnostic-band* signal.

    The detector works on a 5-15 Hz signal whose peak sits near, but not exactly
    on, the R peak. Every downstream measurement (RR, and therefore rate and
    QTc) is a difference of these indices, so they are pinned to the real
    waveform rather than to a filter artefact. Polarity is taken from the
    record: in aVR and in some V1 morphologies the dominant deflection is
    negative and the extremum must be a minimum.
    """
    if detection_indices.size == 0:
        return detection_indices
    half = max(1, int(window_ms * fs / 1000.0))
    ref = np.asarray(reference_signal, dtype=float)
    baseline = float(np.median(ref))

    refined = []
    for idx in detection_indices:
        lo, hi = max(0, idx - half), min(ref.size, idx + half + 1)
        seg = ref[lo:hi] - baseline
        if seg.size == 0:
            refined.append(int(idx))
            continue
        pos, neg = int(np.argmax(seg)), int(np.argmin(seg))
        best = pos if abs(seg[pos]) >= abs(seg[neg]) else neg
        refined.append(lo + best)
    return np.asarray(sorted(set(refined)), dtype=int)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def detect_single_lead(x: np.ndarray, fs: int = config.FS, lead_name: str = "?") -> RPeakDetection:
    """Run the full detector on one lead. This is the form validated against LUDB."""
    x = np.asarray(x, dtype=float)
    integrated, derivative = preprocess(x, fs)
    result = detect_from_integrated(integrated, derivative, fs)
    result.r_peaks = refine_r_peaks(result.r_peaks, diagnostic_filter(x, fs), fs)
    result.lead_used = lead_name
    return result


def preprocess_multilead(signal_2d: np.ndarray, fs: int = config.FS) -> tuple[np.ndarray, np.ndarray]:
    """Stages 1-4 across all twelve leads, combined at the squaring stage.

    A single lead can be flat, saturated, or dominated by electrode noise. The
    QRS is the one event that appears in *every* lead simultaneously, so summing
    QRS energy across leads makes detection robust to any one lead failing,
    without having to assume in advance which lead is good.

    The leads are combined *after* squaring, never before. Combining earlier
    would mean band-passing an already-rectified envelope, which is not an ECG
    and which the 5-15 Hz stage would simply destroy. Each lead is normalised by
    its own standard deviation first, so a high-amplitude lead cannot outvote
    the other eleven.

    Returns `(integrated, derivative_envelope)`, matching `preprocess`.
    """
    x = np.asarray(signal_2d, dtype=float)
    banded = qrs_emphasis_filter(x, fs)
    scale = np.std(banded, axis=0)
    scale[scale == 0] = 1.0
    banded = banded / scale

    deriv = np.column_stack([stage_derivative(banded[:, j]) for j in range(banded.shape[1])])
    energy = np.mean(stage_square(deriv), axis=1)
    return stage_integrate(energy, fs), np.sqrt(energy)


def detect_r_peaks(
    signal_2d: np.ndarray,
    fs: int = config.FS,
    leads: tuple[str, ...] = config.LEADS,
    reference_lead: str = "II",
) -> RPeakDetection:
    """Detect beats across a 12-lead record.

    Detection runs on the multi-lead composite; the final index is refined on
    the reference lead (lead II, where the R wave is upright in almost every
    normal axis), falling back to the highest-amplitude lead if lead II is flat.
    """
    signal_2d = np.asarray(signal_2d, dtype=float)
    integrated, derivative = preprocess_multilead(signal_2d, fs)
    result = detect_from_integrated(integrated, derivative, fs)

    ref_idx = leads.index(reference_lead) if reference_lead in leads else 0
    ref = diagnostic_filter(signal_2d[:, ref_idx], fs)
    if float(np.ptp(ref)) < 0.05:  # lead II is flat -- pick the liveliest lead
        filtered = diagnostic_filter(signal_2d, fs)
        ref_idx = int(np.argmax(np.ptp(filtered, axis=0)))
        ref = filtered[:, ref_idx]

    result.r_peaks = refine_r_peaks(result.r_peaks, ref, fs)
    result.lead_used = f"composite (refined on {leads[ref_idx]})"
    return result


__all__ = [
    "DERIVATIVE_KERNEL",
    "RPeakDetection",
    "detect_from_integrated",
    "detect_r_peaks",
    "detect_single_lead",
    "preprocess",
    "preprocess_multilead",
    "refine_r_peaks",
    "stage_bandpass",
    "stage_derivative",
    "stage_integrate",
    "stage_square",
]
