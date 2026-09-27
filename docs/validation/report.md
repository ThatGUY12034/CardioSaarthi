# CardioSaarthi — Layer 1 technical validation

Engine version `0.1.0`, schema `1.0.0`, generated 2026-08-09 11:13 UTC.

Regenerate with `cardiosignal validate --report`. Every figure below is computed, not transcribed.

All measurement is deterministic signal processing. No model is consulted anywhere in the pipeline these numbers describe.

---

### Known-answer test (synthetic)

| set rate (bpm) | beats found | measured (bpm) | error (bpm) |
|---:|---:|---:|---:|
| 45 | 8 | 45.3 | +0.3 |
| 60 | 10 | 60.3 | +0.3 |
| 75 | 13 | 75.5 | +0.5 |
| 90 | 15 | 90.4 | +0.4 |
| 120 | 21 | 121.3 | +1.3 |
| 150 | 26 | 151.3 | +1.3 |

Simulated with `neurokit2.ecg_simulate`. This checks the arithmetic end to end against a known truth; it is not evidence about real ECGs, which is what the LUDB and QTDB sections are for.

---

### Render round-trip (measured off the PNG, not the signal)

| check | value |
|---|---|
| Image size | 2800 x 1800 px (expected 2800 x 1800) |
| Pixels per mm | 10.0000 |
| 1 large square (5 mm = 200 ms) | 50.0 px |
| Geometry exact | yes |
| Beats recovered from image | 12 of 13 |
| R-R interval MAE | 0.40 ms |
| R-peak position MAE | 2.36 ms |
| Amplitude MAE | 0.20 mV |

The waveform was reconstructed from pixel positions alone and re-measured with the same detector. Residual error is line width and anti-aliasing, which is also what a student's caliper contends with.

---

### Beat detection (LUDB)

| metric | value | target |
|---|---|---|
| Sensitivity | 98.74% | 99% |
| PPV | 98.64% | 99% |
| True positives | 1808 | |
| False positives | 25 | |
| False negatives | 23 | |

### Boundary delineation (LUDB, all leads pooled)

| boundary | n | coverage | MAE ms | bias ms | SD ms | p95 ms |
|---|---|---|---|---|---|---|
| P onset | 12480 | 74.3% | 11.8 | 0.1 | 21.9 | 44.0 |
| P offset | 11172 | 66.5% | 17.0 | 4.4 | 25.0 | 46.0 |
| QRS onset | 21724 | 99.5% | 13.4 | 2.8 | 22.0 | 42.0 |
| QRS offset | 21873 | 99.7% | 10.1 | 2.4 | 15.7 | 30.0 |
| T offset | 15287 | 77.8% | 19.3 | -9.0 | 28.7 | 66.0 |

Records evaluated: 200. Failures: 0.

*Coverage* is the share of expert-marked boundaries for which the engine produced a comparable estimate. Boundaries the engine declined to produce are counted here, not averaged into the error as zeros.

---

### QT interval (QT Database, manual annotations)

| metric | value |
|---|---|
| Records with manual annotation | 101 of 105 |
| Annotated beats used | 3471 |
| Annotated beats rejected as implausible | 2 |
| Beats matched and measured | 3284 (94.6%) |
| QT mean absolute error | 43.4 ms |
| QT median absolute error | 28.0 ms |
| QT bias (signed) | -11.4 ms |
| QT SD of error | 68.3 ms |
| Beats with error > 100 ms | 10.6% |

QTDB is sampled at 250 Hz, so one sample is 4 ms — a floor of roughly ±2 ms is inherent to the reference itself. Reference beats whose annotated QT falls outside 150–1200 ms are excluded: the manual annotator marks only selected beats, so a T wave marked without a preceding QRS attaches to a beat thousands of samples earlier and yields a 'QT' of tens of seconds. The count is reported above rather than quietly dropped.

The median is given alongside the mean because the mean is sensitive to the small number of beats where the T wave is genuinely unmeasurable.

---

## Reading these numbers

**Bias versus scatter.** A large bias is a systematic offset and is usually fixable in the algorithm; a large error with near-zero bias is scatter and is not. The two are reported separately for that reason.

**Coverage is not optional.** A delineator that declines to place a boundary scores no error at all, so accuracy quoted without coverage is meaningless. Boundaries the engine refused to produce are counted as missing coverage and never averaged in as zero error.

**P waves are the weak point, by design of the problem.** They are low amplitude, sometimes buried in the preceding T wave, and sometimes genuinely absent. The engine reports `P_ABSENT` rather than guessing, because an invented P wave yields a confident wrong PR interval and the platform would then mark a correct student answer wrong.

**The confidence gate.** Cases below the confidence threshold are withheld from the student bank until a faculty reviewer confirms or corrects them. A case sent for review costs a reviewer two minutes; a bad measurement served to a student costs their trust in the platform.

## Still to do

- Physical check: print `calibration_sheet.pdf` at 100% scale and confirm with an ECG caliper that 200 ms measures exactly 5 mm.
- Measurement agreement against faculty corrections, once the review queue has run (week 4+).
