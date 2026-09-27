package com.cardiosaarthi.review.cases;

import java.time.OffsetDateTime;

/**
 * One measured quantity as the review console shows it.
 *
 * <p>Both numbers are present at once and neither replaces the other:
 * {@code value} is what the engine computed, {@code correctedValue} is what a
 * reviewer changed it to. The console shows the engine's number alongside its
 * spread and confidence so a reviewer can see why it is being questioned, and
 * the difference between the two is the evidence that validates the engine.
 *
 * @param mad    median absolute deviation across beats -- spread, not standard
 *               deviation, because one artefactual beat cannot move a median
 * @param status OK, NEEDS_REVIEW, NOT_MEASURABLE or FAILED. NOT_MEASURABLE is a
 *               finding: a PR interval genuinely does not exist without a P wave,
 *               and the console must show that rather than an empty box
 */
public record MeasurementView(
        String name,
        Double value,
        Double mad,
        String unit,
        int nBeats,
        Double confidence,
        String status,
        String flag,
        Double refLow,
        Double refHigh,
        Double correctedValue,
        Long correctedBy,
        OffsetDateTime correctedAt) {

    public boolean isCorrected() {
        return correctedValue != null;
    }

    /** What a student would be graded against today. */
    public Double servedValue() {
        return correctedValue != null ? correctedValue : value;
    }
}
