package com.cardiosaarthi.review.cases;

/**
 * One of the nine interpretation parameters, as a reviewer needs to see it.
 *
 * <p>All nine in one shape, so the console renders one list rather than a table
 * of numbers plus three special cases. A reviewer verifying a case is checking
 * exactly the nine things a student will be examined on, and they should be able
 * to see them together.
 *
 * @param kind      NUMERIC, CATEGORICAL or MULTI_CATEGORICAL, which decides the
 *                  input the console offers
 * @param value     the number, for a numeric parameter
 * @param textValue the answer, for the four that are not numbers
 * @param corrected whether the value shown came from a reviewer rather than the
 *                  engine
 */
public record ParameterView(
        int step,
        String name,
        String label,
        String kind,
        Double value,
        String textValue,
        String unit,
        Double mad,
        Double confidence,
        String status,
        Double computedValue,
        String computedText,
        boolean corrected) {
}
