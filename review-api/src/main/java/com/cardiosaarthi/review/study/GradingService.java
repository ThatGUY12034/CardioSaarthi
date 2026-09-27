package com.cardiosaarthi.review.study;

import java.util.Set;

import org.springframework.stereotype.Service;

/**
 * Marks one answer against what the platform computed.
 *
 * <p>Entirely deterministic, and deliberately so. Section 5.1 of the brief is
 * explicit that the model is never asked whether a student was right: it writes
 * explanations, and this decides correctness. That separation is what lets a
 * wrong answer be explained without the explanation being the thing that decided
 * it was wrong.
 *
 * <p>Three outcomes, not two. A step the platform cannot mark returns
 * NOT_GRADABLE rather than a guess in either direction, because marking a
 * student wrong against a value the platform does not have is precisely the
 * failure this project is arranged to prevent.
 */
@Service
public class GradingService {

    private final GroundTruthRepository groundTruths;
    private final StepRepository steps;

    GradingService(GroundTruthRepository groundTruths, StepRepository steps) {
        this.groundTruths = groundTruths;
        this.steps = steps;
    }

    public GradeResult grade(long caseId, int stepNumber, StudentAnswer answer) {
        InterpretationStep step = steps.byStep(stepNumber)
                .orElseThrow(() -> new IllegalArgumentException("no step " + stepNumber));
        return grade(caseId, step, answer);
    }

    public GradeResult grade(long caseId, InterpretationStep step, StudentAnswer answer) {
        GroundTruth truth = groundTruths.forStep(caseId, step);

        if (!truth.available()) {
            return GradeResult.notGradable(truth.unavailableReason());
        }
        if (answer == null || answer.isEmpty()) {
            return GradeResult.wrong("NO_ANSWER", expectedOf(truth), truth.unit(),
                    "Nothing was submitted for this step.");
        }

        return switch (truth.kind()) {
            case NUMERIC -> gradeNumeric(truth, answer);
            case CATEGORICAL -> gradeCategorical(truth, answer);
            case MULTI_CATEGORICAL -> gradeLeads(truth, answer);
        };
    }

    // -----------------------------------------------------------------------
    // numeric
    // -----------------------------------------------------------------------
    private GradeResult gradeNumeric(GroundTruth truth, StudentAnswer answer) {
        // "There is no PR interval here" is an answer, and on a rhythm with no P
        // waves it is the right one. Getting this backwards in either direction
        // is a distinct and clinically important mistake, so each has its own
        // error label.
        if (truth.notMeasurable()) {
            if (answer.claimsNotPresent()) {
                return GradeResult.correct("not measurable", truth.unit());
            }
            return GradeResult.wrong(
                    notMeasurableErrorFor(truth.concept()), "not measurable", truth.unit(),
                    "The student gave a value for something the recording does not contain.");
        }
        if (answer.claimsNotPresent()) {
            return GradeResult.wrong(
                    presentButCalledAbsentErrorFor(truth.concept()), truth.value(), truth.unit(),
                    "The student said this could not be measured, but it was measured.");
        }
        if (answer.value() == null) {
            return GradeResult.wrong("ANSWER_NOT_UNDERSTOOD", truth.value(), truth.unit(),
                    "A numeric step needs a number.");
        }

        double expected = truth.value();
        double tolerance = truth.toleranceFor(expected);
        double difference = answer.value() - expected;

        if (Math.abs(difference) <= tolerance) {
            return GradeResult.correct(expected, truth.unit());
        }
        return GradeResult.wrong(
                directionalError(truth.concept(), difference > 0),
                expected,
                truth.unit(),
                "Submitted %.0f against %.0f %s, outside the %.0f %s tolerance."
                        .formatted(answer.value(), expected, truth.unit(), tolerance, truth.unit()));
    }

    /** Over- and under-estimating are different mistakes and are taught differently. */
    private String directionalError(String concept, boolean tooHigh) {
        return switch (concept) {
            case "rate" -> tooHigh ? "RATE_OVERESTIMATED" : "RATE_UNDERESTIMATED";
            case "pr_interval" -> tooHigh ? "PR_OVERESTIMATED" : "PR_UNDERESTIMATED";
            case "qrs" -> tooHigh ? "QRS_OVERESTIMATED" : "QRS_UNDERESTIMATED";
            case "qt_interval" -> tooHigh ? "QT_OVERESTIMATED" : "QT_UNDERESTIMATED";
            default -> "ANSWER_NOT_UNDERSTOOD";
        };
    }

