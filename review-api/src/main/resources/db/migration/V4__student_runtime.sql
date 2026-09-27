-- The student runtime: sessions, attempts, and what each student has mastered.
--
-- Section 5 of the brief. The shape follows one decision made there: control
-- flow is a deterministic state machine, not a model deciding what happens
-- next. So the session's state, its current step and its attempt count are
-- columns with constraints, not something inferred at runtime.
--
-- Two guarantees are enforced here rather than in application code:
--
--   * a session cannot start on a case no reviewer has approved
--   * an attempt, once recorded, is never edited
--
-- Both matter for the same reason the measurement tables are append-only: what
-- a student answered and when is the evidence the evaluation study rests on.

BEGIN;

-- ---------------------------------------------------------------------------
-- Students
-- ---------------------------------------------------------------------------
-- Separate from reviewers on purpose. A nursing student and a faculty reviewer
-- are different populations with different permissions, and one table with a
-- role column would make it possible to grant the wrong one by accident.
CREATE TABLE students (
    id            bigserial PRIMARY KEY,
    email         text        NOT NULL,
    full_name     text        NOT NULL,
    cohort        text,
    password_hash text,
    active        boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX students_email_key ON students (lower(email));
CREATE INDEX students_cohort_idx ON students (cohort);

-- ---------------------------------------------------------------------------
-- The nine steps
-- ---------------------------------------------------------------------------
-- Held as data so the orchestrator, the analytics and the mastery model all
-- read one definition of what step 5 is. The order is dependency-driven and the
-- brief flags it for faculty confirmation: rate is needed for QTc, PR requires
-- the P wave to be located first, ST is measured from the J point which is the
-- QRS offset, and QT needs QRS onset, T offset and rate.
CREATE TABLE interpretation_steps (
    step        smallint PRIMARY KEY CHECK (step BETWEEN 1 AND 9),
    concept     text     NOT NULL UNIQUE,
    label       text     NOT NULL,
    answer_kind text     NOT NULL CHECK (answer_kind IN ('NUMERIC', 'CATEGORICAL', 'MULTI_CATEGORICAL')),
    -- The measure in case_measurements this step is graded against, where the
    -- answer is a number. NULL for steps graded on a category.
    measure     text,
    -- Tolerance for numeric steps. Provisional: question 1 of the brief's open
    -- faculty list is whether these are clinically acceptable, and they are
    -- data so that answer changes a row, not the grading code.
    tolerance_abs numeric(6, 2),
    tolerance_pct numeric(5, 2),
    CONSTRAINT numeric_steps_have_a_tolerance CHECK (
        answer_kind <> 'NUMERIC' OR tolerance_abs IS NOT NULL OR tolerance_pct IS NOT NULL
    )
);

INSERT INTO interpretation_steps (step, concept, label, answer_kind, measure, tolerance_abs, tolerance_pct) VALUES
    (1, 'rate',        'Rate',        'NUMERIC',           'heart_rate',   NULL, 10.0),
    (2, 'rhythm',      'Rhythm',      'CATEGORICAL',       NULL,           NULL, NULL),
    (3, 'axis',        'Axis',        'CATEGORICAL',       NULL,           NULL, NULL),
    (4, 'p_waves',     'P waves',     'CATEGORICAL',       NULL,           NULL, NULL),
    (5, 'pr_interval', 'PR interval', 'NUMERIC',           'pr_interval',  20.0, NULL),
    (6, 'qrs',         'QRS',         'NUMERIC',           'qrs_duration', 15.0, NULL),
    (7, 'st_segment',  'ST segment',  'MULTI_CATEGORICAL', NULL,           NULL, NULL),
    (8, 't_waves',     'T waves',     'CATEGORICAL',       NULL,           NULL, NULL),
    (9, 'qt_interval', 'QT interval', 'NUMERIC',           'qt_interval',  40.0, NULL);

COMMENT ON COLUMN interpretation_steps.tolerance_pct IS
    'Provisional pending faculty ruling (brief section 16, question 1). Held as data so that '
    'ruling changes a row rather than the grading code.';

-- ---------------------------------------------------------------------------
-- Error taxonomy
-- ---------------------------------------------------------------------------
-- A closed list, because an error label is three things at once: what drives
-- the feedback, part of the explanation cache key, and the unit of faculty
-- analytics. Free text would make the third impossible and the second useless.
CREATE TABLE error_labels (
    code        text     PRIMARY KEY,
    step        smallint REFERENCES interpretation_steps (step),
    description text     NOT NULL
);

INSERT INTO error_labels (code, step, description) VALUES
    -- rate
    ('RATE_OVERESTIMATED',            1, 'Counted a faster rate than the recording shows'),
    ('RATE_UNDERESTIMATED',           1, 'Counted a slower rate than the recording shows'),
    ('RATE_METHOD_ERROR',             1, 'Rate consistent with counting large squares on an irregular rhythm'),
    -- rhythm
    ('REGULAR_CALLED_IRREGULAR',      2, 'Called a regular rhythm irregular'),
    ('IRREGULAR_CALLED_REGULAR',      2, 'Called an irregular rhythm regular'),
    ('IRREGULARITY_PATTERN_CONFUSED', 2, 'Confused regularly irregular with irregularly irregular'),
    -- axis
    ('AXIS_WRONG_QUADRANT',           3, 'Axis placed in the wrong quadrant'),
    ('AXIS_DEVIATION_MISSED',         3, 'Called a deviated axis normal'),
    ('AXIS_NORMAL_CALLED_DEVIATED',   3, 'Called a normal axis deviated'),
    -- P waves
    ('P_ABSENT_CALLED_PRESENT',       4, 'Reported P waves where none are present'),
    ('P_PRESENT_CALLED_ABSENT',       4, 'Missed P waves that are present'),
    ('P_MORPHOLOGY_MISREAD',          4, 'P waves located but their morphology misread'),
    -- PR interval
    ('PR_OVERESTIMATED',              5, 'PR interval measured longer than it is'),
    ('PR_UNDERESTIMATED',             5, 'PR interval measured shorter than it is'),
    ('PR_WRONG_LANDMARK',             5, 'PR measured from the P peak rather than the P onset'),
    ('PR_REPORTED_WHEN_ABSENT',       5, 'Reported a PR interval on a rhythm that has no P waves'),
    -- QRS
    ('QRS_OVERESTIMATED',             6, 'QRS duration measured wider than it is'),
    ('QRS_UNDERESTIMATED',            6, 'QRS duration measured narrower than it is'),
    ('QRS_NARROW_CALLED_WIDE',        6, 'Narrow QRS classified as wide'),
    ('QRS_WIDE_CALLED_NARROW',        6, 'Wide QRS classified as narrow'),
    -- ST segment
    ('ST_ELEVATION_MISSED',           7, 'ST elevation present but not reported'),
    ('ST_DEPRESSION_MISSED',          7, 'ST depression present but not reported'),
    ('ST_NORMAL_CALLED_ABNORMAL',     7, 'Reported ST deviation where the segment is isoelectric'),
    ('ST_WRONG_TERRITORY',            7, 'ST change identified but attributed to the wrong leads'),
    -- T waves
    ('T_INVERSION_MISSED',            8, 'T wave inversion present but not reported'),
    ('T_NORMAL_CALLED_INVERTED',      8, 'Reported T inversion where the T waves are upright'),
    -- QT
    ('QT_OVERESTIMATED',              9, 'QT measured longer than it is'),
    ('QT_UNDERESTIMATED',             9, 'QT measured shorter than it is'),
    ('QT_NOT_RATE_CORRECTED',         9, 'Raw QT given where a rate-corrected value was asked for'),
    -- not step specific
    ('NO_ANSWER',                  NULL, 'No answer submitted'),
    ('ANSWER_NOT_UNDERSTOOD',      NULL, 'Answer could not be interpreted as a response to this step');

-- ---------------------------------------------------------------------------
-- Sessions
-- ---------------------------------------------------------------------------
CREATE TABLE sessions (
    id                 bigserial PRIMARY KEY,
    student_id         bigint   NOT NULL REFERENCES students (id),
    case_id            bigint   NOT NULL REFERENCES cases (id),

    mode               text     NOT NULL CHECK (mode IN ('BEGINNER_TUTOR', 'CLINICAL_MENTOR', 'EXAMINER')),
    -- The states from section 5.1. EVALUATING exists inside one request and is
    -- not expected to be seen at rest; ABANDONED is for a session never finished.
    state              text     NOT NULL DEFAULT 'CASE_LOADED'
                                CHECK (state IN ('CASE_LOADED', 'AWAITING_STEP', 'EVALUATING',
                                                 'FEEDBACK_SENT', 'AWAITING_FINAL', 'CASE_COMPLETE',
                                                 'ABANDONED')),
    current_step       smallint NOT NULL DEFAULT 1 CHECK (current_step BETWEEN 1 AND 9),
    attempts_this_step smallint NOT NULL DEFAULT 0 CHECK (attempts_this_step >= 0),

    -- Stamped at start so a session is interpretable after the persona changes.
    persona_version    text     NOT NULL,

    final_interpretation text,
    started_at         timestamptz NOT NULL DEFAULT now(),
    last_activity_at   timestamptz NOT NULL DEFAULT now(),
    completed_at       timestamptz,

    CONSTRAINT completed_sessions_have_a_time CHECK (
        (state = 'CASE_COMPLETE') = (completed_at IS NOT NULL)
    )
);

CREATE INDEX sessions_student_idx ON sessions (student_id, started_at DESC);
CREATE INDEX sessions_case_idx ON sessions (case_id);
CREATE INDEX sessions_open_idx ON sessions (student_id) WHERE state <> 'CASE_COMPLETE';

-- A student may only ever be examined on a case a named reviewer approved.
-- This is the same rule v_served_measurements enforces on the measurements, and
-- it is here too because the check that matters is the one that cannot be
-- forgotten: an unapproved case reaching a student is the failure this whole
-- project is arranged to prevent.
CREATE FUNCTION session_case_must_be_approved() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    status text;
BEGIN
    SELECT review_status INTO status FROM cases WHERE id = NEW.case_id;
    IF status IS DISTINCT FROM 'approved' THEN
        RAISE EXCEPTION
            'case % is %, not approved. A case reaches a student only after a reviewer approves it.',
            NEW.case_id, coalesce(status, 'missing');
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER sessions_case_must_be_approved
    BEFORE INSERT ON sessions
    FOR EACH ROW EXECUTE FUNCTION session_case_must_be_approved();

-- ---------------------------------------------------------------------------
-- Attempts
-- ---------------------------------------------------------------------------
-- Append-only. What a student answered, when, and what the platform told them
-- is the evidence the evaluation study rests on, and an edited attempt is not
-- evidence.
CREATE TABLE session_steps (
    id             bigserial PRIMARY KEY,
    session_id     bigint   NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    step           smallint NOT NULL REFERENCES interpretation_steps (step),
    attempt        smallint NOT NULL CHECK (attempt >= 1),

    answer         jsonb    NOT NULL,
    correct        boolean  NOT NULL,
    -- What the platform graded against, snapshotted. The served value can
    -- change if a reviewer corrects the case later; what the student was marked
    -- against must not change with it.
    expected       jsonb,
    error_label    text     REFERENCES error_labels (code),

    feedback_type  text     CHECK (feedback_type IS NULL OR feedback_type IN
                            ('CONFIRMATION', 'HINT', 'EXPLANATION', 'DEFERRED')),
    -- Where the words came from. TEMPLATE and CACHE cost nothing, MODEL costs a
    -- call, FALLBACK means the call failed or its output was rejected. The
    -- proportions are the cost model, measured rather than assumed.
    feedback_source text   CHECK (feedback_source IS NULL OR feedback_source IN
                            ('TEMPLATE', 'CACHE', 'MODEL', 'FALLBACK')),
    feedback_text  text,

    time_taken_ms  integer  CHECK (time_taken_ms IS NULL OR time_taken_ms >= 0),
    hint_used      boolean  NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),

    UNIQUE (session_id, step, attempt),
    CONSTRAINT correct_answers_have_no_error_label CHECK (correct = (error_label IS NULL))
);

