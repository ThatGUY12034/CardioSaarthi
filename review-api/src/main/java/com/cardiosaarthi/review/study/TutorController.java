package com.cardiosaarthi.review.study;

import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.error.InvalidReviewException;
import com.cardiosaarthi.review.error.NotFoundException;
import com.cardiosaarthi.review.reviewer.ReviewerService;

import jakarta.validation.Valid;

/**
 * The tutor, and the queue of material waiting to become one.
 *
 * <p>Students ask; faculty decide what may be answered from. Both halves live
 * here because they are two ends of the same guarantee, and separating them
 * tends to produce a reading endpoint that forgets the approval filter.
 */
@RestController
@RequestMapping("/api")
public class TutorController {

    private final TutorService tutor;
    private final CurrentStudent currentStudent;
    private final ReviewerService reviewers;
    private final JdbcClient db;

    TutorController(TutorService tutor, CurrentStudent currentStudent,
                    ReviewerService reviewers, JdbcClient db) {
        this.tutor = tutor;
        this.currentStudent = currentStudent;
        this.reviewers = reviewers;
        this.db = db;
    }

    // -----------------------------------------------------------------------
    // students
    // -----------------------------------------------------------------------
    public record Question(
            @NotBlank(message = "a question is required")
            @Size(max = 300, message = "keep the question under 300 characters")
            String question,
            String concept,
            Long sessionId) {
    }

    @PostMapping("/study/tutor/ask")
    public TutorService.Answer ask(@Valid @RequestBody Question request) {
        return tutor.answer(currentStudent.id(), request.sessionId(),
                request.question(), blankToNull(request.concept()));
    }

    /** What the library holds on one concept, for the reading panel beside a step. */
    @GetMapping("/study/tutor/concept/{concept}")
    public List<TutorService.Passage> forConcept(@PathVariable String concept) {
        return tutor.retrieve(concept.replace('_', ' '), concept, 5);
    }

    // -----------------------------------------------------------------------
    // faculty
    // -----------------------------------------------------------------------
    public record PendingChunk(long id, String concept, String heading, String body,
                               String sourceTitle, String sourcePublisher, String sourceUrl,
                               String sourceLicence, String reviewStatus) {
    }

    @GetMapping("/knowledge/queue")
    @PreAuthorize("hasAnyRole('FACULTY','ADMIN')")
    public List<PendingChunk> queue(@RequestParam(defaultValue = "pending") String status,
                                    @RequestParam(required = false) String concept,
                                    @RequestParam(defaultValue = "25") int limit) {
        return db.sql("""
                SELECT k.id, k.concept, k.heading, k.body, k.review_status,
                       s.title AS source_title, s.publisher AS source_publisher,
                       s.url AS source_url, s.licence AS source_licence
                FROM knowledge_chunks k
                JOIN knowledge_sources s ON s.id = k.source_id
                WHERE k.review_status = :status
                  AND (CAST(:concept AS text) IS NULL OR k.concept = :concept)
                ORDER BY k.concept NULLS LAST, k.id
                LIMIT :limit
                """)
                .param("status", status)
                .param("concept", blankToNull(concept))
                .param("limit", Math.clamp(limit, 1, 100))
                .query((rs, n) -> new PendingChunk(
                        rs.getLong("id"), rs.getString("concept"), rs.getString("heading"),
                        rs.getString("body"), rs.getString("source_title"),
                        rs.getString("source_publisher"), rs.getString("source_url"),
                        rs.getString("source_licence"), rs.getString("review_status")))
                .list();
    }

    @GetMapping("/knowledge/status")
    @PreAuthorize("hasAnyRole('FACULTY','ADMIN')")
    public TutorService.CorpusStatus status() {
        return tutor.status();
    }

    public record Decision(
            @NotBlank(message = "action is required: APPROVE or REJECT") String action,
            String reason) {
    }

    /**
     * Approve or reject one paragraph.
     *
     * <p>There is no edit. The body is quoted material under a licence that
     * requires attribution, and a paragraph rewritten after import no longer
     * says what its source says while still carrying its citation. A database
     * trigger enforces that independently of this endpoint.
     */
    @PostMapping("/knowledge/{id}/review")
    @PreAuthorize("hasAnyRole('FACULTY','ADMIN')")
    public PendingChunk review(@PathVariable long id, @Valid @RequestBody Decision decision) {
        long reviewerId = reviewers.current().id();
        String action = decision.action() == null ? "" : decision.action().trim().toUpperCase();

        String status = switch (action) {
            case "APPROVE" -> "approved";
            case "REJECT" -> "rejected";
            default -> throw new InvalidReviewException(
                    "action must be APPROVE or REJECT, not '" + decision.action() + "'");
        };
        if ("rejected".equals(status)
                && (decision.reason() == null || decision.reason().isBlank())) {
            // The same rule as rejecting a case: a rejection without a reason is
            // indistinguishable from a paragraph nobody got round to.
            throw new InvalidReviewException("a rejection needs a reason");
        }

        int updated = db.sql("""
                UPDATE knowledge_chunks
                SET review_status = :status, reviewed_by = :reviewer,
                    reviewed_at = now(), reject_reason = :reason
                WHERE id = :id AND review_status = 'pending'
                """)
                .param("status", status)
                .param("reviewer", reviewerId)
                .param("reason", "rejected".equals(status) ? decision.reason() : null)
                .param("id", id)
                .update();

        if (updated == 0) {
            throw new NotFoundException("no paragraph " + id + " awaiting review");
        }
        return queueOne(id);
    }

    private PendingChunk queueOne(long id) {
        return db.sql("""
                SELECT k.id, k.concept, k.heading, k.body, k.review_status,
                       s.title AS source_title, s.publisher AS source_publisher,
                       s.url AS source_url, s.licence AS source_licence
                FROM knowledge_chunks k
                JOIN knowledge_sources s ON s.id = k.source_id
                WHERE k.id = :id
                """)
                .param("id", id)
                .query((rs, n) -> new PendingChunk(
                        rs.getLong("id"), rs.getString("concept"), rs.getString("heading"),
                        rs.getString("body"), rs.getString("source_title"),
                        rs.getString("source_publisher"), rs.getString("source_url"),
                        rs.getString("source_licence"), rs.getString("review_status")))
                .single();
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
