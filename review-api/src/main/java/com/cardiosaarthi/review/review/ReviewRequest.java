package com.cardiosaarthi.review.review;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

/**
 * A reviewer's decision on one case.
 *
 * <p>The reviewer's identity is not in here. It comes from the authenticated
 * request, because an id a client can put in a body is an id a client can get
 * wrong, and attribution is the only thing that makes a correction evidence.
 *
 * @param durationSeconds how long the reviewer spent. Optional, and worth
 *                        sending: faculty review throughput is the critical path
 *                        of this project, and this is the only way to answer how
 *                        many cases one reviewer clears in a sitting with a
 *                        measurement rather than a guess.
 */
public record ReviewRequest(
        @NotNull(message = "action is required: APPROVE, EDIT or REJECT")
        ReviewAction action,

        @Valid
        List<Correction> corrections,

        RejectionReason rejectionReason,

        @Size(max = 2000, message = "note must be 2000 characters or fewer")
        String note,

        @PositiveOrZero(message = "durationSeconds cannot be negative")
        Integer durationSeconds) {

    /**
     * One corrected measurement.
     *
     * @param name  the measure being corrected, as the engine names it
     *              (heart_rate, pr_interval, qrs_duration, qt_interval,
     *              qtc_bazett, qtc_fridericia, p_duration)
     * @param value the reviewer's number, in the measure's own unit
     */
    public record Correction(
            @NotBlank(message = "each correction needs a measure name")
            String name,

            @NotNull(message = "each correction needs a value")
            Double value,

            @Size(max = 500, message = "correction note must be 500 characters or fewer")
            String note) {
    }

    public List<Correction> correctionsOrEmpty() {
        return corrections == null ? List.of() : corrections;
    }
}
