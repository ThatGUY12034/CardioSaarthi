# CardioSaarthi — Project Brief

> This is the settled specification. Decisions recorded here are not to be
> re-litigated during implementation. Where implementation reveals that a
> decision cannot hold, the finding is recorded in `docs/decisions/` and taken
> to the guide — it is not silently changed here.

## 1. Identity

**Title:** CardioSaarthi: An AI-Based Adaptive Platform for ECG Learning and Clinical Case Simulation

Final-year B.E. Computer Engineering major project (Semester VII), Terna Engineering College,
Mumbai. Academic year 2026–27. Guide: Dr. Neelam Phadnis. Built in collaboration with Terna
Nursing College, whose faculty supply reference material, validate all clinical content, and
provide the student cohort for evaluation.

Originated from a nursing department topic list ("digital booklet on ECG interpretation"),
deliberately scoped up into a full platform.

## 2. The one design principle everything follows from

**Clinical facts are computed, never generated.**

- Measurements come from deterministic signal processing on the raw waveform.
- Diagnoses are inherited from the cardiologist annotations already in the dataset.
- The LLM only writes explanations, and only from faculty-approved sources.
- The LLM never decides correctness, never computes a value, never chooses the next action.

**Justification:** a 2026 evaluation of five current multimodal LLMs on ECG interpretation found
overall accuracy 52.3–64.9%, none exceeding the 75.6% majority-class baseline; ST/T-wave
assessment 20–41%; heart-rate error 14.8–46.7 bpm; and the same model returning different answers
on repeated runs. That paper's own limitations section names the absence of RAG and external
knowledge bases as motivation for future work — which is precisely this system.

## 3. Architecture — four layers

| Layer | What it is | Nature |
|---|---|---|
| 1 — Content pipeline | Ingest, measure, render, generate scenarios, faculty review | Offline batch, run once |
| 2 — Student runtime | Guided case sessions, grading, tutoring, competency tracking | Live |
| 3 — Faculty console | Content review queue + cohort analytics | Live |
| 4 — Patient explainer | Plain-language explanation of an issued ECG report | Live |

## 4. Layer 1 — content pipeline (build this first)

### 4.1 Data

PTB-XL from PhysioNet: 21,799 ten-second 12-lead recordings, 18,869 patients, 500 Hz and 100 Hz,
WFDB format, cardiologist SCP-ECG annotations, signal-quality flags, CC-BY licence. Read with the
`wfdb` package; each record is a 5000×12 array at 500 Hz.

### 4.2 Case selection

Exclude noisy, uncertain and paced records using the dataset's quality flags. Stratify the
remainder against the nursing syllabus so the bank has a planned distribution rather than mostly
normals. Process ~400–600 candidates to yield 120–200 approved cases covering: normal sinus
rhythm, sinus brady/tachycardia, atrial fibrillation, atrial flutter, SVT, VT, 1st/2nd/3rd-degree
block, RBBB, LBBB, STEMI by territory (anterior/inferior/lateral), ST depression, T-wave
inversion, chamber enlargement, hyper/hypokalaemia.

### 4.3 Measurement engine (Python + FastAPI, NeuroKit2 / SciPy)

Every value below is closed-form arithmetic. This is the single source of truth for the whole
application, stored in a `case_measurements` table.

- **Filter:** 4th-order Butterworth bandpass 0.5–40 Hz applied with `filtfilt` (forward +
  backward, zero phase). Zero phase is mandatory — a phase shift displaces wave boundaries, and
  PR/QRS/QT are all differences between boundaries.
- **R-peak detection (Pan–Tompkins):** bandpass 5–15 Hz → derivative
  `y[n] = (2x[n] + x[n−1] − x[n−3] − 2x[n−4])/8` → squaring → 150 ms moving-window integration →
  adaptive threshold. Refractory rules: no peak within 200 ms; candidates at 200–360 ms re-tested
  at half threshold to reject tall T waves.
- **Rate:** `HR = 60 / mean(RR)`.
- **Rhythm:** SDNN, `CV = SDNN/mean(RR)` (<0.05 regular, >0.15 irregular), RMSSD, plus
  autocorrelation on the RR series to separate irregularly irregular (AF) from regularly irregular
  (Wenckebach).
