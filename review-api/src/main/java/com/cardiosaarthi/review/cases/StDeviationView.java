package com.cardiosaarthi.review.cases;

/**
 * ST deviation in one lead.
 *
 * <p>Per lead rather than summarised, because which leads are involved is what
 * localises the territory, and a single "ST abnormal" flag throws away the only
 * clinically useful part of the finding.
 *
 * @param deviationMm deviation at the J point plus 60 ms, against the PR-segment baseline
 * @param thresholdMm the threshold applied to this lead; limb and precordial leads differ
 */
public record StDeviationView(
        String lead,
        Double deviationMm,
        Double thresholdMm,
        String finding,
        Double madMm,
        int nBeats,
        Double confidence) {

    public boolean isAbnormal() {
        return finding != null && !"NORMAL".equals(finding);
    }
}
