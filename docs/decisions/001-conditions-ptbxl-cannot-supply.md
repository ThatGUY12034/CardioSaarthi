# 001 — Three conditions on the committed list cannot come from PTB-XL

**Status:** open, needs a decision from Dr. Phadnis and Terna Nursing College faculty
**Raised:** 2026-08-09, during Layer 1 case selection
**Relates to:** brief §4.2 (case selection), §10 (committed scope), §16.3 (which twenty
conditions must be in the case bank)

## What was found

Case selection was run against the full PTB-XL metadata (21,799 records, v1.0.3). Every SCP
code in the brief's condition list was checked against `scp_statements.csv` and counted in
`ptbxl_database.csv`. The full table is in
[condition_coverage.md](../validation/condition_coverage.md); this note records only what
needs a decision.

**12,695 of 21,799 records pass the quality gate**, and 714 candidates were drawn against the
syllabus targets. Rejections: not human-validated 5,551; static noise 1,605; baseline drift
1,479; paced 291; burst noise 163; electrode problems 15.

### Not obtainable at all

| Condition | Why |
|---|---|
| **Ventricular tachycardia** | There is no VT statement in PTB-XL's SCP vocabulary. The only codes matching "ventricular tachycardia" are `SVTAC` and `PSVT`, which are *supra*ventricular. PTB-XL is ten-second resting ECGs from an outpatient population; sustained VT is not in it. |
| **Hyperkalaemia** | PTB-XL has no electrolyte statements of any kind. It annotates the trace, not the serum. |
| **Hypokalaemia** | As above. |

### Obtainable but scarce

These exist, but the dataset does not hold enough clean examples to reach the planned counts.

| Condition | In dataset | Pass quality gate | Target |
|---|---:|---:|---:|
| Second-degree AV block | 14 | 8 | 14 |
| Third-degree AV block | 16 | 11 | 16 |
| Acute injury, lateral | 17 | 8 | 17 |
| Acute injury, inferior | 33 | 17 | 20 |
| Atrial flutter | 73 | 40 | 25 |
| Supraventricular tachycardia | 51 | 31 | 20 |

## Why this matters now rather than later

VT and hyperkalaemia are both conditions where recognition speed matters clinically, and both
are the kind of thing a nursing ECG syllabus is likely to treat as essential. Discovering in
week 12 that the case bank has none would be a scope failure at the worst possible moment.
The counts above are known now, before any faculty review time has been spent.

## Options

1. **Remove VT and the electrolyte disturbances from the committed scope.** Honest, costs
   nothing, and the brief's §10 already distinguishes committed from extended scope. The
   validation chapter would state the dataset's limits explicitly, which is a legitimate
   finding rather than an omission.
2. **Add a second source for these conditions only.** There are other open PhysioNet
   collections containing VT. This means a second ingest path, a second licence to check, and
   a second set of quality flags — real work, and it changes the "one dataset, inherited
   labels" story that makes the anti-hallucination argument clean.
3. **Relax the quality gate for the scarce conditions only**, accepting records flagged for
   baseline drift or static noise, and mark those cases for closer faculty review. This
   roughly doubles the pool for second- and third-degree block. It does not help VT or the
   electrolyte disturbances at all, since those records do not exist.

## Recommendation

Option 1 for VT and the electrolyte disturbances, option 3 for the scarce conductions blocks.
Teaching VT from a dataset that does not contain it is not possible, and the platform's
central claim is that its clinical facts are inherited from cardiologist annotations — the
moment a VT case is sourced any other way, that claim needs a separate defence.

## What faculty need to decide

1. Are VT and hyperkalaemia/hypokalaemia essential to the syllabus, or can the committed bank
   omit them and say so?
2. For second- and third-degree block, is 8 and 11 cases acceptable, or should the noisy
   records be included with a review flag?
3. The scarce acute-injury territories (lateral, 8 cases) are the STEMI-localisation teaching
   material. Is that enough to teach territorial localisation, or should the evolved-MI codes
   (`LMI`, 201 records) be used for that step instead?

## How to reproduce

```bash
cardiosignal select
```

Writes `artifacts/candidates.parquet` and regenerates the coverage table. Nothing in it is
typed by hand.
