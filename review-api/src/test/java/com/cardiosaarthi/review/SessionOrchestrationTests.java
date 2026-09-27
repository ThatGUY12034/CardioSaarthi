package com.cardiosaarthi.review;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.List;

import com.cardiosaarthi.review.error.ConflictException;
import com.cardiosaarthi.review.error.NotFoundException;
import com.cardiosaarthi.review.study.FeedbackLibrary;
import com.cardiosaarthi.review.study.FeedbackSource;
import com.cardiosaarthi.review.study.FeedbackType;
import com.cardiosaarthi.review.study.GradeOutcome;
import com.cardiosaarthi.review.study.Mode;
import com.cardiosaarthi.review.study.SessionService;
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
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The student runtime's turn, against a real approved case.
 *
 * <p>What is worth protecting here is the control flow, because section 5.1
 * makes it code rather than a model's decision: the steps are locked in order,
 * the mode decides how many attempts a step allows, and a correct answer never
 * costs a model call.
 */
@SpringBootTest
@Transactional
@EnabledIf("databaseIsRunning")
class SessionOrchestrationTests {

    @Autowired
    private SessionService sessions;

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
    private long student(String email) {
        return db.sql("""
                INSERT INTO students (email, full_name, password_hash)
                VALUES (:email, 'Test Student', '$2a$10$x')
                ON CONFLICT (lower(email)) DO UPDATE SET full_name = excluded.full_name
                RETURNING id
                """).param("email", email).query(Long.class).single();
    }

