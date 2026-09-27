package com.cardiosaarthi.review.study;

import java.util.HashSet;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * What the platform knows the answer to be, read from the database.
 *
 * <p>Numeric steps are read from {@code v_served_measurements}, which is the
 * reviewer's correction where one exists and the engine's value otherwise, and
 * which contains nothing at all for an unapproved case. A student therefore
 * cannot be graded against a number no reviewer has stood behind.
 *
 * <p>Nothing here consults a diagnosis. The cardiologist's label says what the
 * ECG shows; it does not say what a student should have measured, and using it
 * as an answer key would let an inherited diagnosis stand in for a measurement.
 */
@Repository
public class GroundTruthRepository {

    private final JdbcClient db;

    GroundTruthRepository(JdbcClient db) {
        this.db = db;
    }

    /** One served measurement: the value a student is graded against, and its status. */
    private record Served(Double value, String unit, String status) {
    }

    public GroundTruth forStep(long caseId, InterpretationStep step) {
        return switch (step.concept()) {
            case "rate", "pr_interval", "qrs", "qt_interval" -> numeric(caseId, step);
            case "rhythm" -> rhythm(caseId, step);
            case "axis" -> categorical(caseId, step, "axis_category");
            case "p_waves" -> pWaves(caseId, step);
            case "st_segment" -> stSegment(caseId, step);
            // The engine locates the T wave to measure QT but never measures its
            // polarity, so there is no computed answer to compare against. Said
            // plainly rather than guessed at from the diagnosis label.
            case "t_waves" -> GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The measurement engine does not yet compute T-wave polarity, so this step "
                            + "cannot be marked. It is skipped rather than guessed.");
            default -> GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "No ground truth is defined for '" + step.concept() + "'.");
        };
    }

    private GroundTruth numeric(long caseId, InterpretationStep step) {
        Optional<Served> served = db.sql("""
                SELECT value, unit, status FROM v_served_measurements
                WHERE case_id = :caseId AND name = :name
                """)
                .param("caseId", caseId)
                .param("name", step.measure())
                .query((rs, n) -> {
                    double value = rs.getDouble("value");
                    return new Served(rs.wasNull() ? null : value, rs.getString("unit"), rs.getString("status"));
                })
                .optional();

        if (served.isEmpty()) {
            // Either the case is not approved, or the engine produced nothing for
            // this measure at all.
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "No served value for " + step.measure() + " on this case.");
        }

        Served found = served.get();
        boolean notMeasurable = "NOT_MEASURABLE".equals(found.status()) || found.value() == null;

        return GroundTruth.numeric(
                step.step(), step.concept(), found.value(), found.unit(),
                step.toleranceAbs(), step.tolerancePct(), notMeasurable);
    }

    /**
     * The rhythm, unless the engine and the cardiologist disagree about it.
     *
     * <p>Atrial fibrillation and flutter are irregularly irregular by definition.
     * On 10 of the 50 fibrillation cases in the bank the rhythm classifier
     * instead called the rhythm regularly irregular, usually because ectopic
     * beats gave the R-R series a periodic-looking autocorrelation. A student
     * answering "irregularly irregular" on one of those -- the textbook answer,
     * and the right one -- would be marked wrong by the platform.
     *
     * <p>That is risk 1 in the brief exactly: a measurement the platform is
     * confident about and wrong about, marking a correct student answer
     * incorrect. Neither side is assumed right here. The step is simply not
     * marked, the same resolution the engine uses when an inherited diagnosis
     * contradicts a computed P-wave measurement.
     */
    private GroundTruth rhythm(long caseId, InterpretationStep step) {
        GroundTruth computed = categorical(caseId, step, "rhythm_regularity");
        if (!computed.available()) {
            return computed;
        }

        boolean fibrillatingByLabel = Boolean.TRUE.equals(db.sql("""
                SELECT scp_codes ?? 'AFIB' OR scp_codes ?? 'AFLT'
                FROM cases WHERE id = :caseId
                """)
                .param("caseId", caseId)
                .query(Boolean.class)
                .optional()
                .orElse(false));

        if (fibrillatingByLabel && !"IRREGULARLY_IRREGULAR".equals(computed.category())) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The cardiologist's annotation and the rhythm classifier disagree about this "
                            + "recording, so the step is not marked. A student is not marked wrong "
                            + "for a disagreement between the platform and the label.");
        }
        return computed;
    }

    private GroundTruth categorical(long caseId, InterpretationStep step, String column) {
        String value = db.sql("SELECT " + column + " FROM cases WHERE id = :caseId")
                .param("caseId", caseId)
                .query(String.class)
                .optional()
                .orElse(null);

        if (value == null) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The engine did not determine the " + step.concept() + " for this case.");
        }
        if ("INDETERMINATE".equals(value)) {
            // The engine saying it could not tell is not an answer to grade a
            // student against. Marking them wrong for disagreeing with a
            // non-answer would be the platform's fault presented as theirs.
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "The engine could not determine the " + step.concept()
                            + " for this case, so the step is not marked.");
        }
        return GroundTruth.categorical(step.step(), step.concept(), value);
    }

    /**
     * Whether P waves are present.
     *
     * <p>Derived from the P duration rather than stored separately: a P duration
     * the engine reports as NOT_MEASURABLE means it found no P wave to measure,
     * which is the same statement.
     */
    private GroundTruth pWaves(long caseId, InterpretationStep step) {
        Optional<String> status = db.sql("""
                SELECT status FROM v_served_measurements
                WHERE case_id = :caseId AND name = 'p_duration'
                """)
                .param("caseId", caseId)
                .query(String.class)
                .optional();

        if (status.isEmpty()) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "No served P-wave measurement for this case.");
        }
        boolean absent = "NOT_MEASURABLE".equals(status.get());
        return GroundTruth.categorical(step.step(), step.concept(), absent ? "ABSENT" : "PRESENT");
    }

    /** Which leads deviate, and in which direction. */
    private GroundTruth stSegment(long caseId, InterpretationStep step) {
        Map<String, Set<String>> byFinding = Map.of(
                "ELEVATION", new HashSet<>(),
                "DEPRESSION", new HashSet<>());

        var rows = db.sql("""
                SELECT lead, finding FROM case_st_deviations
                WHERE case_id = :caseId AND finding <> 'NORMAL'
                """)
                .param("caseId", caseId)
                .query((rs, n) -> Map.entry(rs.getString("finding"), rs.getString("lead")))
                .list();

        // A case with no ST deviation is a perfectly gradable case whose answer
        // is "none", so an empty result is not the same as no ground truth. The
        // case's existence is what is checked, not the row count.
        boolean caseExists = Boolean.TRUE.equals(db.sql("SELECT true FROM cases WHERE id = :caseId")
                .param("caseId", caseId)
                .query(Boolean.class)
                .optional()
                .orElse(false));
        if (!caseExists) {
            return GroundTruth.unavailable(step.step(), step.concept(), step.answerKind(),
                    "No such case.");
        }

        for (var row : rows) {
            byFinding.getOrDefault(row.getKey(), new HashSet<>()).add(row.getValue());
        }
        return GroundTruth.leads(step.step(), step.concept(),
                Set.copyOf(byFinding.get("ELEVATION")), Set.copyOf(byFinding.get("DEPRESSION")));
    }
}
