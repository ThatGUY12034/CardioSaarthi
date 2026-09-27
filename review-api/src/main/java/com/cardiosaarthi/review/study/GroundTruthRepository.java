package com.cardiosaarthi.review.study;

import java.util.Optional;
import java.util.Set;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * What the platform knows the answer to be, read from the database.
 *
 * <p>Everything comes from {@code v_served_parameters}, which holds all nine
 * interpretation parameters in one shape, each as the reviewer corrected it or
 * as the engine computed it, and which contains nothing at all for an unapproved
 * case. A student therefore cannot be graded against a value no reviewer has
 * stood behind, and a reviewer who corrects a rhythm has thereby changed what a
 * right answer is.
 *
 * <p>Nothing here consults a diagnosis as an answer key. The cardiologist's
 * label says what the ECG shows; it does not say what a student should have
 * measured. It is used in exactly one way: to notice when it contradicts the
 * engine, and decline to mark the step rather than pick a side.
 */
@Repository
public class GroundTruthRepository {

    private final JdbcClient db;

    GroundTruthRepository(JdbcClient db) {
        this.db = db;
    }

    /** One served parameter, whichever kind it is. */
    private record Served(String kind, Double value, String text, String unit, String status) {
    }

    public GroundTruth forStep(long caseId, InterpretationStep step) {
        String name = parameterName(step);
        Optional<Served> served = load(caseId, name);

        if (served.isEmpty()) {
            // Either the case is not approved, or the engine produced nothing
            // for this parameter at all.
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "No served value for " + name + " on this case.");
        }

        Served found = served.get();
        return switch (step.answerKind()) {
            case NUMERIC -> numeric(step, found);
            case CATEGORICAL -> categorical(caseId, step, found);
            case MULTI_CATEGORICAL -> leads(caseId, step, found);
        };
    }

    /** Numeric steps are graded against a measure; the rest are named directly. */
    private String parameterName(InterpretationStep step) {
        return step.measure() != null ? step.measure() : step.concept();
    }

    private Optional<Served> load(long caseId, String name) {
        return db.sql("""
                SELECT kind, value, text_value, unit, status
                FROM v_served_parameters
                WHERE case_id = :caseId AND name = :name
                """)
                .param("caseId", caseId)
                .param("name", name)
                .query((rs, n) -> {
                    double value = rs.getDouble("value");
                    return new Served(
                            rs.getString("kind"),
                            rs.wasNull() ? null : value,
                            rs.getString("text_value"),
                            rs.getString("unit"),
                            rs.getString("status"));
                })
                .optional();
    }

    private GroundTruth numeric(InterpretationStep step, Served served) {
        // A reviewer may correct a numeric measure to "there is nothing here to
        // measure", which is a different statement from a missing value.
        boolean notMeasurable = "NOT_MEASURABLE".equals(served.status())
                || "NOT_MEASURABLE".equals(served.text())
                || served.value() == null;

        return GroundTruth.numeric(step.step(), step.concept(), served.value(), served.unit(),
                step.toleranceAbs(), step.tolerancePct(), notMeasurable);
    }

    private GroundTruth categorical(long caseId, InterpretationStep step, Served served) {
        String value = served.text();

        if (value == null || value.isBlank()) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The engine did not determine the " + step.concept() + " for this case.");
        }
        if ("INDETERMINATE".equals(value)) {
            // The engine saying it could not tell is not an answer key. Marking a
            // student wrong for disagreeing with a non-answer would present the
            // platform's limitation as their mistake.
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The " + step.concept() + " could not be determined for this case, "
                            + "so the step is not marked.");
        }
        if ("rhythm".equals(step.concept()) && rhythmContradictsTheLabel(caseId, value)) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The cardiologist's annotation and the rhythm classifier disagree about this "
                            + "recording, so the step is not marked. A reviewer can settle it by "
                            + "correcting the rhythm.");
        }
        return GroundTruth.categorical(step.step(), step.concept(), value);
    }

    /**
     * Whether the rhythm on record contradicts the inherited diagnosis.
     *
     * <p>Atrial fibrillation and flutter are irregularly irregular by definition.
     * On 10 of the 50 fibrillation cases in the bank the classifier instead
     * called the rhythm regularly irregular, usually because ectopic beats gave
     * the R-R series a periodic-looking autocorrelation. A student answering
     * "irregularly irregular" -- the textbook answer, and the right one -- would
     * be marked wrong.
     *
     * <p>Neither side is assumed correct; the step is simply not marked. Note
     * that the value checked here is the served one, so a reviewer who corrects
     * the rhythm resolves the conflict and the step becomes markable again.
     */
    private boolean rhythmContradictsTheLabel(long caseId, String servedRhythm) {
        if ("IRREGULARLY_IRREGULAR".equals(servedRhythm)) {
            return false;
        }
        return Boolean.TRUE.equals(db.sql("""
                SELECT scp_codes ?? 'AFIB' OR scp_codes ?? 'AFLT'
                FROM cases WHERE id = :caseId
                """)
                .param("caseId", caseId)
                .query(Boolean.class)
                .optional()
                .orElse(false));
    }

    private GroundTruth leads(long caseId, InterpretationStep step, Served served) {
        String value = served.text() == null ? "" : served.text().trim();
        Set<String> deviating = value.isBlank() ? Set.of() : Set.of(value.split(","));

        // Which leads deviate is the served value, so a reviewer's correction
        // decides it. The direction is read from the engine separately and only
        // to choose between "you missed an elevation" and "you missed a
        // depression"; a reviewer who edits the lead set is not asked to restate
        // the direction, so this stays the engine's view of it.
        Set<String> elevated = Set.copyOf(db.sql("""
                SELECT lead FROM case_st_deviations
                WHERE case_id = :caseId AND finding = 'ELEVATION'
                """)
                .param("caseId", caseId)
                .query(String.class)
                .list());

        Set<String> depressed = deviating.stream()
                .filter(lead -> !elevated.contains(lead))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

        return GroundTruth.leads(step.step(), step.concept(),
                elevated.stream().filter(deviating::contains)
                        .collect(java.util.stream.Collectors.toUnmodifiableSet()),
                depressed);
    }
}
