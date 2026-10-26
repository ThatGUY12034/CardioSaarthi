package com.cardiosaarthi.review.cohort;

import java.time.Instant;
import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.error.NotFoundException;
import com.cardiosaarthi.review.reviewer.ReviewerService;
import com.cardiosaarthi.review.support.Timestamps;

/**
 * What a teacher can see of their students, and what they can say back.
 *
 * <p>Every attempt a student has made has been recorded since the runtime was
 * built, including which of the thirty-two named errors each wrong answer was,
 * and none of it has ever reached the person teaching them. The faculty view of
 * a student was sample data.
 *
 * <p>The arithmetic here is deliberately the same the student sees on their own
 * pages. A teacher and a student looking at the same figure and getting
 * different numbers is worse than either of them having no figure at all.
 */
@RestController
@RequestMapping("/api/cohort")
@PreAuthorize("hasAnyRole('FACULTY','ADMIN')")
public class CohortController {

    private static final Logger log = LoggerFactory.getLogger(CohortController.class);

    private final JdbcClient db;
    private final ReviewerService reviewers;

    CohortController(JdbcClient db, ReviewerService reviewers) {
        this.db = db;
        this.reviewers = reviewers;
    }

    // -----------------------------------------------------------------------
    // the class
    // -----------------------------------------------------------------------
    public record StudentRow(long studentId, String fullName, String collegeId, String cohort,
                             boolean active, int casesCompleted, int casesInProgress,
                             Integer averageScorePct, Integer bestScorePct,
                             int currentStreakDays, int mistakes, int remarks,
                             String weakestConcept, Instant lastActiveAt,
                             Double learningGainPct) {
    }

    @GetMapping("/students")
    public List<StudentRow> students(@RequestParam(required = false) String cohort) {
        return db.sql("""
                SELECT c.*, g.gain_pct
                FROM v_cohort_students c
                LEFT JOIN v_student_learning_gain g ON g.student_id = c.student_id
                WHERE (CAST(:cohort AS text) IS NULL OR c.cohort = :cohort)
                ORDER BY c.cases_completed DESC, c.full_name
                """)
                .param("cohort", cohort == null || cohort.isBlank() ? null : cohort)
                .query((rs, n) -> new StudentRow(
                        rs.getLong("student_id"), rs.getString("full_name"),
                        rs.getString("college_id"), rs.getString("cohort"),
                        rs.getBoolean("active"), rs.getInt("cases_completed"),
                        rs.getInt("cases_in_progress"),
                        Timestamps.integer(rs, "average_score_pct"),
                        Timestamps.integer(rs, "best_score_pct"),
                        rs.getInt("current_streak_days"), rs.getInt("mistakes"),
                        rs.getInt("remarks"), rs.getString("weakest_concept"),
                        Timestamps.instant(rs, "last_active_at"),
                        rs.getObject("gain_pct") == null ? null : rs.getDouble("gain_pct")))
                .list();
    }

    public record StepDifficulty(int step, String concept, String label, int studentsAttempted,
                                 int attempts, int correctFirstTime,
                                 Double firstAttemptAccuracyPct, Double meanSeconds) {
    }

    public record CohortError(String code, int step, String stepLabel, String description,
                              int occurrences, int studentsAffected) {
    }

    /** What the class as a whole finds hard, which is what to teach next. */
    @GetMapping("/difficulty")
    public List<StepDifficulty> difficulty() {
        return db.sql("SELECT * FROM v_cohort_step_difficulty ORDER BY step")
                .query((rs, n) -> new StepDifficulty(
                        rs.getInt("step"), rs.getString("concept"), rs.getString("label"),
                        rs.getInt("students_attempted"), rs.getInt("attempts"),
                        rs.getInt("correct_first_time"),
                        rs.getObject("first_attempt_accuracy_pct") == null
                                ? null : rs.getDouble("first_attempt_accuracy_pct"),
                        rs.getObject("mean_seconds") == null
                                ? null : rs.getDouble("mean_seconds")))
                .list();
    }

