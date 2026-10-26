-- The adaptive layer, and the numbers a student's own pages have been inventing.
--
-- student_mastery has existed since V4 with every column SM-2 needs, and until
-- now nothing has ever written a row to it. Practice was a flat list ordered by
-- case id, so a student who could not read an axis met axis questions exactly
-- as often as one who always got them right. This migration adds the views the
-- scheduler and the student pages read; the arithmetic itself lives in
-- MasteryService, because a scheduling rule belongs somewhere it can be tested.
--
-- It also ends a smaller dishonesty. The student dashboard, progress page and
-- leaderboard displayed a completion count, a streak and an average score that
-- were written into the interface as constants. Every one of those numbers is
-- derivable from session_steps, which has been recording the real thing all
-- along.

BEGIN;

-- ---------------------------------------------------------------------------
-- Per-concept strength
-- ---------------------------------------------------------------------------
-- One row per student per concept they have attempted, built from the attempt
-- record rather than from student_mastery, so it is correct even for a student
-- whose scheduling state has never been written. student_mastery carries the
-- scheduling; this carries the evidence.
--
-- first_attempt_accuracy is the honest measure of what a student knows. Overall
-- accuracy counts the retry after a hint, which measures whether they can take
-- a hint rather than whether they knew the answer.
CREATE VIEW v_student_concept_strength AS
SELECT
    se.student_id,
    s.step,
    s.concept,
    s.label,
    count(ss.id)                                            AS attempts,
    count(ss.id) FILTER (WHERE ss.correct)                   AS correct,
    count(ss.id) FILTER (WHERE ss.attempt = 1)               AS first_attempts,
    count(ss.id) FILTER (WHERE ss.correct AND ss.attempt = 1) AS first_attempt_correct,
    round(100.0 * count(ss.id) FILTER (WHERE ss.correct AND ss.attempt = 1)
          / nullif(count(ss.id) FILTER (WHERE ss.attempt = 1), 0), 1)
                                                            AS first_attempt_accuracy_pct,
    max(ss.created_at)                                      AS last_practised_at
FROM session_steps ss
JOIN sessions se            ON se.id = ss.session_id
JOIN interpretation_steps s ON s.step = ss.step
GROUP BY se.student_id, s.step, s.concept, s.label;

COMMENT ON VIEW v_student_concept_strength IS
    'What a student actually knows, per concept, from the append-only attempt record. '
    'first_attempt_accuracy_pct is the measure that matters: overall accuracy counts the '
    'retry after a hint, which measures whether they can take a hint.';

-- ---------------------------------------------------------------------------
-- The practice queue
-- ---------------------------------------------------------------------------
-- Weakest first, then overdue, then unseen, then everything else in syllabus
-- order. A concept never practised sorts before a strong one but after a weak
-- one: there is no evidence either way, and a known weakness outranks an
-- unknown.
CREATE VIEW v_student_next_concepts AS
SELECT
    st.id                                   AS student_id,
    s.step,
    s.concept,
    s.label,
    m.due_on,
    m.interval_days,
    m.repetitions,
    m.ease,
    cs.first_attempt_accuracy_pct,
    cs.attempts,
    (cs.attempts IS NULL)                   AS never_practised,
    (m.due_on IS NOT NULL AND m.due_on <= current_date) AS due,
    CASE
        WHEN cs.first_attempt_accuracy_pct IS NOT NULL
             AND cs.first_attempt_accuracy_pct < 60 THEN 0   -- weak, practise now
        WHEN m.due_on IS NOT NULL AND m.due_on <= current_date THEN 1  -- scheduled
        WHEN cs.attempts IS NULL THEN 2                       -- never seen
        ELSE 3                                                -- known, not due
    END                                     AS priority
FROM students st
CROSS JOIN interpretation_steps s
LEFT JOIN student_mastery m          ON m.student_id = st.id AND m.concept = s.concept
LEFT JOIN v_student_concept_strength cs
                                     ON cs.student_id = st.id AND cs.concept = s.concept
