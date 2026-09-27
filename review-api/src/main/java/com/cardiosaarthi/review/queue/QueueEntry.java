package com.cardiosaarthi.review.queue;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * One row of the review queue: enough for a reviewer to decide what to open
 * next, without loading a case.
 *
 * <p>{@code warnings} is carried here on purpose. A reviewer should be able to
 * see that a case was held back because the P wave was absent in three of
 * fourteen beats before spending time opening it.
 *
 * <p>Image paths are exposed as URLs rather than filesystem locations. Where the
 * bytes live is this service's business.
 */
public record QueueEntry(
        long caseId,
        String source,
        int sourceEcgId,
        Double age,
        String sex,
        List<String> diagnosticLabels,
        List<String> conditionCodes,
        String measurementStatus,
        double overallConfidence,
        int nBeats,
        List<String> warnings,
        boolean hasNarrative,
        String cleanImageUrl,
        String annotatedImageUrl,
        int maxConditionShortfall,
        OffsetDateTime createdAt) {
}
