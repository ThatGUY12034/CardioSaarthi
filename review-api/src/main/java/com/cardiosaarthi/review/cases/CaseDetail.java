package com.cardiosaarthi.review.cases;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * Everything a reviewer needs to decide on one case.
 *
 * <p>Note what is absent: no interpretation and no diagnosis of ours.
 * {@code diagnosticLabels} are the dataset's cardiologist annotations copied
 * verbatim, and the reviewer's job is to check the measurements against the
 * waveform, not to re-derive the diagnosis.
 *
 * @param ageCensored the source dataset stores ages above 89 as 300 to prevent
 *                    re-identification; such an age is clamped and flagged, so
 *                    "89" on screen can be shown as "89 or older"
 * @param warnings    why the engine held the case back, in its own words
 */
public record CaseDetail(
        long id,
        String source,
        int sourceEcgId,
        Double age,
        boolean ageCensored,
        String sex,
        List<String> diagnosticLabels,
        List<String> conditionCodes,
        String schemaVersion,
        String engineVersion,
        OffsetDateTime computedAt,
        int samplingRate,
        int nSamples,
        String measurementStatus,
        double overallConfidence,
        int nBeats,
        Double sqiOverall,
        String rhythmRegularity,
        Double rrMeanMs,
        Double axisDegrees,
        String axisCategory,
        List<String> warnings,
        String cleanImageUrl,
        String annotatedImageUrl,
        String narrative,
        String reviewStatus,
        OffsetDateTime reviewedAt,
        Long reviewedBy,
        List<MeasurementView> measurements,
        List<StDeviationView> stDeviations,
        /*
         * The nine interpretation parameters, in one shape. This is what a
         * reviewer actually verifies: exactly the nine things a student will
         * be examined on, rather than the seven that happen to be numbers.
         */
        List<ParameterView> parameters) {

    public boolean isPending() {
        return "pending".equals(reviewStatus);
    }
}
