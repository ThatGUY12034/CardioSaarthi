package com.cardiosaarthi.review.reviewer;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * Creating and listing reviewer accounts.
 *
 * <p>Restricted to administrators in {@code SecurityConfig}, declaratively, so
 * the rule holds for a bearer token and for HTTP Basic without this class having
 * to check twice.
 *
 * <p>This exists because nursing faculty cannot review anything without an
 * account, and until now the only way to create one was the single bootstrap
 * administrator read from configuration at start-up.
 */
@RestController
@RequestMapping("/api/reviewers")
public class ReviewerAdminController {

    private static final Logger log = LoggerFactory.getLogger(ReviewerAdminController.class);

    private final ReviewerRepository reviewers;
    private final PasswordEncoder passwordEncoder;

    ReviewerAdminController(ReviewerRepository reviewers, PasswordEncoder passwordEncoder) {
        this.reviewers = reviewers;
        this.passwordEncoder = passwordEncoder;
    }

    /**
     * @param role     faculty or admin. The system role is deliberately not
     *                 creatable here: it exists for seeded development fixtures
     *                 and its decisions are excluded from every reported
     *                 statistic, which is not something to hand out through an API.
     * @param password hashed before it reaches the database and never logged
     */
    public record NewReviewer(
            @NotBlank @Email(message = "a valid email address is required")
            String email,

            @NotBlank(message = "full name is required")
            @Size(max = 200)
            String fullName,

            @Pattern(regexp = "faculty|admin", message = "role must be faculty or admin")
            String role,

            String collegeId,

            @NotBlank
            @Size(min = 12, message = "password must be at least 12 characters")
            String password) {

        String roleOrDefault() {
            return role == null || role.isBlank() ? "faculty" : role;
        }
    }

    /**
     * Creates the account, or resets the password and details of an existing one.
     *
     * <p>Upsert rather than a conflict, because the realistic administrative task
     * is "this reviewer has forgotten their password", and a create-only endpoint
     * would leave no way to do it.
     */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Reviewer create(@Valid @RequestBody NewReviewer request) {
        long id = reviewers.upsert(
                request.email().trim(),
                request.fullName().trim(),
                request.roleOrDefault(),
                passwordEncoder.encode(request.password()));

        if (request.collegeId() != null && !request.collegeId().isBlank()) {
            reviewers.setCollegeId(id, request.collegeId().trim());
        }

        log.info("reviewer {} created or updated as {}", id, request.roleOrDefault());
        return reviewers.findById(id).orElseThrow();
    }

    /** Everyone who can review, without a password hash in sight. */
    @GetMapping
    public List<Reviewer> list() {
        return reviewers.findAll();
    }
}
