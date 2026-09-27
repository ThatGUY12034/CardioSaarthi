"""P, QRS and T boundary delineation.

Every interval the platform teaches is a difference between two boundaries
found here, so this module is where measurement accuracy is won or lost. It is
also the acknowledged weak point of the whole engine: P waves are low
amplitude, are sometimes buried in the preceding T wave, and are sometimes
genuinely absent. A P wave invented where there is none produces a confident,
wrong PR interval, and the platform then marks a *correct* student answer wrong
-- the worst failure this system can have.

Three defences are built in rather than bolted on:

  * a P wave must clear an explicit signal-to-noise bar before it is accepted;
    below it the beat is reported `PWaveStatus.ABSENT`, which is a clinical
    finding in its own right, not a gap in the data;
  * every boundary is found independently in all twelve leads and reconciled,
    so one noisy lead cannot set an interval on its own;
  * per-lead estimates are retained, because that is the form LUDB's expert
    annotations take and therefore the only form the accuracy claim can be
    checked in.

Method, per the specification:

  QRS  the rectified derivative envelope, searched *inward from the window
       edges*. Inward rather than outward because the derivative inside the
       complex is large and noisy while outside it is quiet, so a threshold
       crossing found from the quiet side is far more stable.

  P    searched *outward from the P peak*, never outward from R. At R the
       derivative is zero -- an outward walk from R starts at a degenerate
       point and its first threshold crossing is set by noise. The P peak has a
       well-defined flank on each side.

  T    offset by the tangent method: take the steepest slope after the T peak,
       extend that tangent to the isoelectric baseline, and take the
       intersection. This is the standard construction and is far more
       reproducible than the point where the T wave "looks like" it ends,
       because the end of a T wave approaches baseline asymptotically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sps

from cardiosignal import config
from cardiosignal.preprocess.filters import diagnostic_filter
from cardiosignal.types import BeatFiducials, PWaveStatus


def _ms(n_ms: float, fs: int) -> int:
    return int(round(n_ms * fs / 1000.0))


def _smooth_derivative(x: np.ndarray, fs: int) -> np.ndarray:
    """First derivative via Savitzky-Golay.

    A raw `np.diff` amplifies every sample of noise. Savitzky-Golay fits a local
    polynomial and differentiates that fit, so it differentiates and smooths in
    one pass with no phase shift.
    """
    window = _ms(22, fs)
    window = window + 1 if window % 2 == 0 else window
    window = max(5, min(window, len(x) - 1 if len(x) % 2 == 0 else len(x) - 2))
    if window < 5:
        return np.gradient(np.asarray(x, dtype=float))
    return sps.savgol_filter(np.asarray(x, dtype=float), window_length=window, polyorder=2, deriv=1)


@dataclass
class LeadBeatDelineation:
    """Boundaries for one beat as seen in one lead. Indices are into the record."""

    lead: str
    beat_index: int
    r_index: int
    qrs_onset: int | None = None
    qrs_offset: int | None = None
    p_onset: int | None = None
    p_peak: int | None = None
    p_offset: int | None = None
    p_status: PWaveStatus = PWaveStatus.UNCERTAIN
    p_amplitude_mv: float | None = None
    t_peak: int | None = None
    t_offset: int | None = None
    baseline_mv: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class DelineationResult:
    beats: list[BeatFiducials]
    per_lead: dict[str, list[LeadBeatDelineation]]
    filtered: np.ndarray = field(repr=False, default=None)


# ---------------------------------------------------------------------------
# QRS
# ---------------------------------------------------------------------------
def _first_sustained(mask: np.ndarray, run: int, reverse: bool = False) -> int | None:
    """Index of the first point where `mask` stays True for `run` samples.

    Requiring the crossing to hold is what stops one noisy sample from defining
    a boundary -- without it the onset lands on whatever the loudest artefact in
    the window happens to be.
    """
    if mask.size < run:
        return None
    sequence = mask[::-1] if reverse else mask
    # Cumulative-window trick: a run of `run` True values sums to `run`.
    sums = np.convolve(sequence.astype(int), np.ones(run, dtype=int), mode="valid")
    hits = np.flatnonzero(sums == run)
    if hits.size == 0:
        return None
    start = int(hits[0])
    return int(mask.size - 1 - start) if reverse else start


def find_qrs_boundaries(
    envelope: np.ndarray,
    r_index: int,
    fs: int,
    before_ms: float = config.QRS_SEARCH_BEFORE_MS,
    after_ms: float = config.QRS_SEARCH_AFTER_MS,
    max_expansions: int = 3,
) -> tuple[int | None, int | None]:
    """Walk inward from each window edge until the slope envelope rises.

    Onset and offset get their own windows, `[R-before, R]` and `[R, R+after]`,
    each searched inward from its outer edge -- the edge is the quiet PR or ST
    segment, and a threshold crossing found from the quiet side is far more
    stable than one found from inside the complex.

    The threshold is a fraction of the peak slope *within the QRS core*
    (`R +/- QRS_CORE_MS`), not of the whole window. Referencing the window would
    let a tall T wave set the scale, and the boundary would then be found on the
    T wave rather than on the QRS.

    Each window is widened and retried if its boundary lands on the edge, which
    is what a genuinely wide QRS does -- LBBB reaches 160 ms and would otherwise
    be clipped by the default window.
    """
    n = envelope.size
    core = _ms(config.QRS_CORE_MS, fs)
    core_lo, core_hi = max(0, r_index - core), min(n, r_index + core + 1)
    if core_hi <= core_lo:
        return None, None
    peak = float(np.max(envelope[core_lo:core_hi]))
    if peak <= 0:
        return None, None
    threshold = config.QRS_BOUNDARY_SLOPE_FRACTION * peak
    run = max(2, _ms(config.BOUNDARY_PERSISTENCE_MS, fs))

    onset: int | None = None
    for expansion in range(max_expansions + 1):
        lo = max(0, r_index - _ms(before_ms + 40 * expansion, fs))
        if r_index - lo < run:
            break
        found = _first_sustained(envelope[lo:r_index] > threshold, run)
        if found is None:
            onset = None
            break
        onset = lo + found
        if onset > lo + 1 or lo == 0:
            break  # not clipped by the window edge

    offset: int | None = None
    for expansion in range(max_expansions + 1):
        hi = min(n, r_index + _ms(after_ms + 40 * expansion, fs))
        if hi - r_index < run:
            break
        window = envelope[r_index:hi] > threshold
        found = _first_sustained(window, run, reverse=True)
        if found is None:
            offset = None
            break
        offset = r_index + found
        if offset < hi - 2 or hi == n:
            break

    # Second pass. The high threshold locates the complex reliably but lands
    # *inside* it -- measured against LUDB it put the onset ~13 ms late and the
    # offset ~9 ms early, so every QRS came out about 22 ms too narrow. So walk
    # back out from each crossing to where the envelope reaches the foot of the
    # wave, at a much lower threshold. Starting the low-threshold search from a
    # point already known to be inside the QRS is what makes it safe: an
    # outward walk stops at the first quiet sample and so cannot run away onto
    # the P or T wave, which is exactly what a low threshold applied from the
    # window edge would have done.
    foot = config.QRS_FOOT_SLOPE_FRACTION * peak
    travel = _ms(config.QRS_FOOT_MAX_TRAVEL_MS, fs)
    quiet_run = max(2, _ms(config.QRS_FOOT_PERSISTENCE_MS, fs))

    if onset is not None:
        limit = max(0, onset - travel)
        found = _first_sustained(envelope[limit:onset] < foot, quiet_run, reverse=True)
        if found is not None:
            onset = limit + found + quiet_run - 1
    if offset is not None:
        limit = min(n, offset + travel)
        found = _first_sustained(envelope[offset:limit] < foot, quiet_run)
        if found is not None:
            offset = offset + found

    return onset, offset


# ---------------------------------------------------------------------------
# P wave
# ---------------------------------------------------------------------------
def find_p_wave(
    x: np.ndarray,
    derivative: np.ndarray,
    qrs_onset: int,
    search_start: int,
    fs: int,
    baseline: float,
    noise_floor: float,
) -> tuple[int | None, int | None, int | None, PWaveStatus, float | None]:
    """Locate the P wave, then walk outward from its peak to its boundaries.

    Returns `(onset, peak, offset, status, amplitude_mv)`.
    """
    end = qrs_onset - _ms(config.P_SEARCH_END_MS, fs)
    start = max(0, search_start)
    if end - start < _ms(30, fs):
        return None, None, None, PWaveStatus.UNCERTAIN, None

    segment = x[start:end] - baseline
    peak_rel = int(np.argmax(np.abs(segment)))
    amplitude = float(segment[peak_rel])
    p_peak = start + peak_rel

    # Detection gate. Below it we say ABSENT rather than guess: an invented P
    # wave produces a confident wrong PR interval, which is the one failure mode
    # that makes the platform mark a correct student answer wrong.
    required = max(config.P_DETECTION_SNR * noise_floor, config.P_MIN_AMPLITUDE_MV)
    if abs(amplitude) < required:
        return None, None, None, PWaveStatus.ABSENT, float(amplitude)

    # Outward walk from the peak. The flank slope on each side is well defined
    # here, unlike at R where the derivative is zero. The reference slope is
    # taken from a window around the P peak, not from the whole search region --
    # the region's far end abuts the QRS upstroke, which would otherwise set the
    # scale and collapse the P wave to nothing.
    half = _ms(config.P_MAX_HALF_WIDTH_MS, fs)
    flank = np.abs(derivative[max(start, p_peak - half) : min(end, p_peak + half)])
    peak_slope = float(np.max(flank)) if flank.size else 0.0
    if peak_slope <= 0:
        return None, p_peak, None, PWaveStatus.UNCERTAIN, float(amplitude)
    threshold = config.P_BOUNDARY_SLOPE_FRACTION * peak_slope
    # The wave has also to have come back down. Slope alone ends the P wave at
    # any momentary flattening on its shoulder.
    return_level = abs(amplitude) * config.P_RETURN_FRACTION

    def walk(direction: int) -> int | None:
        """Step out from the peak to the first point that is both flat and
        back near baseline. Bounded by `P_MAX_HALF_WIDTH_MS`, so an unbounded
        search can never run to the edge of the region -- which is what
        previously produced 300 ms 'P waves' and had them all discarded."""
        limit = p_peak + direction * half
        limit = max(start, min(end - 1, limit))
        for i in range(p_peak, limit, direction):
            if abs(derivative[i]) < threshold and abs(x[i] - baseline) < return_level:
                return i
        return None

    onset = walk(-1)
    offset = walk(1)

    if onset is None or offset is None or offset <= onset:
        # The peak is real but at least one boundary could not be resolved.
        # Reported as UNCERTAIN with whatever was found: a faculty reviewer can
        # place the boundary, and the PR interval simply is not served.
        return onset, p_peak, offset, PWaveStatus.UNCERTAIN, float(amplitude)

    status = PWaveStatus.PRESENT
    if (offset - onset) < _ms(30, fs) or (offset - onset) > _ms(200, fs):
        status = PWaveStatus.UNCERTAIN  # implausible duration -- flag, do not drop
    return onset, p_peak, offset, status, float(amplitude)


# ---------------------------------------------------------------------------
# T wave
# ---------------------------------------------------------------------------
def find_t_wave(
    x: np.ndarray,
    derivative: np.ndarray,
    qrs_offset: int,
    rr_samples: float | None,
    fs: int,
    baseline: float,
    next_r: int | None = None,
) -> tuple[int | None, int | None]:
    """T peak, then T offset by the tangent construction."""
    start = qrs_offset + _ms(config.T_SEARCH_START_MS, fs)
    span = _ms(config.T_SEARCH_MAX_MS, fs)
    if rr_samples:
        span = int(min(span, config.T_SEARCH_RR_FRACTION * rr_samples))
    end = min(x.size - 1, start + span)
    if next_r is not None:
        # Hard stop before the next beat. Without it the search can reach into
        # the following P wave and take *that* as the T peak, which produced a
        # handful of 200-400 ms QT errors against QTDB -- rare, but large enough
        # to double the mean error on their own.
        end = min(end, next_r - _ms(config.T_SEARCH_NEXT_BEAT_GUARD_MS, fs))
    if end - start < _ms(40, fs):
        return None, None

    segment = x[start:end] - baseline
    t_peak = start + int(np.argmax(np.abs(segment)))

    # Steepest slope on the far side of the T peak. For an upright T this is the
    # downslope; for an inverted T it is the upslope. Either way it is the
    # steepest return toward baseline, and the tangent construction is identical.
    tail = derivative[t_peak:end]
    if tail.size < 3:
        return t_peak, None
    steep_rel = int(np.argmax(np.abs(tail)))
    steep_idx = t_peak + steep_rel
    slope = float(derivative[steep_idx])  # mV per sample
    if abs(slope) < 1e-9:
        return t_peak, None

    value = float(x[steep_idx])
    intersect = steep_idx + (baseline - value) / slope
    if not np.isfinite(intersect):
        return t_peak, None
    t_offset = int(round(intersect))
    if t_offset <= steep_idx:
        return t_peak, None
    # A shallow slope sends the tangent a long way out. Beyond the search window
    # the intersection is extrapolation, not measurement, so it is refused
    # rather than clamped -- a clamped value looks like a measurement.
    if t_offset > end:
        return t_peak, None
    return t_peak, t_offset


# ---------------------------------------------------------------------------
# Per-lead delineation
# ---------------------------------------------------------------------------
def delineate_lead(
    x: np.ndarray,
    r_peaks: np.ndarray,
    fs: int,
    lead: str,
) -> list[LeadBeatDelineation]:
    """Delineate every beat in one lead."""
    x = np.asarray(x, dtype=float)
    derivative = _smooth_derivative(x, fs)
    envelope = np.abs(derivative)
    global_baseline = float(np.median(x))

    noise_floor = estimate_noise_floor(x, r_peaks, fs)

    results: list[LeadBeatDelineation] = []
    for i, r in enumerate(r_peaks):
        r = int(r)
        det = LeadBeatDelineation(lead=lead, beat_index=i, r_index=r)

        qrs_on, qrs_off = find_qrs_boundaries(envelope, r, fs)
        det.qrs_onset, det.qrs_offset = qrs_on, qrs_off

        rr_prev = float(r - r_peaks[i - 1]) if i > 0 else None
        rr_next = float(r_peaks[i + 1] - r) if i < len(r_peaks) - 1 else None
        rr = rr_next or rr_prev

        if qrs_on is None:
            det.notes.append("qrs_onset_not_found")
            det.baseline_mv = global_baseline
            results.append(det)
            continue

        # PR-segment baseline: isoelectric by definition, and the same reference
        # the ST measurement uses, so ST and T are measured against one datum.
        b_hi = max(0, qrs_on - _ms(6, fs))
        b_lo = max(0, b_hi - _ms(config.PR_BASELINE_WINDOW_MS, fs))
        det.baseline_mv = float(np.median(x[b_lo:b_hi])) if b_hi > b_lo else global_baseline

        p_search_start = qrs_on - _ms(config.P_SEARCH_START_MS, fs)
        if rr_prev:
            # Never search back past the previous beat's T wave.
            p_search_start = max(p_search_start, int(r - 0.62 * rr_prev))
        det.p_onset, det.p_peak, det.p_offset, det.p_status, det.p_amplitude_mv = find_p_wave(
            x, derivative, qrs_on, p_search_start, fs, det.baseline_mv, noise_floor
        )

        if qrs_off is not None:
            next_r = int(r_peaks[i + 1]) if i < len(r_peaks) - 1 else None
            det.t_peak, det.t_offset = find_t_wave(
                x, derivative, qrs_off, rr, fs, det.baseline_mv, next_r
            )
        results.append(det)
    return results


def estimate_noise_floor(x: np.ndarray, r_peaks: np.ndarray, fs: int) -> float:
    """High-frequency noise amplitude in the TP segment, in mV.

    This is the bar a P wave has to clear, so it must not be contaminated by the
    P wave itself. Two things follow.

    First, only the TP segment is sampled -- roughly 0.50 to 0.72 of the way
    through each R-R interval, which is after the T wave has finished and before
    the P wave begins. Sampling the whole inter-beat region instead would
    measure the P wave and then demand that the P wave exceed itself, which is
    why every beat in a clean synthetic record was previously reported ABSENT.

    Second, what is measured is the *residual* after a short median filter, not
    the raw spread. Residual isolates the sample-to-sample noise a real P wave
    has to be distinguished from, and ignores the slow baseline drift that a raw
    spread would count as noise.
    """
    if r_peaks.size < 2:
        return 0.0
    pieces = []
    for a, b in zip(r_peaks[:-1], r_peaks[1:], strict=True):
        rr = b - a
        lo, hi = int(a + 0.50 * rr), int(a + 0.72 * rr)
        if hi - lo > _ms(30, fs):
            pieces.append(x[lo:hi])
    if not pieces:
        return 0.0

    quiet = np.concatenate(pieces)
    width = _ms(40, fs)
    width = width + 1 if width % 2 == 0 else width
    if quiet.size <= width:
        return float(np.median(np.abs(quiet - np.median(quiet))) * 1.4826)
    residual = quiet - sps.medfilt(quiet, kernel_size=width)
    return float(np.median(np.abs(residual - np.median(residual))) * 1.4826)


# ---------------------------------------------------------------------------
# Reconciliation across leads
# ---------------------------------------------------------------------------
def _robust_extreme(values: list[int], take: str) -> int | None:
    """Earliest onset / latest offset across leads, after discarding outliers.

    The standards define an interval by the earliest onset and latest offset
    seen in any simultaneously recorded lead -- a wave that begins in one lead
    has begun. Taken literally that makes a single noisy lead decisive, so
    estimates more than 3 MAD from the median are discarded first.
    """
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    if mad > 0:
        arr = arr[np.abs(arr - median) <= 3.0 * mad * 1.4826 + 2]
    if arr.size == 0:
        return int(median)
    return int(np.min(arr)) if take == "min" else int(np.max(arr))


def reconcile(
    per_lead: dict[str, list[LeadBeatDelineation]],
    r_peaks: np.ndarray,
    fs: int,
) -> list[BeatFiducials]:
    """Combine per-lead boundaries into one set of global fiducials per beat."""
    leads = list(per_lead)
    beats: list[BeatFiducials] = []

    for i, r in enumerate(r_peaks):
        views = [per_lead[ld][i] for ld in leads if i < len(per_lead[ld])]
        beat = BeatFiducials(beat_index=i, r_index=int(r))

        beat.qrs_onset = _robust_extreme([v.qrs_onset for v in views if v.qrs_onset is not None], "min")
        beat.qrs_offset = _robust_extreme([v.qrs_offset for v in views if v.qrs_offset is not None], "max")

        present = [v for v in views if v.p_status is PWaveStatus.PRESENT]
        # A P wave must be visible in at least two leads before it is called
        # present. One lead agreeing with itself is not evidence.
        if len(present) >= 2:
            beat.p_status = PWaveStatus.PRESENT
            beat.p_onset = _robust_extreme([v.p_onset for v in present if v.p_onset is not None], "min")
            beat.p_offset = _robust_extreme([v.p_offset for v in present if v.p_offset is not None], "max")
            peaks = [v.p_peak for v in present if v.p_peak is not None]
            beat.p_peak = int(np.median(peaks)) if peaks else None
        elif len(present) == 1:
            beat.p_status = PWaveStatus.UNCERTAIN
            beat.p_onset = present[0].p_onset
            beat.p_peak = present[0].p_peak
            beat.p_offset = present[0].p_offset
        else:
            beat.p_status = PWaveStatus.ABSENT
            beat.notes.append("no_p_wave_in_any_lead")

        beat.t_offset = _robust_extreme([v.t_offset for v in views if v.t_offset is not None], "max")
        t_peaks = [v.t_peak for v in views if v.t_peak is not None]
        beat.t_peak = int(np.median(t_peaks)) if t_peaks else None

        if i > 0:
            beat.rr_prev_ms = float(r - r_peaks[i - 1]) * 1000.0 / fs

        _sanity_check(beat, fs)
        beats.append(beat)
    return beats


def _sanity_check(beat: BeatFiducials, fs: int) -> None:
    """Drop orderings that cannot be true. Flagged, never silently repaired."""
    if beat.qrs_onset is not None and beat.qrs_offset is not None and beat.qrs_offset <= beat.qrs_onset:
        beat.notes.append("qrs_offset_before_onset")
        beat.qrs_onset = beat.qrs_offset = None
    if beat.p_offset is not None and beat.qrs_onset is not None and beat.p_offset > beat.qrs_onset:
        beat.notes.append("p_offset_after_qrs_onset")
        beat.p_status = PWaveStatus.UNCERTAIN
    if beat.t_offset is not None and beat.qrs_offset is not None and beat.t_offset <= beat.qrs_offset:
        beat.notes.append("t_offset_before_qrs_offset")
        beat.t_offset = None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def delineate(
    signal_2d: np.ndarray,
    r_peaks: np.ndarray,
    fs: int = config.FS,
    leads: tuple[str, ...] = config.LEADS,
    already_filtered: bool = False,
) -> DelineationResult:
    """Delineate a full 12-lead record.

    Returns both the reconciled global fiducials (what the measurements use) and
    the per-lead detail (what LUDB's per-lead expert annotations are compared
    against).
    """
    signal_2d = np.asarray(signal_2d, dtype=float)
    filtered = signal_2d if already_filtered else diagnostic_filter(signal_2d, fs)
    r_peaks = np.asarray(r_peaks, dtype=int)

    per_lead = {
        lead: delineate_lead(filtered[:, j], r_peaks, fs, lead)
        for j, lead in enumerate(leads[: filtered.shape[1]])
    }
    return DelineationResult(beats=reconcile(per_lead, r_peaks, fs), per_lead=per_lead, filtered=filtered)


__all__ = [
    "DelineationResult",
    "LeadBeatDelineation",
    "delineate",
    "delineate_lead",
    "estimate_noise_floor",
    "find_p_wave",
    "find_qrs_boundaries",
    "find_t_wave",
    "reconcile",
]
