package com.cardiosaarthi.review.auth;

import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * Finds the person behind a login attempt.
 *
 * <p>Two tables, queried by role, because students and reviewers are different
 * populations. The password hash leaves this class only inside {@link Candidate}
 * and is never placed on {@link Principal}, which is what the API returns.
 */
@Repository
public class PrincipalRepository {

    private final JdbcClient db;

    PrincipalRepository(JdbcClient db) {
        this.db = db;
    }

    /** A row that might authenticate, including the hash to check against. */
    public record Candidate(Principal principal, String passwordHash, boolean active) {
    }

    /**
     * @param role        which table to look in
     * @param identifier  an email address, or a college ID when {@code byCollegeId}
     * @param byCollegeId the console's login form offers both
     */
    public Optional<Candidate> find(Role role, String identifier, boolean byCollegeId) {
        if (role == Role.STUDENT) {
            return findStudent(identifier, byCollegeId);
        }
        return findReviewer(role, identifier, byCollegeId);
    }

    private Optional<Candidate> findStudent(String identifier, boolean byCollegeId) {
        String column = byCollegeId ? "college_id" : "email";
        return db.sql("""
                SELECT id, full_name, email, college_id, password_hash, active
                FROM students
                WHERE lower(%s) = lower(:identifier)
                """.formatted(column))
                .param("identifier", identifier)
                .query((rs, n) -> new Candidate(
                        new Principal(
                                rs.getLong("id"),
                                rs.getString("full_name"),
                                rs.getString("email"),
                                rs.getString("college_id"),
                                Role.STUDENT),
                        rs.getString("password_hash"),
                        rs.getBoolean("active")))
                .optional();
    }

    /**
     * Reviewers carry their own role column, so the request's claimed role is
     * checked against it rather than trusted: someone signing in through the
     * faculty form must actually be faculty.
     */
    /** A reviewer row before its stored role has been reconciled. */
    private record ReviewerRow(long id, String name, String email, String collegeId,
                               String storedRole, String passwordHash, boolean active) {
    }

    private Optional<Candidate> findReviewer(Role requested, String identifier, boolean byCollegeId) {
        String column = byCollegeId ? "college_id" : "email";
        Optional<ReviewerRow> row = db.sql("""
                SELECT id, full_name, email, college_id, role, password_hash, active
                FROM reviewers
                WHERE lower(%s) = lower(:identifier)
                """.formatted(column))
                .param("identifier", identifier)
                .query((rs, n) -> new ReviewerRow(
                        rs.getLong("id"),
                        rs.getString("full_name"),
                        rs.getString("email"),
                        rs.getString("college_id"),
                        rs.getString("role"),
                        rs.getString("password_hash"),
                        rs.getBoolean("active")))
                .optional();

        // Reconciled outside the mapper. A mapper that returns null for an
        // unwanted row puts a null inside the result list, which .optional()
        // then has to make sense of.
        return row.flatMap(found -> {
            Role actual = switch (found.storedRole()) {
                case "admin" -> Role.ADMIN;
                case "faculty" -> Role.FACULTY;
                // The system account that seeds development fixtures belongs to
                // neither. It has a null hash and cannot authenticate anyway.
                default -> null;
            };
            // The claimed role is checked against the stored one rather than
            // trusted: someone signing in through the faculty form must actually
            // be faculty.
            if (actual == null || actual != requested) {
                return Optional.empty();
            }
            return Optional.of(new Candidate(
                    new Principal(found.id(), found.name(), found.email(), found.collegeId(), actual),
                    found.passwordHash(),
                    found.active()));
        });
    }

    /** Re-read on every request, so revoking access takes effect at once. */
    public Optional<Principal> byId(Role role, long id) {
        if (role == Role.STUDENT) {
            return db.sql("SELECT id, full_name, email, college_id FROM students WHERE id = :id AND active")
                    .param("id", id)
                    .query((rs, n) -> new Principal(
                            rs.getLong("id"), rs.getString("full_name"), rs.getString("email"),
                            rs.getString("college_id"), Role.STUDENT))
                    .optional();
        }
        return db.sql("SELECT id, full_name, email, college_id, role FROM reviewers WHERE id = :id AND active")
                .param("id", id)
                .query((rs, n) -> new Principal(
                        rs.getLong("id"), rs.getString("full_name"), rs.getString("email"),
                        rs.getString("college_id"),
                        "admin".equals(rs.getString("role")) ? Role.ADMIN : Role.FACULTY))
                .optional();
    }
}