WHERE st.active;

COMMENT ON VIEW v_student_next_concepts IS
    'The scheduling order: weak concepts first, then concepts that have come due, then '
    'ones never practised, then the rest in syllabus order. Ordering by priority, then '
    'first_attempt_accuracy_pct NULLS LAST, then step gives the queue.';

-- ---------------------------------------------------------------------------
-- Per-session score
-- ---------------------------------------------------------------------------
-- Scored over steps that were marked, never over nine. A case where three steps
-- could not be graded is scored out of six, because marking a student against a
-- value the platform does not have is the failure this whole system is arranged
-- to prevent, and quietly counting it as a miss is the same mistake wearing a
-- different hat.
CREATE VIEW v_session_scores AS
SELECT
    se.id                                       AS session_id,
    se.student_id,
    se.case_id,
    se.mode,
    se.state,
    se.started_at,
    se.completed_at,
    count(DISTINCT ss.step)                     AS steps_marked,
    count(DISTINCT ss.step) FILTER (WHERE ss.correct AND ss.attempt = 1)
                                                AS steps_correct_first_time,
    round(100.0 * count(DISTINCT ss.step) FILTER (WHERE ss.correct AND ss.attempt = 1)
          / nullif(count(DISTINCT ss.step), 0), 0)
                                                AS score_pct
FROM sessions se
LEFT JOIN session_steps ss ON ss.session_id = se.id
GROUP BY se.id;

COMMENT ON VIEW v_session_scores IS
    'Scored over the steps that were actually marked, not out of nine. A step the platform '
    'declined to mark is excluded from both numerator and denominator.';

-- ---------------------------------------------------------------------------
-- The dashboard
-- ---------------------------------------------------------------------------
-- The streak counts consecutive calendar days ending today or yesterday on
-- which the student finished at least one case. Ending yesterday still counts:
-- a streak should not be destroyed by the clock passing midnight before the
-- student has sat down.
CREATE VIEW v_student_progress AS
WITH days AS (
    SELECT DISTINCT student_id, (completed_at AT TIME ZONE 'UTC')::date AS day
    FROM sessions
    WHERE state = 'CASE_COMPLETE' AND completed_at IS NOT NULL
),
streaks AS (
    SELECT student_id, day,
           day - (row_number() OVER (PARTITION BY student_id ORDER BY day))::int AS grp
    FROM days
),
runs AS (
    SELECT student_id, max(day) AS last_day, count(*) AS length
    FROM streaks GROUP BY student_id, grp
)
SELECT
    st.id                                             AS student_id,
    count(sc.session_id) FILTER (WHERE sc.state = 'CASE_COMPLETE') AS cases_completed,
    -- Genuinely open, not merely unfinished. ABANDONED is a closed state, and
    -- counting it here would tell a student they have ten cases on the go when
    -- the platform closed nine of them behind their back.
    count(sc.session_id) FILTER (WHERE sc.state NOT IN ('CASE_COMPLETE', 'ABANDONED'))
                                                      AS cases_in_progress,
    round(avg(sc.score_pct) FILTER (WHERE sc.state = 'CASE_COMPLETE'), 0) AS average_score_pct,
    max(sc.score_pct) FILTER (WHERE sc.state = 'CASE_COMPLETE')     AS best_score_pct,
    coalesce((SELECT r.length FROM runs r
              WHERE r.student_id = st.id
                AND r.last_day >= current_date - 1
              ORDER BY r.last_day DESC LIMIT 1), 0)   AS current_streak_days,
    (SELECT count(*) FROM v_servable_cases)           AS cases_available
FROM students st
LEFT JOIN v_session_scores sc ON sc.student_id = st.id
GROUP BY st.id;

COMMENT ON VIEW v_student_progress IS
    'The figures the student dashboard shows. Every one is derived from the attempt record; '
    'none is a constant in the interface.';

COMMIT;
