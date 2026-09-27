package com.cardiosaarthi.review.auth;

import jakarta.validation.Valid;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private final PrincipalRepository principals;
    private final PasswordEncoder passwordEncoder;
    private final TokenService tokens;

    AuthController(PrincipalRepository principals, PasswordEncoder passwordEncoder, TokenService tokens) {
        this.principals = principals;
        this.passwordEncoder = passwordEncoder;
        this.tokens = tokens;
    }

    /**
     * Exchange credentials for a bearer token.
     *
     * <p>Every failure returns the same 401 and the same message. Distinguishing
     * "no such account" from "wrong password" tells an attacker which half to
     * keep working on, and tells a legitimate user nothing they can act on that
     * "check your details" does not.
     *
     * <p>The one exception is a role nothing implements yet, which says so: a
     * person told "wrong password" for an account that could never work will
     * keep trying.
     */
    @PostMapping("/login/{role}")
    public LoginResponse login(@PathVariable String role, @Valid @RequestBody LoginRequest request) {
        Role requested = parseRole(role);

        if (!requested.isImplemented()) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_IMPLEMENTED,
                    "The patient area is not built yet. Layer 4 of the project covers it.");
        }

        String identifier = request.identifier();
        if (identifier.isBlank()) {
            throw unauthorized();
        }

        PrincipalRepository.Candidate candidate = principals
                .find(requested, identifier, request.byCollegeId())
                .orElseThrow(AuthController::unauthorized);

        // A null hash is an account that exists but cannot be signed in to: one
        // invited but not activated, or the system account that seeds fixtures.
        if (candidate.passwordHash() == null || !candidate.active()) {
            throw unauthorized();
        }
        if (!passwordEncoder.matches(request.password(), candidate.passwordHash())) {
            log.info("failed login for {} as {}", identifier, requested);
            throw unauthorized();
        }

        TokenService.IssuedToken issued = tokens.issue(candidate.principal());
        log.info("{} {} signed in", requested, candidate.principal().id());
        return new LoginResponse(issued.token(), issued.expiresAt(), candidate.principal().view());
    }

    private static Role parseRole(String role) {
        try {
            return Role.valueOf(role.trim().toUpperCase());
        } catch (IllegalArgumentException exception) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "no such role: " + role);
        }
    }

    private static ResponseStatusException unauthorized() {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Check your details and try again.");
    }
}
