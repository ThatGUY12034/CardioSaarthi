package com.cardiosaarthi.review.auth;

import java.time.Instant;

/**
 * The shape the console's AuthContext stores: a token and the person.
 *
 * @param expiresAt sent so the console can log someone out before a request
 *                  fails, rather than after
 */
public record LoginResponse(String token, Instant expiresAt, Principal.View user) {
}
