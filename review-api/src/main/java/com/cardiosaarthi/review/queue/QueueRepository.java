package com.cardiosaarthi.review.queue;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.List;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class QueueRepository {

    private final JdbcClient db;

    QueueRepository(JdbcClient db) {
        this.db = db;
    }

    /**
     * A page of the review queue.
     *
     * <p>{@code conditionCode} and {@code measurementStatus} are optional filters;
     * both are bound as parameters. The only part of the query that varies
     * structurally is the ORDER BY, and that comes from a fixed constant on
     * {@link QueueOrder}, never from the request.
     *
     * <p>The CAST around each filter is required, not decoration: PostgreSQL
     * cannot infer the type of a parameter that appears only as {@code ? IS NULL}
     * and rejects the statement outright.
     */
    public List<QueueEntry> page(QueueOrder order, String conditionCode, String measurementStatus,
                                 int limit, int offset) {
        String sql = """
                SELECT case_id, source, source_ecg_id, age, sex, diagnostic_labels, condition_codes,
                       measurement_status, overall_confidence, n_beats, warnings, has_narrative,
                       image_clean_path, image_annotated_path, max_condition_shortfall, created_at
                FROM v_review_queue
                WHERE (CAST(:conditionCode AS text) IS NULL
                       OR CAST(:conditionCode AS text) = ANY (condition_codes))
                  AND (CAST(:measurementStatus AS text) IS NULL
                       OR measurement_status = CAST(:measurementStatus AS text))
                ORDER BY %s
                LIMIT :limit OFFSET :offset
                """.formatted(order.orderBy());

        return db.sql(sql)
                .param("conditionCode", conditionCode)
                .param("measurementStatus", measurementStatus)
                .param("limit", limit)
                .param("offset", offset)
                .query(MAPPER)
                .list();
    }

    public int count(String conditionCode, String measurementStatus) {
        return db.sql("""
                SELECT count(*) FROM v_review_queue
                WHERE (CAST(:conditionCode AS text) IS NULL
                       OR CAST(:conditionCode AS text) = ANY (condition_codes))
                  AND (CAST(:measurementStatus AS text) IS NULL
                       OR measurement_status = CAST(:measurementStatus AS text))
                """)
                .param("conditionCode", conditionCode)
                .param("measurementStatus", measurementStatus)
                .query(Integer.class)
                .single();
    }

    static final RowMapper<QueueEntry> MAPPER = (rs, rowNum) -> new QueueEntry(
            rs.getLong("case_id"),
            rs.getString("source"),
            rs.getInt("source_ecg_id"),
            nullableDouble(rs, "age"),
            rs.getString("sex"),
            textArray(rs.getArray("diagnostic_labels")),
            textArray(rs.getArray("condition_codes")),
            rs.getString("measurement_status"),
            rs.getDouble("overall_confidence"),
            rs.getInt("n_beats"),
            textArray(rs.getArray("warnings")),
            rs.getBoolean("has_narrative"),
            imageUrl(rs.getLong("case_id"), rs.getString("image_clean_path"), "clean"),
            imageUrl(rs.getLong("case_id"), rs.getString("image_annotated_path"), "annotated"),
            rs.getInt("max_condition_shortfall"),
            rs.getObject("created_at", java.time.OffsetDateTime.class));

    private static Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private static List<String> textArray(Array array) throws SQLException {
        if (array == null) {
            return List.of();
        }
        Object raw = array.getArray();
        if (raw instanceof String[] values) {
            return Arrays.asList(values);
        }
        return List.of();
    }

    /** Null when no image was rendered, so the console can show that honestly. */
    private static String imageUrl(long caseId, String storedPath, String kind) {
        return storedPath == null ? null : "/api/cases/" + caseId + "/image/" + kind;
    }
}
