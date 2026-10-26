package com.cardiosaarthi.review.study;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * What the tutor may and may not say.
 *
 * <p>The guarantee worth protecting is not that retrieval finds good matches —
 * it is that it cannot find anything a reviewer has not approved. Everything
 * else about the tutor is a quality question; that one is a safety question,
 * and it is enforced by the view rather than by a WHERE clause somebody has to
 * remember.
 */
@SpringBootTest
@Transactional
@EnabledIf("databaseIsRunning")
class TutorRetrievalTests {

    @Autowired
    private TutorService tutor;

    @Autowired
    private JdbcClient db;

    static boolean databaseIsRunning() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", 55432), 400);
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    private long source(String title) {
        return db.sql("""
                INSERT INTO knowledge_sources (title, publisher, url, licence, attribution)
                VALUES (:title, 'Test publisher', :url, 'CC BY 4.0', 'Test attribution')
                RETURNING id
                """)
                .param("title", title)
                .param("url", "https://example.invalid/" + title.replace(' ', '-'))
                .query(Long.class)
                .single();
    }

    private long chunk(long sourceId, String concept, String body, String status) {
        long id = db.sql("""
                INSERT INTO knowledge_chunks (source_id, concept, heading, body)
                VALUES (:sourceId, :concept, 'Test heading', :body)
                RETURNING id
                """)
                .param("sourceId", sourceId)
                .param("concept", concept)
                .param("body", body)
                .query(Long.class)
                .single();
        if (!"pending".equals(status)) {
            long reviewer = db.sql("SELECT id FROM reviewers ORDER BY id LIMIT 1")
                    .query(Long.class).single();
            db.sql("""
                    UPDATE knowledge_chunks
                    SET review_status = :status, reviewed_by = :reviewer, reviewed_at = now(),
                        reject_reason = CASE WHEN :status = 'rejected' THEN 'test' END
                    WHERE id = :id
                    """)
                    .param("status", status).param("reviewer", reviewer).param("id", id)
                    .update();
        }
        return id;
    }

    /** A phrase unlikely to occur anywhere in the real corpus. */
    private static final String MARKER = "zymotic quibbling flugelhorn";

    @Test
    @DisplayName("an approved paragraph is retrievable")
    void approvedIsRetrievable() {
        long s = source("Approved material");
        chunk(s, "rate", "The " + MARKER + " describes how the heart rate is counted "
                + "across a ten second recording when the rhythm is irregular.", "approved");

        List<TutorService.Passage> found = tutor.retrieve(MARKER, null, 5);

        assertThat(found).hasSize(1);
        assertThat(found.getFirst().body()).contains(MARKER);
        assertThat(found.getFirst().sourceAttribution()).isNotBlank();
    }

    @Test
    @DisplayName("a pending paragraph is not retrievable, however well it matches")
    void pendingIsInvisible() {
        long s = source("Unreviewed material");
        chunk(s, "rate", "The " + MARKER + " describes how the heart rate is counted "
                + "across a ten second recording when the rhythm is irregular.", "pending");

        // The best possible lexical match in the corpus, and still absent: the
        // tutor reads a view that contains only approved rows.
        assertThat(tutor.retrieve(MARKER, null, 5)).isEmpty();
    }

    @Test
    @DisplayName("a rejected paragraph is not retrievable")
    void rejectedIsInvisible() {
        long s = source("Rejected material");
        chunk(s, "rate", "The " + MARKER + " describes how the heart rate is counted "
                + "across a ten second recording when the rhythm is irregular.", "rejected");

        assertThat(tutor.retrieve(MARKER, null, 5)).isEmpty();
    }

    @Test
    @DisplayName("nothing approved means a refusal, not an invented answer")
    void refusesRatherThanInventing() {
        TutorService.Answer answer = tutor.answer(null, null,
                "what is the " + MARKER + " threshold", "rate");

        assertThat(answer.refused()).isTrue();
        assertThat(answer.citations()).isEmpty();
        // The refusal says what to do about it rather than merely failing.
        assertThat(answer.text()).contains("approved reference material");
    }

    @Test
    @DisplayName("every answer carries at least one citation")
    void answersAreAlwaysCited() {
        long s = source("Citable material");
        chunk(s, "qt_interval", "The " + MARKER + " interval is measured from the start of "
                + "the QRS complex to the end of the T wave and is corrected for heart rate.",
                "approved");

        TutorService.Answer answer = tutor.answer(null, null, MARKER + " interval", "qt_interval");

        assertThat(answer.refused()).isFalse();
        assertThat(answer.citations()).isNotEmpty();
        assertThat(answer.citations().getFirst().sourceUrl()).isNotBlank();
    }

    @Test
    @DisplayName("the text of a paragraph cannot be edited after import")
    void bodyIsQuotedMaterial() {
        long s = source("Immutable material");
        long id = chunk(s, "rate", "The " + MARKER + " describes how the heart rate is counted "
                + "across a ten second recording when the rhythm is irregular.", "approved");

        // A paragraph rewritten after import no longer says what its source says
        // while still carrying its citation, so the database refuses it.
        assertThatBodyEditIsRefused(id);
    }

    private void assertThatBodyEditIsRefused(long id) {
        try {
            db.sql("UPDATE knowledge_chunks SET body = 'rewritten by a reviewer' WHERE id = :id")
                    .param("id", id)
                    .update();
            throw new AssertionError("expected the database to refuse an edit to quoted material");
        } catch (org.springframework.dao.DataAccessException expected) {
            assertThat(expected.getMostSpecificCause().getMessage()).contains("quoted material");
        }
    }
}
