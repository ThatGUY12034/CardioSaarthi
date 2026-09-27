package com.cardiosaarthi.review.auth;

/**
 * Who someone is, from the console's point of view.
 *
 * <p>PATIENT is listed because the console has a patient area and Layer 4 of the
 * brief specifies one. Nothing implements it yet, and login for that role is
 * refused with a message saying so rather than quietly failing as bad
 * credentials -- a person told "wrong password" will keep trying.
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
        return this != PATIENT;
    }

    /** The value stored in reviewers.role. */
    public String reviewerRole() {
        return this == ADMIN ? "admin" : "faculty";
    }
}
