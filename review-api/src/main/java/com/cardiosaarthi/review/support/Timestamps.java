package com.cardiosaarthi.review.support;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;

/**
 * Reading a {@code timestamptz} as an {@link Instant}.
 *
 * <p>The obvious spelling, {@code rs.getObject(column, Instant.class)},
 * compiles and then throws at run time: the PostgreSQL driver refuses that
 * conversion with "conversion to class java.time.Instant from timestamptz not
 * supported". It fails only when a row is actually mapped, so a query with no
 * rows passes its test and the same code 500s the moment somebody has data.
 *
 * <p>This is the second conversion in this codebase the driver would not do --
 * {@code getObject(column, Double.class)} on a numeric was the first -- so it
 * is worth having one place that gets it right.
 */
public final class Timestamps {

    private Timestamps() {
    }

    /** Null-safe: a null column is a null Instant, not an exception. */
    public static Instant instant(ResultSet rs, String column) throws SQLException {
        Timestamp timestamp = rs.getTimestamp(column);
        return timestamp == null ? null : timestamp.toInstant();
    }

    /**
     * A nullable whole number out of a numeric column.
     *
     * <p>{@code (Integer) rs.getObject(column)} compiles and throws: a
     * PostgreSQL {@code numeric} arrives as a BigDecimal, and the cast fails on
     * the first row that has one. Rounded rather than truncated, because these
     * are percentages that have already been rounded in SQL and the conversion
     * should not quietly shave one off.
     */
    public static Integer integer(ResultSet rs, String column) throws SQLException {
        int value = rs.getInt(column);
        return rs.wasNull() ? null : value;
    }
}
