package com.cardiosaarthi.review.review;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.cardiosaarthi.review.error.ConflictException;
import com.cardiosaarthi.review.error.InvalidReviewException;
import com.cardiosaarthi.review.error.NotFoundException;
import com.cardiosaarthi.review.reviewer.Reviewer;

/**
 * Records a review decision.
 *
 * <p>Everything a review touches is written in one transaction: the corrections,
 * the audit row, and the case's new status. A case that is marked approved
 * without the corrections that justified it, or corrections with no record of who
 * made them, would both be worse than a failed request.
 *
 * <p>The rules enforced here are enforced here on purpose. A console can forget
 * to disable a button; the server is the only place a rule actually holds.
 */
@Service
public class ReviewService {

    private static final Logger log = LoggerFactory.getLogger(ReviewService.class);

    private final JdbcClient db;

    ReviewService(JdbcClient db) {
        this.db = db;
    }

    private record CaseState(long id, String reviewStatus, String engineVersion) {
    }

    private record ComputedMeasure(Double value, String unit) {
    }

    @Transactional
    public ReviewOutcome submit(long caseId, ReviewRequest request, Reviewer reviewer) {
        CaseState state = loadCase(caseId);

        if (!"pending".equals(state.reviewStatus())) {
            // Two reviewers opened the same case. The first decision stands; a
            // review is a record of what a person judged, not a settable field.
            throw new ConflictException(
                    "case %d was already %s and cannot be reviewed again".formatted(caseId, state.reviewStatus()));
        }

        List<ReviewRequest.Correction> corrections = request.correctionsOrEmpty();
        validateShape(request, corrections);

        List<String> recorded = new ArrayList<>();
        List<String> unchanged = new ArrayList<>();

        for (ReviewRequest.Correction correction : corrections) {
            if (!Parameters.isKnown(correction.name())) {
                throw new InvalidReviewException(
                        "'%s' is not a correctable parameter".formatted(correction.name()));
            }

            if (correction.isTextual() || Parameters.isCategorical(correction.name())) {
                if (recordTextual(caseId, correction, reviewer.id())) {
                    recorded.add(correction.name());
                } else {
                    unchanged.add(correction.name());
                }
                continue;
            }

            ComputedMeasure computed = loadMeasure(caseId, correction.name())
                    .orElseThrow(() -> new InvalidReviewException(
                            "case %d has no measure called '%s'".formatted(caseId, correction.name())));

            if (correction.value() == null) {
                throw new InvalidReviewException(
                        "'%s' is a measurement and needs a number".formatted(correction.name()));
            }
            checkPlausible(correction);

            if (computed.value() != null && computed.value().equals(correction.value())) {
                // Not a correction. Writing it would put a zero into the
                // measurement-agreement table and dilute the real disagreements.
                unchanged.add(correction.name());
                continue;
            }

            insertCorrection(caseId, correction, computed, state.engineVersion(), reviewer.id());
            recorded.add(correction.name());
        }

        if (request.action().requiresCorrections() && recorded.isEmpty()) {
            throw new InvalidReviewException(
                    "EDIT recorded no change. Every value submitted matched the engine's; use APPROVE instead.");
        }

        OffsetDateTime reviewedAt = insertReviewLog(caseId, request, reviewer.id());
        updateCaseStatus(caseId, request.action().resultingCaseStatus(), reviewer.id());

        log.info("case {} {} by reviewer {} ({} correction(s){})",
                caseId, request.action().logValue(), reviewer.id(), recorded.size(),
                request.rejectionReason() == null ? "" : ", reason " + request.rejectionReason().dbValue());

        return new ReviewOutcome(
                caseId,
                request.action(),
                request.action().resultingCaseStatus(),
                reviewer.id(),
                reviewedAt,
                List.copyOf(recorded),
                List.copyOf(unchanged),
                countPending());
    }

