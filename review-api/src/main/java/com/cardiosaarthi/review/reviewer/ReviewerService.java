package com.cardiosaarthi.review.reviewer;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

/**
 * Turns database rows into authenticated identities, and back again.
 *
 * <p>The second direction is the one that matters: a review or a correction must
 * carry the database id of the person who made it, so every write path resolves
 * the authenticated principal to a reviewer row rather than trusting an id sent
 * by the client.
 */
@Service
public class ReviewerService implements UserDetailsService {

    private final ReviewerRepository reviewers;

    ReviewerService(ReviewerRepository reviewers) {
        this.reviewers = reviewers;
    }

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        ReviewerRepository.Credentials credentials = reviewers.findCredentialsByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("no reviewer with that email"));

        if (credentials.passwordHash() == null) {
            // Deliberately the same failure as an unknown email: whether an
            // account exists is not something an unauthenticated caller should
            // be able to probe for.
            throw new UsernameNotFoundException("no reviewer with that email");
        }

        return User.withUsername(credentials.email())
                .password(credentials.passwordHash())
                .roles(credentials.role().toUpperCase())
                .disabled(!credentials.active())
                .build();
    }

    /**
     * The reviewer making the current request.
     *
     * @throws IllegalStateException if there is no authentication, which would
     *                               mean the security filter chain let an
     *                               unauthenticated request reach a write path
     */
    public Reviewer current() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new IllegalStateException("no authenticated reviewer on this request");
        }
        return reviewers.findByEmail(authentication.getName())
                .orElseThrow(() -> new IllegalStateException(
                        "authenticated as " + authentication.getName() + " but no reviewer row exists"));
    }
}
