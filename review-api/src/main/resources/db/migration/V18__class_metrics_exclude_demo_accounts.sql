-- Keep the demonstration accounts out of the class figures.
--
-- "Hardest steps for this class" and "most common mistakes" aggregate every
-- answer in session_steps with no filter on who gave it. That was harmless
-- while the only answers belonged to enrolled students, and stops being
-- harmless the moment somebody signs in as the demonstration student and works
-- a case: their answers land in the class averages, and a teacher reading the
-- dashboard is told something about their class that a stranger did.
--
-- Marking the account rather than inferring it. The obvious filter -- require a
-- cohort -- would have been wrong: cohort is optional on the enrolment form, so
-- it would silently drop real students out of their own class metrics, which is
-- a worse failure than the one being fixed because nobody would notice it.

BEGIN;

ALTER TABLE students ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN students.is_demo IS
    'A four-digit demonstration login rather than an enrolled student. Their '
    'work is still recorded and still visible to them; it is kept out of '
    'class-wide figures so a demonstration cannot move a real cohort average.';

-- The two that exist: the seeded one and the one DemoAccounts maintains.
UPDATE students
   SET is_demo = true
 WHERE lower(email) IN ('demo.student@terna.edu', 'student@terna.edu');

-- ---------------------------------------------------------------------------
-- The three views that aggregate across students
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_cohort_students;
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
    (SELECT cs.label
       FROM v_student_concept_strength cs
      WHERE cs.student_id = st.id AND cs.first_attempts >= 2
      ORDER BY cs.first_attempt_accuracy_pct NULLS LAST, cs.step
      LIMIT 1)                              AS weakest_concept
FROM students st
LEFT JOIN v_student_progress p ON p.student_id = st.id
WHERE NOT st.is_demo;

DROP VIEW IF EXISTS v_cohort_step_difficulty;
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
-- Filtered before the outer join rather than after it. A WHERE clause on the
-- student would turn the outer join inner and drop any step nobody has
-- answered yet, so the list of nine would quietly become a list of however
-- many had been attempted.
LEFT JOIN (
    SELECT ss.*
      FROM session_steps ss
      JOIN sessions se  ON se.id = ss.session_id
      JOIN students stu ON stu.id = se.student_id
     WHERE NOT stu.is_demo
) ss ON ss.step = s.step
LEFT JOIN sessions se ON se.id = ss.session_id
GROUP BY s.step, s.concept, s.label;

DROP VIEW IF EXISTS v_cohort_errors;
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
-- Same shape as above, for the same reason: an error nobody has made yet is
-- still part of the taxonomy and still belongs in the list, at zero.
LEFT JOIN (
    SELECT ss.*
      FROM session_steps ss
      JOIN sessions se  ON se.id = ss.session_id
      JOIN students stu ON stu.id = se.student_id
     WHERE NOT stu.is_demo
) ss ON ss.error_label = e.code
LEFT JOIN sessions se ON se.id = ss.session_id
GROUP BY e.code, e.step, s.label, e.description;

COMMIT;