    // -----------------------------------------------------------------------
    // rules
    // -----------------------------------------------------------------------
    private void validateShape(ReviewRequest request, List<ReviewRequest.Correction> corrections) {
        ReviewAction action = request.action();

        if (action == ReviewAction.REJECT && request.rejectionReason() == null) {
            // Mirrors the CHECK constraint on reviews. Caught here so the
            // reviewer gets a sentence instead of a constraint-violation page.
            throw new InvalidReviewException(
                    "a rejection needs a reason: the rejection log is reported as a pipeline-accuracy "
                            + "measure, and a rejection without a reason is just a missing case");
        }
        if (action != ReviewAction.REJECT && request.rejectionReason() != null) {
            throw new InvalidReviewException(
                    "rejectionReason only applies to REJECT, and this request is " + action);
        }
        if (action.forbidsCorrections() && !corrections.isEmpty()) {
            throw new InvalidReviewException(
                    "%s carries %d correction(s). Use EDIT to change a measurement."
                            .formatted(action, corrections.size()));
        }
        if (action.requiresCorrections() && corrections.isEmpty()) {
            throw new InvalidReviewException("EDIT needs at least one correction. Use APPROVE if nothing changed.");
        }

        long distinct = corrections.stream().map(ReviewRequest.Correction::name).distinct().count();
        if (distinct != corrections.size()) {
            throw new InvalidReviewException("the same measure was corrected twice in one request");
        }
    }

    private void checkPlausible(ReviewRequest.Correction correction) {
        Plausibility.Bounds bounds = Plausibility.forMeasure(correction.name())
                .orElseThrow(() -> new InvalidReviewException(
                        "'%s' is not a correctable measure".formatted(correction.name())));

        if (!bounds.contains(correction.value())) {
            throw new InvalidReviewException(
                    "%s of %s is outside the physiologically possible range (%s). Check the units."
                            .formatted(correction.name(), correction.value(), bounds.describe()));
        }
    }

    // -----------------------------------------------------------------------
    // reads
    // -----------------------------------------------------------------------
    private CaseState loadCase(long caseId) {
        return db.sql("SELECT id, review_status, engine_version FROM cases WHERE id = :caseId FOR UPDATE")
                .param("caseId", caseId)
                .query((rs, n) -> new CaseState(
                        rs.getLong("id"), rs.getString("review_status"), rs.getString("engine_version")))
                .optional()
                .orElseThrow(() -> new NotFoundException("no case with id " + caseId));
    }

    private Optional<ComputedMeasure> loadMeasure(long caseId, String name) {
        return db.sql("SELECT value, unit FROM case_measurements WHERE case_id = :caseId AND name = :name")
                .param("caseId", caseId)
                .param("name", name)
                .query((rs, n) -> new ComputedMeasure(
                        // getObject(column, Double.class) is not supported for a
                        // PostgreSQL numeric; getDouble plus wasNull is, and the
                        // null matters -- a NOT_MEASURABLE interval has no value.
                        nullableDouble(rs, "value"), rs.getString("unit")))
                .optional();
    }

    private static Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private int countPending() {
        return db.sql("SELECT count(*) FROM cases WHERE review_status = 'pending'")
                .query(Integer.class)
                .single();
    }

    // -----------------------------------------------------------------------
    // writes
    // -----------------------------------------------------------------------
    /**
     * Records a correction to a parameter that is not a number.
     *
     * <p>The rhythm, the axis, P-wave presence, which leads deviate -- and a
     * numeric measure a reviewer marks NOT_MEASURABLE. As with a numeric
     * correction the computed value is snapshotted beside the corrected one and
     * nothing is overwritten.
     *
     * @return false when the reviewer's value matches what the engine already
     *         says, which is not a correction and is not worth a row
     */
    private boolean recordTextual(long caseId, ReviewRequest.Correction correction, long reviewerId) {
        String corrected;
        try {
            corrected = Parameters.normalise(correction.name(), correction.text());
        } catch (IllegalArgumentException exception) {
            throw new InvalidReviewException(exception.getMessage());
        }

        String computed = currentTextValue(caseId, correction.name());
        if (corrected.equals(computed)) {
            return false;
        }

        db.sql("""
                INSERT INTO measurement_corrections
                    (case_id, name, computed_text, corrected_text, engine_version, reviewer_id, note)
                VALUES (:caseId, :name, :computed, :corrected,
                        (SELECT engine_version FROM cases WHERE id = :caseId), :reviewerId, :note)
                """)
                .param("caseId", caseId)
                .param("name", correction.name())
                .param("computed", computed)
                .param("corrected", corrected)
                .param("reviewerId", reviewerId)
                .param("note", correction.note())
                .update();
        return true;
    }

