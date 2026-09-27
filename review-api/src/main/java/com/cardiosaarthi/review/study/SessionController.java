package com.cardiosaarthi.review.study;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.error.NotFoundException;

/**
 * The student runtime's endpoints.
 *
 * <p>The student is taken from the authenticated request, never from the body: a
 * session id a client can send is a session id a client can change, and a
 * student must not be able to answer inside someone else's session.
 */
@RestController
@RequestMapping("/api/study")
public class SessionController {

    private final SessionService sessions;
    private final StepRepository steps;
    private final JdbcClient db;

    SessionController(SessionService sessions, StepRepository steps, JdbcClient db) {
        this.sessions = sessions;
        this.steps = steps;
        this.db = db;
    }

    public record StartRequest(
            @NotNull(message = "caseId is required") Long caseId,
            @NotNull(message = "mode is required: BEGINNER_TUTOR, CLINICAL_MENTOR or EXAMINER") Mode mode) {
    }

    public record SubmitRequest(
            @NotNull(message = "step is required") Integer step,
            @Valid StudentAnswer answer,
            @PositiveOrZero(message = "timeTakenMs cannot be negative") Integer timeTakenMs) {
    }

    public record FinishRequest(
            @Size(max = 2000, message = "the interpretation must be 2000 characters or fewer")
            String interpretation) {
    }

    /** A case this student may start: approved, and not already open. */
    public record AvailableCase(long caseId, int sourceEcgId, Double age, String sex,
                                boolean hasNarrative, List<String> conditionCodes) {
    }

    @GetMapping("/cases")
    public List<AvailableCase> availableCases(@RequestParam(defaultValue = "20") int limit) {
        return db.sql("""
                SELECT case_id, source_ecg_id, age, sex, has_narrative, condition_codes
                FROM v_servable_cases
                ORDER BY case_id
                LIMIT :limit
                """)
                .param("limit", Math.clamp(limit, 1, 100))
                .query((rs, n) -> new AvailableCase(
                        rs.getLong("case_id"),
                        rs.getInt("source_ecg_id"),
                        rs.getObject("age") == null ? null : rs.getDouble("age"),
                        rs.getString("sex"),
                        rs.getBoolean("has_narrative"),
                        java.util.Arrays.asList((String[]) rs.getArray("condition_codes").getArray())))
                .list();
    }

    @PostMapping("/sessions")
    @ResponseStatus(HttpStatus.CREATED)
    public SessionService.SessionView start(@Valid @RequestBody StartRequest request) {
        return sessions.start(currentStudentId(), request.caseId(), request.mode());
    }

    @GetMapping("/sessions/{id}")
    public SessionService.SessionView view(@PathVariable long id) {
        SessionService.SessionView view = sessions.view(id);
        requireOwnSession(id);
        return view;
    }

    /**
     * Answer the current step.
     *
     * <p>Returns 409 if the session is on a different step: the nine steps are
     * locked in order because the order is dependency-driven, and answering out
     * of sequence is a client bug rather than a student mistake.
     */
    @PostMapping("/sessions/{id}/answer")
    public SessionService.TurnResult answer(@PathVariable long id, @Valid @RequestBody SubmitRequest request) {
        return sessions.submit(id, currentStudentId(), request.step(), request.answer(), request.timeTakenMs());
    }

    @PostMapping("/sessions/{id}/finish")
    public SessionService.SessionSummary finish(@PathVariable long id, @Valid @RequestBody FinishRequest request) {
        return sessions.finish(id, currentStudentId(), request.interpretation());
    }

    @GetMapping("/sessions/{id}/summary")
    public SessionService.SessionSummary summary(@PathVariable long id) {
        requireOwnSession(id);
        return sessions.summary(id);
    }

    /**
     * The nine steps and what each one accepts.
     *
     * <p>Served rather than duplicated in the console. A client with its own copy
     * of the rhythm options will eventually disagree with the grader about what a
     * valid answer is, and the student is the one who finds out.
     *
     * <p>Tolerances are deliberately not included. Telling a student that the
     * rate is accepted within ten percent turns the step into arithmetic on the
     * answer rather than a measurement off the tracing.
     */
    @GetMapping("/steps")
    public List<StepView> steps() {
        return steps.all().stream().map(StepView::of).toList();
    }

    // -----------------------------------------------------------------------
    private void requireOwnSession(long sessionId) {
        long studentId = currentStudentId();
        boolean owned = db.sql("SELECT count(*) > 0 FROM sessions WHERE id = :id AND student_id = :student")
                .param("id", sessionId)
                .param("student", studentId)
                .query(Boolean.class)
                .single();
        if (!owned) {
            // Not 403: a student has no business learning that someone else's
            // session exists.
            throw new NotFoundException("no session " + sessionId);
        }
    }

    /**
     * The student making this request.
     *
     * <p>Resolved from the token or from the Basic principal's email, never from
     * the request body.
     */
    private long currentStudentId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new IllegalStateException("no authenticated student on this request");
        }
        if (authentication instanceof JwtAuthenticationToken token) {
            Long id = token.getToken().getClaim("uid");
            if (id == null) {
                throw new IllegalStateException("token carries no uid claim");
            }
            return id;
        }
        return db.sql("SELECT id FROM students WHERE lower(email) = lower(:email) AND active")
                .param("email", authentication.getName())
                .query(Long.class)
                .optional()
                .orElseThrow(() -> new NotFoundException(
                        "authenticated as " + authentication.getName() + " but no student row exists"));
    }
}
