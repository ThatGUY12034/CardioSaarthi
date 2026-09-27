# review-api

The faculty review service: the gate between the measured case bank and any student.

Its whole job is to make a reviewer's judgement **durable and attributable**. Nothing reaches a
student that a named person has not approved, and nothing a reviewer corrects is ever written over
what the engine measured — the difference between those two numbers is the evidence that validates
the measurement engine.

## Running it

Three things in this order, once:

```bash
docker compose up -d
```

```bash
cd review-api && ./mvnw spring-boot:run
```

```bash
cd signal-service && python scripts/ingest_cases.py
```

The database must be up first because Flyway builds the schema when this service starts, and the
ingest needs the tables to exist. Configuration comes from `.env` at the repository root — copy
`.env.example` and fill it in. Nothing can log in until `CARDIO_BOOTSTRAP_EMAIL` and
`CARDIO_BOOTSTRAP_PASSWORD` are set, which is the intended default for an unconfigured service.

Ports on this machine: the API is on **8090** (Docker Desktop's WSL relay holds 8080) and PostgreSQL
on **55432** (a PostgreSQL install already owns 5432).

```bash
cd review-api && ./mvnw test
```

28 integration tests, run against the real database and rolled back. They skip themselves if the
database is not running, so a fresh clone reports honestly rather than failing with a connection
error.

## Endpoints

All of `/api/**` requires authentication. `/actuator/health` does not, so a container probe does not
need a password.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/me` | who the server thinks you are |
| `GET` | `/api/queue` | page of pending cases — `order`, `condition`, `status`, `limit`, `offset` |
| `GET` | `/api/queue/next` | the single next case to review |
| `GET` | `/api/cases/{id}` | full case: measurements with spread and confidence, per-lead ST, warnings |
| `GET` | `/api/cases/{id}/image/{clean\|annotated}` | the rendered ECG, as PNG |
| `POST` | `/api/cases/{id}/review` | record a decision |
| `GET` | `/api/review/options` | the valid action and rejection-reason names |
| `GET` | `/api/conditions` | how full the bank is per syllabus condition |
| `GET` | `/api/stats` | pipeline accuracy, measurement agreement, reviewer throughput |

### Queue ordering

`order=BANK_FIRST` (default) makes the case bank usable soonest: conditions furthest from their
target first, and within those the engine's most confident cases, which are the ones most likely to
be a quick confirmation rather than a careful correction.

`order=LEAST_CONFIDENT` validates the engine instead, putting the cases it is least sure of in front
of the reviewer, which is where its errors are.

Both are legitimate answers to different questions, which is why the choice is the caller's.

### Recording a decision

```json
POST /api/cases/412/review
{
  "action": "EDIT",
  "corrections": [
    {"name": "pr_interval", "value": 196.0, "note": "P onset earlier than the engine placed it"}
  ],
  "durationSeconds": 150
}
```

`APPROVE` and `EDIT` both make a case servable and are kept apart deliberately: the share of cases
that needed correcting before they were usable *is* the pipeline-accuracy figure.

`durationSeconds` is optional and worth sending. Faculty review capacity is the critical path of
this project, and this is the only way to answer "how many cases can one reviewer clear in a
sitting" with a measurement instead of a guess.

## What the server refuses, and why

A console can forget to disable a button. The server is the only place a rule actually holds.

| Status | Refused | Reason |
|---|---|---|
| 409 | reviewing a case that was already decided | two reviewers opened the same case; the first judgement stands rather than being silently overwritten |
| 422 | `REJECT` with no reason | the rejection log is reported as a pipeline-accuracy measure, and a rejection without a reason is just a missing case |
| 422 | a correction outside physiological bounds | a 4000 ms QT is a slipped decimal point; accepted, it becomes ground truth and grades students wrong |
| 422 | a correction to a measure the case does not have | |
| 422 | `APPROVE` carrying corrections | they would otherwise be silently dropped |
| 422 | `EDIT` whose values all match the engine | a zero-difference row would dilute the agreement figures with disagreements that never happened |
| 422 | the same measure corrected twice in one request | |
| 400 | a misspelled action or malformed body | the client's error, and it has to say so |

Plausibility bounds are deliberately far wider than the normal reference ranges. A PR interval
corrected to 280 ms is first-degree AV block, which is the entire point of the case. The bounds
catch slipped decimal points and unit mistakes, not abnormal findings.

## Design notes

**Spring JDBC, not JPA.** The schema's core guarantee is that a computed value is never edited in
place, and a trigger enforces it. JPA manages entity state and emits `UPDATE` on flush, so it would
fight the schema and fail at runtime. Explicit SQL also suits a design built on views, arrays and
`jsonb`.

**Flyway owns the schema.** The migrations in `src/main/resources/db/migration` are the only copy of
the DDL, and the only thing that applies it. A migration that has run is never edited; later changes
go in a new V-numbered file.

**Nulls are serialised.** In this domain an absent value is a finding: a PR interval of `null` with
status `NOT_MEASURABLE` means there is no P wave to measure from, and a console receiving no field at
all could not tell that from a missing one.

**HTTP Basic is a floor, not a finished design.** It is here from the start because retrofitting
authentication means re-touching every controller, and because a correction that is not attributable
to a named reviewer is not evidence. A frontend can move to session or token authentication without
the controllers changing. Anywhere that is not localhost, this service must be behind TLS: Basic
credentials are base64, not encrypted.