- **Delineation:** boundaries from the rectified-derivative envelope, searched inward from window
  edges for QRS and outward from the peak for P (this is more stable than walking outward from R,
  where the derivative is zero). T offset by the tangent method — steepest downslope after the T
  peak extended to the isoelectric baseline.
- **Intervals:** `PR = QRS_onset − P_onset`, `QRS = QRS_offset − QRS_onset`,
  `QT = T_offset − QRS_onset`. Corrections: Bazett `QT/√RR` and Fridericia `QT/RR^(1/3)` — report
  both.
- **Axis:** net QRS area (not peak height — area is robust to morphology) in leads I and aVF,
  which are orthogonal at 0° and +90°. `α = atan2(A_aVF, A_I)·180/π`. Normal −30° to +90°.
- **ST deviation:** measured per lead at J + 60 ms against the PR-segment baseline (isoelectric by
  definition). Per-lead measurement is what enables territorial localisation. Thresholds: ≥1 mm
  limb, ≥2 mm V2–V3.
- **Robust aggregation:** median across all beats, spread by `MAD = median(|xᵢ − median(x)|)`. MAD
  not standard deviation, because one artefactual beat drags a mean but cannot move a median.
- **Confidence score:** `C = w₁(1 − MAD/median) + w₂·SQI`, where SQI is beat-template correlation.
  Below threshold → withheld from the student bank until a faculty reviewer corrects it.

### 4.4 Rendering (Matplotlib)

Work entirely in millimetre coordinates. Two constants define the geometry: 25 mm/s and 10 mm/mV.

```
x_mm = (n / fs) × 25
y_mm = v_mV × 10 + row_offset
```

`ax.set_aspect('equal')` is mandatory — without it Matplotlib stretches the figure and every
interval is silently wrong. `dpi = 254` → exactly 10 px/mm, so a 200 ms interval is exactly 50 px.

Layout: 3×4 leads, each column 2.5 s = 62.5 mm, total 250 mm wide; row pitch 40 mm; lead II rhythm
strip across the full 10 s; 1 mV calibration pulse (10 mm tall × 5 mm wide); minor gridlines 1 mm,
major 5 mm.

Output two images per case: clean (for examination) and annotated (for feedback).

Rendering from signal rather than digitising photographed printouts is settled and justified — it
is established practice (ECG-Image-Kit, PhysioNet/CinC Challenge 2024, PTB-XL-Image-17K), it
avoids the unsolved digitisation problem, and it gives exact pixel↔millisecond ground truth.

### 4.5 Clinical scenario generation

One batched LLM call per case. Input: computed measurements + SCP diagnosis label. Output:
clinically consistent patient scenario (age, sex from real metadata, presenting complaint,
history, vitals, relevant labs). Must be coherent with the diagnosis. This is the only place AI
authors content in Layer 1, runs once offline, and nothing reaches a student unreviewed.

### 4.6 Faculty review queue

Every candidate case enters with status `pending`. Reviewer sees: rendered ECG, computed
measurements in editable fields, generated narrative. Actions: approve / edit / reject-with-reason.
Only approved cases are served. The rejection log is retained and reported as a pipeline-accuracy
measure. Build this early (by week 4) and put it in front of nursing faculty — their corrections
validate the measurement engine.

### 4.7 Knowledge base

Nursing college lecture notes and approved chapters → chunked (~500 tokens, overlapping) →
embedded → stored in pgvector (Postgres, not a separate vector DB). Each chunk retains source and
page for citation.

## 5. Layer 2 — student runtime

### 5.1 Orchestration: a deterministic state machine, NOT an intent router

The interface already knows which step the student is answering, so there is nothing to classify.
Control flow is code; the LLM is invoked inside a state and never selects a state transition. (An
intent router exists only in one bounded place: the free-form question box, classifying into
concept question / hint request / navigation / out-of-scope.)

States: `CASE_LOADED → AWAITING_STEP → EVALUATING → FEEDBACK_SENT → (next step, ×9) →
AWAITING_FINAL → CASE_COMPLETE`

### 5.2 Session state — one object, loaded at turn start, persisted at turn end

```
SessionState {
  sessionId, studentId, caseId
  currentStep         // 1..9
  attemptsThisStep    // 0,1,2
  mode                // BEGINNER_TUTOR | CLINICAL_MENTOR | EXAMINER
  stepResults[]       // answer, correct?, timeTaken, hintsUsed
  masterySnapshot     // per-concept scores
}
```

