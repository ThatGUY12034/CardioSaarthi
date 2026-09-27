package com.cardiosaarthi.review.cases;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class CaseRepository {

    /**
     * Presentation order for the measurement list: rate, then rhythm intervals,
     * then the corrected QT values, then P duration. This is the order the
     * nine-step interpretation sequence reads them in, so the console does not
     * have to know it.
     */
    private static final String MEASURE_ORDER =
            "ARRAY['heart_rate','pr_interval','qrs_duration','qt_interval',"
                    + "'qtc_bazett','qtc_fridericia','p_duration']";

    private final JdbcClient db;

    CaseRepository(JdbcClient db) {
        this.db = db;
    }

    public Optional<CaseDetail> findDetail(long caseId) {
        Optional<CaseDetail> shell = db.sql("""
                SELECT c.id, c.source, c.source_ecg_id, c.age, c.age_censored, c.sex,
                       c.diagnostic_labels, c.schema_version, c.engine_version, c.computed_at,
                       c.sampling_rate, c.n_samples, c.measurement_status, c.overall_confidence,
                       c.n_beats, c.sqi_overall, c.rhythm_regularity, c.rr_mean_ms,
                       c.axis_degrees, c.axis_category, c.warnings,
                       c.image_clean_path, c.image_annotated_path, c.narrative::text AS narrative,
                       c.review_status, c.reviewed_at, c.reviewed_by,
                       (SELECT array_remove(array_agg(cc.condition_code ORDER BY cc.condition_code), NULL)
                          FROM case_conditions cc WHERE cc.case_id = c.id) AS condition_codes
                FROM cases c
                WHERE c.id = :caseId
                """)
                .param("caseId", caseId)
                .query(detailMapper())
                .optional();

        return shell.map(detail -> withChildren(detail, caseId));
    }

    private CaseDetail withChildren(CaseDetail detail, long caseId) {
        return new CaseDetail(
                detail.id(), detail.source(), detail.sourceEcgId(), detail.age(), detail.ageCensored(),
                detail.sex(), detail.diagnosticLabels(), detail.conditionCodes(), detail.schemaVersion(),
                detail.engineVersion(), detail.computedAt(), detail.samplingRate(), detail.nSamples(),
                detail.measurementStatus(), detail.overallConfidence(), detail.nBeats(), detail.sqiOverall(),
                detail.rhythmRegularity(), detail.rrMeanMs(), detail.axisDegrees(), detail.axisCategory(),
                detail.warnings(), detail.cleanImageUrl(), detail.annotatedImageUrl(), detail.narrative(),
                detail.reviewStatus(), detail.reviewedAt(), detail.reviewedBy(),
                measurements(caseId), stDeviations(caseId), parameters(caseId));
    }

    public List<MeasurementView> measurements(long caseId) {
        return db.sql("""
                SELECT m.name, m.value, m.mad, m.unit, m.n_beats, m.confidence, m.status, m.flag,
                       m.ref_low, m.ref_high,
                       corr.corrected_value, corr.reviewer_id AS corrected_by, corr.created_at AS corrected_at
                FROM case_measurements m
                LEFT JOIN LATERAL (
                    SELECT mc.corrected_value, mc.reviewer_id, mc.created_at
                    FROM measurement_corrections mc
                    WHERE mc.case_id = m.case_id AND mc.name = m.name
                    ORDER BY mc.created_at DESC, mc.id DESC
                    LIMIT 1
                ) corr ON true
                WHERE m.case_id = :caseId
                ORDER BY coalesce(array_position(%s, m.name), 99), m.name
                """.formatted(MEASURE_ORDER))
                .param("caseId", caseId)
                .query((rs, n) -> new MeasurementView(
                        rs.getString("name"),
                        nullableDouble(rs, "value"),
                        nullableDouble(rs, "mad"),
                        rs.getString("unit"),
                        rs.getInt("n_beats"),
                        nullableDouble(rs, "confidence"),
                        rs.getString("status"),
                        rs.getString("flag"),
                        nullableDouble(rs, "ref_low"),
                        nullableDouble(rs, "ref_high"),
                        nullableDouble(rs, "corrected_value"),
                        nullableLong(rs, "corrected_by"),
                        rs.getObject("corrected_at", OffsetDateTime.class)))
                .list();
    }

    /**
     * All nine interpretation parameters for a case, whether or not it is
     * approved.
     *
     * <p>v_served_parameters covers approved cases only, because that view exists
     * to decide what a student may be graded against. A reviewer needs to see the
     * parameters of a case that is still pending -- that is the whole job -- so
     * this reads the underlying values and applies any correction itself.
     */
    public List<ParameterView> parameters(long caseId) {
        return db.sql("""
                WITH latest AS (
                    SELECT DISTINCT ON (name) name, corrected_value, corrected_text
                    FROM measurement_corrections
                    WHERE case_id = :caseId
                    ORDER BY name, created_at DESC, id DESC
                )
                SELECT s.step, s.concept AS name, s.label, s.answer_kind AS kind,
                       CASE WHEN s.answer_kind = 'NUMERIC'
                            THEN coalesce(l.corrected_value, m.value) END AS value,
                       CASE WHEN s.answer_kind = 'NUMERIC' THEN l.corrected_text
                            WHEN s.concept = 'rhythm'     THEN coalesce(l.corrected_text, c.rhythm_regularity)
                            WHEN s.concept = 'axis'       THEN coalesce(l.corrected_text, c.axis_category)
                            WHEN s.concept = 'p_waves'    THEN coalesce(l.corrected_text,
                                 CASE WHEN pm.status = 'NOT_MEASURABLE' THEN 'ABSENT'
                                      WHEN pm.status IS NULL THEN NULL ELSE 'PRESENT' END)
                            WHEN s.concept = 'st_segment' THEN coalesce(l.corrected_text, st.leads, '')
                       END AS text_value,
                       m.unit, m.mad, m.confidence,
                       coalesce(m.status, 'OK') AS status,
                       m.value AS computed_value,
                       CASE WHEN s.concept = 'rhythm'     THEN c.rhythm_regularity
                            WHEN s.concept = 'axis'       THEN c.axis_category
                            WHEN s.concept = 'p_waves'    THEN
                                 CASE WHEN pm.status = 'NOT_MEASURABLE' THEN 'ABSENT'
                                      WHEN pm.status IS NULL THEN NULL ELSE 'PRESENT' END
                            WHEN s.concept = 'st_segment' THEN coalesce(st.leads, '')
                       END AS computed_text,
                       l.name IS NOT NULL AS corrected
                FROM interpretation_steps s
                CROSS JOIN cases c
                LEFT JOIN case_measurements m ON m.case_id = c.id AND m.name = s.measure
                LEFT JOIN case_measurements pm ON pm.case_id = c.id AND pm.name = 'p_duration'
                LEFT JOIN latest l ON l.name = s.concept OR l.name = s.measure
                LEFT JOIN LATERAL (
                    SELECT string_agg(d.lead, ',' ORDER BY d.lead) AS leads
                    FROM case_st_deviations d WHERE d.case_id = c.id AND d.finding <> 'NORMAL'
                ) st ON true
                WHERE c.id = :caseId
                ORDER BY s.step
                """)
                .param("caseId", caseId)
                .query((rs, n) -> new ParameterView(
                        rs.getInt("step"),
                        rs.getString("name"),
                        rs.getString("label"),
                        rs.getString("kind"),
                        nullableDouble(rs, "value"),
                        rs.getString("text_value"),
                        rs.getString("unit"),
                        nullableDouble(rs, "mad"),
                        nullableDouble(rs, "confidence"),
                        rs.getString("status"),
                        nullableDouble(rs, "computed_value"),
                        rs.getString("computed_text"),
                        rs.getBoolean("corrected")))
                .list();
    }

    public List<StDeviationView> stDeviations(long caseId) {
        return db.sql("""
                SELECT lead, deviation_mm, threshold_mm, finding, mad_mm, n_beats, confidence
                FROM case_st_deviations
                WHERE case_id = :caseId
                ORDER BY array_position(
                    ARRAY['I','II','III','aVR','aVL','aVF','V1','V2','V3','V4','V5','V6'], lead)
                """)
                .param("caseId", caseId)
                .query((rs, n) -> new StDeviationView(
                        rs.getString("lead"),
                        nullableDouble(rs, "deviation_mm"),
                        nullableDouble(rs, "threshold_mm"),
                        rs.getString("finding"),
                        nullableDouble(rs, "mad_mm"),
                        rs.getInt("n_beats"),
                        nullableDouble(rs, "confidence")))
                .list();
    }

    /** Stored path for a rendered image, exactly as the ingest recorded it. */
    public Optional<String> findImagePath(long caseId, String kind) {
        String column = switch (kind) {
            case "clean" -> "image_clean_path";
            case "annotated" -> "image_annotated_path";
            // Never interpolate the caller's string into SQL. An unknown kind is
            // an absent image, which the controller turns into a 404.
            default -> null;
        };
        if (column == null) {
            return Optional.empty();
        }
        return db.sql("SELECT " + column + " FROM cases WHERE id = :caseId")
                .param("caseId", caseId)
                .query(String.class)
                .optional();
    }

    private RowMapper<CaseDetail> detailMapper() {
        return (rs, rowNum) -> new CaseDetail(
                rs.getLong("id"),
                rs.getString("source"),
                rs.getInt("source_ecg_id"),
                nullableDouble(rs, "age"),
                rs.getBoolean("age_censored"),
                rs.getString("sex"),
                textArray(rs.getArray("diagnostic_labels")),
                textArray(rs.getArray("condition_codes")),
                rs.getString("schema_version"),
                rs.getString("engine_version"),
                rs.getObject("computed_at", OffsetDateTime.class),
                rs.getInt("sampling_rate"),
                rs.getInt("n_samples"),
                rs.getString("measurement_status"),
                rs.getDouble("overall_confidence"),
                rs.getInt("n_beats"),
                nullableDouble(rs, "sqi_overall"),
                rs.getString("rhythm_regularity"),
                nullableDouble(rs, "rr_mean_ms"),
                nullableDouble(rs, "axis_degrees"),
                rs.getString("axis_category"),
                textArray(rs.getArray("warnings")),
                imageUrl(rs.getLong("id"), rs.getString("image_clean_path"), "clean"),
                imageUrl(rs.getLong("id"), rs.getString("image_annotated_path"), "annotated"),
                // Raw JSON text. Null until the scenario generator exists; it is
                // authored once, offline, and never reaches a student unreviewed.
                rs.getString("narrative"),
                rs.getString("review_status"),
                rs.getObject("reviewed_at", OffsetDateTime.class),
                nullableLong(rs, "reviewed_by"),
                List.of(),
                List.of(),
                List.of());
    }

    static Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    static Long nullableLong(ResultSet rs, String column) throws SQLException {
        long value = rs.getLong(column);
        return rs.wasNull() ? null : value;
    }

    static List<String> textArray(Array array) throws SQLException {
        if (array == null) {
            return List.of();
        }
        return array.getArray() instanceof String[] values ? Arrays.asList(values) : List.of();
    }

    private static String imageUrl(long caseId, String storedPath, String kind) {
        return storedPath == null ? null : "/api/cases/" + caseId + "/image/" + kind;
    }
}
