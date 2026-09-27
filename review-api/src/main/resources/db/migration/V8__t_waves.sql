-- T-wave polarity, so step 8 of the nine can finally be marked.
--
-- The engine has always located the T wave, because the QT interval cannot be
-- measured without it, and never measured it. Eight of the nine steps had a
-- computed answer and this one did not, so it was reported to students as "not
-- marked yet" rather than guessed at. It now has one.
--
-- Stored per lead because that is how the finding is reported and acted on:
-- inversion in V1 to V3 means something different from inversion in II, III and
-- aVF, and a single overall verdict throws that away. The case-level answer sits
-- on the case row beside it, for the step that asks one question.

BEGIN;

CREATE TABLE case_t_waves (
    case_id           bigint NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    lead              text   NOT NULL,
    amplitude_mv      numeric(6, 4),
    mad_mv            numeric(6, 4),
    finding           text   NOT NULL CHECK (finding IN ('UPRIGHT', 'INVERTED', 'FLAT', 'BIPHASIC')),
    -- aVR looks at the heart from the opposite direction and its T wave is
    -- normally inverted; III and V1 commonly are in healthy people. Carried per
    -- row so the reason a lead was not reported as abnormal is visible.
    normally_inverted boolean NOT NULL DEFAULT false,
    n_beats           integer NOT NULL DEFAULT 0,
    confidence        numeric(4, 3),
    status            text   NOT NULL DEFAULT 'OK'
                             CHECK (status IN ('OK', 'NEEDS_REVIEW', 'NOT_MEASURABLE', 'FAILED')),
    PRIMARY KEY (case_id, lead)
);

-- Computed values are evidence, the same as every other measurement.
CREATE TRIGGER case_t_waves_no_update
    BEFORE UPDATE ON case_t_waves
    FOR EACH ROW EXECUTE FUNCTION forbid_update();

ALTER TABLE cases
    ADD COLUMN t_wave_finding text
        CHECK (t_wave_finding IS NULL OR t_wave_finding IN ('UPRIGHT', 'INVERTED', 'FLAT', 'BIPHASIC')),
    -- Leads inverted where they should be upright. Empty is a real answer;
    -- null means too few leads could be measured to say anything at all.
    ADD COLUMN t_wave_inverted_leads text[];

COMMENT ON COLUMN cases.t_wave_finding IS
    'The case-level answer for step 8. NULL when fewer than half the leads could be measured, '
    'which the grader treats as not markable rather than guessing.';

-- ---------------------------------------------------------------------------
-- Serve it alongside the other eight
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_served_parameters AS
WITH latest AS (
    SELECT DISTINCT ON (case_id, name)
           case_id, name, corrected_value, corrected_text, reviewer_id, created_at
    FROM measurement_corrections
    ORDER BY case_id, name, created_at DESC, id DESC
)
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

SELECT
    c.id, p.name, 'CATEGORICAL', NULL,
    coalesce(l.corrected_text, p.computed), NULL,
    CASE WHEN p.computed IS NULL OR p.computed = 'INDETERMINATE' THEN 'NEEDS_REVIEW' ELSE 'OK' END,
    NULL, p.computed, l.case_id IS NOT NULL
FROM cases c
CROSS JOIN LATERAL (
    VALUES ('rhythm', c.rhythm_regularity),
           ('axis', c.axis_category),
           -- The T wave joins the other two case-level categoricals. A null
           -- finding reads as NEEDS_REVIEW, which the grader declines to mark.
           ('t_waves', c.t_wave_finding)
) AS p(name, computed)
LEFT JOIN latest l ON l.case_id = c.id AND l.name = p.name
WHERE c.review_status = 'approved'

UNION ALL

SELECT
    c.id, 'p_waves', 'CATEGORICAL', NULL,
    coalesce(l.corrected_text,
             CASE WHEN m.status = 'NOT_MEASURABLE' THEN 'ABSENT' ELSE 'PRESENT' END),
    NULL, 'OK', NULL,
    CASE WHEN m.status = 'NOT_MEASURABLE' THEN 'ABSENT' ELSE 'PRESENT' END,
    l.case_id IS NOT NULL
FROM cases c
JOIN case_measurements m ON m.case_id = c.id AND m.name = 'p_duration'
LEFT JOIN latest l ON l.case_id = c.id AND l.name = 'p_waves'
WHERE c.review_status = 'approved'

UNION ALL

SELECT
    c.id, 'st_segment', 'MULTI_CATEGORICAL', NULL,
    coalesce(l.corrected_text, st.leads, ''), NULL, 'OK', NULL,
    coalesce(st.leads, ''), l.case_id IS NOT NULL
FROM cases c
LEFT JOIN LATERAL (
    SELECT string_agg(d.lead, ',' ORDER BY d.lead) AS leads
    FROM case_st_deviations d
    WHERE d.case_id = c.id AND d.finding <> 'NORMAL'
) st ON true
LEFT JOIN latest l ON l.case_id = c.id AND l.name = 'st_segment'
WHERE c.review_status = 'approved';

COMMIT;
