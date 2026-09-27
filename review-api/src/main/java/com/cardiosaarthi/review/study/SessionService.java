package com.cardiosaarthi.review.study;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import tools.jackson.databind.ObjectMapper;

import com.cardiosaarthi.review.error.ConflictException;
import com.cardiosaarthi.review.error.InvalidReviewException;
import com.cardiosaarthi.review.error.NotFoundException;

/**
 * The student runtime's turn.
 *
 * <p>Section 5.1: this is a deterministic state machine, not a model deciding
 * what happens next. The interface already knows which step is being answered,
 * so there is nothing to classify. Control flow is code; a model is invoked
 * inside a state and never selects a transition.
 *
 * <p>The turn, in the order section 5.4 sets out: load the session, refuse an
 * answer to the wrong step, grade deterministically, label the error, branch on
 * the mode's rules, and persist the attempt. Steps 5 to 8 of that sequence --
 * the cache, the retrieval, the model call -- are not wired yet, so feedback for
 * a wrong answer comes from the faculty-approved library. That is the fallback
 * path working; the model slots in front of it later without the branching
 * changing.
 */
@Service
public class SessionService {

    private static final Logger log = LoggerFactory.getLogger(SessionService.class);

    /** The persona configuration version a session is stamped with. */
    private static final String PERSONA_VERSION = "1.0";

    private static final int FINAL_STEP = 9;

    private final JdbcClient db;
    private final StepRepository steps;
    private final GradingService grading;
    private final FeedbackLibrary feedback;
    private final ObjectMapper mapper;

    SessionService(JdbcClient db, StepRepository steps, GradingService grading,
                   FeedbackLibrary feedback, ObjectMapper mapper) {
        this.db = db;
        this.steps = steps;
        this.grading = grading;
        this.feedback = feedback;
        this.mapper = mapper;
    }

    // -----------------------------------------------------------------------
    // starting
    // -----------------------------------------------------------------------
    /**
     * Begins a session on a case.
     *
     * <p>The case must be approved. That is checked by a trigger in the database
     * as well, and deliberately so: an unapproved case reaching a student is the
     * failure this whole project is arranged to prevent, and the check that
     * matters is the one that cannot be forgotten.
     */
    @Transactional
    public SessionView start(long studentId, long caseId, Mode mode) {
        // A case already open is resumed, not refused. A student who left a
        // case half-read and came back was previously told to "finish or
        // abandon it", and nothing could abandon it -- the case was closed to
        // them permanently. Returning the session they already have is both
        // the useful answer and the one that cannot strand anybody.
        //
        // Their earlier answers stay on it. Handing back a clean session would
        // let a wrong step be re-answered for full marks, which is not what a
        // record of what a student knew should say.
        Optional<Long> alreadyOpen = openSessionFor(studentId, caseId);
        if (alreadyOpen.isPresent()) {
            log.info("student {} resumed session {} on case {}", studentId, alreadyOpen.get(), caseId);
            return view(alreadyOpen.get());
        }

        String status = db.sql("SELECT review_status FROM cases WHERE id = :caseId")
                .param("caseId", caseId)
                .query(String.class)
                .optional()
                .orElseThrow(() -> new NotFoundException("no case " + caseId));
        if (!"approved".equals(status)) {
            throw new InvalidReviewException(
                    "That case is not available: only cases a reviewer has approved are served.");
        }

        long sessionId;
        try {
            sessionId = db.sql("""
                    INSERT INTO sessions (student_id, case_id, mode, persona_version, state)
                    VALUES (:studentId, :caseId, :mode, :persona, 'AWAITING_STEP')
                    RETURNING id
                    """)
                    .param("studentId", studentId)
                    .param("caseId", caseId)
                    .param("mode", mode.name())
                    .param("persona", PERSONA_VERSION)
                    .query(Long.class)
                    .single();
        } catch (org.springframework.dao.DuplicateKeyException race) {
            // Two requests arrived together, both found no open session, and
            // both tried to insert one. The interface does exactly this: its
            // start effect runs twice. The unique index settles it, and the
            // loser answers with the session that won rather than an error.
            return openSessionFor(studentId, caseId)
                    .map(this::view)
                    .orElseThrow(() -> new ConflictException("Could not start this case. Try again."));
        } catch (org.springframework.dao.DataAccessException exception) {
            // The database trigger is the backstop, and it raises a plain
            // exception that Spring cannot categorise. Reaching here means the
            // case was approved a moment ago and is not now.
            throw new InvalidReviewException(
                    "That case is not available: only cases a reviewer has approved are served.");
        }

        log.info("student {} started session {} on case {} in {}", studentId, sessionId, caseId, mode);
        return view(sessionId);
    }

