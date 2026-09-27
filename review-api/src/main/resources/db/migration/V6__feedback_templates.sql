-- Pre-written feedback, one paragraph per error and feedback type.
--
-- Section 6 of the brief calls this the fallback library and says to write it
-- before writing prompts. Two reasons it comes first: it is what the platform
-- says when a model call times out or its output is rejected, and writing the
-- teaching text by hand forces the question of what each error actually needs
-- said about it, which a prompt lets you avoid answering.
--
-- Held in the database rather than in code so that faculty can correct the
-- wording without a deploy, and so that `approved` can mean something. Every row
-- seeded here is a DRAFT: approved = false, written by a developer, not a
-- clinician. The orchestrator serves drafts and marks them as such rather than
-- staying silent, but nothing here should reach a student in the evaluation
-- study until a nursing lecturer has read it.
--
-- The hardest rule is on hints. Section 5.4 requires that a hint never contain
-- the expected value, because a hint that gives the answer is not a hint. Every
-- hint below points at where to look or what to reconsider, and none of them
-- states a number.

BEGIN;

CREATE TABLE feedback_templates (
    error_label   text NOT NULL REFERENCES error_labels (code) ON DELETE CASCADE,
    feedback_type text NOT NULL CHECK (feedback_type IN ('HINT', 'EXPLANATION')),
    body          text NOT NULL CHECK (length(btrim(body)) > 0),

    -- False until a nursing lecturer has read it. The platform can tell a
    -- student the difference between "your faculty wrote this" and "this is
    -- placeholder wording", and so can a viva panel.
    approved      boolean NOT NULL DEFAULT false,
    approved_by   bigint REFERENCES reviewers (id),
    approved_at   timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (error_label, feedback_type),

    CONSTRAINT approval_is_attributed CHECK (
        (approved = false AND approved_by IS NULL AND approved_at IS NULL)
        OR (approved = true AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

COMMENT ON TABLE feedback_templates IS
    'The fallback library. Used when no model call is made, when one times out, or when its '
    'output fails validation. Seeded rows are drafts pending faculty approval.';

COMMENT ON COLUMN feedback_templates.body IS
    'For HINT rows this must never contain the expected value: a hint that gives the answer away '
    'is not a hint. Enforced in the application, which knows the value, and checked by a test.';

-- ---------------------------------------------------------------------------
-- Rate
-- ---------------------------------------------------------------------------
INSERT INTO feedback_templates (error_label, feedback_type, body) VALUES
('RATE_OVERESTIMATED', 'HINT',
 'Your rate is higher than the tracing supports. Check which R waves you counted between: at 25 mm/s one large square is 0.2 s, so counting across a smaller span than you think inflates the rate.'),
('RATE_OVERESTIMATED', 'EXPLANATION',
 'The rate you gave is faster than the recording shows. The reliable method on a regular rhythm is to divide 300 by the number of large squares between two consecutive R waves, or 1500 by the number of small squares. Counting from the wrong landmark, usually a tall T wave mistaken for the next R, is the common cause of an over-read.'),

('RATE_UNDERESTIMATED', 'HINT',
 'Your rate is lower than the tracing supports. Look again at where each R wave actually peaks, and check you have not skipped one.'),
('RATE_UNDERESTIMATED', 'EXPLANATION',
 'The rate you gave is slower than the recording shows. On a regular rhythm, divide 300 by the number of large squares between consecutive R waves. A missed beat, or measuring across two cycles instead of one, halves the apparent rate.'),

('RATE_METHOD_ERROR', 'HINT',
 'The rate looks as though it came from counting large squares between two beats. Consider whether this rhythm is regular enough for that method.'),
('RATE_METHOD_ERROR', 'EXPLANATION',
 'The large-square method assumes every R-R interval is the same length. When the rhythm is irregular it gives whatever the one interval you happened to pick gives. On an irregular rhythm, count the QRS complexes across a six-second strip and multiply by ten.'),

-- ---------------------------------------------------------------------------
-- Rhythm
-- ---------------------------------------------------------------------------
('REGULAR_CALLED_IRREGULAR', 'HINT',
 'March out the R-R intervals with a pair of calipers or the edge of a piece of paper, and compare each to the next before deciding.'),
('REGULAR_CALLED_IRREGULAR', 'EXPLANATION',
 'This rhythm is regular. Small beat-to-beat variation is normal, particularly with respiration, and does not make a rhythm irregular. The test is whether the R-R intervals march out consistently, not whether they are identical to the millisecond.'),

('IRREGULAR_CALLED_REGULAR', 'HINT',
 'Compare the first R-R interval with the last one on the strip, not just neighbouring pairs. A slow drift is easy to miss beat by beat.'),
('IRREGULAR_CALLED_REGULAR', 'EXPLANATION',
 'This rhythm is irregular. Measuring only adjacent R-R intervals can hide it, because each pair looks close to the one before. Marking several intervals along the whole strip and comparing the first to the last makes the variation obvious.'),

('IRREGULARITY_PATTERN_CONFUSED', 'HINT',
 'You correctly saw that this rhythm is irregular. Now look for whether the irregularity repeats in a pattern or has none at all.'),
('IRREGULARITY_PATTERN_CONFUSED', 'EXPLANATION',
 'There are two kinds of irregular rhythm and the distinction matters clinically. A regularly irregular rhythm has a repeating pattern, such as progressive PR lengthening before a dropped beat. An irregularly irregular rhythm has no pattern at all, which is what atrial fibrillation looks like. Mistaking one for the other points at a different diagnosis.'),

-- ---------------------------------------------------------------------------
-- Axis
-- ---------------------------------------------------------------------------
('AXIS_DEVIATION_MISSED', 'HINT',
 'Look at the net deflection in leads I and aVF: add the positive and negative parts of the QRS in each and decide whether the total is above or below the baseline.'),
('AXIS_DEVIATION_MISSED', 'EXPLANATION',
 'The axis here is deviated, not normal. The quickest check is the net QRS deflection in leads I and aVF. Both positive is a normal axis; positive in I with negative in aVF is left deviation; negative in I with positive in aVF is right deviation. Judging by the tallest R wave alone rather than the net area is what usually hides a deviation.'),

('AXIS_NORMAL_CALLED_DEVIATED', 'HINT',
 'Recheck the net deflection in lead I and lead aVF, counting the negative part of each QRS as well as the positive.'),
('AXIS_NORMAL_CALLED_DEVIATED', 'EXPLANATION',
 'The axis here is within the normal range. A deep S wave alongside a tall R wave can look like deviation if only the R is considered; the axis depends on the net area of the complex, positive minus negative.'),

('AXIS_WRONG_QUADRANT', 'HINT',
 'You have identified that the axis is deviated. Check the sign of the net deflection in lead I and in lead aVF separately, then work out which quadrant that puts it in.'),
('AXIS_WRONG_QUADRANT', 'EXPLANATION',
 'The direction of deviation is not the one you gave. Lead I and lead aVF divide the frontal plane into quadrants: the sign of the net QRS in each determines which quadrant the axis falls into. Reversing the two leads is the usual reason for naming the opposite deviation.'),

-- ---------------------------------------------------------------------------
-- P waves
-- ---------------------------------------------------------------------------
('P_ABSENT_CALLED_PRESENT', 'HINT',
 'Look along the baseline between QRS complexes in lead II and V1, and ask whether what you are seeing repeats at a fixed distance before every QRS.'),
('P_ABSENT_CALLED_PRESENT', 'EXPLANATION',
 'There are no organised P waves on this recording. Fibrillatory or flutter activity can look like P waves, especially in a single lead, but it does not sit at a fixed interval before each QRS. Checking several leads and confirming that each candidate precedes a QRS by the same distance is what separates a P wave from baseline activity.'),

('P_PRESENT_CALLED_ABSENT', 'HINT',
 'P waves can be small, and can hide inside the preceding T wave. Compare lead II with V1 before concluding they are absent.'),
('P_PRESENT_CALLED_ABSENT', 'EXPLANATION',
 'P waves are present on this recording. They are best seen in lead II and V1, and a low-amplitude P sitting on the downslope of a T wave is easy to miss in a single lead. Absent P waves is a specific finding and should only be called after looking across several leads.'),

-- ---------------------------------------------------------------------------
-- PR interval
-- ---------------------------------------------------------------------------
('PR_OVERESTIMATED', 'HINT',
 'Check where you started measuring. The PR interval begins at the first deflection of the P wave from the baseline, not at its peak.'),
('PR_OVERESTIMATED', 'EXPLANATION',
 'Your PR interval is longer than the recording shows. It is measured from the onset of the P wave to the onset of the QRS, taking the earliest visible deflection in any lead. Starting from the P peak, or ending at the R peak rather than the start of the Q, both lengthen it.'),

('PR_UNDERESTIMATED', 'HINT',
 'Check the start of the P wave. Its onset is often more gradual than it first appears, particularly in lead II.'),
('PR_UNDERESTIMATED', 'EXPLANATION',
 'Your PR interval is shorter than the recording shows. It runs from the very first deflection of the P wave to the very first deflection of the QRS. A shallow P onset is easy to clip, which shortens the measurement.'),

('PR_REPORTED_WHEN_ABSENT', 'HINT',
 'Before measuring a PR interval, check that there are organised P waves conducting to each QRS at a fixed delay.'),
('PR_REPORTED_WHEN_ABSENT', 'EXPLANATION',
 'A PR interval cannot be measured on this recording, because it has no organised P waves conducting to the ventricles. The interval describes the delay between atrial and ventricular activation; with no coordinated atrial activation there is nothing to measure from. Reporting one here is a more serious error than measuring it inaccurately, because it describes physiology the patient does not have.'),

-- ---------------------------------------------------------------------------
-- QRS
-- ---------------------------------------------------------------------------
('QRS_OVERESTIMATED', 'HINT',
 'Check where the QRS ends. The J point is where the steep deflection stops, which is often earlier than where the trace finally flattens.'),
('QRS_OVERESTIMATED', 'EXPLANATION',
 'Your QRS duration is wider than the recording shows. It is measured from the first deflection away from the baseline to the J point, where the sharp deflection ends and the ST segment begins. Including the early, slurred part of the ST segment is the usual reason a QRS is read as too wide.'),

('QRS_UNDERESTIMATED', 'HINT',
 'Measure the QRS in the lead where it appears widest, and check for a small initial Q wave before the main deflection.'),
('QRS_UNDERESTIMATED', 'EXPLANATION',
 'Your QRS duration is narrower than the recording shows. The complex does not begin and end at the same moment in every lead, so it should be measured where it appears widest. Missing a small initial Q wave shortens it.'),

('QRS_NARROW_CALLED_WIDE', 'HINT',
 'Count the small squares across the complex. At 25 mm/s each one is 0.04 s.'),
('QRS_NARROW_CALLED_WIDE', 'EXPLANATION',
 'This QRS is within the normal width. At 25 mm/s, three small squares is 0.12 s, which is the usual boundary. A tall complex can look broad without being broad; the width is what counts.'),

('QRS_WIDE_CALLED_NARROW', 'HINT',
 'Find the lead where the complex looks widest and count small squares across the whole of it.'),
('QRS_WIDE_CALLED_NARROW', 'EXPLANATION',
 'This QRS is broader than normal. A broad QRS means the ventricles are not being activated through the normal conducting system, which is why the measurement matters. Measuring in a lead where the complex happens to look narrow is what usually hides it.'),

-- ---------------------------------------------------------------------------
-- ST segment
-- ---------------------------------------------------------------------------
('ST_ELEVATION_MISSED', 'HINT',
 'Compare the ST segment just after the J point with the baseline taken from the PR segment, lead by lead.'),
('ST_ELEVATION_MISSED', 'EXPLANATION',
 'There is ST elevation on this recording that was not reported. ST deviation is measured about 60 ms after the J point, against the PR segment as the isoelectric baseline. Which leads are involved is as important as the finding itself, because the pattern of leads is what localises the territory.'),

('ST_DEPRESSION_MISSED', 'HINT',
 'Check whether the ST segment sits below the PR-segment baseline in any lead, not just whether it is raised.'),
('ST_DEPRESSION_MISSED', 'EXPLANATION',
 'There is ST depression on this recording that was not reported. It is easy to look only for elevation. Depression is measured the same way, about 60 ms after the J point against the PR-segment baseline, and carries its own clinical meaning.'),

('ST_NORMAL_CALLED_ABNORMAL', 'HINT',
 'Re-establish your baseline from the PR segment before judging the ST level, and check whether the trace is drifting.'),
('ST_NORMAL_CALLED_ABNORMAL', 'EXPLANATION',
 'The ST segments here are at the baseline. Baseline wander can lift or drop a segment that is actually isoelectric, which is why the PR segment immediately before each complex is used as the reference rather than the overall level of the trace.'),

('ST_WRONG_TERRITORY', 'HINT',
 'You have identified the ST change. Now check which leads it appears in, and group those leads by the territory they look at.'),
('ST_WRONG_TERRITORY', 'EXPLANATION',
 'The ST change is real but the leads you named are not where it appears. Leads group by territory: II, III and aVF look inferiorly; V1 to V4 anteriorly; I, aVL, V5 and V6 laterally. Naming the wrong group changes which territory the finding points to, which is the clinically important part.'),

-- ---------------------------------------------------------------------------
-- QT
-- ---------------------------------------------------------------------------
('QT_OVERESTIMATED', 'HINT',
 'Check where you ended the measurement. The T wave ends where its steepest downslope, extended, meets the baseline.'),
('QT_OVERESTIMATED', 'EXPLANATION',
 'Your QT is longer than the recording shows. It is measured from the start of the QRS to the end of the T wave, using the tangent method: follow the steepest part of the T wave''s downslope and take the point where that line crosses the baseline. Including a U wave, or following the T wave to where it finally flattens, both lengthen it.'),

('QT_UNDERESTIMATED', 'HINT',
 'Measure in a lead where the T wave is clearly visible, and check you have taken its true end rather than the point where it becomes shallow.'),
('QT_UNDERESTIMATED', 'EXPLANATION',
 'Your QT is shorter than the recording shows. The measurement runs from the onset of the QRS to the end of the T wave. A flat or low-amplitude T wave in the lead chosen makes the end look earlier than it is.'),

('QT_NOT_RATE_CORRECTED', 'HINT',
 'The QT interval shortens as the heart rate rises. Check whether this step asked for the raw interval or the corrected one.'),
('QT_NOT_RATE_CORRECTED', 'EXPLANATION',
 'The raw QT cannot be compared against a normal range without correcting for rate, because it shortens as the rate rises. Bazett''s formula divides the QT by the square root of the R-R interval in seconds. At very fast or very slow rates it over- and under-corrects respectively, which is why Fridericia''s is often reported alongside it.'),

-- ---------------------------------------------------------------------------
-- Not step specific
-- ---------------------------------------------------------------------------
('NO_ANSWER', 'HINT',
 'Nothing was submitted for this step. An answer you are unsure of is more useful than a blank one, because it shows where the reasoning went.'),
('NO_ANSWER', 'EXPLANATION',
 'No answer was recorded for this step. Working through each step in order, even when uncertain, is what builds a reliable reading; skipping one tends to leave the same gap next time.'),

('ANSWER_NOT_UNDERSTOOD', 'HINT',
 'That answer could not be read as a response to this step. Check the format the step is asking for.'),
('ANSWER_NOT_UNDERSTOOD', 'EXPLANATION',
 'The answer submitted did not match what this step expects. Some steps want a measurement, some want one of a fixed set of descriptions, and one asks which leads are involved.');

COMMIT;
