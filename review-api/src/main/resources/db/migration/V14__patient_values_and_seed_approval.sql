-- Two corrections to V12.
--
-- The patient report view joined the served parameters on the step's *concept*,
-- and the numeric steps are not stored under their concept. Step 1's concept is
-- `rate` and its measurement is `heart_rate`; step 6 is `qrs` and
-- `qrs_duration`. So the two measurements a patient is most likely to ask about
-- came back empty and the report said "not reported" for a rate the engine had
-- measured perfectly well. interpretation_steps.measure has carried the right
-- name all along.
--
-- And the seeded sentences were left unapproved with no way to approve them,
-- which made the whole layer undemonstrable: correct, but inert.

BEGIN;

-- ---------------------------------------------------------------------------
-- Join on the name the measurement is actually stored under
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_patient_report_values AS
SELECT
    r.id            AS report_id,
    r.patient_id,
    r.case_id,
    r.issued_on,
    r.clinician_note,
    s.step,
    s.concept,
    s.label,
    p.value,
    p.text_value,
    p.unit,
    p.status
FROM patient_reports r
JOIN cases c                ON c.id = r.case_id AND c.review_status = 'approved'
JOIN interpretation_steps s ON true
-- coalesce, not concept: a numeric step is served under its measure name and a
-- categorical one under its concept.
LEFT JOIN v_served_parameters p
       ON p.case_id = r.case_id AND p.name = coalesce(s.measure, s.concept)
ORDER BY r.id, s.step;

-- ---------------------------------------------------------------------------
-- Seed approval, attributable to the seed account and to nobody else
-- ---------------------------------------------------------------------------
-- The same device the case bank uses: development fixtures are approved by the
-- `system` reviewer, which is not a person and is excluded from every figure
-- that reports faculty activity. The layer becomes demonstrable without any
-- seeded decision being counted as a clinician's.
UPDATE patient_explanations
   SET approved = true,
       approved_by = (SELECT id FROM reviewers WHERE role = 'system' LIMIT 1),
       approved_at = now()
 WHERE NOT approved
   AND EXISTS (SELECT 1 FROM reviewers WHERE role = 'system');

UPDATE glossary_terms
   SET approved = true,
       approved_by = (SELECT id FROM reviewers WHERE role = 'system' LIMIT 1)
 WHERE NOT approved
   AND EXISTS (SELECT 1 FROM reviewers WHERE role = 'system');

-- ---------------------------------------------------------------------------
-- Whether a human has actually seen it
-- ---------------------------------------------------------------------------
-- A patient reading an explanation deserves to know whether a clinician
-- approved that sentence or whether a seed script did. This view answers it,
-- and the API passes the answer through to the page.
CREATE VIEW v_patient_explanation_provenance AS
SELECT
    count(*)                                                   AS total,
    count(*) FILTER (WHERE e.approved)                         AS approved,
    count(*) FILTER (WHERE e.approved AND r.role <> 'system')  AS approved_by_clinician
FROM patient_explanations e
LEFT JOIN reviewers r ON r.id = e.approved_by;

COMMENT ON VIEW v_patient_explanation_provenance IS
    'Seeded approvals are not clinical approvals. The patient page says which it is looking at.';

COMMIT;
