# Literature Survey

**CardioSaarthi: An AI-Based Adaptive Platform for ECG Learning and Clinical Case Simulation**

---

## 2.1 Scope and method

This survey covers six strands that together bound the problem: the educational need for ECG
competence in nursing; the effectiveness of digital and self-directed instruction; the public
data foundations on which any ECG system must rest; deterministic algorithms for measuring the
ECG; the rendering of signals as standards-compliant diagnostic images; and the emerging and
largely negative evidence on large language models applied to ECG interpretation, together with
retrieval-augmented generation as the proposed mitigation.

Sources were drawn from IEEE Xplore, PhysioNet, ScienceDirect, MDPI, Nature Portfolio and arXiv,
prioritising peer-reviewed work from 2020 onward, with foundational algorithmic papers retained
regardless of age where they remain the accepted method.

---

## 2.2 The educational problem: ECG interpretation competence among nurses

The clinical case for the project rests on a documented and persistent competence gap. A 2026
systematic review searched MEDLINE, CINAHL, Embase and Scopus and identified **twenty-three
studies** — randomised controlled trials and pre-post quasi-experimental designs across several
countries and clinical settings — evaluating educational interventions intended to improve ECG
interpretation among nurses [1]. The review found that interventions were consistently associated
with measurable improvement, and grouped them into five themes: traditional and structured
education, technology-enhanced learning, micro-learning, blended and learner-centred models, and
**sustainability and reinforcement of learning over time**.

That final theme is the one this project takes as a design requirement rather than a finding.
The review establishes that teaching ECG interpretation works, but that improvement is not
self-sustaining; without reinforcement, gains decay. It does not, however, propose or evaluate a
specific platform, and the heterogeneity of designs across the twenty-three studies prevents any
pooled estimate of effect size. The gap it leaves is not *whether* to teach, but *what to build*.

The need itself is separately documented. A systematic mixed-studies review of forty-three papers
on nurses' ECG competence in acute care settings [16] identified inadequate exposure to ECG
interpretation and the absence of regular training as the principal contributors to poor
competence, and found completion of ECG-related education and clinical experience to be the
factors most associated with confidence. Taken together, [16] establishes the deficit and [1]
establishes that structured intervention closes it.

---

## 2.3 Digital and self-directed learning

Work on self-directed digital instruction for arrhythmia interpretation reports measurable skill
gain and a correlation between outcome and prior clinical experience [2]. Such studies support
the feasibility of unsupervised, learner-paced ECG practice, which is the delivery model this
project adopts.

Their limitations are consistent: single-site cohorts, absence of a control group, and scope
restricted to rhythm recognition rather than the full systematic interpretation sequence. They
establish that self-directed ECG learning *can* work; they do not establish what content or
feedback mechanism makes it work.

---

## 2.4 Data foundations: public ECG databases

**PTB-XL** [3] is the field-standard corpus: 21,799 ten-second twelve-lead records from 18,869
patients, at 100 Hz and 500 Hz, in WFDB format, with cardiologist SCP-ECG annotations, per-record
signal-quality flags, and a CC-BY licence. Its companion benchmarking study [4] established
standardised train/test folds and baseline deep-learning results, and remains the reference point
for evaluation protocol on this dataset.

Two properties of PTB-XL bear directly on the present work. First, it distributes **signals only**
— it contains no ECG images, so any image-based teaching material must be generated. Second, its
diagnostic coverage is **uneven at the tail**. Verification against the distributed metadata for
this project found that several conditions common to a nursing syllabus are scarce or absent
entirely, a finding developed in §2.10.

For validating measurement rather than classification, two further databases are required, since
PTB-XL carries diagnoses but not interval ground truth:

- **LUDB** [5] — 200 ten-second twelve-lead records at 500 Hz in which cardiologists manually
  annotated the boundaries and peaks of every P wave, QRS complex and T wave, **independently for
  each lead**. It is the reference tool for validating delineation algorithms, and published deep
  learning approaches evaluated on it report F1 measures of at least 97.8% for P-wave boundaries,
  99.5% for T waves and 99.9% for QRS complexes.
- **QT Database** [6] — 105 records with manually annotated QT intervals, the long-standing
  benchmark against which QT measurement algorithms are compared.

---

## 2.5 Deterministic ECG measurement and delineation

The algorithmic basis for automated ECG measurement predates the current machine-learning
literature and remains standard.

**QRS detection.** The Pan–Tompkins algorithm [7] — band-pass filtering, differentiation,
squaring, moving-window integration and adaptive thresholding, with refractory-period logic to
reject T waves misread as beats — is still the reference real-time QRS detector and the basis of
most subsequent work.