    private long reviewer() {
        return db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash)
                VALUES ('session.reviewer@example.invalid', 'Session Reviewer', 'faculty', '$2a$10$x')
                ON CONFLICT (lower(email)) DO UPDATE SET full_name = excluded.full_name
                RETURNING id
                """).query(Long.class).single();
    }

    /** An approved case with every measurement the nine steps need. */
    private long approvedCase(int ecgId) {
        long caseId = db.sql("""
                INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                                   sampling_rate, n_samples, measurement_status, overall_confidence,
                                   raw_measurement, rhythm_regularity, axis_category,
                                   review_status, reviewed_at, reviewed_by)
                VALUES ('test', :ecgId, '1.0.0', '0.2.0', now(), 500, 5000, 'OK', 0.95, '{}'::jsonb,
                        'REGULAR', 'NORMAL', 'approved', now(), :reviewer)
                RETURNING id
                """)
                .param("ecgId", ecgId)
                .param("reviewer", reviewer())
                .query(Long.class)
                .single();

        record Measure(String name, double value, String unit) {
        }
        for (Measure m : List.of(
                new Measure("heart_rate", 80.0, "bpm"),
                new Measure("pr_interval", 160.0, "ms"),
                new Measure("qrs_duration", 100.0, "ms"),
                new Measure("qt_interval", 400.0, "ms"),
                new Measure("p_duration", 100.0, "ms"))) {
            db.sql("""
                    INSERT INTO case_measurements (case_id, name, value, mad, unit, n_beats, confidence, status, flag)
                    VALUES (:caseId, :name, :value, 3.0, :unit, 12, 0.95, 'OK', 'NORMAL')
                    """)
                    .param("caseId", caseId).param("name", m.name())
                    .param("value", m.value()).param("unit", m.unit())
                    .update();
        }
        db.sql("""
                INSERT INTO case_st_deviations (case_id, lead, deviation_mm, finding)
                VALUES (:caseId, 'V2', 0.2, 'NORMAL')
                """).param("caseId", caseId).update();
        return caseId;
    }

    private static StudentAnswer number(double value) {
        return new StudentAnswer(value, null, null, null);
    }

    private static StudentAnswer category(String value) {
        return new StudentAnswer(null, null, value, null);
    }

    // -----------------------------------------------------------------------
    @Nested
    @DisplayName("starting")
    class Starting {

        @Test
        @DisplayName("a new session begins at step one, awaiting an answer")
        void startsAtStepOne() {
            long studentId = student("start@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3001), Mode.BEGINNER_TUTOR);

            assertThat(view.currentStep()).isEqualTo(1);
            assertThat(view.currentStepLabel()).isEqualTo("Rate");
            assertThat(view.state()).isEqualTo("AWAITING_STEP");
            assertThat(view.totalSteps()).isEqualTo(9);
            assertThat(view.attemptsRemaining()).isEqualTo(2);
        }

        @Test
        @DisplayName("an unapproved case cannot be started")
        void unapprovedCaseIsRefused() {
            // Enforced by a database trigger as well. An unapproved case reaching
            // a student is the failure the whole project is arranged to prevent.
            long studentId = student("unapproved@example.invalid");
            long pending = db.sql("""
                    INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                                       sampling_rate, n_samples, measurement_status, overall_confidence,
                                       raw_measurement)
                    VALUES ('test', -3002, '1.0.0', '0.2.0', now(), 500, 5000, 'OK', 0.9, '{}'::jsonb)
                    RETURNING id
                    """).query(Long.class).single();

            assertThatThrownBy(() -> sessions.start(studentId, pending, Mode.BEGINNER_TUTOR))
                    .hasMessageContaining("only cases a reviewer has approved");
        }

        @Test
        @DisplayName("the same case cannot be opened twice at once")
        void noDuplicateOpenSession() {
            long studentId = student("duplicate@example.invalid");
            long caseId = approvedCase(-3003);
            sessions.start(studentId, caseId, Mode.BEGINNER_TUTOR);

            assertThatThrownBy(() -> sessions.start(studentId, caseId, Mode.BEGINNER_TUTOR))
                    .isInstanceOf(ConflictException.class);
        }
    }

    @Nested
    @DisplayName("the steps are locked in order")
    class StepOrder {

        @Test
        @DisplayName("answering a step the session is not on is refused")
        void outOfOrderIsRefused() {
            // The order is dependency-driven: the rate is needed for QTc, and the
            // P wave has to be located before the PR interval can be measured.
            long studentId = student("order@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3010), Mode.BEGINNER_TUTOR);

            assertThatThrownBy(() -> sessions.submit(view.sessionId(), studentId, 5, number(160), 1000))
                    .isInstanceOf(ConflictException.class)
                    .hasMessageContaining("step 1");
        }

        @Test
        @DisplayName("a correct answer advances exactly one step")
        void correctAdvancesOneStep() {
            long studentId = student("advance@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3011), Mode.BEGINNER_TUTOR);

            var turn = sessions.submit(view.sessionId(), studentId, 1, number(80), 5000);

            assertThat(turn.outcome()).isEqualTo(GradeOutcome.CORRECT);
            assertThat(turn.advanced()).isTrue();
            assertThat(turn.nextStep()).isEqualTo(2);
            assertThat(sessions.view(view.sessionId()).currentStep()).isEqualTo(2);
        }

        @Test
        @DisplayName("another student cannot answer inside this session")
        void sessionsAreNotShared() {
            long owner = student("owner@example.invalid");
            long stranger = student("stranger@example.invalid");
            var view = sessions.start(owner, approvedCase(-3012), Mode.BEGINNER_TUTOR);

            // Not "forbidden": a student has no business learning that someone
            // else's session exists.
            assertThatThrownBy(() -> sessions.submit(view.sessionId(), stranger, 1, number(80), 1000))
                    .isInstanceOf(NotFoundException.class);
        }
    }

    @Nested
    @DisplayName("the mode decides the branching")
    class Modes {

        @Test
        @DisplayName("beginner tutor gives a hint first and keeps the student on the step")
        void hintThenExplanation() {
            long studentId = student("beginner@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3020), Mode.BEGINNER_TUTOR);

            var first = sessions.submit(view.sessionId(), studentId, 1, number(140), 4000);
            assertThat(first.feedbackType()).isEqualTo(FeedbackType.HINT);
            assertThat(first.advanced()).as("a hint keeps the student on the step").isFalse();
            assertThat(first.attemptsRemaining()).isEqualTo(1);
            assertThat(first.expected()).as("a hint must not carry the answer").isNull();

            var second = sessions.submit(view.sessionId(), studentId, 1, number(150), 4000);
            assertThat(second.feedbackType()).isEqualTo(FeedbackType.EXPLANATION);
            assertThat(second.advanced()).as("the second wrong answer advances anyway").isTrue();
            assertThat(second.expected()).as("the answer is released once the step is done").isNotNull();
        }

        @Test
        @DisplayName("clinical mentor allows one attempt, then explains and moves on")
        void mentorAllowsOneAttempt() {
            long studentId = student("mentor@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3021), Mode.CLINICAL_MENTOR);

            var turn = sessions.submit(view.sessionId(), studentId, 1, number(140), 3000);
            assertThat(turn.feedbackType()).isEqualTo(FeedbackType.EXPLANATION);
            assertThat(turn.advanced()).isTrue();
        }

        @Test
        @DisplayName("examiner mode says nothing until the end")
        void examinerDefersFeedback() {
            long studentId = student("examiner@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3022), Mode.EXAMINER);

            var wrong = sessions.submit(view.sessionId(), studentId, 1, number(140), 3000);
            assertThat(wrong.feedbackType()).isEqualTo(FeedbackType.DEFERRED);
            assertThat(wrong.feedback()).as("nothing is said during the case").isNull();
            assertThat(wrong.advanced()).isTrue();

            var right = sessions.submit(view.sessionId(), studentId, 2, category("REGULAR"), 3000);
            assertThat(right.feedbackType()).isEqualTo(FeedbackType.DEFERRED);
            assertThat(right.outcome()).as("it is still graded, just not reported").isEqualTo(GradeOutcome.CORRECT);
        }
    }

    @Nested
    @DisplayName("feedback")
    class Feedback {

        @Test
        @DisplayName("a correct answer never costs a model call")
        void correctAnswersAreTemplated() {
            // Section 5.4 expects about half of all turns to land here. Paying a
            // model to say "yes, that's right" is the easiest cost to avoid.
            long studentId = student("template@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3030), Mode.BEGINNER_TUTOR);

            var turn = sessions.submit(view.sessionId(), studentId, 1, number(80), 2000);
            assertThat(turn.feedbackSource()).isEqualTo(FeedbackSource.TEMPLATE);
            assertThat(turn.feedbackType()).isEqualTo(FeedbackType.CONFIRMATION);
        }

        @Test
        @DisplayName("a wrong answer draws on the faculty library and says whether it is approved")
        void wrongAnswersUseTheLibrary() {
            long studentId = student("library@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3031), Mode.CLINICAL_MENTOR);

            // Clinical mentor allows one attempt, so a first wrong answer gets
            // the explanation rather than the hint.
            var turn = sessions.submit(view.sessionId(), studentId, 1, number(140), 3000);
            assertThat(turn.feedbackSource()).isEqualTo(FeedbackSource.FALLBACK);
            assertThat(turn.feedbackType()).isEqualTo(FeedbackType.EXPLANATION);
            assertThat(turn.feedback()).contains("faster than the recording shows");
            assertThat(turn.facultyApproved())
                    .as("seeded wording is a draft until a clinician reads it")
                    .isFalse();
        }

        @Test
        @DisplayName("no hint in the library contains the value it is hinting at")
        void noHintLeaksItsAnswer() {
            // The rule from section 5.4, checked over every row rather than
            // trusted to whoever wrote them.
            var hints = db.sql("""
                    SELECT error_label, body FROM feedback_templates WHERE feedback_type = 'HINT'
                    """)
                    .query((rs, n) -> List.of(rs.getString("error_label"), rs.getString("body")))
                    .list();

            assertThat(hints).isNotEmpty();
            for (var hint : hints) {
                // A hint mentioning any of the values a case might hold would be
                // giving the answer away.
                for (double plausible : new double[] {80, 160, 100, 400, 60, 120}) {
                    assertThat(FeedbackLibrary.leaksExpectedValue(hint.get(1), plausible))
                            .as("hint for %s contains %s", hint.get(0), plausible)
                            .isFalse();
                }
            }
        }

        @Test
        @DisplayName("the leak check ignores numbers that are not the answer")
        void leakCheckIsNotOverBroad() {
            // Rejecting a hint for containing "12" when the answer is 120 would
            // make it impossible to mention a 12-lead ECG or lead V1.
            assertThat(FeedbackLibrary.leaksExpectedValue("Look across all 12 leads.", 120.0)).isFalse();
            assertThat(FeedbackLibrary.leaksExpectedValue("The rate is 120.", 120.0)).isTrue();
        }
    }

    @Nested
    @DisplayName("finishing")
    class Finishing {

        @Test
        @DisplayName("a case cannot be finished before the ninth step")
        void cannotFinishEarly() {
            long studentId = student("early@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3040), Mode.BEGINNER_TUTOR);

            assertThatThrownBy(() -> sessions.finish(view.sessionId(), studentId, "sinus rhythm"))
                    .isInstanceOf(ConflictException.class)
                    .hasMessageContaining("steps left");
        }

        @Test
        @DisplayName("working through all nine steps completes the case and summarises it")
        void fullRunThrough() {
            long studentId = student("full@example.invalid");
            long caseId = approvedCase(-3041);
            var view = sessions.start(studentId, caseId, Mode.CLINICAL_MENTOR);
            long sessionId = view.sessionId();

            sessions.submit(sessionId, studentId, 1, number(80), 1000);
            sessions.submit(sessionId, studentId, 2, category("REGULAR"), 1000);
            sessions.submit(sessionId, studentId, 3, category("NORMAL"), 1000);
            sessions.submit(sessionId, studentId, 4, category("PRESENT"), 1000);
            sessions.submit(sessionId, studentId, 5, number(160), 1000);
            sessions.submit(sessionId, studentId, 6, number(100), 1000);
            sessions.submit(sessionId, studentId, 7,
                    new StudentAnswer(null, true, null, List.of()), 1000);
            // Step 8 is not gradable: the engine does not compute T-wave polarity.
            var tWave = sessions.submit(sessionId, studentId, 8, category("UPRIGHT"), 1000);
            assertThat(tWave.outcome()).isEqualTo(GradeOutcome.NOT_GRADABLE);
            sessions.submit(sessionId, studentId, 9, number(400), 1000);

            assertThat(sessions.view(sessionId).state()).isEqualTo("AWAITING_FINAL");

            var summary = sessions.finish(sessionId, studentId, "Normal sinus rhythm, no acute changes.");
            assertThat(summary.state()).isEqualTo("CASE_COMPLETE");
            assertThat(summary.completedAt()).isNotNull();
            assertThat(summary.correctFirstTime())
                    .as("eight gradable steps, all right first time")
                    .isEqualTo(8);
        }

        @Test
        @DisplayName("a finished case cannot be answered again")
        void finishedCaseIsClosed() {
            long studentId = student("closed@example.invalid");
            var view = sessions.start(studentId, approvedCase(-3042), Mode.EXAMINER);
            long sessionId = view.sessionId();
            for (int step = 1; step <= 9; step++) {
                sessions.submit(sessionId, studentId, step, number(80), 500);
            }
            sessions.finish(sessionId, studentId, "done");

            assertThatThrownBy(() -> sessions.submit(sessionId, studentId, 1, number(80), 500))
                    .isInstanceOf(ConflictException.class)
                    .hasMessageContaining("finished");
        }
    }

    @Test
    @DisplayName("every attempt is recorded, and recorded attempts cannot be edited")
    void attemptsAreAppendOnly() {
        // What a student answered and when is the evidence the evaluation study
        // rests on.
        long studentId = student("append@example.invalid");
        var view = sessions.start(studentId, approvedCase(-3050), Mode.BEGINNER_TUTOR);
        sessions.submit(view.sessionId(), studentId, 1, number(140), 2000);
        sessions.submit(view.sessionId(), studentId, 1, number(145), 2000);

        var attempts = db.sql("""
                SELECT attempt, correct, error_label, feedback_type, time_taken_ms
                FROM session_steps WHERE session_id = :id ORDER BY attempt
                """)
                .param("id", view.sessionId())
                .query((rs, n) -> rs.getInt("attempt") + ":" + rs.getString("feedback_type"))
                .list();

        assertThat(attempts).containsExactly("1:HINT", "2:EXPLANATION");

        assertThatThrownBy(() -> db.sql("UPDATE session_steps SET correct = true WHERE session_id = :id")
                .param("id", view.sessionId())
                .update())
                .hasMessageContaining("append-only");
    }
}
