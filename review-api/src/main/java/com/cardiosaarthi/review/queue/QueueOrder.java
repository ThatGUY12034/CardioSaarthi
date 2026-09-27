package com.cardiosaarthi.review.queue;

/**
 * How the queue is sorted.
 *
 * <p>Two of these are legitimate answers to different questions, which is why
 * the choice is the caller's rather than baked into the view:
 *
 * <ul>
 *   <li>{@link #BANK_FIRST} makes the case bank usable soonest. It puts the
 *       conditions furthest from their target first, and within those the
 *       engine's most confident cases, which are the ones most likely to be a
 *       quick confirmation rather than a careful correction.
 *   <li>{@link #LEAST_CONFIDENT} validates the engine instead. It puts the cases
 *       the engine is least sure of in front of the reviewer, which is where its
 *       errors are.
 * </ul>
 *
 * The SQL fragment is a fixed constant per enum value and never built from
 * caller input.
 */
public enum QueueOrder {

    BANK_FIRST("max_condition_shortfall DESC, overall_confidence DESC, case_id"),
    LEAST_CONFIDENT("overall_confidence ASC, case_id"),
    OLDEST_FIRST("created_at ASC, case_id");

    private final String orderBy;

    QueueOrder(String orderBy) {
        this.orderBy = orderBy;
    }

    String orderBy() {
        return orderBy;
    }
}
