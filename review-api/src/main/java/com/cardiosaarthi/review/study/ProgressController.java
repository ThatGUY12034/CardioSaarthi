package com.cardiosaarthi.review.study;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

import org.springframework.jdbc.core.simple.JdbcClient;

import com.cardiosaarthi.review.support.Timestamps;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * A student's own record, served from what they actually did.
 *
 * <p>The dashboard, the progress page and the leaderboard have been showing
 * figures written into the interface as constants: five cases completed, a
 * three-day streak, seventy-eight per cent. Every one of those is derivable
 * from the attempt record, which has been collecting the real thing since the
 * runtime was built. A platform whose entire argument is that clinical values
 * are computed rather than asserted should not assert a student's score.
 *
 * <p>Everything here is scoped to the caller. A student may read their own
 * progress and nobody else's; the leaderboard is the one exception and carries
 * no names, only positions.
 */
@RestController
@RequestMapping("/api/study")
public class ProgressController {

    private final JdbcClient db;
    private final MasteryService mastery;
    private final CurrentStudent currentStudent;

    ProgressController(JdbcClient db, MasteryService mastery, CurrentStudent currentStudent) {
        this.db = db;
        this.mastery = mastery;
        this.currentStudent = currentStudent;
    }

    // -----------------------------------------------------------------------
    // the dashboard
    // -----------------------------------------------------------------------
    public record Progress(int casesAvailable, int casesCompleted, int casesInProgress,
                           Integer averageScorePct, Integer bestScorePct, int currentStreakDays) {
    }

    @GetMapping("/progress")
    public Progress progress() {
        long studentId = currentStudent.id();
        return db.sql("""
                SELECT cases_available, cases_completed, cases_in_progress,
                       average_score_pct, best_score_pct, current_streak_days
                FROM v_student_progress
                WHERE student_id = :studentId
                """)
                .param("studentId", studentId)
                .query((rs, n) -> new Progress(
                        rs.getInt("cases_available"),
                        rs.getInt("cases_completed"),
                        rs.getInt("cases_in_progress"),
                        Timestamps.integer(rs, "average_score_pct"),
                        Timestamps.integer(rs, "best_score_pct"),
                        rs.getInt("current_streak_days")))
                .optional()
                // A student who has never started a case has no row in the view,
                // and zero is the honest answer rather than an error.
                .orElseGet(() -> new Progress(availableCases(), 0, 0, null, null, 0));
    }

    private int availableCases() {
        return db.sql("SELECT count(*) FROM v_servable_cases").query(Integer.class).single();
    }

    // -----------------------------------------------------------------------
    // per-concept strength
    // -----------------------------------------------------------------------
    public record ConceptStrength(int step, String concept, String label, int attempts,
                                  int firstAttempts, int firstAttemptCorrect,
                                  Double firstAttemptAccuracyPct, Instant lastPractisedAt) {
    }

    @GetMapping("/progress/concepts")
    public List<ConceptStrength> concepts() {
        long studentId = currentStudent.id();
        return db.sql("""
                SELECT s.step, s.concept, s.label,
                       coalesce(cs.attempts, 0)               AS attempts,
                       coalesce(cs.first_attempts, 0)         AS first_attempts,
                       coalesce(cs.first_attempt_correct, 0)  AS first_attempt_correct,
                       cs.first_attempt_accuracy_pct,
                       cs.last_practised_at
                FROM interpretation_steps s
                LEFT JOIN v_student_concept_strength cs
                       ON cs.concept = s.concept AND cs.student_id = :studentId
                ORDER BY s.step
                """)
                .param("studentId", studentId)
                .query((rs, n) -> new ConceptStrength(
                        rs.getInt("step"),
                        rs.getString("concept"),
                        rs.getString("label"),
                        rs.getInt("attempts"),
                        rs.getInt("first_attempts"),
                        rs.getInt("first_attempt_correct"),
                        rs.getObject("first_attempt_accuracy_pct") == null
                                ? null : rs.getDouble("first_attempt_accuracy_pct"),
                        Timestamps.instant(rs, "last_practised_at")))
                .list();
    }

    // -----------------------------------------------------------------------
    // what to practise next
    // -----------------------------------------------------------------------
    /**
     * The scheduler's answer, with its reasoning attached.
     *
     * <p>Each entry says why it is where it is. A student told to practise axis
     * is owed the reason, and "weakest concept, 40% correct first time" is a
     * reason; a reordered list with no explanation is not.
     */
    @GetMapping("/progress/next")
    public List<MasteryService.ConceptPriority> next(
            @RequestParam(defaultValue = "3") int limit) {
        return mastery.nextConcepts(currentStudent.id(), limit);
    }

    // -----------------------------------------------------------------------
    // recent sessions
    // -----------------------------------------------------------------------
    public record RecentSession(long sessionId, long caseId, Integer sourceEcgId, String mode,
                                String state, Integer scorePct, int stepsMarked,
                                Instant startedAt, Instant completedAt) {
    }

