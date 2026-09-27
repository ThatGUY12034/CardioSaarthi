package com.cardiosaarthi.review.reviewer;

import java.time.OffsetDateTime;

/**
 * A person who reviews cases.
 *
 * <p>No password hash appears here. This record is what the API returns, and a
 * hash that is never loaded into a response object cannot be leaked by one.
 */
public record Reviewer(
        long id,
        String email,
        String fullName,
        String role,
        boolean active,
        OffsetDateTime createdAt) {

    public boolean isAdmin() {
        return "admin".equals(role);
    }
}
