# 002 — PTB-XL may not contain acute STEMI patterns at all

**Status:** open, needs a decision from Dr. Phadnis and Terna Nursing College faculty
**Raised:** 2026-08-09, while preparing demo cases for the faculty review session
**Relates to:** brief §4.2 ("STEMI by territory — anterior / inferior / lateral"), §10 committed scope

## What was found

The brief commits to teaching **STEMI by territory**. Mapping that onto PTB-XL, the obvious
candidates are the `INJ*` statements — and they are the wrong thing.

| SCP code | PTB-XL description | What it actually is |
|---|---|---|
| `INJAS`, `INJAL` | subendocardial injury in anteroseptal / anterolateral leads | **ST depression** |
| `INJIN`, `INJIL` | subendocardial injury in inferior / inferolateral leads | **ST depression** |
| `INJLA` | subendocardial injury in lateral leads | **ST depression** |

Subendocardial injury is a **non-ST-elevation** pattern. These are not STEMI cases.

The remaining infarct codes — `AMI`, `ASMI`, `ALMI`, `IMI`, `ILMI`, `LMI` and so on — describe an
**evolved** infarct pattern (pathological Q waves, T inversion), not the acute ST elevation a
nurse is being trained to recognise and escalate.

This was caught by the measurement engine itself. Record 6751 carries `INJIL` and had been
labelled "Acute injury, inferior" in our condition map; the engine measured **anterior ST
depression in V2, V3 and V4** and grouped it correctly by territory. The measurement was right
and the label was wrong.

## Why this matters more than it looks

Acute STEMI recognition is the single most time-critical thing on a nursing ECG syllabus. A case
bank that silently substitutes evolved infarcts and subendocardial depression for acute ST
elevation would teach the wrong visual pattern for the highest-stakes finding on the list.

It also interacts with decision [001](001-conditions-ptbxl-cannot-supply.md): ventricular
tachycardia and the electrolyte disturbances are absent outright, and acute STEMI now looks
under-represented as well. Together these are a scope question, not a detail.

## The cross-tabulation, now done

The engine's per-lead ST measurements were cross-tabulated against the SCP codes for all 714
candidate cases, applying the standard voltage rule (≥1 mm elevation in two contiguous leads,
≥2 mm in V2–V3).

**204 of 714 cases meet the voltage criterion** — 171 anterior, 49 inferior, 33 lateral. That
looks like plenty until you look at what those cases actually are:

| SCP code on the "elevation" cases | count |
|---|---:|
| `CLBBB` — complete left bundle branch block | 47 |
| `LVH` — left ventricular hypertrophy | 37 |
| `AFIB` | 29 |
| `IMI` — inferior MI | 26 |
| **`NORM` — normal ECG** | **25** |

The criterion is firing overwhelmingly on **secondary** repolarisation change, not on infarction:
discordant ST elevation is expected in LBBB, LVH produces its own repolarisation abnormality, and
25 of the flagged records are labelled *normal* — benign early repolarisation.

**This does not mean the ST measurement is wrong.** It means ST elevation as a *voltage criterion*
is not specific on its own, which is precisely why the standard criteria carry exclusions for LBBB
and LVH. It is also a clean demonstration of the platform's founding principle: the engine
measures the millimetres and stops. It never converts them into "STEMI".

The practical conclusion: **the voltage criterion alone cannot be used to mine acute STEMI cases
out of PTB-XL.** Any such case set would need faculty to confirm each one, and the yield after
excluding LBBB, LVH and normal variants is likely small.

## Options

1. **Retitle honestly and teach what the data holds** — subendocardial injury (ST depression) and
   evolved infarct patterns. Drop "STEMI by territory" from the committed list. Costs nothing,
   loses the most clinically urgent teaching target.
2. **Cross-tabulate first**, then decide. Use the engine's per-lead ST measurements to find
   records that genuinely show ≥1 mm elevation in two contiguous leads, whatever their SCP code,
   and have faculty confirm a sample. This is the option the measurement engine makes possible
   and is recommended.
3. **Second source for STEMI only.** Same cost and same caveat as in decision 001: it breaks the
   "one dataset, inherited labels" story the anti-hallucination argument rests on.

## Questions for faculty

1. Is acute STEMI recognition essential to the committed scope, or can Phase 2 teach
   ST depression and evolved infarct patterns and say so explicitly?
2. If it is essential — is a case with ≥1 mm elevation in two contiguous leads, confirmed by you,
   acceptable as a teaching case even where the dataset's own label says only "myocardial
   infarction"?
