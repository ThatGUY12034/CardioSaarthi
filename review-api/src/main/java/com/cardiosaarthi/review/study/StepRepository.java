package com.cardiosaarthi.review.study;

import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** The nine steps and their tolerances, read from the database. */
@Repository
public class StepRepository {

    private final JdbcClient db;

    StepRepository(JdbcClient db) {
        this.db = db;
    }

    public List<InterpretationStep> all() {
        return db.sql("""
                SELECT step, concept, label, answer_kind, measure, tolerance_abs, tolerance_pct
                FROM interpretation_steps
                ORDER BY step
                """)
                .query(StepRepository::map)
                .list();
    }

    public Optional<InterpretationStep> byStep(int step) {
        return db.sql("""
                SELECT step, concept, label, answer_kind, measure, tolerance_abs, tolerance_pct
                FROM interpretation_steps WHERE step = :step
                """)
                .param("step", step)
                .query(StepRepository::map)
                .optional();
    }

    private static InterpretationStep map(java.sql.ResultSet rs, int rowNum) throws java.sql.SQLException {
        return new InterpretationStep(
                rs.getInt("step"),
                rs.getString("concept"),
                rs.getString("label"),
                AnswerKind.valueOf(rs.getString("answer_kind")),
                rs.getString("measure"),
                nullableDouble(rs, "tolerance_abs"),
                nullableDouble(rs, "tolerance_pct"));
    }

    private static Double nullableDouble(java.sql.ResultSet rs, String column) throws java.sql.SQLException {
        double value = rs.getDouble(column);
        return rs.wasNull() ? null : value;
    }
}
