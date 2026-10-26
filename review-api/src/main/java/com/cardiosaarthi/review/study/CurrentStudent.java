package com.cardiosaarthi.review.study;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

import com.cardiosaarthi.review.error.NotFoundException;

/**
 * The student making the current request.
 *
 * <p>Resolved from the token or from the Basic principal's email, never from
 * the request body: a student id a caller can choose is a student id a caller
 * can choose to be somebody else's.
 *
 * <p>This lived as a private method on the session controller until a second
 * controller needed it. Sharing it by injecting one controller into another
 * would have made a request-scoped identity lookup part of a controller's
 * public surface, which is the wrong place for it.
 */
@Component
public class CurrentStudent {

    private final JdbcClient db;

    CurrentStudent(JdbcClient db) {
        this.db = db;
    }

    public long id() {
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
