-- Closing the loop between a student's mistake and their teacher.
--
-- Everything needed for this has been recorded since the runtime was built:
-- every attempt, which step it was on, whether it was right first time, and
-- which of the thirty-two named errors it was. None of it has ever been shown
-- to the person teaching the student. The faculty view of a student was sample
-- data, and there was no way for a teacher to say anything back.
--
-- Three things here. A remark a teacher can leave on the exact attempt that
-- went wrong. The cohort views that turn per-attempt records into something a
-- teacher can act on in a class. And a learning-gain measure, which is the only
-- figure in this platform that tries to say whether the teaching worked.

BEGIN;

-- ---------------------------------------------------------------------------
-- Remarks
-- ---------------------------------------------------------------------------
-- Anchored to one attempt, not to a student. "You keep getting the axis wrong"
-- is advice a student cannot act on; a remark on the attempt where they called
-- a left axis normal is advice about something they can still see.
CREATE TABLE faculty_remarks (
    id              bigserial PRIMARY KEY,
    session_step_id bigint NOT NULL REFERENCES session_steps (id) ON DELETE CASCADE,
    reviewer_id     bigint NOT NULL REFERENCES reviewers (id),
    -- Denormalised so a student's remarks can be found without walking back
    -- through sessions, and so the row still says who it was for if the
    -- session is ever removed.
    student_id      bigint NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    body            text   NOT NULL CHECK (length(btrim(body)) BETWEEN 2 AND 2000),
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- When the student opened it. Null means unread, and the student's pages
    -- surface those first.
    read_at         timestamptz
);

CREATE INDEX faculty_remarks_student_idx ON faculty_remarks (student_id, created_at DESC);
CREATE INDEX faculty_remarks_step_idx    ON faculty_remarks (session_step_id);
CREATE INDEX faculty_remarks_unread_idx  ON faculty_remarks (student_id)
    WHERE read_at IS NULL;

-- A remark is a thing a named person said to a named student on a named date.
-- Editing it afterwards would make the record of that conversation a record of
-- whatever it was last changed to. Marking it read is the one permitted change.
CREATE OR REPLACE FUNCTION forbid_remark_edit() RETURNS trigger AS $$
BEGIN
    IF NEW.body IS DISTINCT FROM OLD.body
       OR NEW.reviewer_id IS DISTINCT FROM OLD.reviewer_id
       OR NEW.session_step_id IS DISTINCT FROM OLD.session_step_id THEN
        RAISE EXCEPTION
            'a remark is a record of what was said: it cannot be edited, only marked read';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER faculty_remarks_are_a_record
    BEFORE UPDATE ON faculty_remarks
    FOR EACH ROW EXECUTE FUNCTION forbid_remark_edit();

-- ---------------------------------------------------------------------------
-- What a student actually got wrong
-- ---------------------------------------------------------------------------
-- One row per mistake, with enough context for a teacher to see what happened
-- without opening the case: the step, the error, what they said, what the
-- recording showed, and whether a remark has already been left.
CREATE VIEW v_student_mistakes AS
SELECT
    ss.id                         AS session_step_id,
    se.student_id,
    se.id                         AS session_id,
    se.case_id,
    c.source_ecg_id,
    ss.step,
    s.label                       AS step_label,
    s.concept,
    ss.attempt,
    ss.answer,
    ss.expected,
    ss.error_label,
    e.description                 AS error_description,
    ss.time_taken_ms,
    ss.created_at,
    (SELECT count(*) FROM faculty_remarks r WHERE r.session_step_id = ss.id) AS remark_count
FROM session_steps ss
JOIN sessions se              ON se.id = ss.session_id
JOIN cases c                  ON c.id = se.case_id
JOIN interpretation_steps s   ON s.step = ss.step
LEFT JOIN error_labels e      ON e.code = ss.error_label
WHERE NOT ss.correct;

COMMENT ON VIEW v_student_mistakes IS
    'Every wrong answer, with the named error and what the recording showed. This is what a '
    'teacher needs to see; it has been recorded since the runtime was built and shown to '
    'nobody.';

-- ---------------------------------------------------------------------------
-- The class
-- ---------------------------------------------------------------------------
-- Per student, for the faculty list. Deliberately the same arithmetic the
-- student sees on their own pages, so a teacher and a student are never
-- looking at two different numbers for the same thing.
CREATE VIEW v_cohort_students AS
SELECT
    st.id                                   AS student_id,
    st.full_name,
    st.college_id,
    st.cohort,
    st.active,
    coalesce(p.cases_completed, 0)          AS cases_completed,
    coalesce(p.cases_in_progress, 0)        AS cases_in_progress,
    p.average_score_pct,
    p.best_score_pct,
    coalesce(p.current_streak_days, 0)      AS current_streak_days,
    (SELECT count(*) FROM v_student_mistakes m WHERE m.student_id = st.id) AS mistakes,
    (SELECT count(*) FROM faculty_remarks r WHERE r.student_id = st.id)    AS remarks,
    (SELECT max(ss.created_at)
       FROM session_steps ss JOIN sessions se2 ON se2.id = ss.session_id
      WHERE se2.student_id = st.id)         AS last_active_at,
    -- The concept they are weakest at, which is the single most useful thing
    -- for a teacher deciding what to say.
    (SELECT cs.label
       FROM v_student_concept_strength cs
      WHERE cs.student_id = st.id AND cs.first_attempts >= 2
      ORDER BY cs.first_attempt_accuracy_pct NULLS LAST, cs.step
      LIMIT 1)                              AS weakest_concept
