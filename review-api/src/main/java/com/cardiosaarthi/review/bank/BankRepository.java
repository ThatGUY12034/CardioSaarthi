package com.cardiosaarthi.review.bank;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.List;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class BankRepository {

    private final JdbcClient db;

    BankRepository(JdbcClient db) {
        this.db = db;
    }

    public List<ConditionBankEntry> conditions() {
        return db.sql("""
                SELECT b.code, b.label, b.group_name, b.available, b.target_cases,
                       b.candidates, b.approved, b.pending, b.rejected, b.shortfall,
                       c.scp_codes, c.note
                FROM v_condition_bank_status b
                JOIN conditions c ON c.code = b.code
                ORDER BY b.group_name, b.shortfall DESC, b.code
                """)
                .query((rs, n) -> new ConditionBankEntry(
                        rs.getString("code"),
                        rs.getString("label"),
                        rs.getString("group_name"),
                        rs.getBoolean("available"),
                        textArray(rs.getArray("scp_codes")),
                        rs.getInt("target_cases"),
                        rs.getInt("candidates"),
                        rs.getInt("approved"),
                        rs.getInt("pending"),
                        rs.getInt("rejected"),
                        rs.getInt("shortfall"),
                        rs.getString("note")))
                .list();
    }

    public Statistics statistics() {
        return new Statistics(outcomes(), agreement(), rejectionReasons());
    }

    private Statistics.Outcomes outcomes() {
        int pending = db.sql("SELECT count(*) FROM cases WHERE review_status = 'pending'")
                .query(Integer.class)
                .single();

        // v_review_outcomes is a single-row aggregate, so it always returns a row
        // -- with nulls throughout before anyone has reviewed anything.
        return db.sql("""
                SELECT n_reviews, approved, edited, rejected, approved_pct, usable_pct,
                       mean_seconds_per_case, median_seconds_per_case
                FROM v_review_outcomes
                """)
                .query((rs, n) -> new Statistics.Outcomes(
                        rs.getInt("n_reviews"),
                        rs.getInt("approved"),
                        rs.getInt("edited"),
                        rs.getInt("rejected"),
                        nullableDouble(rs, "approved_pct"),
                        nullableDouble(rs, "usable_pct"),
                        nullableDouble(rs, "mean_seconds_per_case"),
                        nullableDouble(rs, "median_seconds_per_case"),
                        pending))
                .single();
    }

    private List<Statistics.Agreement> agreement() {
        return db.sql("""
                SELECT name, unit, n_corrections, mae, median_abs_error, bias, sd, worst
                FROM v_measurement_agreement
                ORDER BY n_corrections DESC, name
                """)
                .query((rs, n) -> new Statistics.Agreement(
                        rs.getString("name"),
                        rs.getString("unit"),
                        rs.getInt("n_corrections"),
                        nullableDouble(rs, "mae"),
                        nullableDouble(rs, "median_abs_error"),
                        nullableDouble(rs, "bias"),
                        nullableDouble(rs, "sd"),
                        nullableDouble(rs, "worst")))
                .list();
    }

    private List<Statistics.RejectionCount> rejectionReasons() {
        return db.sql("SELECT reason, n, pct FROM v_rejection_reasons ORDER BY n DESC, reason")
                .query((rs, n) -> new Statistics.RejectionCount(
                        rs.getString("reason"),
                        rs.getInt("n"),
                        nullableDouble(rs, "pct")))
                .list();
    }

    private static Double nullableDouble(ResultSet rs, String column) throws SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }

    private static List<String> textArray(Array array) throws SQLException {
        if (array == null) {
            return List.of();
        }
        return array.getArray() instanceof String[] values ? Arrays.asList(values) : List.of();
    }
}
