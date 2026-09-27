package com.cardiosaarthi.review.error;

/**
 * The request is syntactically valid but clinically or logically impossible --
 * a correction to a measure the case does not have, a PR interval of 5 seconds,
 * a rejection with no reason. Rendered as 422.
 */
public class InvalidReviewException extends RuntimeException {

    public InvalidReviewException(String message) {
        super(message);
    }
}
