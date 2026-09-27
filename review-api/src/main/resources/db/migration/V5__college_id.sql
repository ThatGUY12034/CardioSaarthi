-- College identifiers, because that is what people are actually issued.
--
-- The console's login form offers two modes: college ID or email. Students and
-- faculty at Terna are given an institutional ID and know it; many will not know
-- which email address the platform holds for them. Supporting only email would
-- make the form lie about what it accepts.
--
-- Nullable on both tables: an account can exist before an ID is assigned, and
-- the system reviewer that seeds development fixtures has no college at all.
-- Unique where present, case-insensitively, so two people cannot share one.

BEGIN;

ALTER TABLE students  ADD COLUMN college_id text;
ALTER TABLE reviewers ADD COLUMN college_id text;

CREATE UNIQUE INDEX students_college_id_key  ON students  (lower(college_id)) WHERE college_id IS NOT NULL;
CREATE UNIQUE INDEX reviewers_college_id_key ON reviewers (lower(college_id)) WHERE college_id IS NOT NULL;

COMMENT ON COLUMN students.college_id IS
    'Institutional identifier, e.g. TE18/2023/C5001. Nullable: an account may exist before one is assigned.';
COMMENT ON COLUMN reviewers.college_id IS
    'Institutional identifier. Always null for the system account, which belongs to no college.';

COMMIT;
