package com.cardiosaarthi.review.auth;

import java.time.Duration;
import java.time.Instant;

import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.stereotype.Service;

/**
 * Issues the bearer tokens the console carries.
 *
 * <p>Signed with HMAC-SHA256 using Spring Security's encoder rather than a
 * hand-assembled token: a mistake in hand-rolled auth is a security hole, and
 * this is not the place to save a dependency.
 *
 * <p>The token carries who the person is and nothing about what they may do.
 * Permissions are read from the database on each request, so revoking access
 * takes effect immediately instead of when an unexpired token happens to run
 * out.
 */
@Service
public class TokenService {

    /**
     * Long enough for a teaching session or a faculty review sitting, short
     * enough that a token left on a shared college machine expires the same day.
     */
    public static final Duration LIFETIME = Duration.ofHours(8);

    private static final String ISSUER = "cardiosaarthi";

    private final JwtEncoder encoder;

    TokenService(JwtEncoder encoder) {
        this.encoder = encoder;
    }

    public record IssuedToken(String token, Instant expiresAt) {
    }

    public IssuedToken issue(Principal principal) {
        Instant now = Instant.now();
        Instant expiry = now.plus(LIFETIME);

        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(ISSUER)
                .issuedAt(now)
                .expiresAt(expiry)
                // The subject is the database id prefixed by role, because a
                // student and a reviewer can both be id 7 and they are not the
                // same person.
                .subject(principal.role().name() + ":" + principal.id())
                .claim("uid", principal.id())
                .claim("role", principal.role().name())
                .claim("email", principal.email())
                .claim("name", principal.name())
                .build();

        JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = encoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
        return new IssuedToken(token, expiry);
    }
}
