package com.cardiosaarthi.review.auth;

import jakarta.validation.constraints.NotBlank;

/**
 * What the console's login form sends.
 *
 * <p>It offers two modes. Students and faculty at Terna are issued an
 * institutional ID and know it; many will not know which email address the
 * platform holds for them, so supporting only email would make the form lie
 * about what it accepts.
 *
 * @param mode "college" or "email"; anything else is treated as email
 */
public record LoginRequest(
        String collegeId,
        String email,
        @NotBlank(message = "password is required")
        String password,
        String mode) {

    public boolean byCollegeId() {
        return "college".equalsIgnoreCase(mode);
    }

    /** Whichever identifier this mode uses, trimmed. */
    public String identifier() {
        String raw = byCollegeId() ? collegeId : email;
        return raw == null ? "" : raw.trim();
    }
}
