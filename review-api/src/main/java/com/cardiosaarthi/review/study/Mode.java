package com.cardiosaarthi.review.study;

/**
 * How a session behaves.
 *
 * <p>Section 6 of the brief splits the persona configuration in two, and the
 * split is load-bearing. Tone, depth and word limit are read by the model.
 * Everything on this enum -- how many attempts a step allows, whether a hint
 * precedes an explanation, whether feedback is held to the end -- is read by the
 * orchestrator and is never shown to the model.
 *
 * <p>The reason is that these decide control flow. A model that knew it was in
 * examiner mode could decide to explain anyway; a model that never sees the
 * setting cannot.
 *
 * @param maxAttempts            attempts allowed on a step before it advances
 * @param hintBeforeExplanation  whether a first wrong answer gets a hint rather
 *                               than the full explanation
 * @param deferFeedbackToEnd     examiner mode: the student works through the
 *                               whole case and is told nothing until the end
 */
public enum Mode {

    BEGINNER_TUTOR(2, true, false),
    CLINICAL_MENTOR(1, true, false),
    EXAMINER(1, false, true);

    private final int maxAttempts;
    private final boolean hintBeforeExplanation;
    private final boolean deferFeedbackToEnd;

    Mode(int maxAttempts, boolean hintBeforeExplanation, boolean deferFeedbackToEnd) {
        this.maxAttempts = maxAttempts;
        this.hintBeforeExplanation = hintBeforeExplanation;
        this.deferFeedbackToEnd = deferFeedbackToEnd;
    }

    public int maxAttempts() {
        return maxAttempts;
    }

    public boolean hintBeforeExplanation() {
        return hintBeforeExplanation;
    }

    public boolean deferFeedbackToEnd() {
        return deferFeedbackToEnd;
    }
}
