package com.cardiosaarthi.review;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.List;

import com.cardiosaarthi.review.study.GradeOutcome;
import com.cardiosaarthi.review.study.GradeResult;
import com.cardiosaarthi.review.study.GradingService;
import com.cardiosaarthi.review.study.StudentAnswer;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Grading, against a real case in a rolled-back transaction.
 *
 * <p>The thing most worth protecting here is that a correct student is never
 * marked wrong. Every numeric test therefore checks both edges of the tolerance,
 * not just the middle, and several check that the platform declines to mark
 * rather than guessing.
 */
@SpringBootTest
@Transactional
@EnabledIf("databaseIsRunning")
class GradingIntegrationTests {

    @Autowired
    private GradingService grading;

    @Autowired
    private JdbcClient db;

    static boolean databaseIsRunning() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", 55432), 500);
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    // -----------------------------------------------------------------------
    // fixtures
    // -----------------------------------------------------------------------
    private long reviewer() {
        return db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash)
                VALUES ('grading.reviewer@example.invalid', 'Grading Reviewer', 'faculty', '$2a$10$x')
                ON CONFLICT (lower(email)) DO UPDATE SET full_name = excluded.full_name
                RETURNING id
                """).query(Long.class).single();
    }

    /** An approved case, because only approved cases have served measurements. */
    private long approvedCase(int ecgId, String rhythm, String axis) {
        long reviewerId = reviewer();
        return db.sql("""
                INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                                   sampling_rate, n_samples, measurement_status, overall_confidence,
                                   raw_measurement, rhythm_regularity, axis_category,
                                   review_status, reviewed_at, reviewed_by)
                VALUES ('test', :ecgId, '1.0.0', '0.2.0', now(), 500, 5000, 'OK', 0.9, '{}'::jsonb,
                        :rhythm, :axis, 'approved', now(), :reviewer)
                RETURNING id
                """)
                .param("ecgId", ecgId)
                .param("rhythm", rhythm)
                .param("axis", axis)
                .param("reviewer", reviewerId)
                .query(Long.class)
                .single();
    }

    private void measure(long caseId, String name, Double value, String unit, String status) {
        db.sql("""
                INSERT INTO case_measurements (case_id, name, value, mad, unit, n_beats, confidence, status, flag)
                VALUES (:caseId, :name, :value, 4.0, :unit, 12, 0.9, :status, 'NORMAL')
                """)
                .param("caseId", caseId)
                .param("name", name)
                .param("value", value)
                .param("unit", unit)
                .param("status", status)
                .update();
    }

    private void st(long caseId, String lead, String finding) {
        db.sql("""
                INSERT INTO case_st_deviations (case_id, lead, deviation_mm, finding)
                VALUES (:caseId, :lead, 2.0, :finding)
                """)
                .param("caseId", caseId).param("lead", lead).param("finding", finding)
                .update();
    }

    private static StudentAnswer number(double value) {
        return new StudentAnswer(value, null, null, null);
    }

    private static StudentAnswer category(String value) {
        return new StudentAnswer(null, null, value, null);
    }

    private static StudentAnswer absent() {
        return new StudentAnswer(null, true, null, null);
    }

    private static StudentAnswer leads(String... names) {
        return new StudentAnswer(null, null, null, List.of(names));
    }

    /**
     * The student asserting that no lead deviates.
     *
     * <p>Distinct from submitting the step with nothing filled in: a blank form
     * is an empty answer, and reading it as "none" would mark a student correct
     * for having answered nothing.
     */
    private static StudentAnswer noDeviation() {
        return new StudentAnswer(null, true, null, List.of());
    }

    // -----------------------------------------------------------------------
    @Nested
    @DisplayName("numeric steps")
    class Numeric {

        @Test
        @DisplayName("the rate tolerance is proportional, so it widens with the rate")
        void rateToleranceIsProportional() {
            // 10% of 80 is 8 bpm. Being 8 out at 40 bpm and at 160 bpm are not
            // the same clinical error, which is why this one is a percentage.
            long caseId = approvedCase(-2001, "REGULAR", "NORMAL");
            measure(caseId, "heart_rate", 80.0, "bpm", "OK");

            assertThat(grading.grade(caseId, 1, number(80)).correct()).isTrue();
            assertThat(grading.grade(caseId, 1, number(88)).correct()).as("exactly on the edge").isTrue();
            assertThat(grading.grade(caseId, 1, number(72)).correct()).as("the other edge").isTrue();
            assertThat(grading.grade(caseId, 1, number(89)).correct()).isFalse();
        }

        @Test
        @DisplayName("interval tolerances are absolute, and both edges count as right")
        void intervalToleranceIsAbsolute() {
            long caseId = approvedCase(-2002, "REGULAR", "NORMAL");
            measure(caseId, "pr_interval", 160.0, "ms", "OK");

            assertThat(grading.grade(caseId, 5, number(180)).correct()).as("+20, the edge").isTrue();
            assertThat(grading.grade(caseId, 5, number(140)).correct()).as("-20, the edge").isTrue();
            assertThat(grading.grade(caseId, 5, number(181)).correct()).isFalse();
            assertThat(grading.grade(caseId, 5, number(139)).correct()).isFalse();
        }

        @Test
        @DisplayName("over- and under-estimating are different errors")
        void directionIsRecorded() {
            long caseId = approvedCase(-2003, "REGULAR", "NORMAL");
            measure(caseId, "qrs_duration", 100.0, "ms", "OK");

            assertThat(grading.grade(caseId, 6, number(140)).errorLabel()).isEqualTo("QRS_OVERESTIMATED");
            assertThat(grading.grade(caseId, 6, number(60)).errorLabel()).isEqualTo("QRS_UNDERESTIMATED");
        }

        @Test
        @DisplayName("a student is graded against the reviewer's correction, not the engine's value")
        void correctionOverridesTheEngine() {
            // The entire point of keeping both numbers. A reviewer who corrects a
            // PR interval has changed what a right answer is.
            long caseId = approvedCase(-2004, "REGULAR", "NORMAL");
            measure(caseId, "pr_interval", 160.0, "ms", "OK");
            db.sql("""
                    INSERT INTO measurement_corrections
                        (case_id, name, computed_value, corrected_value, unit, engine_version, reviewer_id)
                    VALUES (:caseId, 'pr_interval', 160.0, 220.0, 'ms', '0.2.0', :reviewer)
                    """)
                    .param("caseId", caseId).param("reviewer", reviewer())
                    .update();

            assertThat(grading.grade(caseId, 5, number(220)).correct())
                    .as("the reviewer's number is the right answer")
                    .isTrue();
            assertThat(grading.grade(caseId, 5, number(160)).correct())
                    .as("the engine's superseded number is not")
                    .isFalse();
        }

        @Test
        @DisplayName("saying a PR interval cannot be measured is right when there are no P waves")
        void notMeasurableIsARealAnswer() {
            long caseId = approvedCase(-2005, "IRREGULARLY_IRREGULAR", "NORMAL");
            measure(caseId, "pr_interval", null, "ms", "NOT_MEASURABLE");

            assertThat(grading.grade(caseId, 5, absent()).correct()).isTrue();

            GradeResult invented = grading.grade(caseId, 5, number(180));
            assertThat(invented.correct()).isFalse();
            assertThat(invented.errorLabel()).isEqualTo("PR_REPORTED_WHEN_ABSENT");
        }

        @Test
        @DisplayName("claiming absence when the interval was measured is its own error")
        void absenceClaimedWhenPresent() {
            long caseId = approvedCase(-2006, "REGULAR", "NORMAL");
            measure(caseId, "pr_interval", 160.0, "ms", "OK");

            assertThat(grading.grade(caseId, 5, absent()).errorLabel()).isEqualTo("P_PRESENT_CALLED_ABSENT");
        }
    }

    @Nested
    @DisplayName("categorical steps")
    class Categorical {

        @Test
        @DisplayName("rhythm errors distinguish missing irregularity from confusing its kind")
        void rhythmErrorsAreSpecific() {
            long regular = approvedCase(-2010, "REGULAR", "NORMAL");
            long fibrillating = approvedCase(-2011, "IRREGULARLY_IRREGULAR", "NORMAL");
            long wenckebach = approvedCase(-2012, "REGULARLY_IRREGULAR", "NORMAL");

            assertThat(grading.grade(regular, 2, category("REGULAR")).correct()).isTrue();
            assertThat(grading.grade(regular, 2, category("IRREGULARLY_IRREGULAR")).errorLabel())
                    .isEqualTo("REGULAR_CALLED_IRREGULAR");
            assertThat(grading.grade(fibrillating, 2, category("REGULAR")).errorLabel())
                    .isEqualTo("IRREGULAR_CALLED_REGULAR");
            // Wenckebach called fibrillation: both irregular, wrong kind.
            assertThat(grading.grade(wenckebach, 2, category("IRREGULARLY_IRREGULAR")).errorLabel())
                    .isEqualTo("IRREGULARITY_PATTERN_CONFUSED");
        }

        @Test
        @DisplayName("answers are case-insensitive, because a student types them")
        void answersAreCaseInsensitive() {
            long caseId = approvedCase(-2013, "REGULAR", "NORMAL");
            assertThat(grading.grade(caseId, 2, category("regular")).correct()).isTrue();
        }

        @Test
        @DisplayName("axis errors separate missing a deviation from getting the quadrant wrong")
        void axisErrorsAreSpecific() {
            long leftAxis = approvedCase(-2014, "REGULAR", "LEFT");
            long normalAxis = approvedCase(-2015, "REGULAR", "NORMAL");

            assertThat(grading.grade(leftAxis, 3, category("NORMAL")).errorLabel())
                    .isEqualTo("AXIS_DEVIATION_MISSED");
            assertThat(grading.grade(leftAxis, 3, category("RIGHT")).errorLabel())
                    .isEqualTo("AXIS_WRONG_QUADRANT");
            assertThat(grading.grade(normalAxis, 3, category("LEFT")).errorLabel())
                    .isEqualTo("AXIS_NORMAL_CALLED_DEVIATED");
        }

        @Test
        @DisplayName("P-wave presence comes from the measurement, not from the diagnosis")
        void pWavePresenceIsDerivedFromTheMeasurement() {
            long withP = approvedCase(-2016, "REGULAR", "NORMAL");
            measure(withP, "p_duration", 100.0, "ms", "OK");
            long withoutP = approvedCase(-2017, "IRREGULARLY_IRREGULAR", "NORMAL");
            measure(withoutP, "p_duration", null, "ms", "NOT_MEASURABLE");

            assertThat(grading.grade(withP, 4, category("PRESENT")).correct()).isTrue();
            assertThat(grading.grade(withoutP, 4, category("ABSENT")).correct()).isTrue();
            assertThat(grading.grade(withoutP, 4, category("PRESENT")).errorLabel())
                    .isEqualTo("P_ABSENT_CALLED_PRESENT");
        }
    }

    @Nested
    @DisplayName("the ST step, which is about territory")
    class StSegment {

        @Test
        @DisplayName("naming exactly the deviating leads is correct")
        void exactLeadsAreCorrect() {
            long caseId = approvedCase(-2020, "REGULAR", "NORMAL");
            st(caseId, "V2", "ELEVATION");
            st(caseId, "V3", "ELEVATION");

            assertThat(grading.grade(caseId, 7, leads("V2", "V3")).correct()).isTrue();
            assertThat(grading.grade(caseId, 7, leads("V3", "V2")).correct())
                    .as("order cannot matter")
                    .isTrue();
        }

        @Test
        @DisplayName("a case with no deviation is gradable, and its answer is none")
        void noDeviationIsAnAnswer() {
            long caseId = approvedCase(-2021, "REGULAR", "NORMAL");
            st(caseId, "V2", "NORMAL");

            assertThat(grading.grade(caseId, 7, noDeviation()).correct())
                    .as("claiming nothing deviates, on a case where nothing does")
                    .isTrue();
            assertThat(grading.grade(caseId, 7, leads("V2")).errorLabel())
                    .isEqualTo("ST_NORMAL_CALLED_ABNORMAL");
        }

        @Test
        @DisplayName("right finding, wrong leads is a localisation error, not a missed one")
        void wrongTerritoryIsItsOwnError() {
            long caseId = approvedCase(-2022, "REGULAR", "NORMAL");
            st(caseId, "II", "ELEVATION");
            st(caseId, "III", "ELEVATION");

            assertThat(grading.grade(caseId, 7, leads("V2", "V3")).errorLabel())
                    .isEqualTo("ST_WRONG_TERRITORY");
        }

        @Test
        @DisplayName("missing the deviation records which direction was missed")
        void missedDeviationRecordsDirection() {
            long elevated = approvedCase(-2023, "REGULAR", "NORMAL");
            st(elevated, "V2", "ELEVATION");
            long depressed = approvedCase(-2024, "REGULAR", "NORMAL");
            st(depressed, "V5", "DEPRESSION");

            assertThat(grading.grade(elevated, 7, noDeviation()).errorLabel())
                    .isEqualTo("ST_ELEVATION_MISSED");
            assertThat(grading.grade(depressed, 7, noDeviation()).errorLabel())
                    .isEqualTo("ST_DEPRESSION_MISSED");
        }

        @Test
        @DisplayName("a blank ST form is an empty answer, not a claim that nothing deviates")
        void blankFormIsNotAnAssertion() {
            // These are different statements and must not be conflated: reading a
            // blank form as "none" would mark a student correct on every normal
            // case for having answered nothing at all.
            long caseId = approvedCase(-2025, "REGULAR", "NORMAL");
            st(caseId, "V2", "NORMAL");

            assertThat(grading.grade(caseId, 7, leads()).errorLabel()).isEqualTo("NO_ANSWER");
            assertThat(grading.grade(caseId, 7, noDeviation()).correct()).isTrue();
        }
    }

    @Nested
    @DisplayName("refusing to mark")
    class NotGradable {

        @Test
        @DisplayName("a case whose T waves could not be measured is still not marked")
        void tWaveStepWithoutAFindingIsNotGradable() {
            // The engine reports no finding when fewer than half the leads could
            // be measured. Marking a student against a value the platform does
            // not have is the failure this project exists to prevent, and that
            // is now decided per case rather than for the step as a whole.
            long caseId = approvedCase(-2030, "REGULAR", "NORMAL");

            GradeResult result = grading.grade(caseId, 8, category("INVERTED"));
            assertThat(result.outcome()).isEqualTo(GradeOutcome.NOT_GRADABLE);
            assertThat(result.correct()).isFalse();
        }

        @Test
        @DisplayName("an indeterminate engine result is not marked either")
        void indeterminateIsNotGradable() {
            // The engine saying it could not tell is not an answer key. Marking a
            // student wrong for disagreeing with a non-answer would present the
            // platform's limitation as their mistake.
            long caseId = approvedCase(-2031, "INDETERMINATE", "NORMAL");

            assertThat(grading.grade(caseId, 2, category("REGULAR")).outcome())
                    .isEqualTo(GradeOutcome.NOT_GRADABLE);
        }

        @Test
        @DisplayName("the rhythm step is not marked when the label and the classifier disagree")
        void rhythmConflictIsNotGradable() {
            // Atrial fibrillation is irregularly irregular by definition. On 10 of
            // the 50 fibrillation cases in the bank the classifier said regularly
            // irregular instead, so a student giving the textbook answer would be
            // marked wrong. Neither side is assumed right: the step is not marked.
            long caseId = approvedCase(-2040, "REGULARLY_IRREGULAR", "NORMAL");
            db.sql("UPDATE cases SET scp_codes = '{\"AFIB\": 100.0}'::jsonb WHERE id = :id")
                    .param("id", caseId).update();

            GradeResult result = grading.grade(caseId, 2, category("IRREGULARLY_IRREGULAR"));
            assertThat(result.outcome()).isEqualTo(GradeOutcome.NOT_GRADABLE);
            assertThat(result.detail()).contains("disagree");
        }

        @Test
        @DisplayName("a fibrillating case the classifier agrees with is still marked normally")
        void rhythmAgreementIsStillGraded() {
            long caseId = approvedCase(-2041, "IRREGULARLY_IRREGULAR", "NORMAL");
            db.sql("UPDATE cases SET scp_codes = '{\"AFIB\": 100.0}'::jsonb WHERE id = :id")
                    .param("id", caseId).update();

            assertThat(grading.grade(caseId, 2, category("IRREGULARLY_IRREGULAR")).correct()).isTrue();
            assertThat(grading.grade(caseId, 2, category("REGULAR")).errorLabel())
                    .isEqualTo("IRREGULAR_CALLED_REGULAR");
        }

        @Test
        @DisplayName("a case with a measured T wave is marked like any other step")
        void tWaveStepIsGradedWhenMeasured() {
            long caseId = approvedCase(-2035, "REGULAR", "NORMAL");
            db.sql("UPDATE cases SET t_wave_finding = 'INVERTED' WHERE id = :id")
                    .param("id", caseId).update();

            assertThat(grading.grade(caseId, 8, category("INVERTED")).correct()).isTrue();

            GradeResult wrong = grading.grade(caseId, 8, category("UPRIGHT"));
            assertThat(wrong.outcome()).isEqualTo(GradeOutcome.INCORRECT);
            assertThat(wrong.errorLabel()).isEqualTo("T_INVERSION_MISSED");
        }

        @Test
        @DisplayName("calling upright T waves inverted is its own error")
        void tWaveFalsePositiveHasItsOwnLabel() {
            long caseId = approvedCase(-2036, "REGULAR", "NORMAL");
            db.sql("UPDATE cases SET t_wave_finding = 'UPRIGHT' WHERE id = :id")
                    .param("id", caseId).update();

            assertThat(grading.grade(caseId, 8, category("INVERTED")).errorLabel())
                    .isEqualTo("T_NORMAL_CALLED_INVERTED");
        }

        @Test
        @DisplayName("an unapproved case has no served measurements and cannot be graded")
        void unapprovedCaseIsNotGradable() {
            long caseId = db.sql("""
                    INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                                       sampling_rate, n_samples, measurement_status, overall_confidence,
                                       raw_measurement, rhythm_regularity)
                    VALUES ('test', -2032, '1.0.0', '0.2.0', now(), 500, 5000, 'OK', 0.9, '{}'::jsonb, 'REGULAR')
                    RETURNING id
                    """).query(Long.class).single();
            measure(caseId, "heart_rate", 80.0, "bpm", "OK");

            assertThat(grading.grade(caseId, 1, number(80)).outcome())
                    .as("nothing unapproved reaches a student, so nothing unapproved is graded")
                    .isEqualTo(GradeOutcome.NOT_GRADABLE);
        }

        @Test
        @DisplayName("an empty submission is wrong, not ungradable")
        void emptyAnswerIsWrong() {
            long caseId = approvedCase(-2033, "REGULAR", "NORMAL");
            measure(caseId, "heart_rate", 80.0, "bpm", "OK");

            GradeResult result = grading.grade(caseId, 1, new StudentAnswer(null, null, null, null));
            assertThat(result.outcome()).isEqualTo(GradeOutcome.INCORRECT);
            assertThat(result.errorLabel()).isEqualTo("NO_ANSWER");
        }
    }

    @Test
    @DisplayName("every error label the grader can produce exists in the database")
    void everyErrorLabelIsInTheTaxonomy() {
        // The label is a foreign key on session_steps, so one the grader invents
        // would fail at insert time -- after the student had already answered.
        List<String> known = db.sql("SELECT code FROM error_labels").query(String.class).list();

        List<String> produced = List.of(
                "RATE_OVERESTIMATED", "RATE_UNDERESTIMATED",
                "PR_OVERESTIMATED", "PR_UNDERESTIMATED", "PR_REPORTED_WHEN_ABSENT",
                "QRS_OVERESTIMATED", "QRS_UNDERESTIMATED",
                "QT_OVERESTIMATED", "QT_UNDERESTIMATED",
                "REGULAR_CALLED_IRREGULAR", "IRREGULAR_CALLED_REGULAR",
                "IRREGULARITY_PATTERN_CONFUSED",
                "AXIS_WRONG_QUADRANT", "AXIS_DEVIATION_MISSED", "AXIS_NORMAL_CALLED_DEVIATED",
                "P_ABSENT_CALLED_PRESENT", "P_PRESENT_CALLED_ABSENT",
                "ST_ELEVATION_MISSED", "ST_DEPRESSION_MISSED",
                "ST_NORMAL_CALLED_ABNORMAL", "ST_WRONG_TERRITORY",
                "NO_ANSWER", "ANSWER_NOT_UNDERSTOOD");

        assertThat(known).containsAll(produced);
    }
}