    /** The mistakes a class makes most, by name rather than by count of "wrong". */
    @GetMapping("/errors")
    public List<CohortError> errors(@RequestParam(defaultValue = "15") int limit) {
        return db.sql("""
                SELECT * FROM v_cohort_errors
                WHERE occurrences > 0
                ORDER BY occurrences DESC, code
                LIMIT :limit
                """)
                .param("limit", Math.clamp(limit, 1, 40))
                .query((rs, n) -> new CohortError(
                        rs.getString("code"), rs.getInt("step"), rs.getString("step_label"),
                        rs.getString("description"), rs.getInt("occurrences"),
                        rs.getInt("students_affected")))
                .list();
    }

    // -----------------------------------------------------------------------
    // one student
    // -----------------------------------------------------------------------
    public record Mistake(long sessionStepId, long sessionId, long caseId, Integer sourceEcgId,
                          int step, String stepLabel, String concept, int attempt,
                          String answer, String expected, String errorLabel,
                          String errorDescription, Instant createdAt, int remarkCount) {
    }

    public record ConceptStrength(int step, String label, int firstAttempts,
                                  int firstAttemptCorrect, Double firstAttemptAccuracyPct) {
    }

    public record StudentDetail(StudentRow student, Double earlyAccuracyPct,
                                Double lateAccuracyPct, List<ConceptStrength> concepts,
                                List<Mistake> mistakes) {
    }

    @GetMapping("/students/{id}")
    public StudentDetail student(@PathVariable long id) {
        StudentRow row = students(null).stream()
                .filter(s -> s.studentId() == id)
                .findFirst()
                .orElseThrow(() -> new NotFoundException("no student " + id));

        Double early = null;
        Double late = null;
        var gain = db.sql("""
                SELECT early_accuracy_pct, late_accuracy_pct
                FROM v_student_learning_gain WHERE student_id = :id
                """)
                .param("id", id)
                .query((rs, n) -> new double[] {
                        rs.getObject("early_accuracy_pct") == null ? -1 : rs.getDouble("early_accuracy_pct"),
                        rs.getObject("late_accuracy_pct") == null ? -1 : rs.getDouble("late_accuracy_pct")})
                .optional();
        if (gain.isPresent()) {
            early = gain.get()[0] < 0 ? null : gain.get()[0];
            late = gain.get()[1] < 0 ? null : gain.get()[1];
        }

        List<ConceptStrength> concepts = db.sql("""
                SELECT s.step, s.label,
                       coalesce(cs.first_attempts, 0)        AS first_attempts,
                       coalesce(cs.first_attempt_correct, 0) AS first_attempt_correct,
                       cs.first_attempt_accuracy_pct
                FROM interpretation_steps s
                LEFT JOIN v_student_concept_strength cs
                       ON cs.concept = s.concept AND cs.student_id = :id
                ORDER BY s.step
                """)
                .param("id", id)
                .query((rs, n) -> new ConceptStrength(
                        rs.getInt("step"), rs.getString("label"), rs.getInt("first_attempts"),
                        rs.getInt("first_attempt_correct"),
                        rs.getObject("first_attempt_accuracy_pct") == null
                                ? null : rs.getDouble("first_attempt_accuracy_pct")))
                .list();

        List<Mistake> mistakes = db.sql("""
                SELECT session_step_id, session_id, case_id, source_ecg_id, step, step_label,
                       concept, attempt, answer::text AS answer, expected::text AS expected,
                       error_label, error_description, created_at, remark_count
                FROM v_student_mistakes
                WHERE student_id = :id
                ORDER BY created_at DESC
                LIMIT 50
                """)
                .param("id", id)
                .query((rs, n) -> new Mistake(
                        rs.getLong("session_step_id"), rs.getLong("session_id"),
                        rs.getLong("case_id"), Timestamps.integer(rs, "source_ecg_id"),
                        rs.getInt("step"), rs.getString("step_label"), rs.getString("concept"),
                        rs.getInt("attempt"), rs.getString("answer"), rs.getString("expected"),
                        rs.getString("error_label"), rs.getString("error_description"),
                        Timestamps.instant(rs, "created_at"), rs.getInt("remark_count")))
                .list();

        return new StudentDetail(row, early, late, concepts, mistakes);
    }