**Wave delineation.** Boundary detection from the rectified-derivative envelope, and determination
of the T-wave offset by the **tangent method** (the steepest descent after the T peak extended to
the isoelectric baseline), are the conventional constructions. The tangent method is preferred
because a T wave approaches baseline asymptotically and has no objectively identifiable terminal
instant; the tangent construction is reproducible where visual judgement is not.

**Rate correction.** Bazett [8] and Fridericia [9] remain the two corrections in general use, the
former dominant in teaching and the latter better behaved at rate extremes. Reporting both, rather
than choosing, is the position this project takes.

**Standards.** The AHA/ACC/HRS recommendations [10] define the measurement conventions this work
implements: measurement from the earliest onset and latest offset across simultaneously recorded
leads, ST deviation assessed against the PR-segment baseline, and the 25 mm/s, 10 mm/mV display
convention.

What this body of work provides is a fully deterministic path from waveform to clinical
measurement. What it does not provide is any pedagogy — these are algorithms for instrumentation,
not for instruction.

---

## 2.6 From signal to standards-compliant image

Because PTB-XL ships signals and teaching requires images, signal-to-image synthesis is a
necessary step, and it is established practice rather than a novel one.

**ECG-Image-Kit** [11] provides a validated generation pipeline, and the **PhysioNet/CinC
Challenge 2024** [12] established digitisation and classification of ECG images as a shared task.
**PTB-XL-Image-17K** [13] is the most recent contribution: 17,271 synthetic twelve-lead images
generated from PTB-XL, released February 2026 with segmentation masks, ground-truth time series,
YOLO-format bounding boxes for lead regions and lead-name text, and an open generation framework.

The critical observation for the present work is that **all three are built for digitisation
research**, not education. Their images deliberately incorporate realistic degradation — creases,
rotation, shadows, handwritten annotation — because their purpose is to train models that recover
signals from imperfect photographs. An educational platform requires the opposite: an
undegraded rendering with exact and verifiable pixel-to-millisecond correspondence, so that a
measurement taken from the image agrees with the measurement held by the grader. The published
image sets are therefore unsuitable as-is, notwithstanding their scale.

---

## 2.7 Large language models applied to ECG interpretation

This is the strand that motivates the project's central design constraint.

The most direct evidence is a 2026 evaluation of five current multimodal LLMs — ChatGPT-5.3,
Gemini 3.1 Pro, Claude Opus 4.6, Grok 4.1 and ERNIE 5.0 — on thirteen standard twelve-lead ECGs,
each presented across five independent runs, yielding **2,275 task-level assessments** compared
against expert-consensus ground truth [14]. Six categorical tasks were assessed (rhythm,
electrical axis, PR interval and P-wave morphology, QRS duration, ST/T-wave morphology and QTc),
with heart-rate estimation evaluated by mean absolute error.

The reported findings are these:

| Measure | Result |
|---|---|
| Overall categorical accuracy | **52.3 – 64.9%** across models |
| Best-performing task (QRS duration) | 66.2 – 90.8% |
| **Worst-performing task (ST/T-wave)** | **20.0 – 41.5%** |
| Inter-run reliability | A **dissociation between accuracy and reliability** was observed — the same model returned different answers on repeated presentations of the same ECG |

Two conclusions follow, and both are structural rather than incidental. First, accuracy at this
level is not usable as a source of clinical values in a teaching system: a tutor that is wrong on
ST/T assessment between three and four times in five would teach the wrong thing on precisely the
findings where error is most consequential. Second, and more fundamentally, **non-determinism is
disqualifying independent of accuracy**. An educational system must grade a student's answer
against a fixed correct value; a source that returns different answers on repeated runs cannot
provide one.

Related work confirms the direction: comparative studies of multimodal LLMs against dedicated ECG
models find the purpose-built model more precise, and zero-shot LLM diagnostic discrimination
correspondingly limited.

---

## 2.8 Retrieval-augmented generation as the mitigation

The remedy proposed in the LLM literature is grounding rather than scale. A 2026 narrative review
of retrieval-augmented generation in healthcare [15] synthesises methods and contributions across
clinical applications, and the associated empirical literature is consistent: RAG systems grounded
in authoritative guidelines have been reported to reduce hallucination to zero in specific
clinical consultation tasks, against 8% for the ungrounded baseline, while producing a citable
chain back to source material.

RAG therefore addresses the *explanation* problem — a model constrained to approved source
material, with citations, is auditable in a way a free-generating model is not. It does not
address the *measurement* problem, because retrieval cannot compute a QT interval from a waveform.
The reviews are also narrative rather than systematic, and no ECG-specific RAG study was located.

---

## 2.9 Comparative summary

