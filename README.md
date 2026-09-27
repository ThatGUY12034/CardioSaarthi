# CardioSaarthi

**An AI-Based Adaptive Platform for ECG Learning and Clinical Case Simulation**

Final-year B.E. Computer Engineering major project (Semester VII), Terna Engineering College, Mumbai.
Academic year 2026–27. Guide: Dr. Neelam Phadnis. Built in collaboration with Terna Nursing College.

---

## The design principle everything follows from

> **Clinical facts are computed, never generated.**

- Measurements come from deterministic signal processing on the raw waveform.
- Diagnoses are inherited from the cardiologist annotations already in the dataset.
- The LLM only writes explanations, and only from faculty-approved sources.
- The LLM never decides correctness, never computes a value, never chooses the next action.

The full specification is in [docs/brief.md](docs/brief.md).

## Architecture

| Layer | What it is | Nature | Status |
|---|---|---|---|
| 1 — Content pipeline | Ingest, measure, render, generate scenarios, faculty review | Offline batch | measurement + rendering **done**; scenarios and review queue next |
| 2 — Student runtime | Guided case sessions, grading, tutoring, competency tracking | Live | not started |
| 3 — Faculty console | Content review queue + cohort analytics | Live | not started |
| 4 — Patient explainer | Plain-language explanation of an issued ECG report | Live | not started |

## Where Layer 1 stands

Measured against expert-annotated data the engine has never been tuned on. Full detail, and the
command that regenerates every figure, in [docs/validation/report.md](docs/validation/report.md).

**Beat detection** — LUDB, all 200 records: sensitivity **98.7%**, PPV **98.6%** (1,808 true
positives, 25 false positives, 23 false negatives).

**Boundary delineation** — LUDB, all 12 leads pooled, against cardiologist markings:

| boundary | coverage | MAE | bias |
|---|---:|---:|---:|
| P onset | 74.3% | 11.8 ms | +0.1 ms |
| P offset | 66.5% | 17.0 ms | +4.4 ms |
| QRS onset | 99.5% | 13.4 ms | +2.8 ms |
| QRS offset | 99.7% | 10.1 ms | +2.4 ms |
| T offset | 77.8% | 19.3 ms | −9.0 ms |

**QT interval** — QT Database, 101 records, manual annotations: median absolute error **28 ms**,
mean **43 ms**, bias −11 ms.

**Render round-trip** — intervals measured back off the rendered PNG by pixel: image exactly
2800 × 1800 px at 10 px/mm, one large square exactly 50 px, R-R interval MAE **0.4 ms**.

**Case bank** — 714 candidates drawn from PTB-XL, all 714 measured and rendered: 491 servable,
221 withheld by the confidence gate for faculty review, 2 unmeasurable.

Coverage is reported next to accuracy throughout. A delineator that declines to place a boundary
records no error at all, so an accuracy figure quoted without coverage is not a claim.

> **Three conditions on the brief's list cannot be sourced from PTB-XL at all** — ventricular
> tachycardia and both electrolyte disturbances. This needs a decision from faculty; see
> [docs/decisions/001](docs/decisions/001-conditions-ptbxl-cannot-supply.md).

## Repository layout

```
signal-service/      Layer 1 — Python. Measurement engine + renderer. No AI, no DB.
docs/                Specification and generated validation reports.
data/                Downloaded datasets (gitignored).
artifacts/           Pipeline output: measurements, rendered images (gitignored).
```

## Quick start (Layer 1)

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e "signal-service[dev]"
```

Download the datasets (PTB-XL for the case bank; LUDB and QTDB are expert-annotated
answer keys used only by the validation suite):

```bash
python signal-service/scripts/download_data.py ludb
```

```bash
python signal-service/scripts/download_data.py qtdb
```

```bash
python signal-service/scripts/download_data.py ptbxl --metadata-only
```

Then select cases, measure and render:

```bash
cardiosignal select --out artifacts/candidates.parquet
```

```bash
cardiosignal run --batch artifacts/candidates.parquet --out artifacts/
```

Regenerate the technical validation report:

```bash
cardiosignal validate --report
```

Inspect a single case, or serve the engine over HTTP:

```bash
cardiosignal measure --ecg-id 968
```

```bash
uvicorn cardiosignal.api:app --port 8001
```

Run the tests. Dataset-backed tests skip cleanly if the data is not downloaded:

```bash
pytest signal-service/tests -q
```

## Datasets

| Dataset | Use | Licence |
|---|---|---|
| [PTB-XL](https://physionet.org/content/ptb-xl/) — 21,799 records, 18,869 patients | Case bank; diagnoses inherited from its SCP-ECG annotations | CC-BY 4.0 |
| [LUDB](https://physionet.org/content/ludb/) — 200 records, expert P/QRS/T boundaries | Answer key for delineation accuracy | CC-BY 4.0 |
| [QT Database](https://physionet.org/content/qtdb/) — 105 records, manual QT annotation | Answer key for QT accuracy | ODC-BY |

Datasets are **not** committed. `data/` is gitignored.
