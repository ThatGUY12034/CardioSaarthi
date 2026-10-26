package com.cardiosaarthi.review.admin;

import java.time.Instant;
import java.util.List;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.error.InvalidReviewException;
import com.cardiosaarthi.review.error.NotFoundException;
import com.cardiosaarthi.review.support.Timestamps;
import com.cardiosaarthi.review.reviewer.ReviewerService;

import jakarta.validation.Valid;

/**
 * Running the installation: who has an account, and what state the platform is in.
 *
 * <p>Account creation already lives on /api/reviewers, which makes faculty and
 * administrators. What was missing is everything else an administrator needs:
 * seeing the other two populations at all, and being able to revoke access.
 *
 * <p>Deactivation rather than deletion, throughout. A reviewer's decisions and a
 * student's attempts are the evidence this platform is built to preserve, and
 * deleting the person deletes the attribution on all of it. An inactive account
 * cannot authenticate -- the principal lookup re-reads `active` on every request
 * -- while everything they did stays readable and attributed.
 */
@RestController
@RequestMapping("/api/admin")
@PreAuthorize("hasRole('ADMIN')")
public class AdminController {

    private static final Logger log = LoggerFactory.getLogger(AdminController.class);

    private final JdbcClient db;
    private final ReviewerService reviewers;
    private final PasswordEncoder passwordEncoder;

    AdminController(JdbcClient db, ReviewerService reviewers, PasswordEncoder passwordEncoder) {
        this.db = db;
        this.reviewers = reviewers;
        this.passwordEncoder = passwordEncoder;
    }

    // -----------------------------------------------------------------------
    // overview
    // -----------------------------------------------------------------------
    public record Overview(
            int casesTotal, int casesApproved, int casesPending, int casesRejected,
            int reviewers, int students, int patients,
            int sessionsStarted, int sessionsCompleted,
            int knowledgeTotal, int knowledgeApproved, int knowledgeApprovedByClinician,
            int narrativesWritten, int schemaVersion) {
    }

    @GetMapping("/overview")
    public Overview overview() {
        return db.sql("""
                SELECT
                    (SELECT count(*) FROM cases)                                        AS cases_total,
                    (SELECT count(*) FROM cases WHERE review_status = 'approved')       AS cases_approved,
                    (SELECT count(*) FROM cases WHERE review_status = 'pending')        AS cases_pending,
                    (SELECT count(*) FROM cases WHERE review_status = 'rejected')       AS cases_rejected,
                    (SELECT count(*) FROM reviewers WHERE role <> 'system')             AS reviewers,
                    (SELECT count(*) FROM students)                                     AS students,
                    (SELECT count(*) FROM patients)                                     AS patients,
                    (SELECT count(*) FROM sessions)                                     AS sessions_started,
                    (SELECT count(*) FROM sessions WHERE state = 'CASE_COMPLETE')       AS sessions_completed,
                    (SELECT total FROM v_knowledge_provenance)                          AS knowledge_total,
                    (SELECT approved FROM v_knowledge_provenance)                       AS knowledge_approved,
                    (SELECT approved_by_clinician FROM v_knowledge_provenance)          AS knowledge_clinician,
                    (SELECT count(*) FROM cases WHERE narrative IS NOT NULL)            AS narratives,
                    (SELECT max(version::numeric)::int FROM flyway_schema_history
                      WHERE success)                                                    AS schema_version
                """)
                .query((rs, n) -> new Overview(
                        rs.getInt("cases_total"), rs.getInt("cases_approved"),
                        rs.getInt("cases_pending"), rs.getInt("cases_rejected"),
                        rs.getInt("reviewers"), rs.getInt("students"), rs.getInt("patients"),
                        rs.getInt("sessions_started"), rs.getInt("sessions_completed"),
                        rs.getInt("knowledge_total"), rs.getInt("knowledge_approved"),
                        rs.getInt("knowledge_clinician"), rs.getInt("narratives"),
                        rs.getInt("schema_version")))
                .single();
    }

    // -----------------------------------------------------------------------
    // accounts
    // -----------------------------------------------------------------------
    /**
     * @param kind      reviewer, student or patient
     * @param canSignIn false for an account with no password set, which is an
     *                  invitation that was never taken up rather than a person
     *                  who has been locked out
     */
    public record Account(String kind, long id, String fullName, String email,
                          String identifier, String role, boolean active,
                          boolean canSignIn, Instant createdAt) {
    }

    @GetMapping("/users")
    public List<Account> users(@RequestParam(required = false) String kind) {
        String wanted = kind == null || kind.isBlank() ? null : kind.trim().toLowerCase();

        // One query per population rather than a union with padded columns: the
        // three tables genuinely differ, and a union that pretends otherwise
        // ends up with a patient_ref in a column called college_id.
        List<Account> all = new java.util.ArrayList<>();
        if (wanted == null || "reviewer".equals(wanted)) {
            all.addAll(db.sql("""
                    SELECT id, full_name, email, college_id, role, active, password_hash, created_at
                    FROM reviewers
                    WHERE role <> 'system'
                    ORDER BY full_name
                    """)
                    .query((rs, n) -> new Account("reviewer", rs.getLong("id"),
                            rs.getString("full_name"), rs.getString("email"),
                            rs.getString("college_id"), rs.getString("role"),
                            rs.getBoolean("active"), rs.getString("password_hash") != null,
                            Timestamps.instant(rs, "created_at")))
                    .list());
        }
        if (wanted == null || "student".equals(wanted)) {
            all.addAll(db.sql("""
                    SELECT id, full_name, email, college_id, cohort, active, password_hash, created_at
                    FROM students ORDER BY full_name
                    """)
                    .query((rs, n) -> new Account("student", rs.getLong("id"),
                            rs.getString("full_name"), rs.getString("email"),
                            rs.getString("college_id"), rs.getString("cohort"),
                            rs.getBoolean("active"), rs.getString("password_hash") != null,
                            Timestamps.instant(rs, "created_at")))
                    .list());
        }
        if (wanted == null || "patient".equals(wanted)) {
            all.addAll(db.sql("""
                    SELECT id, full_name, email, patient_ref, active, password_hash, created_at
                    FROM patients ORDER BY full_name
                    """)
                    .query((rs, n) -> new Account("patient", rs.getLong("id"),
                            rs.getString("full_name"), rs.getString("email"),
                            rs.getString("patient_ref"), "patient",
                            rs.getBoolean("active"), rs.getString("password_hash") != null,
                            Timestamps.instant(rs, "created_at")))
                    .list());
        }
        return all;
    }

