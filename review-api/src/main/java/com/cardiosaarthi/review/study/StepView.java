package com.cardiosaarthi.review.study;

import java.util.List;
import java.util.Map;

/**
 * A step as the student console needs it: what it asks, and what it accepts.
 *
 * <p>The accepted values are served rather than duplicated in the client. A
 * console with its own copy of the rhythm options will eventually disagree with
 * the grader about what a valid answer is, and the student is the one who finds
 * out.
 *
 * @param options       the answers a categorical step accepts, in the order they
 *                      should be offered
 * @param allowsAbsent  whether "this cannot be measured" is a valid answer. On a
 *                      rhythm with no P waves it is the correct one, so the
 *                      console has to offer it.
 * @param gradable      false where the platform has no computed answer. The step
 *                      is still asked -- working through it is the point -- but
 *                      the student is told it will not be marked rather than
 *                      being marked against nothing.
 */
public record StepView(
        int step,
        String concept,
        String label,
        AnswerKind answerKind,
        String unit,
        List<String> options,
        boolean allowsAbsent,
        boolean gradable,
        String note) {

    /** Mirrors what the grader and the correction validator accept. */
    private static final Map<String, List<String>> OPTIONS = Map.of(
            "rhythm", List.of("REGULAR", "REGULARLY_IRREGULAR", "IRREGULARLY_IRREGULAR"),
            "axis", List.of("NORMAL", "LEFT", "RIGHT", "EXTREME"),
            "p_waves", List.of("PRESENT", "ABSENT"),
            // Offered so the step can be worked through, though nothing marks it
            // yet: the engine measures the T wave's position for the QT interval
            // and not its polarity.
            "t_waves", List.of("UPRIGHT", "INVERTED", "FLAT", "BIPHASIC"));

    private static final String NOT_GRADED =
            "This step is not marked yet: the measurement engine does not compute T-wave polarity. "
                    + "Answer it anyway; working through every step in order is the habit being built.";

    public static StepView of(InterpretationStep step) {
        boolean gradable = !"t_waves".equals(step.concept());
        return new StepView(
                step.step(),
                step.concept(),
                step.label(),
                step.answerKind(),
                unitFor(step),
                OPTIONS.getOrDefault(step.concept(), List.of()),
                // Every numeric measure can legitimately be unmeasurable, and the
                // ST step's "no lead deviates" is the same kind of answer.
                step.answerKind() != AnswerKind.CATEGORICAL,
                gradable,
                gradable ? null : NOT_GRADED);
    }

    private static String unitFor(InterpretationStep step) {
        if (step.answerKind() != AnswerKind.NUMERIC) {
            return null;
        }
        return "heart_rate".equals(step.measure()) ? "bpm" : "ms";
    }
}
