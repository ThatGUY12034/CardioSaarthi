package com.cardiosaarthi.review.study;

/** What grading concluded, as distinct from whether the student was right. */
public enum GradeOutcome {
    CORRECT,
    INCORRECT,
    /**
     * The platform cannot mark this step, so the student is not marked wrong for
     * it.
     *
     * <p>Step 8 is the live case: the engine locates the T wave in order to
     * measure QT but never measures its polarity, so there is no computed answer
     * to compare against. Marking a student wrong against a value the platform
     * does not have would be exactly the failure the whole design is arranged to
     * prevent, and quietly marking them right would teach nothing.
     */
    NOT_GRADABLE
}