    /**
     * What the platform currently says this parameter is.
     *
     * <p>Read from v_served_parameters, so a reviewer correcting the same
     * parameter twice is compared against their own previous correction rather
     * than against the engine's original.
     */
    private String currentTextValue(long caseId, String name) {
        // Read from the underlying values rather than from v_served_parameters:
        // that view covers approved cases only, and a reviewer corrects a case
        // while it is still pending. Reading the view here left computed_text
        // empty on every correction, which is exactly the snapshot the
        // measurement-agreement evidence depends on.
        return db.sql("""
                SELECT coalesce(
                    (SELECT mc.corrected_text FROM measurement_corrections mc
                      WHERE mc.case_id = c.id AND mc.name = :name
                      ORDER BY mc.created_at DESC, mc.id DESC LIMIT 1),
                    CASE :name
                        WHEN 'rhythm' THEN c.rhythm_regularity
                        WHEN 'axis'   THEN c.axis_category
                        WHEN 'p_waves' THEN (
                            SELECT CASE WHEN m.status = 'NOT_MEASURABLE' THEN 'ABSENT' ELSE 'PRESENT' END
                            FROM case_measurements m
                            WHERE m.case_id = c.id AND m.name = 'p_duration')
                        WHEN 'st_segment' THEN (
                            SELECT coalesce(string_agg(d.lead, ',' ORDER BY d.lead), '')
                            FROM case_st_deviations d
                            WHERE d.case_id = c.id AND d.finding <> 'NORMAL')
                        ELSE (
                            SELECT m.status FROM case_measurements m
                            WHERE m.case_id = c.id AND m.name = :name)
                    END,
                    '')
                FROM cases c WHERE c.id = :caseId
                """)
                .param("caseId", caseId)
                .param("name", name)
                .query(String.class)
                .optional()
                .orElse("");
    }

    private void insertCorrection(long caseId, ReviewRequest.Correction correction,
                                  ComputedMeasure computed, String engineVersion, long reviewerId) {
        db.sql("""
                INSERT INTO measurement_corrections
                    (case_id, name, computed_value, corrected_value, unit, engine_version, reviewer_id, note)
                VALUES (:caseId, :name, :computed, :corrected, :unit, :engineVersion, :reviewerId, :note)
                """)
                .param("caseId", caseId)
                .param("name", correction.name())
                // Snapshotted, not joined for later. If the engine is improved
                // and this case re-measured, the row still records what the
                // reviewer was actually looking at when they disagreed.
                .param("computed", computed.value())
                .param("corrected", correction.value())
                .param("unit", computed.unit())
                .param("engineVersion", engineVersion)
                .param("reviewerId", reviewerId)
                .param("note", correction.note())
                .update();
    }

    private OffsetDateTime insertReviewLog(long caseId, ReviewRequest request, long reviewerId) {
        return db.sql("""
                INSERT INTO reviews (case_id, reviewer_id, action, rejection_reason, note, duration_seconds)
                VALUES (:caseId, :reviewerId, :action, :reason, :note, :duration)
                RETURNING created_at
                """)
                .param("caseId", caseId)
                .param("reviewerId", reviewerId)
                .param("action", request.action().logValue())
                .param("reason", request.rejectionReason() == null ? null : request.rejectionReason().dbValue())
                .param("note", request.note())
                .param("duration", request.durationSeconds())
                .query(OffsetDateTime.class)
                .single();
    }

    private void updateCaseStatus(long caseId, String status, long reviewerId) {
        db.sql("""
                UPDATE cases
                SET review_status = :status, reviewed_at = now(), reviewed_by = :reviewerId
                WHERE id = :caseId
                """)
                .param("status", status)
                .param("reviewerId", reviewerId)
                .param("caseId", caseId)
                .update();
    }
}
