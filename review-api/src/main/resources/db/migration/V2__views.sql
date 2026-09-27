-- CardioSaarthi — derived views
--
-- These exist so that the two questions the project has to answer repeatedly
-- are answered by the database rather than by application code that could
-- answer them differently in two places:
--
--   1. "What should the next reviewer look at?"  -> v_review_queue
--   2. "What value may a student be graded against?" -> v_served_measurements
--
-- Everything here is derived. No view is writable and none of them cache.

BEGIN;

-- ---------------------------------------------------------------------------
-- Bank status per condition
-- ---------------------------------------------------------------------------
-- The shortfall column is what makes the review queue intelligent: it is the
-- difference between the case bank the syllabus needs and the case bank that
-- actually exists in approved form today.
CREATE VIEW v_condition_bank_status AS
SELECT
    c.code,
    c.label,
    c.group_name,
    c.available,
    c.target_cases,
    count(cc.case_id)                                                              AS candidates,
    count(cc.case_id) FILTER (WHERE cs.review_status = 'approved')                 AS approved,
    count(cc.case_id) FILTER (WHERE cs.review_status = 'pending')                  AS pending,
    count(cc.case_id) FILTER (WHERE cs.review_status = 'rejected')                 AS rejected,
    greatest(c.target_cases - count(cc.case_id) FILTER (WHERE cs.review_status = 'approved'), 0)
                                                                                   AS shortfall
FROM conditions c
LEFT JOIN case_conditions cc ON cc.condition_code = c.code
LEFT JOIN cases cs           ON cs.id = cc.case_id
GROUP BY c.code, c.label, c.group_name, c.available, c.target_cases;

COMMENT ON VIEW v_condition_bank_status IS
    'Target versus approved case count per syllabus condition. A condition with available = false '
    'and candidates = 0 is a genuine gap in PTB-XL, not a pipeline failure.';

-- ---------------------------------------------------------------------------
-- Review queue
-- ---------------------------------------------------------------------------
-- Ordered to make a reviewer's hour worth as much as possible: cases whose
-- conditions are furthest from a usable bank come first, and within that the
-- engine's most confident cases come first, because those are the ones most
-- likely to be a quick confirmation rather than a careful correction. The
-- first sitting therefore makes the bank servable soonest.
--
-- The API may re-order this (for instance lowest confidence first, when the
-- goal of a sitting is to validate the engine rather than to fill the bank).
-- Both orderings are legitimate; the columns needed for either are exposed.
CREATE VIEW v_review_queue AS
SELECT
    cs.id                        AS case_id,
    cs.source,
    cs.source_ecg_id,
    cs.age,
    cs.sex,
    cs.diagnostic_labels,
    cs.measurement_status,
    cs.overall_confidence,
    cs.n_beats,
    cs.warnings,
    cs.narrative IS NOT NULL     AS has_narrative,
    cs.image_clean_path,
    cs.image_annotated_path,
    cs.created_at,
    array_remove(array_agg(DISTINCT cc.condition_code), NULL) AS condition_codes,
    coalesce(max(bank.shortfall), 0)                          AS max_condition_shortfall
FROM cases cs
LEFT JOIN case_conditions cc          ON cc.case_id = cs.id
LEFT JOIN v_condition_bank_status bank ON bank.code = cc.condition_code
WHERE cs.review_status = 'pending'
GROUP BY cs.id;

-- ---------------------------------------------------------------------------
-- Served measurements
-- ---------------------------------------------------------------------------
-- The single source of the numbers a student is graded against. A faculty
-- correction wins over the engine; where there is no correction the computed
-- value stands. Nothing that is not approved appears here at all, so a case
-- cannot reach a student by accident.
CREATE VIEW v_served_measurements AS
SELECT
    m.case_id,
    m.name,
    coalesce(corr.corrected_value, m.value) AS value,
    m.unit,
    m.mad,
    m.confidence,
    m.status,
    m.flag,
    m.ref_low,
    m.ref_high,
    corr.id IS NOT NULL                     AS faculty_corrected,
    m.value                                 AS computed_value,
    corr.corrected_value,
    corr.reviewer_id                        AS corrected_by,
    corr.created_at                         AS corrected_at
FROM case_measurements m
JOIN cases cs ON cs.id = m.case_id AND cs.review_status = 'approved'
LEFT JOIN LATERAL (
    -- Most recent correction for this measure. A reviewer may correct the same
    -- interval twice; the last word is the one that counts, and the earlier
    -- rows stay in the table as history.
    SELECT mc.id, mc.corrected_value, mc.reviewer_id, mc.created_at
    FROM measurement_corrections mc
    WHERE mc.case_id = m.case_id AND mc.name = m.name
    ORDER BY mc.created_at DESC, mc.id DESC
    LIMIT 1
) corr ON true;

COMMENT ON VIEW v_served_measurements IS
    'Approved cases only. Faculty correction overrides the computed value; both are retained side by side.';

-- ---------------------------------------------------------------------------
-- Measurement agreement — the engine's report card
-- ---------------------------------------------------------------------------
-- This is the week-4+ validation the technical report is waiting on: how far
-- the engine was from a cardiologist-trained reviewer, per measure, on real
-- cases nobody tuned it against.
--
-- Bias and scatter are reported separately because they mean different things:
-- a consistent offset is usually fixable in the algorithm, a large error with
-- near-zero bias is scatter and is not.
CREATE VIEW v_measurement_agreement AS
SELECT
    mc.name,
    mc.unit,
    count(*)                                                        AS n_corrections,
    round(avg(abs(mc.corrected_value - mc.computed_value)), 2)      AS mae,
    round(percentile_cont(0.5) WITHIN GROUP (
        ORDER BY abs(mc.corrected_value - mc.computed_value))::numeric, 2) AS median_abs_error,
    round(avg(mc.corrected_value - mc.computed_value), 2)           AS bias,
    round(stddev_samp(mc.corrected_value - mc.computed_value), 2)   AS sd,
    max(abs(mc.corrected_value - mc.computed_value))                AS worst
FROM measurement_corrections mc
WHERE mc.computed_value IS NOT NULL AND mc.corrected_value IS NOT NULL
GROUP BY mc.name, mc.unit;

-- ---------------------------------------------------------------------------
-- Review outcomes — pipeline accuracy and reviewer throughput
-- ---------------------------------------------------------------------------
-- The rejection log is retained and reported as a pipeline-accuracy measure,
-- so it gets a view rather than an ad-hoc query.
CREATE VIEW v_review_outcomes AS
SELECT
    count(*)                                                    AS n_reviews,
    count(*) FILTER (WHERE action = 'approve')                   AS approved,
    count(*) FILTER (WHERE action = 'edit')                      AS edited,
    count(*) FILTER (WHERE action = 'reject')                    AS rejected,
    round(100.0 * count(*) FILTER (WHERE action = 'approve') / nullif(count(*), 0), 1)
                                                                AS approved_pct,
    round(100.0 * count(*) FILTER (WHERE action <> 'reject') / nullif(count(*), 0), 1)
                                                                AS usable_pct,
    round(avg(duration_seconds)::numeric, 1)                     AS mean_seconds_per_case,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_seconds)::numeric, 1)
                                                                AS median_seconds_per_case
FROM reviews;

CREATE VIEW v_rejection_reasons AS
SELECT
    rejection_reason AS reason,
    count(*)         AS n,
    round(100.0 * count(*) / nullif(sum(count(*)) OVER (), 0), 1) AS pct
FROM reviews
WHERE action = 'reject'
GROUP BY rejection_reason;

COMMIT;
