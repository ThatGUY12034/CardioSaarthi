package com.cardiosaarthi.review.study;

import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

/**
 * The pre-written feedback, and the rule that protects it.
 *
 * <p>Section 5.4 requires that a hint never contain the expected value, and that
 * rule is enforced here rather than trusted to whoever wrote the paragraph. The
 * library is currently the only source of feedback for a wrong answer; once a
 * model is wired in, the same check runs over its output and this becomes the
 * fallback when that check fails.
 */
@Component
public class FeedbackLibrary {

    private final JdbcClient db;

    FeedbackLibrary(JdbcClient db) {
        this.db = db;
    }

    /**
     * @param approved whether a clinician has read this wording. Seeded rows are
     *                 drafts, and the API says so rather than presenting a
     *                 developer's paragraph as faculty-approved teaching.
     */
    public record Entry(String body, boolean approved) {
    }

    public Optional<Entry> find(String errorLabel, FeedbackType type) {
        if (errorLabel == null || type == FeedbackType.CONFIRMATION) {
            return Optional.empty();
        }
        String stored = type == FeedbackType.HINT ? "HINT" : "EXPLANATION";
        return db.sql("""
                SELECT body, approved FROM feedback_templates
                WHERE error_label = :label AND feedback_type = :type
                """)
                .param("label", errorLabel)
                .param("type", stored)
                .query((rs, n) -> new Entry(rs.getString("body"), rs.getBoolean("approved")))
                .optional();
    }

    /**
     * Whether a hint gives the answer away.
     *
     * <p>Checked numerically rather than by string comparison, because "160" and
     * "160.0" are the same number and a student reads them the same way. Only
     * whole numbers close to the expected value count: rejecting a hint for
     * containing "12" when the answer is 120 would make it impossible to mention
     * lead V1 or a 12-lead ECG.
     */
    public static boolean leaksExpectedValue(String body, Object expected) {
        if (body == null || !(expected instanceof Number number)) {
            return false;
        }
        double value = number.doubleValue();
        var matcher = java.util.regex.Pattern.compile("\\d+(?:\\.\\d+)?").matcher(body);
        while (matcher.find()) {
            try {
                if (Math.abs(Double.parseDouble(matcher.group()) - value) < 0.5) {
                    return true;
                }
            } catch (NumberFormatException ignored) {
                // Not a number we need to worry about.
            }
        }
        return false;
    }
}
