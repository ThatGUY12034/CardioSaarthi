package com.cardiosaarthi.review.review;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The nine parameters a reviewer may correct, and what a valid value looks like.
 *
 * <p>Five are numbers with a plausibility range; four are one of a fixed set, or
 * a list of leads. Checked here rather than trusted to the console, because the
 * console can be wrong and a corrected value becomes the answer a student is
 * marked against.
 */
public final class Parameters {

    /** The twelve leads, in the order they appear on a standard recording. */
    public static final List<String> LEADS =
            List.of("I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6");

    /**
     * Values a categorical parameter may take.
     *
     * <p>INDETERMINATE is accepted for the rhythm and the axis because a reviewer
     * may genuinely conclude that a recording does not support a confident call,
     * and saying so is better than picking one. The grader already declines to
     * mark a step whose answer is indeterminate.
     */
    private static final Map<String, Set<String>> CATEGORIES = Map.of(
            "rhythm", Set.of("REGULAR", "REGULARLY_IRREGULAR", "IRREGULARLY_IRREGULAR", "INDETERMINATE"),
            "axis", Set.of("NORMAL", "LEFT", "RIGHT", "EXTREME", "INDETERMINATE"),
            "p_waves", Set.of("PRESENT", "ABSENT"));

    private static final String ST = "st_segment";

    /** A numeric measure may also be corrected to "there is nothing to measure". */
    public static final String NOT_MEASURABLE = "NOT_MEASURABLE";

    private Parameters() {
    }

    public static boolean isCategorical(String name) {
        return CATEGORIES.containsKey(name) || ST.equals(name);
    }

    public static boolean isNumeric(String name) {
        return Plausibility.forMeasure(name).isPresent();
    }

    public static boolean isKnown(String name) {
        return isCategorical(name) || isNumeric(name);
    }

    /**
     * Normalises and checks a categorical correction.
     *
     * @return the stored form
     * @throws IllegalArgumentException with a message naming what would be accepted
     */
    public static String normalise(String name, String raw) {
        String value = raw == null ? "" : raw.trim();

        if (ST.equals(name)) {
            return normaliseLeads(value);
        }

        Set<String> allowed = CATEGORIES.get(name);
        if (allowed == null) {
            // A numeric measure being marked unmeasurable, e.g. a PR interval on
            // a rhythm with no P waves.
            if (NOT_MEASURABLE.equalsIgnoreCase(value) && isNumeric(name)) {
                return NOT_MEASURABLE;
            }
            throw new IllegalArgumentException("'" + name + "' does not take a text value");
        }

        String upper = value.toUpperCase().replace(' ', '_');
        if (!allowed.contains(upper)) {
            throw new IllegalArgumentException(
                    "'%s' is not a %s. Accepted: %s".formatted(value, name, String.join(", ", sorted(allowed))));
        }
        return upper;
    }

    /**
     * A comma-separated lead list, deduplicated and put in recording order.
     *
     * <p>Order is imposed rather than preserved so that two reviewers naming the
     * same leads in a different order produce the same stored value, and so that
     * comparing a student's answer to it is a set comparison either way.
     */
    private static String normaliseLeads(String raw) {
        if (raw.isBlank()) {
            // A legitimate answer: no lead deviates.
            return "";
        }
        List<String> named = java.util.Arrays.stream(raw.split("[,;\\s]+"))
                .map(String::trim)
                .filter(part -> !part.isEmpty())
                .map(Parameters::canonicalLead)
                .distinct()
                .toList();

        List<String> unknown = named.stream().filter(lead -> !LEADS.contains(lead)).toList();
        if (!unknown.isEmpty()) {
            throw new IllegalArgumentException(
                    "not lead names: %s. The twelve leads are %s"
                            .formatted(String.join(", ", unknown), String.join(", ", LEADS)));
        }
        return LEADS.stream().filter(named::contains).collect(java.util.stream.Collectors.joining(","));
    }

    /** aVR, avr and AVR are the same lead, and a reviewer may type any of them. */
    private static String canonicalLead(String raw) {
        String upper = raw.toUpperCase();
        return switch (upper) {
            case "AVR" -> "aVR";
            case "AVL" -> "aVL";
            case "AVF" -> "aVF";
            default -> upper;
        };
    }

    private static List<String> sorted(Set<String> values) {
        return values.stream().sorted().toList();
    }
}
