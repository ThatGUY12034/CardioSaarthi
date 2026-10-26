package com.cardiosaarthi.review.study;

import com.cardiosaarthi.review.study.MasteryService.ConceptOutcome;
import com.cardiosaarthi.review.study.MasteryService.Schedule;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The scheduler's arithmetic.
 *
 * <p>No database: SM-2 is a pure function of the previous schedule and one
 * quality score, and the value of keeping it that way is exactly that it can be
 * checked like this. The parts that touch the database are covered by the
 * session tests, which finish a case and then look at what was written.
 */
class MasteryTests {

    private static final Schedule FRESH = new Schedule(2.50, 0, 0);

    @Nested
    @DisplayName("the interval")
    class Intervals {

        @Test
        @DisplayName("a first success comes back tomorrow")
        void firstSuccess() {
            Schedule next = MasteryService.schedule(FRESH, 5);
            assertThat(next.repetitions()).isEqualTo(1);
            assertThat(next.intervalDays()).isEqualTo(1);
        }

        @Test
        @DisplayName("a second success comes back in six days")
        void secondSuccess() {
            Schedule next = MasteryService.schedule(new Schedule(2.50, 1, 1), 5);
            assertThat(next.repetitions()).isEqualTo(2);
            assertThat(next.intervalDays()).isEqualTo(6);
        }

        @Test
        @DisplayName("later successes multiply the interval by the ease")
        void laterSuccesses() {
            // Six days at an ease of 2.6 is a little over a fortnight.
            Schedule next = MasteryService.schedule(new Schedule(2.60, 6, 2), 5);
            assertThat(next.repetitions()).isEqualTo(3);
            assertThat(next.intervalDays()).isEqualTo(16);
        }

        @Test
        @DisplayName("a failure brings the concept back tomorrow and restarts the count")
        void failureResets() {
            Schedule next = MasteryService.schedule(new Schedule(2.50, 30, 5), 1);
            assertThat(next.intervalDays()).isEqualTo(1);
            assertThat(next.repetitions()).isZero();
        }
    }

    @Nested
    @DisplayName("the ease")
    class Ease {

        @Test
        @DisplayName("answering well raises it")
        void goodAnswersRaiseEase() {
            assertThat(MasteryService.schedule(FRESH, 5).ease()).isGreaterThan(FRESH.ease());
        }

        @Test
        @DisplayName("answering badly lowers it")
        void badAnswersLowerEase() {
            assertThat(MasteryService.schedule(FRESH, 1).ease()).isLessThan(FRESH.ease());
        }

        @Test
        @DisplayName("a lapse lowers the ease but does not reset it")
        void lapseKeepsEaseMemory() {
            // The ease is the algorithm's memory of how hard this item has been
            // for this person, and that is the part worth keeping across a
            // lapse. Only the interval restarts.
            Schedule practised = new Schedule(1.90, 30, 5);
            Schedule afterLapse = MasteryService.schedule(practised, 1);
            assertThat(afterLapse.ease()).isLessThan(practised.ease());
            assertThat(afterLapse.ease()).isGreaterThan(1.30);
        }

        @Test
        @DisplayName("it never falls below 1.3")
        void easeHasAFloor() {
            Schedule schedule = FRESH;
            for (int i = 0; i < 20; i++) {
                schedule = MasteryService.schedule(schedule, 0);
            }
            // Below this floor an item would be scheduled so often it crowds
            // every other concept out of the queue.
            assertThat(schedule.ease()).isGreaterThanOrEqualTo(1.30);
        }
    }

    @Nested
    @DisplayName("turning a session into a quality score")
    class Quality {

        @Test
        @DisplayName("right first time is full marks")
        void firstTime() {
            assertThat(MasteryService.qualityOf(new ConceptOutcome("rate", true, true, 1)))
                    .isEqualTo(5);
        }

        @Test
        @DisplayName("right on the second attempt scores below a clean answer")
        void secondAttempt() {
            int quality = MasteryService.qualityOf(new ConceptOutcome("rate", true, false, 2));
            assertThat(quality).isEqualTo(4);
            assertThat(quality).isLessThan(5);
        }

        @Test
        @DisplayName("right only after several attempts still passes, barely")
        void lateButCorrect() {
            assertThat(MasteryService.qualityOf(new ConceptOutcome("rate", true, false, 3)))
                    .isEqualTo(3);
        }

        @Test
        @DisplayName("never correct is a failure and restarts the interval")
        void neverCorrect() {
            int quality = MasteryService.qualityOf(new ConceptOutcome("rate", false, false, 3));
            assertThat(quality).isLessThan(3);
            assertThat(MasteryService.schedule(new Schedule(2.50, 30, 5), quality).intervalDays())
                    .isEqualTo(1);
        }

        @Test
        @DisplayName("a strong concept is scheduled further out than a weak one")
        void strongerConceptsRecurLessOften() {
            // The property the whole feature exists for: getting something right
            // should push it away, getting it wrong should pull it closer.
            Schedule practised = new Schedule(2.50, 6, 2);
            Schedule strong = MasteryService.schedule(practised,
                    MasteryService.qualityOf(new ConceptOutcome("axis", true, true, 1)));
            Schedule weak = MasteryService.schedule(practised,
                    MasteryService.qualityOf(new ConceptOutcome("axis", false, false, 2)));
            assertThat(strong.intervalDays()).isGreaterThan(weak.intervalDays());
        }
    }
}
