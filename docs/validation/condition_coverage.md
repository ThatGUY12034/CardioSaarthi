# PTB-XL condition coverage

Records in dataset: **21,799**  
Passing the quality gate: **12,695**  
Candidates selected: **714**

Rejections at the gate: not_human_validated 5,551, static_noise 1,605, baseline_drift 1,479, paced 291, burst_noise 163, electrodes_problems 15

| condition | group | in dataset | eligible | selected | target | shortfall |
|---|---|---:|---:|---:|---:|---:|
| Normal sinus rhythm | rhythm | 8,204 | 5,360 | 90 | 90 | 0 |
| Sinus bradycardia | rhythm | 637 | 421 | 40 | 40 | 0 |
| Sinus tachycardia | rhythm | 826 | 528 | 40 | 40 | 0 |
| Atrial fibrillation | rhythm | 1,514 | 789 | 50 | 50 | 0 |
| Atrial flutter | rhythm | 73 | 40 | 25 | 25 | 0 |
| Supraventricular tachycardia | rhythm | 42 | 31 | 20 | 20 | 0 |
| First-degree AV block | conduction | 793 | 434 | 35 | 35 | 0 |
| Second-degree AV block | conduction | 14 | 8 | 8 | 14 | **6** |
| Third-degree AV block | conduction | 16 | 11 | 11 | 16 | **5** |
| Right bundle branch block | conduction | 541 | 304 | 35 | 35 | 0 |
| Left bundle branch block | conduction | 536 | 243 | 35 | 35 | 0 |
| Subendocardial injury, anterior/anteroseptal | ischaemia | 299 | 183 | 30 | 30 | 0 |
| Subendocardial injury, inferior | ischaemia | 33 | 17 | 17 | 20 | **3** |
| Subendocardial injury, lateral | ischaemia | 17 | 8 | 8 | 17 | **9** |
| Myocardial infarction, anterior territory | ischaemia | 2,830 | 1,502 | 40 | 40 | 0 |
| Myocardial infarction, inferior territory | ischaemia | 3,238 | 1,469 | 40 | 40 | 0 |
| Myocardial infarction, lateral territory | ischaemia | 201 | 101 | 25 | 25 | 0 |
| ST depression | ischaemia | 1,009 | 917 | 35 | 35 | 0 |
| T-wave inversion | ischaemia | 294 | 271 | 30 | 30 | 0 |
| Long QT interval | ischaemia | 117 | 54 | 20 | 20 | 0 |
| Left ventricular hypertrophy | chamber | 2,132 | 1,214 | 35 | 35 | 0 |
| Right ventricular hypertrophy | chamber | 126 | 61 | 20 | 20 | 0 |
| Atrial enlargement | chamber | 509 | 300 | 25 | 25 | 0 |

## Not obtainable from PTB-XL

These are on the brief's condition list and **cannot be sourced from this dataset**. Each needs a decision: drop it from the committed scope, or find a second source.

| condition | why |
|---|---|
| Ventricular tachycardia | NOT IN PTB-XL. No VT statement exists in this vocabulary. Needs a second source or removal from the committed condition list. |
| Hyperkalaemia | NOT IN PTB-XL. No electrolyte statements exist in the SCP vocabulary. |
| Hypokalaemia | NOT IN PTB-XL. As above. |

## Short of target

Obtainable, but the dataset does not hold enough clean examples to reach the planned count. Either accept a thinner bank for these, or relax the quality gate for them specifically and mark the cases for closer review.

| condition | selected | target | note |
|---|---:|---:|---|
| Second-degree AV block | 8 | 14 | Only 14 records in the entire dataset. Take all of them. |
| Third-degree AV block | 11 | 16 | Only 16 records. Take all of them. |
| Subendocardial injury, inferior | 17 | 20 | 18 + 15 = 33 records. ST depression, not elevation. Scarce. |
| Subendocardial injury, lateral | 8 | 17 | 17 records. ST depression, not elevation. |