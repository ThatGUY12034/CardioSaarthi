"""Every tunable constant in the measurement engine and renderer lives here.

Nothing downstream may hard-code a number that appears in this file. When a
faculty reviewer disputes a threshold, this is the only file that changes.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Repo root is three levels up from this file: src/cardiosignal/config.py
# -> src/cardiosignal -> src -> signal-service -> CardioSaarthi
PACKAGE_ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = PACKAGE_ROOT.parent.parent
REPO_ROOT = SERVICE_ROOT.parent

DATA_ROOT = Path(os.environ.get("CARDIOSIGNAL_DATA", REPO_ROOT / "data"))
ARTIFACT_ROOT = Path(os.environ.get("CARDIOSIGNAL_ARTIFACTS", REPO_ROOT / "artifacts"))
DOCS_ROOT = REPO_ROOT / "docs"

PTBXL_ROOT = DATA_ROOT / "ptbxl"
LUDB_ROOT = DATA_ROOT / "ludb"
QTDB_ROOT = DATA_ROOT / "qtdb"

# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------
FS = 500  # Hz. The 500 Hz PTB-XL records give 2 ms resolution; the 100 Hz
# records give 10 ms, which cannot support a +/-15 ms QRS tolerance.
RECORD_SECONDS = 10.0
N_SAMPLES = int(FS * RECORD_SECONDS)  # 5000

LEADS = ("I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6")
LIMB_LEADS = ("I", "II", "III", "aVR", "aVL", "aVF")
PRECORDIAL_LEADS = ("V1", "V2", "V3", "V4", "V5", "V6")

# Coronary territories, used to localise ST deviation.
TERRITORIES: dict[str, tuple[str, ...]] = {
    "anterior": ("V1", "V2", "V3", "V4"),
    "inferior": ("II", "III", "aVF"),
    "lateral": ("I", "aVL", "V5", "V6"),
}

# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
# Diagnostic band. Applied with filtfilt (forward + backward) so the response is
# zero phase. A phase shift displaces wave boundaries, and PR / QRS / QT are all
# *differences between boundaries*, so any shift corrupts every interval.
BANDPASS_HZ = (0.5, 40.0)
FILTER_ORDER = 4

# Pan-Tompkins QRS emphasis band (separate from the diagnostic band above; this
# signal is used only to locate beats, never to measure amplitudes).
QRS_BAND_HZ = (5.0, 15.0)

POWERLINE_HZ = 50.0  # India. Notch is optional; the 40 Hz low-pass already covers it.

# ---------------------------------------------------------------------------
# R-peak detection (Pan-Tompkins)
# ---------------------------------------------------------------------------
INTEGRATION_MS = 150  # moving-window integrator width, ~ one QRS duration
REFRACTORY_MS = 200  # no second peak may be declared inside this window
TWAVE_SEARCH_MS = 360  # candidates in [REFRACTORY, TWAVE_SEARCH] are re-tested
TWAVE_THRESHOLD_FACTOR = 0.5  # ...at half threshold, to reject tall T waves
LEARNING_SECONDS = 2.0  # initial threshold estimation window
SEARCHBACK_FACTOR = 1.66  # if no peak within 1.66 x mean RR, search back

# ---------------------------------------------------------------------------
# Delineation
# ---------------------------------------------------------------------------
QRS_SEARCH_BEFORE_MS = 120  # window edges either side of R within which the
QRS_SEARCH_AFTER_MS = 140  # QRS onset/offset are searched inward
QRS_CORE_MS = 60  # +/- this around R is "definitely QRS"; the peak slope
# inside it is the reference the boundary threshold is a fraction of. Taking
# the reference from the whole search window instead lets a large T wave set
# the scale and drags the boundary out onto the T.
QRS_BOUNDARY_SLOPE_FRACTION = 0.15  # P and T slopes reach ~0.10 of the QRS
# peak slope, so anything below ~0.12 latches onto the wrong wave.
BOUNDARY_PERSISTENCE_MS = 6  # a crossing must hold this long to count, so a
# single noisy sample cannot define a boundary

# Second, lower threshold. The 0.15 crossing reliably finds the complex but sits
# inside it; walking back out to the foot of the wave removes the systematic
# narrowing that measurement against LUDB exposed.
QRS_FOOT_SLOPE_FRACTION = 0.04
QRS_FOOT_MAX_TRAVEL_MS = 40  # how far outward the refinement may walk
QRS_FOOT_PERSISTENCE_MS = 4

P_SEARCH_START_MS = 350  # P is sought in [QRS_onset-350ms, QRS_onset-20ms]
P_SEARCH_END_MS = 20
P_BOUNDARY_SLOPE_FRACTION = 0.10  # relative to the P wave's own peak slope
P_MAX_HALF_WIDTH_MS = 90  # the outward walk from the P peak stops here, so a
# P wave can never be reported wider than ~180 ms
P_RETURN_FRACTION = 0.55  # ...and must also be back within this fraction of its
# own amplitude, so the walk does not stop on a shoulder.
#
# This value trades coverage against precision and was chosen by measurement,
# not taste. Against LUDB (15 records, all leads):
#     0.30 -> P-onset coverage 53%, MAE 11.4 ms, bias -5.5 ms
#     0.45 -> 68%, 11.8 ms, -3.0 ms
#     0.55 -> 71%, 12.3 ms, -2.0 ms
#     0.75 -> 76%, 14.6 ms,  0.0 ms
# A stricter value refuses to place a boundary on any P wave that does not
# return cleanly to baseline, which is most of them; a looser one stops on the
# shoulder and inflates the error. 0.55 buys 18 points of coverage for 0.9 ms.
T_SEARCH_START_MS = 100  # T is sought in [QRS_offset+100ms, +min(0.6*RR, 500ms)]
T_SEARCH_MAX_MS = 500
T_SEARCH_RR_FRACTION = 0.6
T_SEARCH_NEXT_BEAT_GUARD_MS = 120  # the T search always stops this far short of
# the next R, so it can never reach into the following P wave

# A P candidate must clear *both* bars, otherwise the beat is reported
# P_ABSENT rather than guessed at. The SNR bar rejects noise dressed up as a P
# wave; the absolute bar stops an extremely clean record from promoting a
# 0.1 mm ripple, since in a quiet record almost anything beats the noise floor.
P_DETECTION_SNR = 3.0
P_MIN_AMPLITUDE_MV = 0.02  # 0.2 mm. Real P waves in LUDB have a median
# amplitude of ~0.057 mV and a lower quartile of ~0.032 mV, so a 0.04 mV floor
# discarded roughly a third of genuine P waves. The floor now only rejects
# ripple; the requirement that a P wave appear in at least two leads
# (see `reconcile`) is what actually guards against calling noise a P wave.

# ---------------------------------------------------------------------------
# Interval reference values (for flagging only — never for grading)
# ---------------------------------------------------------------------------
PR_NORMAL_MS = (120, 200)
QRS_NORMAL_MS = (70, 110)

# PR is a conduction time. In sinus rhythm it does not vary by tens of
# milliseconds from beat to beat, so a large *absolute* spread does not mean
# "an imprecise PR interval" -- it means the waves being measured are not
# consistent P waves. In atrial fibrillation the delineator will happily find a
# fibrillatory wave in the P position on most beats and report a confident PR
# interval for a rhythm that has none. The relative confidence score does not
# catch this (a 44 ms spread on a 276 ms interval still scores 0.90), so the
# gate has to be absolute.
PR_MAX_MAD_MS = 20.0
# ...and the P wave must actually be present on most beats before any PR
# interval is served at all.
PR_MIN_P_FRACTION = 0.6

# The QT cannot occupy most of the cardiac cycle. Repolarisation has to finish
# before the next beat depolarises, and a QT beyond ~65% of the R-R interval
# means the T offset has been carried too far -- usually into the following P
# wave at faster rates. Measured across the first full run of the case bank,
# 15.5% of released cases exceeded this, with a median heart rate of 95 bpm
# against 68 bpm for the rest, and a median Bazett QTc of 658 ms. Those are not
# long QT intervals, they are over-extended T offsets, and they are withheld.
QT_MAX_RR_FRACTION = 0.65

# PTB-XL anonymises every age above 89 by recording it as 300.
AGE_CENSOR_VALUE = 300
AGE_CENSOR_CEILING = 89.0
QTC_UPPER_MS = {"male": 450, "female": 460}
HR_NORMAL_BPM = (60, 100)
AXIS_NORMAL_DEG = (-30.0, 90.0)

# ---------------------------------------------------------------------------
# Rhythm classification
# ---------------------------------------------------------------------------
CV_REGULAR = 0.05  # CV = SDNN / mean(RR)
CV_IRREGULAR = 0.15
AUTOCORR_PERIODIC = 0.35  # RR-series autocorrelation peak above this implies a
# repeating pattern (regularly irregular, e.g. Wenckebach)
MIN_BEATS_FOR_RHYTHM = 4

# ---------------------------------------------------------------------------
# ST segment
# ---------------------------------------------------------------------------
J_OFFSET_MS = 60  # measurement point after the J point (= QRS offset)
PR_BASELINE_WINDOW_MS = 20  # PR segment window used as the isoelectric reference
ST_THRESH_LIMB_MM = 1.0
ST_THRESH_V2V3_MM = 2.0
ST_DEPRESSION_THRESH_MM = 0.5

# ---------------------------------------------------------------------------
# Aggregation and confidence
# ---------------------------------------------------------------------------
# Spread is reported as MAD = median(|x_i - median(x)|), not standard deviation:
# one artefactual beat drags a mean but cannot move a median.
MIN_BEATS_FOR_MEASURE = 3
CONFIDENCE_W_SPREAD = 0.6  # w1, weight on beat-to-beat consistency
CONFIDENCE_W_SQI = 0.4  # w2, weight on beat-template correlation
CONFIDENCE_MIN = 0.70  # below this the case is withheld from the student bank
SQI_TEMPLATE_WINDOW_MS = (-200, 400)  # window around R used to build the template

# ---------------------------------------------------------------------------
# Rendering — the two constants that define ECG paper geometry
# ---------------------------------------------------------------------------
MM_PER_S = 25.0  # standard paper speed
MM_PER_MV = 10.0  # standard gain
DPI = 254  # -> exactly 10 px/mm, so 200 ms is exactly 50 px

SHEET_WIDTH_MM = 250.0  # 4 columns x 2.5 s x 25 mm/s
COLUMN_SECONDS = 2.5
ROW_PITCH_MM = 40.0
N_ROWS = 3
N_COLUMNS = 4
RHYTHM_LEAD = "II"
MARGIN_MM = 10.0
CAL_LEAD_IN_MM = 10.0  # space left of t=0 for the calibration pulse

# Standard 3x4 arrangement. Rows are lead groups, columns are 2.5 s time
# windows -- the four columns are consecutive slices of the same ten seconds,
# not four repetitions.
SHEET_LAYOUT = (
    ("I", "aVR", "V1", "V4"),
    ("II", "aVL", "V2", "V5"),
    ("III", "aVF", "V3", "V6"),
)

GRID_MINOR_MM = 1.0
GRID_MAJOR_MM = 5.0
CAL_PULSE_HEIGHT_MM = 10.0  # 1 mV
CAL_PULSE_WIDTH_MM = 5.0  # 200 ms

COLOR_GRID_MINOR = "#f2b8b5"
COLOR_GRID_MAJOR = "#e0736d"
COLOR_TRACE = "#111111"
COLOR_ANNOTATION = {
    "p": "#1f77b4",
    "qrs": "#2ca02c",
    "t": "#d62728",
    "baseline": "#7f7f7f",
    "j_point": "#9467bd",
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
RPEAK_MATCH_WINDOW_MS = 75  # Se/PPV match tolerance against reference annotations
BOUNDARY_MATCH_WINDOW_MS = 150  # window for pairing our boundary to a reference one

# Targets quoted in the validation report. Not assertions on real data — the
# report states the measured value regardless; these mark the pass line.
TARGET_RPEAK_SENSITIVITY = 0.99
TARGET_RPEAK_PPV = 0.99
TARGET_QRS_BOUNDARY_MAE_MS = 10.0
TARGET_T_OFFSET_MAE_MS = 25.0
TARGET_P_ONSET_MAE_MS = 15.0

SCHEMA_VERSION = "1.0.0"
