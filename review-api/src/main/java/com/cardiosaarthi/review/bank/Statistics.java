package com.cardiosaarthi.review.bank;

import java.util.List;

/**
 * The two things this project has to be able to report at the end.
 *
 * @param outcomes         what happened to the cases that were reviewed
 * @param agreement        how far the engine was from a trained reviewer, per measure
 * @param rejectionReasons why cases were thrown out, which is the pipeline-accuracy measure
 */
public record Statistics(
        Outcomes outcomes,
        List<Agreement> agreement,
        List<RejectionCount> rejectionReasons) {

    /**
     * @param usablePct            approved plus edited, as a share of all reviews:
     *                             the proportion of generated cases that turned
     *                             out to be teachable
     * @param medianSecondsPerCase reviewer throughput. Faculty review capacity is
     *                             the critical path of this project, so it is
     *                             measured rather than assumed.
     */
    public record Outcomes(
            int nReviews,
            int approved,
            int edited,
            int rejected,
            Double approvedPct,
            Double usablePct,
            Double meanSecondsPerCase,
            Double medianSecondsPerCase,
            int pendingRemaining) {
    }

    /**
     * Agreement between the engine and the reviewers for one measure.
     *
     * <p>Bias and scatter are separate columns because they mean different things.
     * A consistent offset is usually fixable in the algorithm. A large error with
     * near-zero bias is scatter and is not. Corrections of +20 ms and -20 ms are
     * 20 ms of error and zero bias, and a single averaged figure would report
     * this engine as perfect.
     *
     * @param nCorrections how many times a reviewer changed this measure; a small
     *                     n means the rest of these numbers are not yet evidence
     */
    public record Agreement(
            String name,
            String unit,
            int nCorrections,
            Double mae,
            Double medianAbsError,
            Double bias,
            Double sd,
            Double worst) {
    }

    public record RejectionCount(String reason, int n, Double pct) {
    }
}