    public record ActiveFlag(@NotNull(message = "active is required") Boolean active) {
    }

    /**
     * Revoke or restore access.
     *
     * <p>Takes effect on the next request rather than at the next login: the
     * principal lookup re-reads `active` every time, so a revoked account cannot
     * keep working on a token issued a minute ago.
     */
    @PostMapping("/users/{kind}/{id}/active")
    public Account setActive(@PathVariable String kind, @PathVariable long id,
                             @Valid @RequestBody ActiveFlag flag) {
        String table = switch (kind.toLowerCase()) {
            case "reviewer" -> "reviewers";
            case "student" -> "students";
            case "patient" -> "patients";
            default -> throw new InvalidReviewException(
                    "kind must be reviewer, student or patient, not '" + kind + "'");
        };

        // An administrator locking themselves out cannot unlock themselves, and
        // on a single-administrator installation that is the end of the account
        // management story.
        if ("reviewers".equals(table) && !flag.active() && id == reviewers.current().id()) {
            throw new InvalidReviewException("you cannot deactivate your own account");
        }

        int updated = db.sql("UPDATE %s SET active = :active WHERE id = :id".formatted(table))
                .param("active", flag.active())
                .param("id", id)
                .update();
        if (updated == 0) {
            throw new NotFoundException("no " + kind + " " + id);
        }

        log.warn("administrator {} set {} {} active={}",
                reviewers.current().email(), kind, id, flag.active());

        return users(kind).stream()
                .filter(account -> account.id() == id)
                .findFirst()
                .orElseThrow(() -> new NotFoundException("no " + kind + " " + id));
    }

    // -----------------------------------------------------------------------
    // enrolment
    // -----------------------------------------------------------------------
    /**
     * @param password hashed before it reaches the database and never logged.
     *                 Twelve characters, the same floor the reviewer endpoint
     *                 enforces: the four-digit demonstration logins come from a
     *                 flag that defaults to off and are not created here.
     */
    public record NewStudent(
            @NotBlank @Email(message = "a valid email address is required") String email,
            @NotBlank(message = "full name is required") @Size(max = 200) String fullName,
            @NotBlank(message = "college ID is required") String collegeId,
            String cohort,
            @NotBlank @Size(min = 12, message = "password must be at least 12 characters")
            String password) {
    }

    /**
     * Enrol a student, or reset an existing one's password.
     *
     * <p>Upsert rather than a conflict, for the same reason the reviewer
     * endpoint does it: the realistic administrative task is "this student has
     * forgotten their password", and a create-only endpoint leaves no way to do
     * it. Their attempts and remarks are keyed on the row, so they survive it.
     */
    @PostMapping("/students")
    @ResponseStatus(HttpStatus.CREATED)
    public Account enrol(@Valid @RequestBody NewStudent request) {
        long id = db.sql("""
                INSERT INTO students (email, full_name, college_id, cohort, password_hash)
                VALUES (:email, :fullName, :collegeId, :cohort, :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    full_name     = excluded.full_name,
                    college_id    = excluded.college_id,
                    cohort        = excluded.cohort,
                    password_hash = excluded.password_hash,
                    active        = true
                RETURNING id
                """)
                .param("email", request.email().trim())
                .param("fullName", request.fullName().trim())
                .param("collegeId", request.collegeId().trim())
                .param("cohort", request.cohort() == null || request.cohort().isBlank()
                        ? null : request.cohort().trim())
                .param("hash", passwordEncoder.encode(request.password()))
                .query(Long.class)
                .single();

        log.info("administrator {} enrolled student {}", reviewers.current().email(), id);
        return users("student").stream()
                .filter(a -> a.id() == id)
                .findFirst()
                .orElseThrow(() -> new NotFoundException("no student " + id));
    }

    // -----------------------------------------------------------------------
    // content
    // -----------------------------------------------------------------------
    /** Syllabus coverage, so an administrator can see where the bank is thin. */
    public record ConditionCoverage(String code, String label, int approved, int pending,
                                    int target) {
    }

    @GetMapping("/coverage")
    public List<ConditionCoverage> coverage() {
        return db.sql("""
                SELECT c.code, c.label, c.target_cases,
                       count(*) FILTER (WHERE ca.review_status = 'approved') AS approved,
                       count(*) FILTER (WHERE ca.review_status = 'pending')  AS pending
                FROM conditions c
                LEFT JOIN case_conditions cc ON cc.condition_code = c.code
                LEFT JOIN cases ca           ON ca.id = cc.case_id
                GROUP BY c.code, c.label, c.target_cases
                ORDER BY approved, c.code
                """)
                .query((rs, n) -> new ConditionCoverage(
                        rs.getString("code"), rs.getString("label"),
                        rs.getInt("approved"), rs.getInt("pending"),
                        rs.getInt("target_cases")))
                .list();
    }
}