| # | Work | Contribution | Limitation for this project |
|---|---|---|---|
| [1] | Nursing ECG education review, 2026 | 23 studies; interventions work; reinforcement matters | No platform proposed; heterogeneous designs prevent pooling |
| [2] | Self-directed e-learning study | Learner-paced ECG practice is feasible | Single site, no control, rhythm only |
| [3] | PTB-XL, 2020 | 21,799 records, cardiologist SCP annotations, quality flags | Signals only; diagnostically uneven at the tail |
| [4] | PTB-XL benchmark, 2021 | Standard folds and evaluation protocol | Classification only; no measurement, no explanation |
| [5] | LUDB, 2020 | Per-lead expert P/QRS/T boundaries, 200 records | A validation set, not teaching material |
| [6] | QT Database, 1997 | Manual QT reference standard | Two leads, 250 Hz, selected beats only |
| [7] | Pan–Tompkins, 1985 | Reference real-time QRS detector | Detection only; no delineation or interpretation |
| [11–13] | ECG image synthesis, 2024–2026 | Signal-to-image generation is validated practice | Built for digitisation; deliberately degraded; no measurement ground truth |
| [14] | Multimodal LLM ECG evaluation, 2026 | 2,275 assessments; 52.3–64.9% accuracy; ST/T 20–41%; unreliable across runs | Establishes that LLMs cannot supply clinical values |
| [15] | Healthcare RAG review, 2026 | Grounding reduces hallucination; citable knowledge chain | Narrative review; no ECG-specific study |

---

## 2.10 Identified research gap

The literature establishes each piece separately and connects none of them.

1. **Teaching ECG interpretation to nurses works, but decays without reinforcement** [1], and no
   evaluated platform delivers that reinforcement systematically.
2. **The data exists but not in teachable form.** PTB-XL supplies expert-labelled signals [3];
   published image sets supply images built for digitisation research rather than instruction
   [11–13]. Neither supplies measured intervals paired with an examinable image.
3. **Current LLMs cannot supply clinical values.** At 52.3–64.9% accuracy, 20–41% on ST/T
   assessment, and demonstrably non-deterministic across repeated runs [14], an LLM cannot be the
   source of the value a student is graded against.
4. **Grounding is the accepted mitigation but has not been applied here.** RAG reduces
   hallucination and provides citable provenance [15], yet no ECG-specific educational application
   was located.

> **The gap.** No existing system separates *computed clinical measurement* from
> *retrieval-grounded explanation*. Systems that measure do not teach; systems that teach rely on
> a generative model for values it is demonstrably unable to supply reliably. ECG instruction
> requires values that are identical on every presentation — a requirement no published
> LLM-based approach satisfies.

---

## 2.11 Positioning of the present work

CardioSaarthi addresses the gap by architectural separation: **clinical facts are computed, never
generated.** Measurements derive from deterministic signal processing over the raw waveform;
diagnoses are inherited verbatim from the dataset's cardiologist annotations; the language model
is confined to composing explanations from faculty-approved sources, and never computes a value,
decides correctness, or selects the next action.

Phase 1 of the implementation has been completed and validated against expert-annotated data the
engine was never tuned on. Measured results are given below alongside the published context.

| Measure | This work | Published context |
|---|---|---|
| QRS detection sensitivity / PPV (LUDB, 200 records) | 98.7% / 98.6% | Deep-learning methods on LUDB report QRS F1 ≈ 99.9% [5] |
| P-wave onset error | 11.8 ms MAE (74% coverage) | P-wave boundaries are the acknowledged hardest case [5] |
| QRS onset / offset error | 13.4 / 10.1 ms MAE | — |
| T-wave offset error | 19.3 ms MAE | — |
| QT interval error (QTDB, 101 records) | 28 ms median, 43 ms mean | Benchmark set for QT algorithms [6] |
| Rendering fidelity | Exactly 10 px/mm at 254 dpi; R-R intervals recovered from the rendered image to 0.4 ms MAE | Published image sets provide no measurement ground truth [11–13] |

Two properties distinguish this from the LLM results in [14]. The measurements are **deterministic**
— identical on every run by construction — and each carries an explicit confidence score, so that
cases the engine cannot measure reliably are withheld for faculty correction rather than served.
Of 714 candidate cases processed, 385 were released and 327 automatically withheld.

A separate contribution arises from the same verification process. Cross-referencing the engine's
per-lead ST measurements against PTB-XL's own labels established that **ventricular tachycardia and
electrolyte disturbances are absent from PTB-XL entirely**, and that its `INJ*` statements denote
*subendocardial* injury — ST depression — rather than the ST elevation implied by "STEMI". This is a
dataset limitation not documented in the benchmark literature [3, 4] and is material to any
educational use of the corpus.

---

## References

1. Educational interventions to improve electrocardiogram interpretation competence among nurses:
   A systematic review. *Nurse Education in Practice*, 2026.
   https://www.sciencedirect.com/science/article/pii/S1471595326001587
