package com.cardiosaarthi.review.review;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * What the server actually recorded.
 *
 * <p>{@code unchangedCorrections} is reported rather than silently dropped: if a
 * reviewer submits a correction whose value equals the engine's, nothing is
 * written for it, and they should be told that instead of believing they changed
 * something.
 *
 * @param pendingRemaining cases still awaiting review, so the console can show
 *                         progress without a second request
 */
public record ReviewOutcome(
        long caseId,
        ReviewAction action,
        String reviewStatus,
        long reviewerId,
        OffsetDateTime reviewedAt,
        List<String> correctionsRecorded,
        List<String> unchangedCorrections,
        int pendingRemaining) {
}
