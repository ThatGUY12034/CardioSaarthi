-- A session that can never be deleted.
--
-- tutor_answers references sessions with ON DELETE SET NULL, deliberately: what
-- a student was told is a record worth keeping even after the session it was
-- asked during has gone. But the table also carries the generic append-only
-- trigger, which refuses every UPDATE. Those two decisions contradict each
-- other, and the contradiction only shows up when somebody tries to delete a
-- session that happens to have a tutor answer attached: PostgreSQL issues the
-- SET NULL as an UPDATE, the trigger rejects it, and the delete fails with a
-- message about computed measurements being evidence, which is not what is
-- happening at all.
--
-- The fix is a trigger specific to this table rather than the shared one. The
-- content of an answer still cannot be edited -- that is the guarantee worth
-- having, since an answer rewritten after the fact is not a record of what a
-- student was told. Detaching it from a deleted session is permitted, because
-- that is the schema's own stated intent.

BEGIN;

CREATE OR REPLACE FUNCTION forbid_tutor_answer_edit() RETURNS trigger AS $$
BEGIN
    IF NEW.question    IS DISTINCT FROM OLD.question
       OR NEW.answer   IS DISTINCT FROM OLD.answer
       OR NEW.chunk_ids IS DISTINCT FROM OLD.chunk_ids
       OR NEW.answer_source IS DISTINCT FROM OLD.answer_source
       OR NEW.student_id IS DISTINCT FROM OLD.student_id
       OR NEW.concept  IS DISTINCT FROM OLD.concept
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION
            'a tutor answer is a record of what a student was told: it cannot be edited';
    END IF;
    -- Only session_id may change, and only to NULL, which is what the
    -- foreign key does when a session is removed.
    IF NEW.session_id IS NOT NULL AND NEW.session_id IS DISTINCT FROM OLD.session_id THEN
        RAISE EXCEPTION 'a tutor answer cannot be moved to a different session';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tutor_answers_no_update ON tutor_answers;

CREATE TRIGGER tutor_answers_are_a_record
    BEFORE UPDATE ON tutor_answers
    FOR EACH ROW EXECUTE FUNCTION forbid_tutor_answer_edit();

COMMIT;
