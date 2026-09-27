package com.cardiosaarthi.review.error;

/** The thing asked for does not exist. Rendered as 404. */
public class NotFoundException extends RuntimeException {

    public NotFoundException(String message) {
        super(message);
    }
}