    /**
     * This student's unfinished session on this case, if they have one.
     *
     * <p>ABANDONED counts as closed. It did not in the rule this replaces, so
     * an abandoned session blocked its case exactly as an open one did.
     */
    private Optional<Long> openSessionFor(long studentId, long caseId) {
        return db.sql("""
                SELECT id FROM sessions
                WHERE student_id = :studentId
                  AND case_id = :caseId
                  AND state NOT IN ('CASE_COMPLETE', 'ABANDONED')
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """)
                .param("studentId", studentId)
                .param("caseId", caseId)
                .query(Long.class)
                .optional();
    }

    // -----------------------------------------------------------------------
    // one turn
    // -----------------------------------------------------------------------
    private record SessionRow(long id, long studentId, long caseId, Mode mode, String state,
                              int currentStep, int attemptsThisStep) {
    }

    @Transactional
    public TurnResult submit(long sessionId, long studentId, int step, StudentAnswer answer,
                             Integer timeTakenMs) {
        SessionRow session = load(sessionId);

        if (session.studentId() != studentId) {
            // Not "forbidden": a student has no business learning that someone
            // else's session exists.
            throw new NotFoundException("no session " + sessionId);
        }
        if ("CASE_COMPLETE".equals(session.state())) {
            throw new ConflictException("This case is finished.");
        }
        if (step != session.currentStep()) {
            // The nine steps are locked in order because the order is
            // dependency-driven: the rate is needed for QTc, the P wave has to be
            // located before the PR interval can be measured from it.
            throw new ConflictException(
                    "This session is on step %d, not step %d.".formatted(session.currentStep(), step));
        }

        InterpretationStep definition = steps.byStep(step)
                .orElseThrow(() -> new NotFoundException("no step " + step));

        GradeResult grade = grading.grade(session.caseId(), definition, answer);
        int attempt = session.attemptsThisStep() + 1;

        // A step the platform cannot mark does not consume an attempt and is not
        // recorded as an error. The student is told plainly and moves on.
        if (grade.outcome() == GradeOutcome.NOT_GRADABLE) {
            advance(session, step);
            return new TurnResult(sessionId, step, definition.label(), GradeOutcome.NOT_GRADABLE,
                    null, FeedbackType.CONFIRMATION, FeedbackSource.TEMPLATE,
                    "This step is not marked on this case: " + grade.detail(),
                    true, nextStepOf(session, step), attemptsRemaining(session.mode(), 0), true, null);
        }

        boolean correct = grade.correct();
        boolean lastAttempt = attempt >= session.mode().maxAttempts();
        boolean advancing = correct || lastAttempt;

        FeedbackType type = feedbackTypeFor(session.mode(), correct, lastAttempt);
        Rendered rendered = render(type, grade, definition);

        record(session, step, attempt, answer, grade, type, rendered, timeTakenMs);

        if (advancing) {
            advance(session, step);
        } else {
            db.sql("""
                    UPDATE sessions SET attempts_this_step = :attempts, state = 'FEEDBACK_SENT',
                                        last_activity_at = now()
                    WHERE id = :id
                    """)
                    .param("attempts", attempt)
                    .param("id", sessionId)
                    .update();
        }

        return new TurnResult(
                sessionId, step, definition.label(),
                correct ? GradeOutcome.CORRECT : GradeOutcome.INCORRECT,
                grade.errorLabel(), type, rendered.source(), rendered.body(),
                advancing,
                // Integer.valueOf, not a bare int: the other branch is null at
                // step 9, and a mixed ternary unboxes, so finishing a case threw.
                advancing ? nextStepOf(session, step) : Integer.valueOf(step),
                attemptsRemaining(session.mode(), attempt),
                rendered.approved(),
                // The expected value is released only once the step is done with.
                // Returning it alongside a hint would put the answer in the
                // response body, where the console could show it by accident.
                advancing && !correct ? grade.expected() : null);
    }

    /**
     * Which kind of feedback this turn produces.
     *
     * <p>Reads only the orchestrator-side mode parameters. A correct answer is
     * always a templated confirmation and never a model call, which section 5.4
     * expects to be about half of all turns.
     */
    private FeedbackType feedbackTypeFor(Mode mode, boolean correct, boolean lastAttempt) {
        if (mode.deferFeedbackToEnd()) {
            return FeedbackType.DEFERRED;
        }
        if (correct) {
            return FeedbackType.CONFIRMATION;
        }
        if (!lastAttempt && mode.hintBeforeExplanation()) {
            return FeedbackType.HINT;
        }
        return FeedbackType.EXPLANATION;
    }

