package com.cardiosaarthi.review.study;

/** How a step's answer is shaped, and therefore how it is compared. */
public enum AnswerKind {
    /** A number judged against a tolerance, e.g. the rate or the PR interval. */
    NUMERIC,
    /** One of a fixed set, e.g. the rhythm or the axis. */
    CATEGORICAL,
    /** A set of leads, e.g. which leads show ST deviation. */
    MULTI_CATEGORICAL
}