### 5.3 The nine locked steps

`rate → rhythm → axis → P waves → PR interval → QRS → ST segment → T waves → QT`

Order is dependency-driven (confirm with nursing faculty): rate is needed for QTc; PR requires the
P wave to be located first; ST is measured from the J point which is the QRS offset; QT needs QRS
onset, T offset and rate.

### 5.4 One turn, exact sequence

1. Load `SessionState` + `case_measurements`. Reject if submitted step ≠ `currentStep`.
2. Grade deterministically. Numeric answers within tolerance (heart rate ±10%, PR ±20 ms, QRS
   ±15 ms); categorical exact match; annotations by coordinate overlap. Returns
   `{correct, expectedValue, errorType}`.
3. Error label — an enum of ~25–30 values, e.g. `P_ABSENT_CALLED_PRESENT`, `PR_UNDERESTIMATED`,
   `REGULAR_CALLED_IRREGULAR`. Drives feedback, cache key and faculty analytics.
4. Branch:
   - correct → templated confirmation, advance step, **no LLM call** (~50% of turns)
   - wrong, 1st attempt, practice mode → hint, stay on step
   - wrong, 2nd attempt, or examiner mode → full explanation, advance
5. Cache check. Key = `(caseId, step, errorType, feedbackType, mode, personaVersion)`. Expect
   50–60% hit rate across a cohort.
6. Context assembly on miss: measurements for this step + student answer + errorType + top-3
   retrieved KB chunks + compact learner-state JSON (never full chat history). Hard token budget;
   truncate retrieval first.
7. One LLM call under the persona system prompt. ~8 s timeout.
8. Code-level validation: reject if a hint contains the expected value; reject if any diagnosis
   alias appears before step 9; reject if over length. One retry with stricter instruction, then a
   stored fallback. Then cache.
9. Persist step result + trace log (inputs, branch, cache hit/miss, prompt hash, latency, tokens).

### 5.5 Competency model

Baseline: 10 mixed-difficulty cases, no hints, initialises per-concept accuracy and review date.
Scheduling is deterministic — weak concepts first, SM-2 style spaced repetition, ordered by the
nursing syllabus. This is code, not an agent.

### 5.6 Free-form Q&A

Embed question → retrieve 3 chunks → answer strictly from them with citations → state explicitly
when no relevant material exists rather than improvising. This refusal behaviour is a demo
highlight.

### 5.7 End of case

Final interpretation → reveal cardiologist label + annotated image → one debrief LLM call → update
mastery.

## 6. CardioSaarthi persona

Implemented as a versioned behaviour configuration plus a prompt assembler — not as separate
agents.

```yaml
persona:
  id: cardiosaarthi
  version: 1.x
  identity: AI teaching assistant for ECG interpretation; not a clinician, never presents as one
  fixed_rules:
    - never state the final diagnosis before the last step
    - never state the correct value when giving a hint
    - explain findings in terms of cardiac physiology
    - use the terminology of the prescribed syllabus
    - cite the source passage for every factual claim
modes:
  beginner_tutor:   { tone: warm, hint_before_explanation: true,  max_attempts: 2, depth: full,     word_limit: 90, acknowledge_correct: true }
  clinical_mentor:  { tone: collegial, hint_before_explanation: true, max_attempts: 1, depth: moderate, word_limit: 60, acknowledge_correct: false }
  examiner:         { tone: terse, hint_before_explanation: false, max_attempts: 1, depth: brief, defer_feedback_to_end: true, word_limit: 40 }
```

Split matters: `tone`, `depth`, `word_limit` are read by the model; `max_attempts`,
`hint_before_explanation`, `defer_feedback_to_end` are read by the orchestrator and never shown to
the model.

Prompt assembly, four layers, rebuilt per call: identity + fixed rules → mode parameters → task
(feedback type, step, errorType, correct value marked "for your reasoning only") → grounding
(3 retrieved passages + citation IDs).

