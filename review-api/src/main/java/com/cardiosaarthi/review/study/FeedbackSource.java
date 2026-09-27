package com.cardiosaarthi.review.study;

/**
 * Where the words came from.
 *
 * <p>Recorded on every turn because the proportions are the cost model. Section
 * 14 of the brief budgets roughly ten rupees per active learner per month, and
 * that number only holds if confirmations stay templated and the cache does its
 * work. Measuring it is the only way to know whether it does.
 */
public enum FeedbackSource {
    /** Written in code, no model involved. Correct answers take this path. */
    TEMPLATE,
    /** A previous identical explanation, reused. */
    CACHE,
    /** A model call. */
    MODEL,
    /**
     * The faculty-approved library, used when a model call fails or its output is
     * rejected. Also the only source until the model is wired in.
     */
    FALLBACK
}
