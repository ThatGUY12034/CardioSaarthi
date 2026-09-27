# Project schedule

`gantt.png` / `gantt.pdf` are generated. Do not edit them by hand — edit the task
list in `signal-service/scripts/build_gantt.py` and re-run:

```bash
python signal-service/scripts/build_gantt.py
```

`START_MONDAY` and `TODAY` at the top of that file are the only two dates to change when
the schedule shifts. Everything else is derived, so the "today" line, the completed bars
and the milestone positions can never disagree with each other.

Phase names and colours are taken from the methodology diagram deliberately, so the two
slides read as one system.

## Status as of 9 August 2026 (end of week 3)

| Phase | State |
|---|---|
| 1 — ECG content preparation | Measurement engine, renderer and technical validation **delivered**. Scenario generation and faculty review still to come. |
| 2 — Student learning workflow | Not started (week 7). |
| 3 — AI-assisted learning | Not started (week 9). |
| 4 — Faculty monitoring & validation | Not started (week 11). |

Phase 1 is **four tasks of seven** complete. The engine is done; the case bank is not,
because a case bank is not finished until faculty have approved it.

## The two critical-path items

Neither is a coding task, and that is the point.

1. **Faculty review cycles (weeks 5–8).** The brief names review throughput as the
   critical path, not the code. 385 cases are measured and waiting; the constraint is
   reviewer hours. Book the sessions in advance rather than requesting them as needed.
2. **Study setup — ethics, consent, cohort scheduling (weeks 12–14).** Consent and
   timetabling with a nursing cohort cannot be compressed, and they land in the busiest
   part of the semester. Starting this in week 12 is already late; week 10 would be safer.

## Milestones

| | Week | |
|---|---|---|
| M1 | 3 | Engine validated against LUDB and QTDB — **done** |
| M2 | 4 | First faculty review session |
| M3 | 8 | 60 approved cases in the bank |
| M4 | 10 | Student runtime live end to end |
| M5 | 13 | Layers 3 and 4 complete |
| M6 | 16 | Final submission |

M3 is set at 60 rather than 200 on purpose — the brief's own guidance is to reach 60
approved cases before chasing 200.

## Editable source (Mermaid)

If the chart needs to go into a tool that renders Mermaid, this is the same schedule.
The generated PNG is the presentation copy; this is the fallback.

```mermaid
gantt
    title CardioSaarthi — 16-week project schedule
    dateFormat YYYY-MM-DD
    axisFormat %d %b

    section Phase 1 — Content preparation
    Dataset acquisition & quality screening   :done, p1a, 2026-07-20, 7d
    Measurement engine                        :done, p1b, 2026-07-20, 21d
    Standards-compliant ECG rendering         :done, p1c, 2026-07-27, 14d
    Technical validation vs LUDB & QTDB       :done, p1d, 2026-08-03, 7d
    Clinical scenario generation              :         p1e, 2026-08-10, 14d
    Faculty review interface                  :         p1f, 2026-08-10, 14d
    Faculty review cycles (CRITICAL PATH)     :crit,    p1g, 2026-08-17, 28d

    section Phase 2 — Student workflow
    Session state machine & step-lock         :         p2a, 2026-08-31, 7d
    Deterministic grading + error taxonomy    :         p2b, 2026-08-31, 14d
    Knowledge base ingestion (pgvector)       :         p2c, 2026-09-07, 7d
    Student interface — nine-step player      :         p2d, 2026-09-07, 21d
    Competency model & spaced repetition      :         p2e, 2026-09-14, 14d

    section Phase 3 — AI-assisted learning
    LLM wrapper + persona configuration       :         p3a, 2026-09-14, 7d
    RAG retrieval & citation pipeline         :         p3b, 2026-09-14, 14d
    Output validation, fallbacks, caching     :         p3c, 2026-09-21, 14d
    Persona fixture suite                     :         p3d, 2026-09-28, 7d
    Patient report explainer                  :         p3e, 2026-10-05, 14d

    section Phase 4 — Monitoring & validation
    Faculty analytics console                 :         p4a, 2026-09-28, 14d
    Technical validation report (final)       :         p4b, 2026-10-12, 7d
    Study setup — ethics & consent (CRITICAL) :crit,    p4c, 2026-10-05, 21d
    Pre-test / post-test with cohort          :         p4d, 2026-10-19, 14d
    Analysis, documentation & final report    :         p4e, 2026-10-26, 14d
```