FROM students st
LEFT JOIN v_student_progress p ON p.student_id = st.id;

-- Class-wide difficulty, which answers "what should I teach next lesson".
CREATE VIEW v_cohort_step_difficulty AS
SELECT
    s.step,
    s.concept,
    s.label,
    count(DISTINCT se.student_id)                                AS students_attempted,
    count(ss.id)                                                 AS attempts,
    count(ss.id) FILTER (WHERE ss.correct AND ss.attempt = 1)    AS correct_first_time,
    round(100.0 * count(ss.id) FILTER (WHERE ss.correct AND ss.attempt = 1)
          / nullif(count(ss.id) FILTER (WHERE ss.attempt = 1), 0), 1)
                                                                 AS first_attempt_accuracy_pct,
    round(avg(ss.time_taken_ms)::numeric / 1000, 1)              AS mean_seconds
FROM interpretation_steps s
LEFT JOIN session_steps ss ON ss.step = s.step
LEFT JOIN sessions se      ON se.id = ss.session_id
GROUP BY s.step, s.concept, s.label;

-- The mistakes a class makes most, which is what the error taxonomy was built
-- to be able to answer.
CREATE VIEW v_cohort_errors AS
SELECT
    e.code,
    e.step,
    s.label                           AS step_label,
    e.description,
    count(ss.id)                      AS occurrences,
    count(DISTINCT se.student_id)     AS students_affected
FROM error_labels e
JOIN interpretation_steps s ON s.step = e.step
LEFT JOIN session_steps ss  ON ss.error_label = e.code
LEFT JOIN sessions se       ON se.id = ss.session_id
GROUP BY e.code, e.step, s.label, e.description;

-- ---------------------------------------------------------------------------
-- Learning gain
-- ---------------------------------------------------------------------------
-- The only figure here that tries to say whether the teaching worked: a
-- student's first-attempt accuracy in their earlier sessions against their
-- later ones.
--
-- First attempts only, because a retry after a hint measures whether a student
-- can take a hint. Sessions are split by order rather than by date so a student
-- who did six cases in one evening still has an early and a late half. Below
-- four completed sessions it returns null rather than a number: the difference
-- between two and two cases is noise, and a precise-looking figure computed
-- from it would be worse than no figure.
CREATE VIEW v_student_learning_gain AS
WITH ordered AS (
    SELECT se.student_id, se.id AS session_id,
           row_number() OVER (PARTITION BY se.student_id ORDER BY se.started_at) AS seq,
           count(*)    OVER (PARTITION BY se.student_id)                         AS total
    FROM sessions se
    WHERE se.state = 'CASE_COMPLETE'
),
halves AS (
    SELECT o.student_id,
           CASE WHEN o.seq <= o.total / 2 THEN 'early' ELSE 'late' END AS half,
           ss.correct, ss.attempt
    FROM ordered o
    JOIN session_steps ss ON ss.session_id = o.session_id
    WHERE o.total >= 4
)
SELECT
    student_id,
    round(100.0 * count(*) FILTER (WHERE half = 'early' AND correct AND attempt = 1)
          / nullif(count(*) FILTER (WHERE half = 'early' AND attempt = 1), 0), 1)
                                                        AS early_accuracy_pct,
    round(100.0 * count(*) FILTER (WHERE half = 'late' AND correct AND attempt = 1)
          / nullif(count(*) FILTER (WHERE half = 'late' AND attempt = 1), 0), 1)
                                                        AS late_accuracy_pct,
    round(
        100.0 * count(*) FILTER (WHERE half = 'late' AND correct AND attempt = 1)
        / nullif(count(*) FILTER (WHERE half = 'late' AND attempt = 1), 0)
      - 100.0 * count(*) FILTER (WHERE half = 'early' AND correct AND attempt = 1)
        / nullif(count(*) FILTER (WHERE half = 'early' AND attempt = 1), 0), 1)
                                                        AS gain_pct
FROM halves
GROUP BY student_id;

COMMENT ON VIEW v_student_learning_gain IS
    'First-attempt accuracy early against late, for students with at least four completed '
    'sessions. Below that it returns nothing: a precise-looking number computed from two '
    'cases is worse than no number.';

COMMIT;
