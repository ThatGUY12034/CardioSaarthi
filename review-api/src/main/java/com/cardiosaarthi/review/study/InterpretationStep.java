package com.cardiosaarthi.review.study;

/**
 * One of the nine steps, as defined in the database.
 *
 * <p>Held as data, not as an enum in code, for one reason: question 1 on the
 * brief's list for nursing faculty is whether the tolerances are clinically
 * acceptable. When they answer, that changes a row rather than the grading
 * logic.
 *
 * @param measure      the served measurement this step is graded against, for
 *                     numeric steps; null for the categorical ones
 * @param toleranceAbs absolute tolerance, e.g. 20 ms on the PR interval
 * @param tolerancePct proportional tolerance, e.g. 10% on the rate. A step has
 *                     one or the other, never both.
 */
public record InterpretationStep(
        int step,
        String concept,
        String label,
        AnswerKind answerKind,
        String measure,
        Double toleranceAbs,
        Double tolerancePct) {
}
