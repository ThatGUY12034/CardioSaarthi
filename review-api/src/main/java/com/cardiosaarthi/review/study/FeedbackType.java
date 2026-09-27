package com.cardiosaarthi.review.study;

/** What kind of thing the platform says back. */
public enum FeedbackType {
    /**
     * A correct answer. Templated, and deliberately never a model call: section
     * 5.4 expects about half of all turns to land here, and paying for a model
     * to say "yes, that's right" is the easiest cost in the system to avoid.
     */
    CONFIRMATION,
    /** A first wrong answer in a practice mode. Must never contain the value. */
    HINT,
    /** A final wrong answer: the full reasoning, and the step then advances. */
    EXPLANATION,
    /** Examiner mode. Recorded now, told to the student at the end of the case. */
    DEFERRED
}
