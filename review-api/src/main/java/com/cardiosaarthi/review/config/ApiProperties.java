package com.cardiosaarthi.review.config;

import java.nio.file.Path;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Configuration for the review service.
 *
 * @param repoRoot           directory that image paths stored in the database are resolved against
 * @param corsAllowedOrigins origins the review console is served from
 * @param bootstrap          optional single administrator created at start up
 * @param jwtSecret          HMAC key the console's bearer tokens are signed with
 */
@ConfigurationProperties(prefix = "cardiosaarthi")
public record ApiProperties(
        String repoRoot,
        List<String> corsAllowedOrigins,
        Bootstrap bootstrap,
        String jwtSecret) {

    /**
     * An account created or updated when the service starts.
     *
     * <p>All three fields must be present for anything to happen. This exists so
     * that a fresh installation can be logged into at all; it is not a way to
     * manage faculty accounts, and leaving it unset is the right default.
     */
    public record Bootstrap(String email, String fullName, String password) {

        public boolean isConfigured() {
            return email != null && !email.isBlank()
                    && password != null && !password.isBlank();
        }
    }

    /**
     * Absolute, normalised root. Image requests are checked to stay inside it.
     *
     * <p>Held as a String rather than a Path because Spring converts a configured
     * Path through resource-path normalisation, which rejects a bare "..".
     */
    public Path resolvedRoot() {
        return Path.of(repoRoot).toAbsolutePath().normalize();
    }
}
