package com.cardiosaarthi.review.error;

/**
 * The request is well formed but the current state does not allow it.
 * Rendered as 409.
 *
 * <p>The case this exists for: two reviewers open the same case and both submit
 * a decision. The second must be told the case was already decided rather than
 * silently overwriting the first, because a review is a record of what a person
 * judged and not a settable field.
 */
public class ConflictException extends RuntimeException {

    public ConflictException(String message) {
        super(message);
    }
}