    @GetMapping("/progress/sessions")
    public List<RecentSession> recent(@RequestParam(defaultValue = "10") int limit) {
        long studentId = currentStudent.id();
        return db.sql("""
                SELECT sc.session_id, sc.case_id, c.source_ecg_id, sc.mode, sc.state,
                       sc.score_pct, sc.steps_marked, sc.started_at, sc.completed_at
                FROM v_session_scores sc
                JOIN cases c ON c.id = sc.case_id
                WHERE sc.student_id = :studentId
                ORDER BY sc.started_at DESC
                LIMIT :limit
                """)
                .param("studentId", studentId)
                .param("limit", Math.clamp(limit, 1, 50))
                .query((rs, n) -> new RecentSession(
                        rs.getLong("session_id"),
                        rs.getLong("case_id"),
                        Timestamps.integer(rs, "source_ecg_id"),
                        rs.getString("mode"),
                        rs.getString("state"),
                        Timestamps.integer(rs, "score_pct"),
                        rs.getInt("steps_marked"),
                        Timestamps.instant(rs, "started_at"),
                        Timestamps.instant(rs, "completed_at")))
                .list();
    }

    // -----------------------------------------------------------------------
    // what a teacher said
    // -----------------------------------------------------------------------
    public record Remark(long id, long sessionStepId, String reviewerName, String body,
                         java.time.Instant createdAt, java.time.Instant readAt,
                         int step, String stepLabel, Integer sourceEcgId, String errorLabel) {
    }

    /**
     * Remarks a teacher has left on this student's attempts.
     *
     * <p>Unread first: a remark a student has not seen is the only one that can
     * still change what they do next.
     */
    @GetMapping("/remarks")
    public List<Remark> remarks(@RequestParam(defaultValue = "20") int limit) {
        return db.sql("""
                SELECT r.id, r.session_step_id, rv.full_name AS reviewer_name, r.body,
                       r.created_at, r.read_at, ss.step, s.label AS step_label,
                       c.source_ecg_id, ss.error_label
                FROM faculty_remarks r
                JOIN reviewers rv            ON rv.id = r.reviewer_id
                JOIN session_steps ss        ON ss.id = r.session_step_id
                JOIN sessions se             ON se.id = ss.session_id
                JOIN cases c                 ON c.id = se.case_id
                JOIN interpretation_steps s  ON s.step = ss.step
                WHERE r.student_id = :studentId
                ORDER BY (r.read_at IS NOT NULL), r.created_at DESC
                LIMIT :limit
                """)
                .param("studentId", currentStudent.id())
                .param("limit", Math.clamp(limit, 1, 100))
                .query((rs, n) -> new Remark(
                        rs.getLong("id"), rs.getLong("session_step_id"),
                        rs.getString("reviewer_name"), rs.getString("body"),
                        Timestamps.instant(rs, "created_at"),
                        Timestamps.instant(rs, "read_at"),
                        rs.getInt("step"), rs.getString("step_label"),
                        Timestamps.integer(rs, "source_ecg_id"), rs.getString("error_label")))
                .list();
    }

    public record UnreadRemarks(int unread) {
    }

    /**
     * How many remarks are waiting, for the badge in the navigation.
     *
     * <p>Separate from {@link #remarks(int)} rather than counted from it. That
     * query joins six tables and carries every body back so the panel can show
     * them; the badge needs one integer, and it is fetched on every page a
     * student opens.
     */
    @GetMapping("/remarks/unread-count")
    public UnreadRemarks unreadRemarks() {
        return new UnreadRemarks(db.sql("""
                SELECT count(*)
                FROM faculty_remarks
                WHERE student_id = :studentId AND read_at IS NULL
                """)
                .param("studentId", currentStudent.id())
                .query(Integer.class)
                .single());
    }

    /** Marking read is the one change permitted to a remark; a trigger enforces the rest. */
    @org.springframework.web.bind.annotation.PostMapping("/remarks/{id}/read")
    public void markRead(@org.springframework.web.bind.annotation.PathVariable long id) {
        db.sql("""
                UPDATE faculty_remarks SET read_at = now()
                WHERE id = :id AND student_id = :studentId AND read_at IS NULL
                """)
                .param("id", id)
                .param("studentId", currentStudent.id())
                .update();
    }

    // -----------------------------------------------------------------------
    // leaderboard
    // -----------------------------------------------------------------------
    /**
     * Positions without names.
     *
     * <p>A cohort ranking that names the people at the bottom publishes a
     * student's weakness to their classmates. The caller is told their own
     * position and the distribution around it, and nothing identifying about
     * anybody else.
     */
    public record LeaderboardEntry(int position, boolean isYou, int casesCompleted,
                                   Integer averageScorePct, int currentStreakDays) {
    }

    @GetMapping("/progress/leaderboard")
    public List<LeaderboardEntry> leaderboard(@RequestParam(defaultValue = "10") int limit) {
        long studentId = currentStudent.id();
        return db.sql("""
                SELECT student_id, cases_completed, average_score_pct, current_streak_days,
                       rank() OVER (ORDER BY coalesce(average_score_pct, 0) DESC,
                                             cases_completed DESC) AS position
                FROM v_student_progress
                WHERE cases_completed > 0
                ORDER BY position
                LIMIT :limit
                """)
                .param("limit", Math.clamp(limit, 1, 50))
                .query((rs, n) -> new LeaderboardEntry(
                        rs.getInt("position"),
                        rs.getLong("student_id") == studentId,
                        rs.getInt("cases_completed"),
                        Timestamps.integer(rs, "average_score_pct"),
                        rs.getInt("current_streak_days")))
                .list();
    }
}
