package com.cardiosaarthi.review.study;

import java.util.Set;

/**
 * What the platform knows the answer to be, for one step of one case.
 *
 * <p>Assembled from what a student may legitimately be graded against: the
 * served measurement, which is the reviewer's correction where one exists and
 * the engine's value otherwise. Never the raw computed value when a reviewer has
 * disagreed with it, and never an inherited diagnosis label.
 *
 * @param available     false when the platform has no computed answer for this
 *                      step; the student is then not marked at all
 * @param unavailableReason why, in words a reviewer could act on
 * @param notMeasurable the correct answer is that this cannot be measured -- a
 *                      PR interval on a rhythm with no P waves. A real finding,
 *                      not a gap.
 * @param facultyCorrected whether the value being graded against came from a
 *                      reviewer rather than the engine
 */
public record GroundTruth(
        int step,
        String concept,
        AnswerKind kind,
        boolean available,
        String unavailableReason,
        boolean notMeasurable,
        Double value,
        String unit,
        Double toleranceAbs,
        Double tolerancePct,
        String category,
        Set<String> elevationLeads,
        Set<String> depressionLeads) {

    static GroundTruth unavailable(int step, String concept, AnswerKind kind, String reason) {
        return new GroundTruth(step, concept, kind, false, reason, false,
                null, null, null, null, null, Set.of(), Set.of());
    }

    static GroundTruth numeric(int step, String concept, Double value, String unit,
                               Double toleranceAbs, Double tolerancePct, boolean notMeasurable) {
        return new GroundTruth(step, concept, AnswerKind.NUMERIC, true, null, notMeasurable,
                value, unit, toleranceAbs, tolerancePct, null, Set.of(), Set.of());
    }

    static GroundTruth categorical(int step, String concept, String category) {
        return new GroundTruth(step, concept, AnswerKind.CATEGORICAL, true, null, false,
                null, null, null, null, category, Set.of(), Set.of());
    }

    static GroundTruth leads(int step, String concept, Set<String> elevation, Set<String> depression) {
        return new GroundTruth(step, concept, AnswerKind.MULTI_CATEGORICAL, true, null, false,
                null, null, null, null, null, elevation, depression);
    }

    /**
     * How far from {@link #value} still counts as right.
     *
     * <p>A step carries either an absolute tolerance or a percentage, never both,
     * and which one is clinically meaningful differs: a rate is judged
     * proportionally because being 8 bpm out at 40 bpm and at 160 bpm are not the
     * same error, while an interval is judged absolutely because 20 ms is 20 ms.
     */
    public double toleranceFor(double expected) {
        if (toleranceAbs != null) {
            return toleranceAbs;
        }
        if (tolerancePct != null) {
            return Math.abs(expected) * tolerancePct / 100.0;
        }
        return 0.0;
    }

    /** All leads with any ST deviation, which is what the step asks for. */
    public Set<String> deviatingLeads() {
        return java.util.stream.Stream
                .concat(elevationLeads.stream(), depressionLeads.stream())
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }
}
