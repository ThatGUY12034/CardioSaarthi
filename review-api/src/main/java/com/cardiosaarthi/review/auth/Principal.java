package com.cardiosaarthi.review.auth;

/**
 * One authenticated person, whichever table they came from.
 *
 * <p>Students and reviewers are deliberately separate tables -- different
 * populations, different permissions, and one table with a role column makes it
 * possible to grant the wrong one by accident. This record is the shape they
 * share once identity has been established, and it is what the console receives.
 *
 * @param collegeId institutional identifier; null when none has been assigned
 */
public record Principal(
        long id,
        String name,
        String email,
        String collegeId,
        Role role) {

    /** The shape the console's AuthContext stores. */
    public record View(long id, String name, String email, String collegeId, String role) {
    }

    public View view() {
        return new View(id, name, email, collegeId, role.name());
    }
}
