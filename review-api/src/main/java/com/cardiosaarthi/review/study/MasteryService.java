package com.cardiosaarthi.review.study;

import java.time.LocalDate;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Which concept a student should meet next, and when.
 *
 * <p>Section 5.5 of the brief: scheduling is deterministic, weak concepts
 * first, SM-2 style spaced repetition ordered by the syllabus. It is code and a
 * table, not an agent. The table has existed since V4 and nothing wrote to it
 * until now, so practice was a flat list: a student who could not read an axis
 * met axis questions exactly as often as one who never got them wrong.
 *
 * <p>SM-2 is used unmodified, because a published algorithm whose behaviour can
 * be described to a student is worth more here than a tuned one that cannot.
 * The one judgement this class adds is how a session becomes a quality score,
 * and that is set out in {@link #qualityOf}.
 */
@Service
public class MasteryService {

    private static final Logger log = LoggerFactory.getLogger(MasteryService.class);

    /** SM-2's floor. Below this an item would be scheduled so often it crowds everything else out. */
    private static final double MINIMUM_EASE = 1.30;

    /** The quality at which SM-2 treats an answer as a failure and restarts the interval. */
    private static final int PASSING_QUALITY = 3;

    private final JdbcClient db;

    MasteryService(JdbcClient db) {
        this.db = db;
    }

    // -----------------------------------------------------------------------
    // recording
    // -----------------------------------------------------------------------
    /**
     * Folds one finished session into the student's mastery record.
     *
     * <p>Called when a session completes rather than after each step, because
     * SM-2 schedules a review of an item, and the item here is the concept as
     * met in one case. A student who answers the rate step twice in one session
     * has had one encounter with rate, not two.
     *
     * <p>Steps the platform declined to mark never reach this: they are not
     * written to session_steps at all, so a concept that could not be graded on
     * this recording neither helps nor harms the student's record of it.
     */
    @Transactional
    public void recordSession(long sessionId, long studentId) {
        List<ConceptOutcome> outcomes = db.sql("""
                SELECT s.concept,
                       bool_or(ss.correct)                                  AS ever_correct,
                       bool_or(ss.correct AND ss.attempt = 1)               AS correct_first_time,
                       max(ss.attempt)                                      AS attempts_taken
                FROM session_steps ss
                JOIN interpretation_steps s ON s.step = ss.step
                WHERE ss.session_id = :sessionId
                GROUP BY s.concept
                """)
                .param("sessionId", sessionId)
                .query((rs, n) -> new ConceptOutcome(
                        rs.getString("concept"),
                        rs.getBoolean("ever_correct"),
                        rs.getBoolean("correct_first_time"),
                        rs.getInt("attempts_taken")))
                .list();

        for (ConceptOutcome outcome : outcomes) {
            apply(studentId, outcome);
        }
        log.info("mastery updated for student {} across {} concepts from session {}",
                studentId, outcomes.size(), sessionId);
    }

    /**
     * How well the student knew this concept, on SM-2's nought-to-five scale.
     *
     * <p>Only the top of the scale is used, and deliberately. SM-2's lower
     * grades distinguish degrees of forgetting that a nine-step reading cannot
     * observe: the platform knows whether an answer was right and how many
     * attempts it took, and inventing a finer distinction than that would be
     * inventing data.
     */
    static int qualityOf(ConceptOutcome outcome) {
        if (!outcome.everCorrect()) {
            return 1;                      // wrong throughout: SM-2 restarts the interval
        }
        if (outcome.correctFirstTime()) {
            return 5;                      // knew it
        }
        return outcome.attemptsTaken() <= 2 ? 4 : 3;   // got there, with help
    }

    private void apply(long studentId, ConceptOutcome outcome) {
        Schedule current = db.sql("""
                SELECT ease, interval_days, repetitions
                FROM student_mastery
                WHERE student_id = :studentId AND concept = :concept
                """)
                .param("studentId", studentId)
                .param("concept", outcome.concept())
                .query((rs, n) -> new Schedule(
                        rs.getDouble("ease"), rs.getInt("interval_days"), rs.getInt("repetitions")))
                .optional()
                .orElse(new Schedule(2.50, 0, 0));

        Schedule next = schedule(current, qualityOf(outcome));

        db.sql("""
                INSERT INTO student_mastery
                    (student_id, concept, attempts, correct, first_attempt_correct,
                     ease, interval_days, repetitions, due_on, updated_at)
                VALUES
                    (:studentId, :concept, 1, :correct, :firstTime,
                     :ease, :interval, :repetitions, :dueOn, now())
                ON CONFLICT (student_id, concept) DO UPDATE SET
                    attempts              = student_mastery.attempts + 1,
                    correct               = student_mastery.correct + excluded.correct,
                    first_attempt_correct = student_mastery.first_attempt_correct
                                            + excluded.first_attempt_correct,
                    ease                  = excluded.ease,
                    interval_days         = excluded.interval_days,
                    repetitions           = excluded.repetitions,
                    due_on                = excluded.due_on,
                    updated_at            = now()
                """)
                .param("studentId", studentId)
                .param("concept", outcome.concept())
                .param("correct", outcome.everCorrect() ? 1 : 0)
                .param("firstTime", outcome.correctFirstTime() ? 1 : 0)
                .param("ease", next.ease())
                .param("interval", next.intervalDays())
                .param("repetitions", next.repetitions())
                .param("dueOn", LocalDate.now().plusDays(next.intervalDays()))
                .update();
    }

    /**
     * SM-2, as published.
     *
     * <p>A failing quality resets the repetition count and brings the concept
     * back tomorrow; it does not reset the ease, which is the algorithm's memory
     * of how hard this item has been for this person and is the part worth
     * keeping across a lapse.
     */
    static Schedule schedule(Schedule current, int quality) {
        double ease = current.ease()
                + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
        ease = Math.max(MINIMUM_EASE, ease);
        ease = Math.round(ease * 100.0) / 100.0;   // the column holds two decimals

        if (quality < PASSING_QUALITY) {
            return new Schedule(ease, 1, 0);
        }

        int repetitions = current.repetitions() + 1;
        int interval = switch (repetitions) {
            case 1 -> 1;
            case 2 -> 6;
            default -> (int) Math.max(1, Math.round(current.intervalDays() * ease));
        };
        return new Schedule(ease, interval, repetitions);
    }

    // -----------------------------------------------------------------------
    // reading
    // -----------------------------------------------------------------------
    /**
     * The concepts this student should practise, weakest first.
     *
     * <p>The ordering is the view's: known weakness, then what has come due,
     * then what has never been seen, then the rest in syllabus order. A concept
     * never practised outranks a strong one but not a weak one, because no
     * evidence is worse than good evidence and better than bad.
     */
    public List<ConceptPriority> nextConcepts(long studentId, int limit) {
        return db.sql("""
                SELECT step, concept, label, due_on, interval_days, repetitions, ease,
                       first_attempt_accuracy_pct, attempts, never_practised, due, priority
                FROM v_student_next_concepts
                WHERE student_id = :studentId
                ORDER BY priority, first_attempt_accuracy_pct NULLS LAST, step
                LIMIT :limit
                """)
                .param("studentId", studentId)
                .param("limit", Math.clamp(limit, 1, 9))
                .query((rs, n) -> new ConceptPriority(
                        rs.getInt("step"),
                        rs.getString("concept"),
                        rs.getString("label"),
                        rs.getObject("due_on", LocalDate.class),
                        rs.getObject("first_attempt_accuracy_pct") == null
                                ? null : rs.getDouble("first_attempt_accuracy_pct"),
                        rs.getInt("attempts"),
                        rs.getBoolean("never_practised"),
                        rs.getBoolean("due"),
                        rs.getInt("priority")))
                .list();
    }

    // -----------------------------------------------------------------------
    // shapes
    // -----------------------------------------------------------------------
    record ConceptOutcome(String concept, boolean everCorrect, boolean correctFirstTime,
                          int attemptsTaken) {
    }

    record Schedule(double ease, int intervalDays, int repetitions) {
    }

    /** One concept in the practice queue, with the reason it is where it is. */
    public record ConceptPriority(int step, String concept, String label, LocalDate dueOn,
                                  Double firstAttemptAccuracyPct, int attempts,
                                  boolean neverPractised, boolean due, int priority) {

        /** Said in words, because a student is owed a reason for what they are given. */
        public String reason() {
            if (priority == 0) {
                return "Weakest concept: %.0f%% correct first time".formatted(firstAttemptAccuracyPct);
            }
            if (priority == 1) {
                return "Due for review";
            }
            if (neverPractised) {
                return "Not practised yet";
            }
            return "Known, not due yet";
        }
    }
}
