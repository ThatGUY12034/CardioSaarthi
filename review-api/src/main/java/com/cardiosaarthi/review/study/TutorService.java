package com.cardiosaarthi.review.study;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Retrieval over faculty-approved material.
 *
 * <p>The design always called for a tutor that answers from approved teaching
 * notes. What changed is where the candidates come from: faculty are not
 * writing a curriculum, so the corpus is drawn from openly licensed published
 * material and faculty approve it rather than author it. The rule the platform
 * rests on is untouched — nothing reaches a student that a named person has not
 * approved — and the approval is enforced by the view this class reads, not by
 * a condition it remembers to apply.
 *
 * <p>Retrieval is lexical, over PostgreSQL's full-text index. For a few hundred
 * curated paragraphs that is adequate, and the alternative would have meant
 * importing a deep learning framework into a pipeline whose entire claim is
 * that it contains none. The pgvector column is in place for the day that
 * trade changes.
 *
 * <p>Two things this tutor will not do. It will not answer from its own
 * knowledge when retrieval finds nothing: an empty result produces a refusal,
 * because a plausible answer with no source behind it is the failure this
 * project exists to avoid. And it will not state a measurement for the case in
 * front of the student — those come from the engine, and the tutor explains
 * concepts rather than reading traces.
 */
@Service
public class TutorService {

    private static final Logger log = LoggerFactory.getLogger(TutorService.class);

    /** Below this the match is noise and a refusal is the honest answer. */
    private static final double MINIMUM_RANK = 0.02;

    private final JdbcClient db;

    TutorService(JdbcClient db) {
        this.db = db;
    }

    /** One approved paragraph, with everything needed to cite it. */
    public record Passage(long id, String concept, String heading, String body,
                          String sourceTitle, String sourcePublisher, String sourceUrl,
                          String sourceLicence, String sourceAttribution, double rank) {
    }

    /**
     * What the student was told, and what it was built from.
     *
     * <p>{@code citations} is never empty unless {@code refused} is true. An
     * answer a student cannot trace to a source is not an answer this platform
     * is willing to give.
     */
    public record Answer(String text, List<Passage> citations, boolean refused,
                         String concept) {
    }

    // -----------------------------------------------------------------------
    // retrieval
    // -----------------------------------------------------------------------
    /**
     * The best approved passages for a question.
     *
     * <p>Scoped to a concept where one is given, because a student asking about
     * the PR interval mid-case wants the PR interval and not the best lexical
     * match across the whole corpus. websearch_to_tsquery rather than
     * plainto_tsquery: it accepts the quoting and negation a person naturally
     * types and never throws on malformed input, which plainto_tsquery does.
     */
    public List<Passage> retrieve(String question, String concept, int limit) {
        return db.sql("""
                SELECT id, concept, heading, body,
                       source_title, source_publisher, source_url,
                       source_licence, source_attribution,
                       ts_rank(search, websearch_to_tsquery('english', :question)) AS rank
                FROM v_approved_knowledge
                WHERE search @@ websearch_to_tsquery('english', :question)
                  AND (CAST(:concept AS text) IS NULL OR concept = :concept)
                ORDER BY rank DESC
                LIMIT :limit
                """)
                .param("question", question)
                .param("concept", concept)
                .param("limit", Math.clamp(limit, 1, 10))
                .query((rs, n) -> new Passage(
                        rs.getLong("id"),
                        rs.getString("concept"),
                        rs.getString("heading"),
                        rs.getString("body"),
                        rs.getString("source_title"),
                        rs.getString("source_publisher"),
                        rs.getString("source_url"),
                        rs.getString("source_licence"),
                        rs.getString("source_attribution"),
                        rs.getDouble("rank")))
                .list()
                .stream()
                .filter(passage -> passage.rank() >= MINIMUM_RANK)
                .toList();
    }

    /**
     * Answer a question, or decline to.
     *
     * <p>The answer is the retrieved text itself, quoted and attributed. No
     * model rewrites it, and that is a deliberate limit rather than an unfinished
     * one: a model asked to paraphrase an approved paragraph can introduce a
     * clinical claim the reviewer never approved, and the reviewer approved the
     * paragraph, not a summary of it.
     */
    @Transactional
    public Answer answer(Long studentId, Long sessionId, String question, String concept) {
        List<Passage> passages = retrieve(question, concept, 3);

        if (passages.isEmpty()) {
            // Widen once: a question scoped to a concept may still be answerable
            // from general material about reading an ECG.
            passages = concept == null ? List.of() : retrieve(question, null, 3);
        }

        if (passages.isEmpty()) {
            String refusal = "Nothing in the approved reference material covers that. "
                    + "Ask your faculty, and the material can be added and approved.";
            record(studentId, sessionId, concept, question, refusal, List.of(), "REFUSED");
            return new Answer(refusal, List.of(), true, concept);
        }

        StringBuilder text = new StringBuilder();
        for (Passage passage : passages) {
            if (!text.isEmpty()) {
                text.append("\n\n");
            }
            if (passage.heading() != null && !passage.heading().isBlank()) {
                text.append(passage.heading()).append(" — ");
            }
            text.append(passage.body());
        }

        record(studentId, sessionId, concept, question, text.toString(), passages, "TEMPLATE");
        log.info("tutor answered a question on {} from {} approved passages",
                concept == null ? "general material" : concept, passages.size());
        return new Answer(text.toString(), passages, false, concept);
    }

    private void record(Long studentId, Long sessionId, String concept, String question,
                        String answer, List<Passage> passages, String source) {
        Long[] ids = passages.stream().map(Passage::id).toArray(Long[]::new);
        db.sql("""
                INSERT INTO tutor_answers
                    (student_id, session_id, concept, question, answer, chunk_ids, answer_source)
                VALUES (:studentId, :sessionId, :concept, :question, :answer, :chunkIds, :source)
                """)
                .param("studentId", studentId)
                .param("sessionId", sessionId)
                .param("concept", concept)
                .param("question", question)
                .param("answer", answer)
                .param("chunkIds", ids)
                .param("source", source)
                .update();
    }

    // -----------------------------------------------------------------------
    // the corpus, for faculty
    // -----------------------------------------------------------------------
    public record CorpusStatus(int pending, int approved, int rejected, int sources) {
    }

    public CorpusStatus status() {
        return db.sql("""
                SELECT
                    count(*) FILTER (WHERE review_status = 'pending')  AS pending,
                    count(*) FILTER (WHERE review_status = 'approved') AS approved,
                    count(*) FILTER (WHERE review_status = 'rejected') AS rejected,
                    (SELECT count(*) FROM knowledge_sources)           AS sources
                FROM knowledge_chunks
                """)
                .query((rs, n) -> new CorpusStatus(
                        rs.getInt("pending"), rs.getInt("approved"),
                        rs.getInt("rejected"), rs.getInt("sources")))
                .single();
    }
}
