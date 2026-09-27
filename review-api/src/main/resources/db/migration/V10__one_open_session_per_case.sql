-- A case a student could never open again.
--
-- Starting a case refused if that student already had one open, and told them
-- to "finish or abandon it" -- but nothing could abandon it, so the case was
-- gone for good. Worse, the interface opened two sessions every time: the
-- effect that starts one runs twice, both requests passed the check before
-- either had committed, and the spare was left open forever. A student's
-- second visit to any case they had ever opened was refused.
--
-- Three things are wrong there and this fixes the database's share of them.
-- The service now resumes an open session instead of refusing it, so the
-- refusal message goes away entirely; what has to hold here is that there is
-- never more than one to resume.

BEGIN;

-- ---------------------------------------------------------------------------
-- Close the duplicates already in the table
-- ---------------------------------------------------------------------------
-- The newest of each pair is the one the interface actually used and the one
-- holding the student's answers; the older is the spare that was orphaned the
-- moment it was created. Abandoned rather than deleted: a session is a record
-- that something happened, and the answers recorded against it stay readable.
WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY student_id, case_id
               ORDER BY started_at DESC, id DESC
           ) AS rank
    FROM sessions
    WHERE state NOT IN ('CASE_COMPLETE', 'ABANDONED')
)
UPDATE sessions
   SET state = 'ABANDONED'
 WHERE id IN (SELECT id FROM ranked WHERE rank > 1);

-- ---------------------------------------------------------------------------
-- Make a second one impossible
-- ---------------------------------------------------------------------------
-- The check in the service is a read followed by a write, so two requests
-- arriving together both see no open session and both insert. Only the
-- database can settle that, and this is how it settles it: the loser of the
-- race gets a unique violation, which the service catches and answers with the
-- session that won.
--
-- ABANDONED counts as closed here, which it did not in the old check -- an
-- abandoned session blocked the case exactly as an open one did, so the
-- instruction to abandon it would not have helped even if it had been
-- possible.
CREATE UNIQUE INDEX sessions_one_open_per_case
    ON sessions (student_id, case_id)
    WHERE state NOT IN ('CASE_COMPLETE', 'ABANDONED');

COMMIT;
