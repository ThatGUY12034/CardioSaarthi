package com.cardiosaarthi.review.auth;

/**
 * Who someone is, from the console's point of view.
 *
 * <p>All four are implemented. PATIENT was refused outright until Layer 4 had a
 * backend, with a message saying so rather than a quiet credential failure --
 * a person told "wrong password" for an account that could never work will keep
 * trying.
 */
public enum Role {
    STUDENT,
    FACULTY,
    ADMIN,
    PATIENT;

    public boolean isReviewer() {
        return this == FACULTY || this == ADMIN;
    }

    public boolean isImplemented() {
        return true;
    }

    /** The value stored in reviewers.role. */
    public String reviewerRole() {
        return this == ADMIN ? "admin" : "faculty";
    }
}
