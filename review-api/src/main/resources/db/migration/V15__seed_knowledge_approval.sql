-- A starting library, so the tutor can be shown working.
--
-- 345 paragraphs were imported and every one is pending, which is correct and
-- also means the tutor answers nothing at all. The case bank had the same
-- problem and the same answer: a small subset is approved by the `system`
-- reviewer, which is not a person, is excluded from every figure that reports
-- faculty activity, and leaves the great majority of the corpus waiting for a
-- clinician exactly as it should.
--
-- Deliberately a subset. Approving all 345 would make the gate look like a
-- formality, and the point of the queue is that somebody reads what goes
-- through it.

BEGIN;

-- The longest paragraph for each concept, which in this corpus is reliably the
-- substantive one rather than a stub or a disambiguation line. Six per concept
-- is enough for the tutor to answer a question on any of the nine steps.
WITH ranked AS (
    SELECT k.id,
           row_number() OVER (
               PARTITION BY k.concept
               ORDER BY length(k.body) DESC, k.id
           ) AS rank
    FROM knowledge_chunks k
    WHERE k.review_status = 'pending'
      AND k.concept IS NOT NULL
      AND length(k.body) >= 200
)
UPDATE knowledge_chunks
   SET review_status = 'approved',
       reviewed_by = (SELECT id FROM reviewers WHERE role = 'system' LIMIT 1),
       reviewed_at = now()
 WHERE id IN (SELECT id FROM ranked WHERE rank <= 6)
   AND EXISTS (SELECT 1 FROM reviewers WHERE role = 'system');

-- A little general material too, for questions that are not about one step.
WITH ranked AS (
    SELECT k.id,
           row_number() OVER (ORDER BY length(k.body) DESC, k.id) AS rank
    FROM knowledge_chunks k
    WHERE k.review_status = 'pending'
      AND k.concept IS NULL
      AND length(k.body) >= 200
)
UPDATE knowledge_chunks
   SET review_status = 'approved',
       reviewed_by = (SELECT id FROM reviewers WHERE role = 'system' LIMIT 1),
       reviewed_at = now()
 WHERE id IN (SELECT id FROM ranked WHERE rank <= 8)
   AND EXISTS (SELECT 1 FROM reviewers WHERE role = 'system');

-- ---------------------------------------------------------------------------
-- Who approved what
-- ---------------------------------------------------------------------------
-- The same distinction the case bank draws. A seeded approval is not a
-- clinical one, and the faculty console reports both numbers so nobody can
-- mistake a fixture for a decision.
CREATE VIEW v_knowledge_provenance AS
SELECT
    count(*)                                                      AS total,
    count(*) FILTER (WHERE k.review_status = 'pending')           AS pending,
    count(*) FILTER (WHERE k.review_status = 'approved')          AS approved,
    count(*) FILTER (WHERE k.review_status = 'rejected')          AS rejected,
    count(*) FILTER (WHERE k.review_status = 'approved'
                       AND r.role <> 'system')                    AS approved_by_clinician
FROM knowledge_chunks k
LEFT JOIN reviewers r ON r.id = k.reviewed_by;

COMMENT ON VIEW v_knowledge_provenance IS
    'Seeded approvals are fixtures, not decisions. approved_by_clinician is the only one of '
    'these numbers that represents a person having read a paragraph.';

COMMIT;
