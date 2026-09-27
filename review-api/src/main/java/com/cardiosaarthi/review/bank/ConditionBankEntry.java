package com.cardiosaarthi.review.bank;

import java.util.List;

/**
 * How full the case bank is for one syllabus condition.
 *
 * <p>{@code available == false} with {@code candidates == 0} is not a pipeline
 * failure. Ventricular tachycardia and both electrolyte disturbances are on the
 * syllabus and simply do not exist in PTB-XL, and this row is how that gap stays
 * visible instead of the condition quietly disappearing from the list.
 *
 * @param shortfall approved cases still needed to reach the target
 */
public record ConditionBankEntry(
        String code,
        String label,
        String groupName,
        boolean available,
        List<String> scpCodes,
        int targetCases,
        int candidates,
        int approved,
        int pending,
        int rejected,
        int shortfall,
        String note) {
}