CREATE INDEX session_steps_session_idx ON session_steps (session_id, step, attempt);
CREATE INDEX session_steps_error_idx ON session_steps (error_label) WHERE error_label IS NOT NULL;

CREATE TRIGGER session_steps_no_update
    BEFORE UPDATE ON session_steps
    FOR EACH ROW EXECUTE FUNCTION forbid_update();

-- ---------------------------------------------------------------------------
-- Mastery
-- ---------------------------------------------------------------------------
-- Section 5.5: scheduling is deterministic, weak concepts first, SM-2 style
-- spaced repetition ordered by the syllabus. This is code and a table, not an
-- agent, and this is the table.
CREATE TABLE student_mastery (
    student_id    bigint   NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    concept       text     NOT NULL REFERENCES interpretation_steps (concept),

    attempts      integer  NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    correct       integer  NOT NULL DEFAULT 0 CHECK (correct >= 0),
    first_attempt_correct integer NOT NULL DEFAULT 0,

    -- SM-2. `ease` starts at 2.5 by convention and is floored at 1.3.
    ease          numeric(4, 2) NOT NULL DEFAULT 2.50 CHECK (ease >= 1.30),
    interval_days integer  NOT NULL DEFAULT 0 CHECK (interval_days >= 0),
    repetitions   integer  NOT NULL DEFAULT 0 CHECK (repetitions >= 0),
    due_on        date,

    updated_at    timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (student_id, concept),
    CONSTRAINT correct_cannot_exceed_attempts CHECK (correct <= attempts)
);