    private record Rendered(String body, FeedbackSource source, boolean approved) {
    }

    private Rendered render(FeedbackType type, GradeResult grade, InterpretationStep step) {
        if (type == FeedbackType.DEFERRED) {
            return new Rendered(null, FeedbackSource.TEMPLATE, true);
        }
        if (type == FeedbackType.CONFIRMATION) {
            return new Rendered("Correct.", FeedbackSource.TEMPLATE, true);
        }

        Optional<FeedbackLibrary.Entry> entry = feedback.find(grade.errorLabel(), type);
        if (entry.isEmpty()) {
            return new Rendered(
                    "That is not what this recording shows. Work through the " + step.label().toLowerCase()
                            + " again.",
                    FeedbackSource.FALLBACK, false);
        }

        // The rule that matters most: a hint that contains the answer is not a
        // hint. Checked against the value rather than trusted to whoever wrote
        // the paragraph, and it will check a model's output the same way.
        if (type == FeedbackType.HINT && FeedbackLibrary.leaksExpectedValue(entry.get().body(), grade.expected())) {
            log.warn("hint for {} contains the expected value and was withheld", grade.errorLabel());
            return new Rendered(
                    "Not quite. Look at that measurement again before answering.",
                    FeedbackSource.FALLBACK, false);
        }

        return new Rendered(entry.get().body(), FeedbackSource.FALLBACK, entry.get().approved());
    }

    // -----------------------------------------------------------------------
    // persistence
    // -----------------------------------------------------------------------
    private void record(SessionRow session, int step, int attempt, StudentAnswer answer,
                        GradeResult grade, FeedbackType type, Rendered rendered, Integer timeTakenMs) {
        db.sql("""
                INSERT INTO session_steps
                    (session_id, step, attempt, answer, correct, expected, error_label,
                     feedback_type, feedback_source, feedback_text, time_taken_ms, hint_used)
                VALUES (:sessionId, :step, :attempt, CAST(:answer AS jsonb), :correct,
                        CAST(:expected AS jsonb), :errorLabel,
                        :feedbackType, :feedbackSource, :feedbackText, :timeTaken, :hintUsed)
                """)
                .param("sessionId", session.id())
                .param("step", step)
                .param("attempt", attempt)
                .param("answer", json(answer))
                .param("correct", grade.correct())
                .param("expected", json(grade.expected()))
                .param("errorLabel", grade.correct() ? null : grade.errorLabel())
                .param("feedbackType", type.name())
                .param("feedbackSource", rendered.source().name())
                .param("feedbackText", rendered.body())
                .param("timeTaken", timeTakenMs)
                .param("hintUsed", type == FeedbackType.HINT)
                .update();
    }

