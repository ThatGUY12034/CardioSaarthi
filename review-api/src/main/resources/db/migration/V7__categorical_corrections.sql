-- Corrections to the parameters that are not numbers.
--
-- Four of the nine interpretation steps have no number to correct: the rhythm,
-- the axis, whether P waves are present, and which leads show ST deviation. Up
-- to now a reviewer could correct an interval and could not correct any of
-- those, which left the most consequential disagreement in the case bank
-- unfixable.
--
-- That disagreement is real and measured: on 10 of the 50 atrial fibrillation
-- cases the rhythm classifier reports regularly irregular rather than
-- irregularly irregular, usually because ectopic beats give the R-R series a
-- periodic-looking autocorrelation. The grader declines to mark the step where
-- the label and the classifier disagree, which protects the student but leaves
-- the case wrong. A reviewer can now say what the rhythm actually is.
--
-- Same shape as before: the computed value is snapshotted beside the corrected
-- one and nothing is overwritten, because the difference between them is the
-- evidence that validates the engine.

BEGIN;

ALTER TABLE measurement_corrections
    ADD COLUMN computed_text  text,
    ADD COLUMN corrected_text text;

-- A categorical correction has no unit. "Irregularly irregular" is not
-- measured in anything.
ALTER TABLE measurement_corrections ALTER COLUMN unit DROP NOT NULL;

ALTER TABLE measurement_corrections ADD CONSTRAINT correction_is_one_kind CHECK (
    (corrected_value IS NOT NULL AND corrected_text IS NULL AND unit IS NOT NULL)
    OR (corrected_text IS NOT NULL AND corrected_value IS NULL)
);

COMMENT ON COLUMN measurement_corrections.corrected_text IS
    'A categorical parameter''s corrected value: a rhythm, an axis, P-wave presence, or a '
    'comma-separated list of leads. Also used to mark a numeric measure NOT_MEASURABLE.';

-- ---------------------------------------------------------------------------
-- Served parameters: one place to ask what the answer is
-- ---------------------------------------------------------------------------
-- The numeric measures already have v_served_measurements. The categorical ones
-- live in three different places -- two columns on cases and a row set in
-- case_st_deviations -- and each needs the same "correction if there is one,
-- computed value otherwise" treatment. This view puts all nine in one shape so
-- that grading asks one question rather than four.
CREATE VIEW v_served_parameters AS
WITH latest AS (
    SELECT DISTINCT ON (case_id, name)
           case_id, name, corrected_value, corrected_text, reviewer_id, created_at
    FROM measurement_corrections
    ORDER BY case_id, name, created_at DESC, id DESC
)
-- the numeric measures
SELECT
    m.case_id,
    m.name,
    'NUMERIC'::text                                    AS kind,
    coalesce(l.corrected_value, m.value)               AS value,
    CASE WHEN l.corrected_text IS NOT NULL THEN l.corrected_text ELSE NULL END AS text_value,
    m.unit,
    m.status,
    m.value                                            AS computed_value,
    NULL::text                                         AS computed_text,
    l.case_id IS NOT NULL                              AS faculty_corrected
FROM case_measurements m
JOIN cases c   ON c.id = m.case_id AND c.review_status = 'approved'
LEFT JOIN latest l ON l.case_id = m.case_id AND l.name = m.name

UNION ALL

-- rhythm and axis, which live on the case row
SELECT
    c.id,
    p.name,
    'CATEGORICAL',
    NULL,
    coalesce(l.corrected_text, p.computed),
    NULL,
    CASE WHEN p.computed IS NULL OR p.computed = 'INDETERMINATE' THEN 'NEEDS_REVIEW' ELSE 'OK' END,
    NULL,
    p.computed,
    l.case_id IS NOT NULL
FROM cases c
CROSS JOIN LATERAL (
    VALUES ('rhythm', c.rhythm_regularity), ('axis', c.axis_category)
) AS p(name, computed)
LEFT JOIN latest l ON l.case_id = c.id AND l.name = p.name
WHERE c.review_status = 'approved'

UNION ALL

-- P-wave presence, which is a statement about the P duration rather than a
-- column of its own: a duration the engine could not measure means it found no
-- P wave to measure.
SELECT
    c.id,
    'p_waves',
    'CATEGORICAL',
    NULL,
    coalesce(l.corrected_text,
             CASE WHEN m.status = 'NOT_MEASURABLE' THEN 'ABSENT' ELSE 'PRESENT' END),
    NULL,
    'OK',
    NULL,
    CASE WHEN m.status = 'NOT_MEASURABLE' THEN 'ABSENT' ELSE 'PRESENT' END,
    l.case_id IS NOT NULL
FROM cases c
JOIN case_measurements m ON m.case_id = c.id AND m.name = 'p_duration'
LEFT JOIN latest l ON l.case_id = c.id AND l.name = 'p_waves'
WHERE c.review_status = 'approved'

UNION ALL

-- the leads that deviate, as one comma-separated value so that a correction is
-- a single row rather than one per lead
SELECT
    c.id,
    'st_segment',
    'MULTI_CATEGORICAL',
    NULL,
    coalesce(l.corrected_text, st.leads, ''),
    NULL,
    'OK',
    NULL,
    coalesce(st.leads, ''),
    l.case_id IS NOT NULL
FROM cases c
LEFT JOIN LATERAL (
    SELECT string_agg(d.lead, ',' ORDER BY d.lead) AS leads
    FROM case_st_deviations d
    WHERE d.case_id = c.id AND d.finding <> 'NORMAL'
) st ON true
LEFT JOIN latest l ON l.case_id = c.id AND l.name = 'st_segment'
WHERE c.review_status = 'approved';

COMMENT ON VIEW v_served_parameters IS
    'All nine interpretation parameters for approved cases, each as the reviewer corrected it or '
    'as the engine computed it. One shape, so grading asks one question instead of four.';

COMMIT;