Six persona types from the guide's document were consolidated: Beginner Tutor / Clinical Mentor /
Examiner become the three modes; Emergency Simulation becomes a case filter + timer +
prioritisation question; Revision Coach is the spaced-repetition scheduler; Faculty Assistant is
the faculty console. Emotion/sentiment detection is deliberately excluded on ethical grounds —
inferring frustration approaches psychological assessment; the same benefit comes deterministically
from repeated errors triggering more scaffolding.

**Fallback library:** ~60 pre-written, faculty-approved paragraphs, one per
(errorType × feedbackType), used on API timeout or double validation failure. Write these before
writing prompts.

**Persona testing:** a fixture set of ~40 known error scenarios re-run after every prompt change,
asserting no answer leakage, no premature diagnosis, within word limit, citation present. Bump
`persona.version` on every change so stale cache entries retire.

## 7. Layer 3 — faculty console

Plain SQL over `step_responses`, no AI needed:

- concept × cohort accuracy heatmap
- step-level failure distribution
- confusion pairs (which conditions get mistaken for which)
- learners below competency threshold
- time-per-case distributions
- the content review queue (§4.6), which also receives newly generated explanations — since
  explanations are cached rather than regenerated, the complete student-facing corpus is a few
  hundred paragraphs and can be fully reviewed

Optional single LLM call: draft viva questions / lesson outline for the weakest concept.

## 8. Layer 4 — patient report explainer

Patient pastes text or uploads a photo of the report **already issued to them by a clinician**
(Tesseract OCR for images). Terms matched against a faculty-validated glossary and explained in
plain language, English + one regional language.

Constraints enforced in code, not by prompt: no diagnosis, no severity assessment, no treatment
suggestion, persistent instruction to discuss with their doctor. A red-flag term list (STEMI,
ventricular tachycardia, complete heart block, etc.) triggers an immediate seek-urgent-care banner
ahead of any explanation.

The module reads written reports only — it never interprets raw ECG waveforms for patients. This is
what keeps it on the education side of the line.

## 9. Tech stack (settled)

- **Backend:** Spring Boot (Java) — auth, session logic, orchestrator, grading, APIs
- **Signal processing & rendering:** Python + FastAPI, NeuroKit2, SciPy, Matplotlib, wfdb
- **Frontend:** React + Tailwind CSS + Chart.js
- **Database:** PostgreSQL with pgvector
- **Cache:** Redis (explanation cache, session state)
- **Deployment:** Docker Compose, institutional server or cloud
- **LLM:** provider-agnostic wrapper written on day one (model name in config). Free tiers
  (OpenRouter, Google AI Studio, Groq) for development; a paid Flash/Haiku-class key for the pilot,
  because free tiers cap at ~20 req/min which breaks a live classroom demo.

Services that know nothing about each other, each with typed contracts: `GradingService` (pure,
fully unit-testable), `RetrievalService`, `LlmService`, `MasteryService`. Only
`OrchestratorService` knows the flow.

## 10. Scope

### Committed

- 120–200 faculty-approved ECG cases
- deterministic measurement engine with confidence scoring
- standards-compliant rendering, clean + annotated
- nine-step locked interpretation with tolerance grading
- RAG tutor with citations, hint-before-explanation, code-enforced validation
- CardioSaarthi persona, three modes
- per-concept competency model + spaced repetition
- faculty review queue + cohort analytics
- technical validation report

### Extended (only if core lands on time)

- patient report explainer
- regional-language support in the learner interface
- on-waveform annotation exercises
- expansion beyond 200 cases
- comparative evaluation of persona modes
- full pre/post educational study

### Explicitly out of scope

- clinical diagnosis of any kind, for students or patients
- digitisation of photographed/scanned paper ECG printouts
- patient upload of raw waveforms
- integration with ECG machines, monitors, wearables, EHR/hospital systems
- training a diagnostic classification model (labels are inherited from the dataset)
- Holter, paced rhythms, paediatric ECGs
- voice interaction, animated avatars, emotion/sentiment detection
- native mobile app (responsive web only)
- multi-institution deployment

## 11. Safety and anti-hallucination

1. No clinical value originates from the model — measurements are computed, diagnoses inherited.
2. All explanations are retrieval-grounded in faculty-approved material, with citations; the system
   states when it has no relevant material rather than generating an answer.
3. Code checks every output before display (answer leakage, premature diagnosis, length), with
   retry then stored fallback.
