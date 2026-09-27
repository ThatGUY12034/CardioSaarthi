package com.cardiosaarthi.review.review;

import java.util.Map;
import java.util.Optional;

/**
 * Bounds a corrected measurement has to fall inside.
 *
 * <p>These are deliberately far wider than the normal reference ranges. A
 * reviewer correcting a PR interval to 280 ms is recording first-degree AV block,
 * which is the entire point of the case; refusing it because it is abnormal would
 * make the tool useless. What these catch is the mistake that produces a number
 * no heart has ever had: a slipped decimal point, a value typed in seconds
 * instead of milliseconds, a stray digit.
 *
 * <p>The cost of the two errors is not symmetric. A rejected legitimate value
 * costs a reviewer one confused moment. An accepted 2400 ms QT becomes ground
 * truth, grades students wrong, and lands in the measurement-agreement table as
 * if the engine had been 2000 ms out.
 */
final class Plausibility {

    record Bounds(double low, double high, String unit) {

        boolean contains(double value) {
            return value >= low && value <= high;
        }

        String describe() {
            return "%.0f to %.0f %s".formatted(low, high, unit);
        }
    }

    private static final Map<String, Bounds> BY_MEASURE = Map.of(
            // Below 15 bpm is not a rhythm, above 300 is not mechanically possible.
            "heart_rate", new Bounds(15, 300, "bpm"),
            // Complete AV block can push PR past 400 ms; 600 allows for it.
            "pr_interval", new Bounds(50, 600, "ms"),
            "qrs_duration", new Bounds(30, 300, "ms"),
            "qt_interval", new Bounds(150, 800, "ms"),
            "qtc_bazett", new Bounds(150, 800, "ms"),
            "qtc_fridericia", new Bounds(150, 800, "ms"),
            "p_duration", new Bounds(20, 200, "ms"));

    private Plausibility() {
    }

    static Optional<Bounds> forMeasure(String name) {
        return Optional.ofNullable(BY_MEASURE.get(name));
    }
}
