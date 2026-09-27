package com.cardiosaarthi.review.review;

/**
 * Why a case was rejected.
 *
 * <p>A closed list rather than free text, because the rejection log is reported
 * as a pipeline-accuracy measure and "bad" counted forty times tells you nothing
 * about what to fix. The values match the CHECK constraint on reviews.
 *
 * <p>{@link #WRONG_MEASUREMENT} and {@link #POOR_SIGNAL_QUALITY} are the two that
 * point back at the engine; the rest point at the case.
 */
public enum RejectionReason {

    WRONG_MEASUREMENT("wrong_measurement"),
    POOR_SIGNAL_QUALITY("poor_signal_quality"),
    WRONG_DIAGNOSIS_LABEL("wrong_diagnosis_label"),
    UNSUITABLE_FOR_TEACHING("unsuitable_for_teaching"),
    NARRATIVE_INCONSISTENT("narrative_inconsistent"),
    OTHER("other");

    private final String dbValue;

    RejectionReason(String dbValue) {
        this.dbValue = dbValue;
    }

    public String dbValue() {
        return dbValue;
    }
}
