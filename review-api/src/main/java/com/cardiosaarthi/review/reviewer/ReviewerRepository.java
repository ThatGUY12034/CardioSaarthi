package com.cardiosaarthi.review.reviewer;

import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class ReviewerRepository {

    private static final String COLUMNS = "id, email, full_name, role, active, created_at";

    private final JdbcClient db;

    ReviewerRepository(JdbcClient db) {
        this.db = db;
    }

    /**
     * Credentials for authentication only.
     *
     * <p>A null hash means the account exists but cannot be logged into. That is
     * a real state -- an invited reviewer who has not set a password, or one
     * whose access was withdrawn without erasing the corrections they made.
     */
    record Credentials(long id, String email, String passwordHash, String role, boolean active) {
    }

    Optional<Credentials> findCredentialsByEmail(String email) {
        return db.sql("SELECT id, email, password_hash, role, active FROM reviewers WHERE lower(email) = lower(:email)")
                .param("email", email)
                .query((rs, n) -> new Credentials(
                        rs.getLong("id"),
                        rs.getString("email"),
                        rs.getString("password_hash"),
                        rs.getString("role"),
                        rs.getBoolean("active")))
                .optional();
    }

    public Optional<Reviewer> findByEmail(String email) {
        return db.sql("SELECT " + COLUMNS + " FROM reviewers WHERE lower(email) = lower(:email)")
                .param("email", email)
                .query(Reviewer.class)
                .optional();
    }

    public Optional<Reviewer> findById(long id) {
        return db.sql("SELECT " + COLUMNS + " FROM reviewers WHERE id = :id")
                .param("id", id)
                .query(Reviewer.class)
                .optional();
    }

    /**
     * Creates the account, or updates the name, role and password of an existing
     * one. Used only by the start-up bootstrap.
     */
    public long upsert(String email, String fullName, String role, String passwordHash) {
        return db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash)
                VALUES (:email, :fullName, :role, :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    full_name     = excluded.full_name,
                    role          = excluded.role,
                    password_hash = excluded.password_hash,
                    active        = true
                RETURNING id
                """)
                .param("email", email)
                .param("fullName", fullName)
                .param("role", role)
                .param("hash", passwordHash)
                .query(Long.class)
                .single();
    }
}