4. Caching makes the corpus finite and reviewable — each explanation is generated once per
   (case, step, errorType), so the entire student-facing text can pass through the same faculty
   review queue as the cases. **This is the strongest single argument; lead with it.**
5. Every generation is logged (prompt, retrieved sources, output, timestamp) — fully auditable.
6. Measurable: sample 100 generated explanations, have faculty rate accurate / minor issue /
   incorrect, report the rate in the validation chapter.

## 12. Evaluation

**Technical**

- round-trip: measure intervals back from the rendered image, compare to source, report mean
  absolute error
- physical: print at 100% scale, verify a 200 ms interval measures exactly 5 mm with an ECG
  calliper
- measurement agreement: computed values vs faculty corrections logged during review
- factual-accuracy audit of generated explanations

**Educational**

Pre-test/post-test with nursing students, platform group vs conventional material. Outcomes:
interpretation accuracy, time per ECG, recognition of emergency conditions, retention, confidence,
usability.

## 13. Build order

| Weeks | Work |
|---|---|
| 1–3 | measurement engine + renderer + validation tests. No AI. Demo-able alone. |
| 4–6 | case generation pipeline + faculty review interface; first faculty review cycle. |
| 7–10 | student runtime: step-lock, grading, tutor with RAG, competency model. |
| 11–13 | faculty analytics console + patient explainer. |
| 14–16 | evaluation study, analysis, documentation. |

## 14. LLM cost strategy

Costs are trivial by design and should stay that way. No model call on correct answers; cache by
error label; generate case narratives once as an offline batch; retrieve 3 chunks not 10; send
compact learner state not chat history; cap `max_tokens`; use prompt caching for the static system
prompt. Steady-state figure to quote: roughly ₹10 per active learner per month.

## 15. Key references

1. Wagner et al., "PTB-XL, a Large Publicly Available Electrocardiography Dataset," *Scientific
   Data* 7:154, 2020.
2. Strodthoff et al., "Deep Learning for ECG Analysis: Benchmarks and Insights from PTB-XL," *IEEE
   JBHI* 25(5):1519–1528, 2021. — **IEEE base paper**
3. Stelling et al., "Diagnostic Accuracy and Reliability of Multimodal Large Language Models in
   Electrocardiogram Interpretation," *Life* 16(4):681, 2026. — **primary gap paper**
4. Shivashankara et al., "ECG-Image-Kit," *Physiological Measurement* 45(5), 2024.
5. Reyna et al., "Digitization and Classification of ECG Images: PhysioNet Challenge 2024," CinC
   2024.
6. "Educational interventions to improve ECG interpretation competence among nurses: a systematic
   review," 2026.
7. "Impact of self-directed e-learning on nurses' competency in arrhythmia interpretation," *PLOS
   One*, 2025.
8. "Retrieval-augmented generation in healthcare: a narrative review," *Digital Medicine*, 2026.
9. AHA/ACC/HRS Recommendations for the Standardization and Interpretation of the Electrocardiogram,
   *Circulation*, 2007.

## 16. Open decisions awaiting nursing faculty input

1. Are the tolerances (±10% rate, ±20 ms PR) clinically acceptable?
2. Is the nine-step order the sequence they teach? (axis placement varies; some curricula omit it
   at basic level)
3. Which twenty conditions must be in the case bank?
4. Which step do students most reliably get wrong?
5. Hint-first-then-retry, or explain immediately?
6. Is the patient module acceptable, and which terms trigger the urgent-care advisory?
7. What single analytics measure would faculty most want?
8. Review capacity — how many cases per sitting?

## 17. Known risks

1. **P-wave delineation is the weak point.** P waves are low-amplitude, sometimes buried in the T
   wave, sometimes genuinely absent. A misidentified P wave produces a wrong PR interval and the
   system then marks a correct student answer wrong. *Mitigation:* confidence scoring + mandatory
   faculty correction + editable interval fields in the review UI.
2. **Faculty review throughput is the critical path, not the code.** Design for reviewing rather
   than authoring; batch review sessions scheduled in advance; target 60 approved cases before 200.
3. **Hint leakage** — getting the model to nudge without naming the answer is fiddly. Hence the
   40-scenario fixture suite.
4. **Evaluation study coordination** — consent, scheduling, two cohorts, landing in the busiest
   weeks.
