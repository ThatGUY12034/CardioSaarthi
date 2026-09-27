package com.cardiosaarthi.review.study;

import java.util.List;
import java.util.Set;

/**
 * What a student submitted for one step.
 *
 * <p>One record covering all three answer shapes rather than a sealed hierarchy:
 * the console posts JSON, only one field is meaningful per step, and the step
 * definition already says which. A polymorphic body would make the client
 * responsible for knowing the shape, and the server checks it anyway.
 *
 * @param value      a measurement, for NUMERIC steps
 * @param notPresent the student's assertion that the thing cannot be measured --
 *                   no P wave, so no PR interval. This is a real answer and
 *                   often the correct one, so it is a field rather than an
 *                   absence of one.
 * @param category   one of a fixed set, for CATEGORICAL steps
 * @param leads      which leads are involved, for MULTI_CATEGORICAL steps
 */
public record StudentAnswer(
        Double value,
        Boolean notPresent,
        String category,
        List<String> leads) {

    public boolean claimsNotPresent() {
        return Boolean.TRUE.equals(notPresent);
    }

    public Set<String> leadSet() {
        return leads == null ? Set.of() : Set.copyOf(leads);
    }

    public boolean isEmpty() {
        return value == null
                && !claimsNotPresent()
                && (category == null || category.isBlank())
                && (leads == null || leads.isEmpty());
    }
}