    /**
     * JSON text for a jsonb column.
     *
     * <p>Passed as a String and cast in the statement rather than wrapped in a
     * driver-specific object: the PostgreSQL driver is a runtime dependency, and
     * reaching for its types here would put the database vendor into the service
     * layer for no gain.
     */
    private String json(Object value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception exception) {
            throw new IllegalStateException("could not serialise an answer for storage", exception);
        }
    }

    private void advance(SessionRow session, int step) {
        if (step >= FINAL_STEP) {
            db.sql("""
                    UPDATE sessions
                    SET state = 'AWAITING_FINAL', attempts_this_step = 0, last_activity_at = now()
                    WHERE id = :id
                    """)
                    .param("id", session.id())
                    .update();
            return;
        }
        db.sql("""
                UPDATE sessions
                SET current_step = :next, attempts_this_step = 0, state = 'AWAITING_STEP',
                    last_activity_at = now()
                WHERE id = :id
                """)
                .param("next", step + 1)
                .param("id", session.id())
                .update();
    }

    private Integer nextStepOf(SessionRow session, int step) {
        return step >= FINAL_STEP ? null : step + 1;
    }

    private int attemptsRemaining(Mode mode, int used) {
        return Math.max(0, mode.maxAttempts() - used);
    }

    // -----------------------------------------------------------------------
    // finishing
    // -----------------------------------------------------------------------
    /**
     * Records the final interpretation and closes the session.
     *
     * <p>The cardiologist's label is revealed here and only here. It is not
     * graded against: a student's free-text interpretation is for a human to
     * read, and section 5.7 reveals the label rather than marking against it.
     */
    @Transactional
    public SessionSummary finish(long sessionId, long studentId, String finalInterpretation) {
        SessionRow session = load(sessionId);
        if (session.studentId() != studentId) {
            throw new NotFoundException("no session " + sessionId);
        }
        if ("CASE_COMPLETE".equals(session.state())) {
            throw new ConflictException("This case is already finished.");
        }
        if (!"AWAITING_FINAL".equals(session.state())) {
            throw new ConflictException(
                    "There are steps left: this session is on step %d of %d."
                            .formatted(session.currentStep(), FINAL_STEP));
        }

        db.sql("""
                UPDATE sessions
                SET state = 'CASE_COMPLETE', completed_at = now(), last_activity_at = now(),
                    final_interpretation = :interpretation
                WHERE id = :id
                """)
                .param("interpretation", finalInterpretation)
                .param("id", sessionId)
                .update();

        log.info("session {} completed by student {}", sessionId, studentId);
        return summary(sessionId);
    }

    // -----------------------------------------------------------------------
    // reads
    // -----------------------------------------------------------------------
    private SessionRow load(long sessionId) {
        return db.sql("""
                SELECT id, student_id, case_id, mode, state, current_step, attempts_this_step
                FROM sessions WHERE id = :id FOR UPDATE
                """)
                .param("id", sessionId)
                .query((rs, n) -> new SessionRow(
                        rs.getLong("id"), rs.getLong("student_id"), rs.getLong("case_id"),
                        Mode.valueOf(rs.getString("mode")), rs.getString("state"),
                        rs.getInt("current_step"), rs.getInt("attempts_this_step")))
                .optional()
                .orElseThrow(() -> new NotFoundException("no session " + sessionId));
    }

    public SessionView view(long sessionId) {
        SessionRow row = load(sessionId);
        InterpretationStep step = steps.byStep(row.currentStep()).orElse(null);
        return new SessionView(
                row.id(), row.caseId(), row.mode(), row.state(), row.currentStep(),
                step == null ? null : step.label(),
                step == null ? null : step.answerKind(),
                attemptsRemaining(row.mode(), row.attemptsThisStep()),
                FINAL_STEP);
    }

    public SessionSummary summary(long sessionId) {
        SessionRow row = load(sessionId);
        List<StepOutcome> outcomes = db.sql("""
                SELECT ss.step, s.label, ss.attempt, ss.correct, ss.error_label, ss.feedback_text
                FROM session_steps ss
                JOIN interpretation_steps s ON s.step = ss.step
                WHERE ss.session_id = :id
                ORDER BY ss.step, ss.attempt
                """)
                .param("id", sessionId)
                .query((rs, n) -> new StepOutcome(
                        rs.getInt("step"), rs.getString("label"), rs.getInt("attempt"),
                        rs.getBoolean("correct"), rs.getString("error_label"),
                        rs.getString("feedback_text")))
                .list();

        long firstTime = outcomes.stream().filter(o -> o.correct() && o.attempt() == 1).count();
        long graded = outcomes.stream().map(StepOutcome::step).distinct().count();

        OffsetDateTime completedAt = db.sql("SELECT completed_at FROM sessions WHERE id = :id")
                .param("id", sessionId)
                .query(OffsetDateTime.class)
                .optional()
                .orElse(null);

        return new SessionSummary(sessionId, row.caseId(), row.state(), (int) graded,
                (int) firstTime, outcomes, completedAt);
    }

    // -----------------------------------------------------------------------
    // views
    // -----------------------------------------------------------------------
    public record SessionView(long sessionId, long caseId, Mode mode, String state, int currentStep,
                              String currentStepLabel, AnswerKind answerKind, int attemptsRemaining,
                              int totalSteps) {
    }

    public record StepOutcome(int step, String label, int attempt, boolean correct,
                              String errorLabel, String feedback) {
    }

    public record SessionSummary(long sessionId, long caseId, String state, int stepsAttempted,
                                 int correctFirstTime, List<StepOutcome> steps,
                                 OffsetDateTime completedAt) {
    }

    /**
     * @param expected released only once a step is finished with. Returning it
     *                 alongside a hint would put the answer in the response body,
     *                 where a console could show it by accident.
     */
    public record TurnResult(long sessionId, int step, String stepLabel, GradeOutcome outcome,
                             String errorLabel, FeedbackType feedbackType, FeedbackSource feedbackSource,
                             String feedback, boolean advanced, Integer nextStep,
                             int attemptsRemaining, boolean facultyApproved, Object expected) {
    }
}
