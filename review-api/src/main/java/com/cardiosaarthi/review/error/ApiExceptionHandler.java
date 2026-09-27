package com.cardiosaarthi.review.error;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * One error shape for the whole API, so the console has one thing to handle.
 *
 * <p>Messages are written to be read by a reviewer, not only by a developer: if
 * a correction is refused the response says which measure and what range would
 * have been accepted, because "422 Unprocessable Entity" tells the person at the
 * screen nothing about what to do next.
 */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    /**
     * @param fieldErrors field name to message, present only for validation failures
     */
    public record ApiError(
            int status,
            String error,
            String message,
            Map<String, String> fieldErrors,
            Instant timestamp) {

        static ApiError of(HttpStatus status, String message) {
            return new ApiError(status.value(), status.getReasonPhrase(), message, null, Instant.now());
        }
    }

    @ExceptionHandler(NotFoundException.class)
    ResponseEntity<ApiError> notFound(NotFoundException exception) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiError.of(HttpStatus.NOT_FOUND, exception.getMessage()));
    }

    @ExceptionHandler(ConflictException.class)
    ResponseEntity<ApiError> conflict(ConflictException exception) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(ApiError.of(HttpStatus.CONFLICT, exception.getMessage()));
    }

    @ExceptionHandler(InvalidReviewException.class)
    ResponseEntity<ApiError> invalid(InvalidReviewException exception) {
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_CONTENT)
                .body(ApiError.of(HttpStatus.UNPROCESSABLE_CONTENT, exception.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> validation(MethodArgumentNotValidException exception) {
        Map<String, String> fields = new TreeMap<>();
        exception.getBindingResult().getFieldErrors()
                .forEach(error -> fields.put(error.getField(), error.getDefaultMessage()));
        List<String> global = exception.getBindingResult().getGlobalErrors().stream()
                .map(error -> error.getDefaultMessage())
                .toList();

        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(new ApiError(
                HttpStatus.BAD_REQUEST.value(),
                HttpStatus.BAD_REQUEST.getReasonPhrase(),
                global.isEmpty() ? "the request body is not valid" : String.join("; ", global),
                fields.isEmpty() ? null : fields,
                Instant.now()));
    }

    /**
     * A URL that matches no handler.
     *
     * <p>Without this, Spring's NoResourceFoundException falls through to the
     * catch-all below and a mistyped path is reported as a server fault. It also
     * covers a path-traversal attempt: the container normalises the path first,
     * so it arrives here as an ordinary unknown URL.
     */
    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<ApiError> noResource(NoResourceFoundException exception) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiError.of(HttpStatus.NOT_FOUND, "no endpoint at " + exception.getResourcePath()));
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<ApiError> methodNotAllowed(HttpRequestMethodNotSupportedException exception) {
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED)
                .body(ApiError.of(HttpStatus.METHOD_NOT_ALLOWED, exception.getMessage()));
    }

    /**
     * A body that could not be parsed at all -- malformed JSON, or a value that is
     * not one of an enum's constants.
     *
     * <p>This is the client's mistake, not the server's, and it has to say so:
     * an unknown action name is the single most likely thing a console gets wrong,
     * and reporting it as 500 would send whoever is debugging it to the wrong side
     * of the wire.
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<ApiError> unreadable(HttpMessageNotReadableException exception) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(ApiError.of(
                HttpStatus.BAD_REQUEST,
                "the request body could not be read; check that every field has the right type "
                        + "and that action and rejectionReason use the names from /api/review/options"));
    }

    /**
     * Anything unanticipated. The detail is logged with a stack trace and not
     * returned: a database message can name columns and constraints, and the
     * person at the other end of this API is a nursing faculty reviewer.
     */
    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> unexpected(Exception exception) {
        log.error("unhandled exception serving a review request", exception);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiError.of(HttpStatus.INTERNAL_SERVER_ERROR, "the server could not complete the request"));
    }
}
