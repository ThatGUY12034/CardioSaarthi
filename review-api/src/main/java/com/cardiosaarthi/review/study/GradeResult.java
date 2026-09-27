package com.cardiosaarthi.review.study;

/**
 * The verdict on one submitted answer.
 *
 * <p>{@code expected} is carried so the orchestrator can decide what to say, but
 * it is emphatically not for showing to a student on a first wrong attempt: the
 * persona rules forbid a hint that contains the correct value, and handing it
 * over here would make that impossible to honour.
 *
 * @param errorLabel one of the ~30 codes in the error_labels table, or null when
 *                   correct. It drives the feedback, part of the explanation
 *                   cache key, and the faculty analytics.
 * @param detail     a sentence a reviewer or developer could act on; not student-facing
 */
public record GradeResult(
        GradeOutcome outcome,
        String errorLabel,
        Object expected,
        String unit,
        String detail) {

    public boolean correct() {
        return outcome == GradeOutcome.CORRECT;
    }

    static GradeResult correct(Object expected, String unit) {
        return new GradeResult(GradeOutcome.CORRECT, null, expected, unit, null);
    }

    static GradeResult wrong(String errorLabel, Object expected, String unit, String detail) {
        return new GradeResult(GradeOutcome.INCORRECT, errorLabel, expected, unit, detail);
    }

    static GradeResult notGradable(String reason) {
        return new GradeResult(GradeOutcome.NOT_GRADABLE, null, null, null, reason);
    }
}
