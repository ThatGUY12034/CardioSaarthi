-- The tutor's library.
--
-- pgvector has been enabled since V1 for this, and nothing has used it. The
-- design always called for retrieval over faculty-approved teaching notes; what
-- changed is where the candidates come from. Faculty are not writing a
-- curriculum for us, so the corpus is drawn from openly licensed published
-- material and faculty approve it instead of authoring it. That turns their job
-- from weeks of writing into an afternoon of ticking, and the rule the platform
-- actually rests on is unchanged: nothing reaches a student that a named person
-- has not approved.
--
-- Two things are therefore non-negotiable in this schema. Every chunk carries
-- its provenance, because an answer that cannot say where it came from is not
-- usable in teaching. And every chunk starts as pending, because an unreviewed
-- paragraph is exactly as dangerous as an unreviewed measurement.

BEGIN;

-- ---------------------------------------------------------------------------
-- Where the text came from
-- ---------------------------------------------------------------------------
-- Licence is NOT NULL and has no default. A source whose licence nobody
-- recorded is a source that cannot be redistributed, and discovering that after
-- the fact means unpicking the corpus.
CREATE TABLE knowledge_sources (
    id           bigserial PRIMARY KEY,
    title        text NOT NULL,
    publisher    text NOT NULL,
    url          text NOT NULL,
    licence      text NOT NULL,
    licence_url  text,
    -- Verbatim attribution line, as the licence requires it to be shown.
    attribution  text NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (url)
);

COMMENT ON TABLE knowledge_sources IS
    'Provenance for every paragraph the tutor can quote. CC BY-SA and CC BY both require '
    'attribution, so the attribution line is stored rather than reconstructed.';

-- ---------------------------------------------------------------------------
-- The paragraphs
-- ---------------------------------------------------------------------------
CREATE TABLE knowledge_chunks (
    id            bigserial PRIMARY KEY,
    source_id     bigint NOT NULL REFERENCES knowledge_sources (id) ON DELETE CASCADE,

    -- Which of the nine this paragraph is about, where it is about one. A
    -- paragraph of general background has no concept and is retrievable only by
    -- its text.
    concept       text REFERENCES interpretation_steps (concept),
    heading       text,
    body          text NOT NULL CHECK (length(body) BETWEEN 80 AND 4000),

    -- Lexical retrieval. A generated column so it can never drift from the body
    -- it indexes; the weighting puts a heading match above a body match.
    search        tsvector GENERATED ALWAYS AS (
                      setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
                      setweight(to_tsvector('english', body), 'B')
                  ) STORED,

    -- Left null. pgvector is enabled and the column is here so semantic search
    -- can be added without a migration on a table that by then holds faculty
    -- decisions. Nothing populates it today: a local embedding model would mean
    -- importing a deep learning framework into a pipeline whose selling point is
    -- that it contains none.
    embedding     vector(384),

    review_status text NOT NULL DEFAULT 'pending'
                  CHECK (review_status IN ('pending', 'approved', 'rejected')),
    reviewed_by   bigint REFERENCES reviewers (id),
    reviewed_at   timestamptz,
    reject_reason text,

    created_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT decided_chunks_have_a_reviewer
        CHECK ((review_status = 'pending') = (reviewed_by IS NULL)),
    CONSTRAINT rejections_have_a_reason
        CHECK (review_status <> 'rejected' OR reject_reason IS NOT NULL)
);

CREATE INDEX knowledge_chunks_search_idx  ON knowledge_chunks USING gin (search);
CREATE INDEX knowledge_chunks_concept_idx ON knowledge_chunks (concept, review_status);
CREATE INDEX knowledge_chunks_pending_idx ON knowledge_chunks (created_at)
    WHERE review_status = 'pending';

-- The body is quoted material. A reviewer decides whether it may be used; they
-- do not rewrite it, because a paragraph edited after import no longer says what
-- its source says and the attribution becomes a lie.
CREATE OR REPLACE FUNCTION forbid_body_edit() RETURNS trigger AS $$
BEGIN
    IF NEW.body IS DISTINCT FROM OLD.body OR NEW.source_id IS DISTINCT FROM OLD.source_id THEN
        RAISE EXCEPTION
            'a knowledge chunk is quoted material: its text and source cannot be edited, only approved or rejected';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER knowledge_chunks_text_is_quoted
    BEFORE UPDATE ON knowledge_chunks
    FOR EACH ROW EXECUTE FUNCTION forbid_body_edit();

-- ---------------------------------------------------------------------------
-- What the tutor may retrieve
-- ---------------------------------------------------------------------------
-- Approved only, with the attribution attached so a citation can never be
-- rendered without it. The tutor reads this view and not the table, for the
-- same reason the grader reads v_served_parameters and not case_measurements.
CREATE VIEW v_approved_knowledge AS
SELECT
    k.id,
    k.concept,
    k.heading,
    k.body,
    k.search,
    s.title       AS source_title,
    s.publisher   AS source_publisher,
    s.url         AS source_url,
    s.licence     AS source_licence,
    s.attribution AS source_attribution
FROM knowledge_chunks k
JOIN knowledge_sources s ON s.id = k.source_id
WHERE k.review_status = 'approved';

COMMENT ON VIEW v_approved_knowledge IS
    'The only thing the tutor may quote. A pending or rejected paragraph is absent, so a '
    'bug in the retrieval code cannot surface unreviewed text.';

-- ---------------------------------------------------------------------------
-- What was asked, and what it was answered from
-- ---------------------------------------------------------------------------
-- Every tutor answer records the chunks it was built from. Without this an
-- answer cannot be audited after the fact, and "the tutor told me" becomes
-- unfalsifiable.
CREATE TABLE tutor_answers (
    id          bigserial PRIMARY KEY,
    student_id  bigint REFERENCES students (id) ON DELETE SET NULL,
    session_id  bigint REFERENCES sessions (id) ON DELETE SET NULL,
    concept     text REFERENCES interpretation_steps (concept),
    question    text NOT NULL,
    answer      text NOT NULL,
    chunk_ids   bigint[] NOT NULL,
    -- TEMPLATE when the answer is the retrieved text verbatim, MODEL when a
    -- model assembled it from that text, REFUSED when nothing approved matched.
    answer_source text NOT NULL CHECK (answer_source IN ('TEMPLATE', 'MODEL', 'REFUSED')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX tutor_answers_student_idx ON tutor_answers (student_id, created_at DESC);

CREATE TRIGGER tutor_answers_no_update
    BEFORE UPDATE ON tutor_answers
    FOR EACH ROW EXECUTE FUNCTION forbid_update();

COMMENT ON TABLE tutor_answers IS
    'Append-only. What a student was told, and which approved paragraphs it was built from.';

COMMIT;