CREATE INDEX student_mastery_due_idx ON student_mastery (student_id, due_on);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------
-- Cases a session may legally be started on: approved, and carrying the
-- measurements the nine steps are graded against.
CREATE VIEW v_servable_cases AS
SELECT
    c.id AS case_id,
    c.source_ecg_id,
    c.age,
    c.sex,
    c.diagnostic_labels,
    c.image_clean_path IS NOT NULL AS has_clean_image,
    c.narrative IS NOT NULL        AS has_narrative,
    array_remove(array_agg(DISTINCT cc.condition_code), NULL) AS condition_codes,
    count(DISTINCT sm.name)        AS served_measures
FROM cases c
LEFT JOIN case_conditions cc      ON cc.case_id = c.id
LEFT JOIN v_served_measurements sm ON sm.case_id = c.id
WHERE c.review_status = 'approved'
GROUP BY c.id;

COMMENT ON VIEW v_servable_cases IS
    'Approved cases only. A case absent from this view cannot be started as a session, and the '
    'trigger on sessions enforces that independently.';

-- Per-step difficulty across a cohort: which step students most reliably get
-- wrong is question 4 on the brief's list for nursing faculty, and this is
-- where the answer comes from once students have used the platform.
CREATE VIEW v_step_difficulty AS
SELECT
    s.step,
    s.concept,
    s.label,
    count(ss.id)                                                   AS attempts,
    count(ss.id) FILTER (WHERE ss.correct)                         AS correct,
    count(*) FILTER (WHERE ss.correct AND ss.attempt = 1)          AS correct_first_time,
    round(100.0 * count(ss.id) FILTER (WHERE ss.correct) / nullif(count(ss.id), 0), 1)
                                                                   AS accuracy_pct,
    round(avg(ss.time_taken_ms)::numeric / 1000, 1)                AS mean_seconds
FROM interpretation_steps s
LEFT JOIN session_steps ss ON ss.step = s.step
GROUP BY s.step, s.concept, s.label;

CREATE VIEW v_error_frequency AS
SELECT
    e.code,
    e.step,
    e.description,
    count(ss.id) AS occurrences,
    count(DISTINCT ss.session_id) AS sessions_affected
FROM error_labels e
LEFT JOIN session_steps ss ON ss.error_label = e.code
GROUP BY e.code, e.step, e.description;

COMMIT;