2. Impact of self-directed e-learning on nurses' competency in arrhythmia interpretation.
   *PLOS ONE*, 2025.
3. Wagner P., Strodthoff N., Bousseljot R.-D., et al. PTB-XL, a large publicly available
   electrocardiography dataset. *Scientific Data*, 7:154, 2020.
   https://physionet.org/content/ptb-xl/
4. Strodthoff N., Wagner P., Schaeffter T., Samek W. Deep learning for ECG analysis: benchmarks and
   insights from PTB-XL. *IEEE Journal of Biomedical and Health Informatics*, 25(5):1519–1528, 2021.
5. Kalyakulina A. I., Yusipov I. I., Moskalenko V. A., Nikolskiy A. V., et al. LUDB: a new
   open-access validation tool for electrocardiogram delineation algorithms. *IEEE Access*,
   8:186181–186190, 2020. https://physionet.org/content/ludb/1.0.1/
6. Laguna P., Mark R. G., Goldberger A. L., Moody G. B. A database for evaluation of algorithms for
   measurement of QT and other waveform intervals in the ECG. *Computers in Cardiology*, 1997.
   https://physionet.org/content/qtdb/
7. Pan J., Tompkins W. J. A real-time QRS detection algorithm. *IEEE Transactions on Biomedical
   Engineering*, BME-32(3):230–236, 1985.
8. Bazett H. C. An analysis of the time-relations of electrocardiograms. *Heart*, 7:353–370, 1920.
9. Fridericia L. S. Die Systolendauer im Elektrokardiogramm bei normalen Menschen und bei
   Herzkranken. *Acta Medica Scandinavica*, 53:469–486, 1920.
10. Kligfield P., Gettes L. S., Bailey J. J., et al. Recommendations for the standardization and
    interpretation of the electrocardiogram (AHA/ACC/HRS). *Circulation*, 115(10):1306–1324, 2007.
11. Shivashankara K. K., et al. ECG-Image-Kit: a synthetic image generation toolbox.
    *Physiological Measurement*, 45(5), 2024.
12. Reyna M. A., et al. Digitization and classification of ECG images: the George B. Moody
    PhysioNet Challenge 2024. *Computing in Cardiology*, 2024.
13. PTB-XL-Image-17K: a large-scale synthetic ECG image dataset with comprehensive ground truth for
    deep learning-based digitization. arXiv:2602.07446, February 2026.
    https://arxiv.org/abs/2602.07446
14. Stelling H., Kraus A., Grieb G., Breidung D., Güler I. Artificial intelligence for biomedical
    diagnostics: diagnostic accuracy and reliability of multimodal large language models in
    electrocardiogram interpretation. *Life*, 16(4):681, 2026.
    https://doi.org/10.3390/life16040681
15. Retrieval-augmented generation in healthcare: a narrative review of methods, contributions, and
    future directions. *Digital Medicine*, 12(3), 2026. doi: 10.1097/dm-2025-00015
16. Chen et al. Nurses' competency in electrocardiogram interpretation in acute care settings: a
    systematic review. *Journal of Advanced Nursing*, 2022. doi: 10.1111/jan.15147

> Full IEEE-formatted reference list, with per-entry verification status and BibTeX entries, is in
> `docs/references.md`.

---

## Citation verification status

Checked against the publisher record on 9 August 2026. **Verify the unchecked entries against the
PDFs before submission.**

| Ref | Status |
|---|---|
| [1] | **Verified** — 23 studies; MEDLINE/CINAHL/Embase/Scopus to March 2025, updated April 2026; five themes. Confirm journal name and page numbers from the PDF. |
| [3], [4], [7], [8], [9], [10] | High confidence — long-established, widely cited. Confirm page numbers. |
| [5] | **Verified** — *IEEE Access*, 8:186181–186190, 2020. |
| [6] | High confidence — the standard QTDB citation. |
| [11], [12] | **Not verified.** Confirm volume, issue and author list. |
| [13] | **Verified** — arXiv:2602.07446, 17,271 images, February 2026. |
| [14] | **Verified** — *Life*, 16(4):681, 2026, DOI 10.3390/life16040681. Accuracy 52.3–64.9%; ST/T 20.0–41.5%; QRS duration 66.2–90.8%; 2,275 task-level assessments. |
| [15] | **Verified** — *Digital Medicine*, 2026;12(3). Confirm page numbers. |
| [2] | **Not verified.** Confirm the exact title, journal and year. |

**One correction to carry forward.** The project brief states that no model exceeded a *"75.6%
majority-class baseline"* in [14]. That figure could not be located in the published abstract or
summary. Either cite it from the paper's results section directly, or omit it — the accuracy range
and the inter-run inconsistency carry the argument on their own.