    // -----------------------------------------------------------------------
    // remarks
    // -----------------------------------------------------------------------
    public record NewRemark(
            @NotBlank(message = "a remark cannot be empty")
            @Size(max = 2000, message = "keep a remark under 2000 characters")
            String body) {
    }

    public record Remark(long id, long sessionStepId, String reviewerName, String body,
                         Instant createdAt, Instant readAt, int step, String stepLabel,
                         Integer sourceEcgId, String errorLabel) {
    }

    /**
     * Leave a remark on the exact attempt that went wrong.
     *
     * <p>Anchored to the attempt rather than the student: "you keep getting the
     * axis wrong" is not advice a student can act on, and a remark on the
     * attempt where they called a left axis normal is.
     */
    @PostMapping("/attempts/{sessionStepId}/remarks")
    @ResponseStatus(HttpStatus.CREATED)
    public Remark addRemark(@PathVariable long sessionStepId, @Valid @RequestBody NewRemark body) {
        Long studentId = db.sql("""
                SELECT se.student_id
                FROM session_steps ss JOIN sessions se ON se.id = ss.session_id
                WHERE ss.id = :id
                """)
                .param("id", sessionStepId)
                .query(Long.class)
                .optional()
                .orElseThrow(() -> new NotFoundException("no attempt " + sessionStepId));

        long reviewerId = reviewers.current().id();
        long id = db.sql("""
                INSERT INTO faculty_remarks (session_step_id, reviewer_id, student_id, body)
                VALUES (:step, :reviewer, :student, :body)
                RETURNING id
                """)
                .param("step", sessionStepId)
                .param("reviewer", reviewerId)
                .param("student", studentId)
                .param("body", body.body().trim())
                .query(Long.class)
                .single();

        log.info("reviewer {} left a remark on attempt {} for student {}",
                reviewerId, sessionStepId, studentId);
        return remarksForStep(sessionStepId).stream()
                .filter(r -> r.id() == id)
                .findFirst()
                .orElseThrow();
    }

    @GetMapping("/attempts/{sessionStepId}/remarks")
    public List<Remark> remarksForStep(@PathVariable long sessionStepId) {
        return db.sql(REMARK_SELECT + " WHERE r.session_step_id = :id ORDER BY r.created_at")
                .param("id", sessionStepId)
                .query(CohortController::mapRemark)
                .list();
    }

    static final String REMARK_SELECT = """
            SELECT r.id, r.session_step_id, rv.full_name AS reviewer_name, r.body,
                   r.created_at, r.read_at, ss.step, s.label AS step_label,
                   c.source_ecg_id, ss.error_label
            FROM faculty_remarks r
            JOIN reviewers rv            ON rv.id = r.reviewer_id
            JOIN session_steps ss        ON ss.id = r.session_step_id
            JOIN sessions se             ON se.id = ss.session_id
            JOIN cases c                 ON c.id = se.case_id
            JOIN interpretation_steps s  ON s.step = ss.step
            """;

    static Remark mapRemark(java.sql.ResultSet rs, int n) throws java.sql.SQLException {
        return new Remark(
                rs.getLong("id"), rs.getLong("session_step_id"), rs.getString("reviewer_name"),
                rs.getString("body"), Timestamps.instant(rs, "created_at"),
                Timestamps.instant(rs, "read_at"), rs.getInt("step"),
                rs.getString("step_label"), Timestamps.integer(rs, "source_ecg_id"),
                rs.getString("error_label"));
    }
}