    private String notMeasurableErrorFor(String concept) {
        // Reporting a PR interval on a fibrillating rhythm is the specific
        // mistake the case bank is full of examples of.
        return "pr_interval".equals(concept) ? "PR_REPORTED_WHEN_ABSENT" : "ANSWER_NOT_UNDERSTOOD";
    }

    private String presentButCalledAbsentErrorFor(String concept) {
        return "pr_interval".equals(concept) ? "P_PRESENT_CALLED_ABSENT" : "ANSWER_NOT_UNDERSTOOD";
    }

    // -----------------------------------------------------------------------
    // categorical
    // -----------------------------------------------------------------------
    private GradeResult gradeCategorical(GroundTruth truth, StudentAnswer answer) {
        if (answer.category() == null || answer.category().isBlank()) {
            return GradeResult.wrong("ANSWER_NOT_UNDERSTOOD", truth.category(), null,
                    "This step expects one of a fixed set of answers.");
        }

        String submitted = answer.category().trim().toUpperCase();
        String expected = truth.category();

        if (submitted.equals(expected)) {
            return GradeResult.correct(expected, null);
        }
        return GradeResult.wrong(
                categoricalError(truth.concept(), submitted, expected), expected, null,
                "Submitted %s against %s.".formatted(submitted, expected));
    }

    private String categoricalError(String concept, String submitted, String expected) {
        return switch (concept) {
            case "rhythm" -> rhythmError(submitted, expected);
            case "axis" -> axisError(submitted, expected);
            case "p_waves" -> "ABSENT".equals(expected)
                    ? "P_ABSENT_CALLED_PRESENT"
                    : "P_PRESENT_CALLED_ABSENT";
            default -> "ANSWER_NOT_UNDERSTOOD";
        };
    }

    private String rhythmError(String submitted, String expected) {
        boolean expectedRegular = "REGULAR".equals(expected);
        boolean submittedRegular = "REGULAR".equals(submitted);
        if (expectedRegular && !submittedRegular) {
            return "REGULAR_CALLED_IRREGULAR";
        }
        if (!expectedRegular && submittedRegular) {
            return "IRREGULAR_CALLED_REGULAR";
        }
        // Both irregular, but the wrong kind: regularly irregular is Wenckebach,
        // irregularly irregular is fibrillation, and confusing them is a
        // different error from missing the irregularity entirely.
        return "IRREGULARITY_PATTERN_CONFUSED";
    }

    private String axisError(String submitted, String expected) {
        if ("NORMAL".equals(expected)) {
            return "AXIS_NORMAL_CALLED_DEVIATED";
        }
        if ("NORMAL".equals(submitted)) {
            return "AXIS_DEVIATION_MISSED";
        }
        return "AXIS_WRONG_QUADRANT";
    }

    // -----------------------------------------------------------------------
    // leads
    // -----------------------------------------------------------------------
    private GradeResult gradeLeads(GroundTruth truth, StudentAnswer answer) {
        Set<String> expected = truth.deviatingLeads();
        Set<String> submitted = answer.leadSet().stream()
                .map(lead -> lead.trim().replace("avr", "aVR").replace("avl", "aVL").replace("avf", "aVF"))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

        if (expected.equals(submitted)) {
            return GradeResult.correct(expected, null);
        }

        if (expected.isEmpty()) {
            return GradeResult.wrong("ST_NORMAL_CALLED_ABNORMAL", expected, null,
                    "No lead deviates; the student named " + submitted + ".");
        }
        if (submitted.isEmpty()) {
            // Which direction was missed decides which lesson this is.
            return GradeResult.wrong(
                    truth.elevationLeads().isEmpty() ? "ST_DEPRESSION_MISSED" : "ST_ELEVATION_MISSED",
                    expected, null,
                    "Deviation in " + expected + " was not reported.");
        }
        // Something was seen, but in the wrong leads -- the finding is right and
        // the territory is wrong, which is a localisation error, not a detection
        // one.
        return GradeResult.wrong("ST_WRONG_TERRITORY", expected, null,
                "Named " + submitted + " against " + expected + ".");
    }

    private Object expectedOf(GroundTruth truth) {
        return switch (truth.kind()) {
            case NUMERIC -> truth.notMeasurable() ? "not measurable" : truth.value();
            case CATEGORICAL -> truth.category();
            case MULTI_CATEGORICAL -> truth.deviatingLeads();
        };
    }
}
