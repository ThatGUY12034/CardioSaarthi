package com.cardiosaarthi.review.review;

/**
 * What a reviewer did with a case.
 *
 * <p>The three the brief specifies. {@link #EDIT} and {@link #APPROVE} both make
 * a case servable and are kept apart deliberately: the proportion of cases that
 * needed correcting before they were usable is the pipeline-accuracy figure, and
 * collapsing an edit into an approval would erase it.
 */
public enum ReviewAction {

    /** The measurements were right as computed. */
    APPROVE("approve", "approved"),

    /** At least one measurement was corrected, and the case is then usable. */
    EDIT("edit", "approved"),

    /** The case is not usable for teaching, with a reason. */
    REJECT("reject", "rejected");

    private final String logValue;
    private final String resultingCaseStatus;

    ReviewAction(String logValue, String resultingCaseStatus) {
        this.logValue = logValue;
        this.resultingCaseStatus = resultingCaseStatus;
    }

    /** Value written to reviews.action. */
    public String logValue() {
        return logValue;
    }

    /** What cases.review_status becomes. */
    public String resultingCaseStatus() {
        return resultingCaseStatus;
    }

    public boolean requiresCorrections() {
        return this == EDIT;
    }

    public boolean forbidsCorrections() {
        return this == APPROVE || this == REJECT;
    }
}
