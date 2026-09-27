-- A third reviewer role, and statistics that refuse to count it.
--
-- Development needs a handful of servable cases to build the student runtime
-- against, long before nursing faculty sit down to review anything. Those cases
-- have to be approved for the runtime to serve them at all.
--
-- The danger is not the seeded approval. It is that six months later a report
-- says "97% of generated cases were approved by faculty" and the number
-- includes approvals no clinician ever made. That would be fabricated evidence,
-- and no amount of remembering not to do it is a safeguard.
--
-- So the exclusion is enforced in SQL. A seeded approval is attributed to a
-- reviewer whose role is 'system', and every view that reports pipeline
-- accuracy, measurement agreement or reviewer throughput filters those out. The
-- case is servable; the approval is not evidence.

BEGIN;

ALTER TABLE reviewers DROP CONSTRAINT reviewers_role_check;
ALTER TABLE reviewers ADD CONSTRAINT reviewers_role_check
    CHECK (role IN ('faculty', 'admin', 'system'));

COMMENT ON COLUMN reviewers.role IS
    'faculty and admin are people. system is a non-human account used to seed development '
    'fixtures; its decisions are excluded from every statistic this project reports.';

-- ---------------------------------------------------------------------------
-- Statistics: human decisions only
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_review_outcomes AS
SELECT
    count(*)                                                    AS n_reviews,
    count(*) FILTER (WHERE r.action = 'approve')                 AS approved,
    count(*) FILTER (WHERE r.action = 'edit')                    AS edited,
    count(*) FILTER (WHERE r.action = 'reject')                  AS rejected,
    round(100.0 * count(*) FILTER (WHERE r.action = 'approve') / nullif(count(*), 0), 1)
                                                                AS approved_pct,
    round(100.0 * count(*) FILTER (WHERE r.action <> 'reject') / nullif(count(*), 0), 1)
                                                                AS usable_pct,
    round(avg(r.duration_seconds)::numeric, 1)                   AS mean_seconds_per_case,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY r.duration_seconds)::numeric, 1)
                                                                AS median_seconds_per_case
FROM reviews r
JOIN reviewers rev ON rev.id = r.reviewer_id
WHERE rev.role <> 'system';

COMMENT ON VIEW v_review_outcomes IS
    'Human review decisions only. Seeded approvals made by a system account are excluded, so this '
    'view can never report pipeline accuracy that no clinician produced.';

CREATE OR REPLACE VIEW v_rejection_reasons AS
SELECT
    r.rejection_reason AS reason,
    count(*)           AS n,
    round(100.0 * count(*) / nullif(sum(count(*)) OVER (), 0), 1) AS pct
FROM reviews r
JOIN reviewers rev ON rev.id = r.reviewer_id
WHERE r.action = 'reject' AND rev.role <> 'system'
GROUP BY r.rejection_reason;

CREATE OR REPLACE VIEW v_measurement_agreement AS
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
JOIN reviewers rev ON rev.id = mc.reviewer_id
WHERE mc.computed_value IS NOT NULL
  AND mc.corrected_value IS NOT NULL
  AND rev.role <> 'system'
GROUP BY mc.name, mc.unit;

COMMENT ON VIEW v_measurement_agreement IS
    'The measurement engine''s report card against human reviewers. A system account cannot '
    'contribute to it: the whole value of this table is that a person disagreed.';

-- ---------------------------------------------------------------------------
-- Bank status: says how a case became approved
-- ---------------------------------------------------------------------------
-- The two new columns are added at the end so dependent views keep working.
-- `approved` still counts every approved case, because a seeded case genuinely
-- is servable; `approved_by_faculty` is the number that belongs on a slide.
CREATE OR REPLACE VIEW v_condition_bank_status AS
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
                                                                                   AS shortfall,
    count(cc.case_id) FILTER (
        WHERE cs.review_status = 'approved' AND coalesce(rev.role, 'faculty') <> 'system')
                                                                                   AS approved_by_faculty,
    count(cc.case_id) FILTER (WHERE cs.review_status = 'approved' AND rev.role = 'system')
                                                                                   AS approved_seeded
FROM conditions c
LEFT JOIN case_conditions cc  ON cc.condition_code = c.code
LEFT JOIN cases cs            ON cs.id = cc.case_id
LEFT JOIN reviewers rev       ON rev.id = cs.reviewed_by
GROUP BY c.code, c.label, c.group_name, c.available, c.target_cases;

COMMIT;
