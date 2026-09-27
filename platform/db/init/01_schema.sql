-- CardioSaarthi — core schema
--
-- One rule shapes this file: clinical facts are computed, never generated, and
-- never overwritten. What the engine measured is kept immutably in
-- `case_measurements`; what a reviewer corrected is appended to
-- `measurement_corrections`. Nothing ever edits a computed value in place,
-- because the difference between the two IS the validation evidence for the
-- measurement engine, and an UPDATE would destroy it.
--
-- `MeasurementResult` in signal-service/src/cardiosignal/types.py is the
-- authority for names, units and enum values. Where this file repeats them it
-- is a mirror, not a second source of truth.
--
-- Applied automatically by Docker on first container start. Once the Spring
-- Boot service exists it adopts this file as a Flyway baseline rather than
-- re-running it.

BEGIN;

-- pgvector is created now, though nothing uses it until the knowledge base in
-- week 7. Enabling an extension later means a privileged migration on a
-- database that by then holds faculty corrections; doing it on an empty one
-- costs nothing.
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- People
-- ---------------------------------------------------------------------------
CREATE TABLE reviewers (
    id          bigserial PRIMARY KEY,
    email       text        NOT NULL,
    full_name   text        NOT NULL,
    role        text        NOT NULL CHECK (role IN ('faculty', 'admin')),
    active      boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Case-insensitive uniqueness without depending on the citext extension.
CREATE UNIQUE INDEX reviewers_email_key ON reviewers (lower(email));

-- ---------------------------------------------------------------------------
-- Syllabus conditions
-- ---------------------------------------------------------------------------
-- Seeded from cardiosignal.conditions by scripts/ingest_cases.py so the two
-- cannot drift. `available = false` rows are kept deliberately: ventricular
-- tachycardia and the two electrolyte disturbances are on the syllabus and
-- absent from PTB-XL, and a row saying so is how that gap stays visible
-- instead of silently vanishing from the bank.
CREATE TABLE conditions (
    code          text    PRIMARY KEY,
    label         text    NOT NULL,
    group_name    text    NOT NULL CHECK (group_name IN ('rhythm', 'conduction', 'ischaemia', 'chamber', 'electrolyte')),
    scp_codes     text[]  NOT NULL DEFAULT '{}',
    target_cases  integer NOT NULL DEFAULT 0 CHECK (target_cases >= 0),
    available     boolean NOT NULL DEFAULT true,
    note          text
);

CREATE INDEX conditions_group_idx ON conditions (group_name);

-- ---------------------------------------------------------------------------
-- Cases
-- ---------------------------------------------------------------------------
CREATE TABLE cases (
    id              bigserial PRIMARY KEY,
    source          text      NOT NULL DEFAULT 'ptbxl',
    source_ecg_id   integer   NOT NULL,

    -- Inherited from the dataset's cardiologist annotations. We never derive a
    -- diagnosis ourselves, so nothing in this block is ours to change.
    age             numeric(4, 1) CHECK (age IS NULL OR age BETWEEN 0 AND 120),
    age_censored    boolean   NOT NULL DEFAULT false,
    sex             text      CHECK (sex IS NULL OR sex IN ('male', 'female', 'unknown')),
    scp_codes       jsonb     NOT NULL DEFAULT '{}'::jsonb,
    diagnostic_labels text[]  NOT NULL DEFAULT '{}',

    -- Engine provenance. A stored result is worthless if you cannot tell which
    -- version of the engine produced it.
    schema_version  text      NOT NULL,
    engine_version  text      NOT NULL,
    computed_at     timestamptz NOT NULL,
    sampling_rate   integer   NOT NULL,
    n_samples       integer   NOT NULL,

    -- Computed summary, duplicated out of raw_measurement for querying.
    measurement_status text   NOT NULL CHECK (measurement_status IN ('OK', 'NEEDS_REVIEW', 'NOT_MEASURABLE', 'FAILED')),
    overall_confidence numeric(4, 3) NOT NULL CHECK (overall_confidence BETWEEN 0 AND 1),
    n_beats         integer   NOT NULL DEFAULT 0,
    sqi_overall     numeric(4, 3),
    rhythm_regularity text    CHECK (rhythm_regularity IS NULL OR rhythm_regularity IN
                                ('REGULAR', 'REGULARLY_IRREGULAR', 'IRREGULARLY_IRREGULAR', 'INDETERMINATE')),
    rr_mean_ms      numeric(7, 2),
    axis_degrees    numeric(6, 2),
    axis_category   text      CHECK (axis_category IS NULL OR axis_category IN
                                ('NORMAL', 'LEFT', 'RIGHT', 'EXTREME', 'INDETERMINATE')),
    warnings        text[]    NOT NULL DEFAULT '{}',

    -- The complete MeasurementResult, verbatim. Per-beat fiducials and
    -- per-lead detail live here rather than in columns nothing queries.
    raw_measurement jsonb     NOT NULL,

    -- Rendered images: clean for examination, annotated for feedback.
    image_clean_path     text,
    image_annotated_path text,

    -- Section 4.5: one batched LLM call per case, offline, reviewed before it
    -- is ever served. This is the only column in the database whose contents
    -- a model authored.
    narrative              jsonb,
    narrative_generated_at timestamptz,
    narrative_model        text,

    -- Review lifecycle. `reviews` is the append-only audit log; this column is
    -- the current state, written in the same transaction as the log entry.
    review_status   text      NOT NULL DEFAULT 'pending'
                              CHECK (review_status IN ('pending', 'approved', 'rejected')),
    reviewed_at     timestamptz,
    reviewed_by     bigint    REFERENCES reviewers (id),

    created_at      timestamptz NOT NULL DEFAULT now(),

    UNIQUE (source, source_ecg_id),

    -- An approved or rejected case must say who decided and when.
    CONSTRAINT cases_decision_complete CHECK (
        (review_status = 'pending' AND reviewed_at IS NULL AND reviewed_by IS NULL)
        OR (review_status <> 'pending' AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX cases_review_status_idx ON cases (review_status);
CREATE INDEX cases_measurement_status_idx ON cases (measurement_status);
CREATE INDEX cases_confidence_idx ON cases (overall_confidence);
CREATE INDEX cases_scp_codes_idx ON cases USING gin (scp_codes);

COMMENT ON COLUMN cases.age_censored IS
    'PTB-XL stores ages above 89 as 300 for de-identification. Such ages are clamped to 89 and flagged here.';
COMMENT ON COLUMN cases.raw_measurement IS
    'Complete MeasurementResult as produced by the engine. Never edited; corrections go to measurement_corrections.';

-- ---------------------------------------------------------------------------
-- Case <-> condition
-- ---------------------------------------------------------------------------
CREATE TABLE case_conditions (
    case_id        bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    condition_code text   NOT NULL REFERENCES conditions (code),
    PRIMARY KEY (case_id, condition_code)
);

CREATE INDEX case_conditions_condition_idx ON case_conditions (condition_code);

-- ---------------------------------------------------------------------------
-- Computed measurements — immutable
-- ---------------------------------------------------------------------------
-- Tall rather than wide: a reviewer corrects one interval at a time, grading
-- looks up one measure by name, and a new measure should not require a schema
-- change. `value` may be NULL with a status that explains why — a PR interval
-- is NOT_MEASURABLE when there is no P wave, which is a finding, not a gap.
CREATE TABLE case_measurements (
    case_id     bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    name        text   NOT NULL,
    value       numeric(9, 3),
    mad         numeric(9, 3),
    unit        text   NOT NULL,
    n_beats     integer NOT NULL DEFAULT 0,
    confidence  numeric(4, 3) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    status      text   NOT NULL CHECK (status IN ('OK', 'NEEDS_REVIEW', 'NOT_MEASURABLE', 'FAILED')),
    flag        text   NOT NULL DEFAULT 'UNKNOWN' CHECK (flag IN ('LOW', 'NORMAL', 'HIGH', 'UNKNOWN')),
    ref_low     numeric(9, 3),
    ref_high    numeric(9, 3),
    PRIMARY KEY (case_id, name)
);

-- The engine's output is evidence. Re-running the pipeline replaces a case
-- wholesale (DELETE cascades, then re-insert); it never edits a measurement in
-- place, because the corrections table is only meaningful if the value it was
-- compared against is still the value the engine actually produced.
CREATE FUNCTION forbid_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'table % is append-only: computed measurements are evidence and are never edited in place. '
        'Record a faculty change in measurement_corrections, or delete the case and re-ingest.',
        TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER case_measurements_no_update
    BEFORE UPDATE ON case_measurements
    FOR EACH ROW EXECUTE FUNCTION forbid_update();

-- ---------------------------------------------------------------------------
-- Per-lead ST deviation
-- ---------------------------------------------------------------------------
CREATE TABLE case_st_deviations (
    case_id       bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    lead          text   NOT NULL,
    deviation_mm  numeric(6, 3),
    deviation_mv  numeric(6, 4),
    baseline_mv   numeric(6, 4),
    threshold_mm  numeric(4, 2),
    finding       text   NOT NULL CHECK (finding IN ('NORMAL', 'ELEVATION', 'DEPRESSION')),
    mad_mm        numeric(6, 3),
    n_beats       integer NOT NULL DEFAULT 0,
    confidence    numeric(4, 3),
    PRIMARY KEY (case_id, lead)
);

CREATE TRIGGER case_st_deviations_no_update
    BEFORE UPDATE ON case_st_deviations
    FOR EACH ROW EXECUTE FUNCTION forbid_update();

-- ---------------------------------------------------------------------------
-- Faculty corrections — append-only
-- ---------------------------------------------------------------------------
-- `computed_value` is snapshotted here rather than read back through a join.
-- If the engine is improved and the case re-ingested, this row still records
-- what the reviewer was actually looking at when they disagreed.
CREATE TABLE measurement_corrections (
    id              bigserial PRIMARY KEY,
    case_id         bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    name            text   NOT NULL,
    computed_value  numeric(9, 3),
    corrected_value numeric(9, 3),
    unit            text   NOT NULL,
    engine_version  text   NOT NULL,
    reviewer_id     bigint NOT NULL REFERENCES reviewers (id),
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX measurement_corrections_case_idx ON measurement_corrections (case_id, name);
CREATE INDEX measurement_corrections_name_idx ON measurement_corrections (name);

-- ---------------------------------------------------------------------------
-- Review log — append-only
-- ---------------------------------------------------------------------------
-- Faculty review throughput is the critical path of this project, not the
-- code, so `duration_seconds` is recorded: it is the only way to answer "how
-- many cases can one reviewer clear in a sitting" with a measurement instead
-- of a guess.
CREATE TABLE reviews (
    id               bigserial PRIMARY KEY,
    case_id          bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    reviewer_id      bigint NOT NULL REFERENCES reviewers (id),
    action           text   NOT NULL CHECK (action IN ('approve', 'edit', 'reject')),
    rejection_reason text   CHECK (rejection_reason IS NULL OR rejection_reason IN (
                                'wrong_measurement',
                                'poor_signal_quality',
                                'wrong_diagnosis_label',
                                'unsuitable_for_teaching',
                                'narrative_inconsistent',
                                'other')),
    note             text,
    duration_seconds integer CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    created_at       timestamptz NOT NULL DEFAULT now(),

    -- A rejection without a reason is not a pipeline-accuracy measure, it is
    -- just a missing case.
    CONSTRAINT reviews_reject_has_reason CHECK (
        (action = 'reject' AND rejection_reason IS NOT NULL)
        OR (action <> 'reject' AND rejection_reason IS NULL)
    )
);

CREATE INDEX reviews_case_idx ON reviews (case_id);
CREATE INDEX reviews_reviewer_idx ON reviews (reviewer_id, created_at);

COMMIT;
