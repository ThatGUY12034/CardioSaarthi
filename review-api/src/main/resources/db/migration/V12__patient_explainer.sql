-- Layer 4: the patient's own report, in words they can read.
--
-- The patient area has had an interface since the first week and no backend at
-- all. Role.isImplemented() returned false for PATIENT, so the login endpoint
-- refused the role outright rather than failing as bad credentials -- which was
-- the honest thing to do while nothing existed behind it. This migration is
-- what goes behind it.
--
-- The governing rule is unchanged and matters more here than anywhere else in
-- the platform: a patient is the one reader who cannot check what they are
-- told. So the explanation is assembled from computed measurements and
-- faculty-approved sentences, and no model writes any part of it. Nothing here
-- is a diagnosis, and the schema says so in a constraint rather than a comment.

BEGIN;

-- ---------------------------------------------------------------------------
-- Patients
-- ---------------------------------------------------------------------------
-- A separate table from students, not a role column on one. A student is a
-- member of the college with a cohort and a mastery record; a patient is a
-- member of the public with a report. Merging them would put a patient's
-- medical record one join away from a classroom leaderboard.
CREATE TABLE patients (
    id            bigserial PRIMARY KEY,
    email         text NOT NULL,
    full_name     text NOT NULL,
    -- The identifier printed on the report the patient was handed.
    patient_ref   text NOT NULL,
    password_hash text,
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX patients_email_key ON patients (lower(email));
CREATE UNIQUE INDEX patients_ref_key   ON patients (lower(patient_ref));

-- ---------------------------------------------------------------------------
-- Issued reports
-- ---------------------------------------------------------------------------
-- A report ties a patient to a recording that was issued to them. The case
-- must be approved before it can be issued, enforced below, for the same
-- reason a student cannot be shown an unapproved case: an unreviewed
-- measurement must not reach anybody as fact.
CREATE TABLE patient_reports (
    id           bigserial PRIMARY KEY,
    patient_id   bigint NOT NULL REFERENCES patients (id) ON DELETE CASCADE,
    case_id      bigint NOT NULL REFERENCES cases (id),
    issued_on    date   NOT NULL DEFAULT current_date,
    -- What the clinician wrote for this patient, if anything. Free text by a
    -- named human, never generated.
    clinician_note text,
    issued_by    bigint REFERENCES reviewers (id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (patient_id, case_id)
);

CREATE INDEX patient_reports_patient_idx ON patient_reports (patient_id, issued_on DESC);

CREATE OR REPLACE FUNCTION forbid_unapproved_report() RETURNS trigger AS $$
BEGIN
    IF (SELECT review_status FROM cases WHERE id = NEW.case_id) <> 'approved' THEN
        RAISE EXCEPTION 'case % is not approved and cannot be issued to a patient', NEW.case_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER patient_reports_approved_only
    BEFORE INSERT ON patient_reports
    FOR EACH ROW EXECUTE FUNCTION forbid_unapproved_report();

-- ---------------------------------------------------------------------------
-- The words
-- ---------------------------------------------------------------------------
-- Every sentence a patient reads comes from this table. A row is shown only
-- once a named reviewer has approved it, exactly as a case is.
--
-- `finding` is the computed value this sentence explains, so the explanation is
-- selected by measurement rather than composed freely. A heart rate of 48 picks
-- the row for a slow rate; nothing writes a new sentence about it.
CREATE TABLE patient_explanations (
    id          bigserial PRIMARY KEY,
    concept     text NOT NULL REFERENCES interpretation_steps (concept),
    -- Which band of the measurement this sentence covers: LOW, NORMAL, HIGH, or
    -- a categorical value such as REGULAR. Matched in code, held as data.
    finding     text NOT NULL,
    headline    text NOT NULL,
    plain_text  text NOT NULL,
    -- Reassurance and alarm are both clinical acts. A sentence that tells a
    -- patient not to worry is a sentence a clinician must have approved.
    reassuring  boolean NOT NULL DEFAULT false,
    approved    boolean NOT NULL DEFAULT false,
    approved_by bigint REFERENCES reviewers (id),
    approved_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (concept, finding),
    CONSTRAINT approved_explanations_have_an_approver
        CHECK (approved = (approved_by IS NOT NULL)),
    -- The one sentence this table may never contain.
    CONSTRAINT explanations_state_no_diagnosis
        CHECK (plain_text !~* '\y(diagnos|infarct|myocardial infarction|heart attack|you have)\y')
);

COMMENT ON TABLE patient_explanations IS
    'Every sentence shown to a patient. Selected by the computed finding, never composed: '
    'a patient is the one reader who cannot check what they are told.';

-- ---------------------------------------------------------------------------
-- Glossary
-- ---------------------------------------------------------------------------
CREATE TABLE glossary_terms (
    term        text PRIMARY KEY,
    plain_text  text NOT NULL,
    approved    boolean NOT NULL DEFAULT false,
    approved_by bigint REFERENCES reviewers (id),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- What a patient may read
-- ---------------------------------------------------------------------------
-- Approved cases, approved sentences, and the patient's own reports. Each of
-- those three conditions is in the WHERE clause rather than in a service, so
-- forgetting one in Java cannot expose anything.
CREATE VIEW v_patient_report_values AS
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
LEFT JOIN v_served_parameters p
       ON p.case_id = r.case_id AND p.name = s.concept
ORDER BY r.id, s.step;

COMMENT ON VIEW v_patient_report_values IS
    'The computed values behind one patient report, for approved cases only. The sentences '
    'that explain them come from patient_explanations and must themselves be approved.';

-- ---------------------------------------------------------------------------
-- Seed sentences, as drafts
-- ---------------------------------------------------------------------------
-- Drafts, not approved: approved = false and no approver. Nothing here reaches
-- a patient until a clinician signs it off, and the interface says so when a
-- draft is shown in a demonstration.
INSERT INTO patient_explanations (concept, finding, headline, plain_text, reassuring) VALUES
 ('rate', 'LOW',    'Your heart rate was slower than the usual range',
  'Your heart was beating more slowly than the typical resting range of 60 to 100 beats each minute. This is common in people who are very fit, and in people taking certain medicines. Your clinician will tell you whether it matters for you.', false),
 ('rate', 'NORMAL', 'Your heart rate was in the usual range',
  'Your heart was beating between 60 and 100 times each minute while the recording was taken, which is the usual resting range for an adult.', true),
 ('rate', 'HIGH',   'Your heart rate was faster than the usual range',
  'Your heart was beating more quickly than the typical resting range. A faster rate is normal during activity, anxiety or illness, and your clinician will consider what was happening when the recording was taken.', false),
 ('rhythm', 'REGULAR', 'Your heartbeat was evenly spaced',
  'The gaps between beats were even, which is what a steady rhythm looks like on this recording.', true),
 ('rhythm', 'IRREGULARLY_IRREGULAR', 'The spacing between your beats varied',
  'The gaps between your heartbeats were uneven. There are several reasons this happens, and the recording on its own does not tell you which applies. Your clinician will explain what it means for you.', false),
 ('rhythm', 'REGULARLY_IRREGULAR', 'Your beats followed an uneven but repeating pattern',
  'The gaps between beats were not all the same, but they repeated in a pattern. Your clinician will explain what this means in your case.', false),
 ('p_waves', 'PRESENT', 'The upper chambers of your heart were signalling normally',
  'Each beat was preceded by the small wave that shows the upper chambers of the heart starting the beat.', true),
 ('p_waves', 'ABSENT', 'The usual small wave before each beat was not seen',
  'The recording did not show the small wave that normally appears before each beat. Your clinician will explain what this means for you.', false),
 ('qrs', 'NORMAL', 'The main electrical signal travelled normally',
  'The signal that makes the main pumping chambers contract took the usual amount of time to spread through them.', true),
 ('qrs', 'WIDE',   'The main electrical signal took longer than usual',
  'The signal through the main pumping chambers took a little longer than usual to spread. Your clinician will explain whether this is significant for you.', false),
 ('st_segment', 'NORMAL', 'No change was seen in this part of the trace',
  'A section of the recording that clinicians examine closely looked as expected.', true),
 ('st_segment', 'DEVIATION', 'A part of the trace differed from the usual shape',
  'One section of the recording did not have its usual shape. This is a finding your clinician will want to discuss with you directly.', false),
 ('t_waves', 'UPRIGHT', 'The recovery wave had its usual shape',
  'The wave that appears as the heart resets between beats pointed the usual way.', true),
 ('t_waves', 'INVERTED', 'The recovery wave pointed the other way in some areas',
  'The wave that appears as the heart resets between beats pointed downwards in places where it usually points upwards. Your clinician will explain what this means for you.', false),
 ('t_waves', 'FLAT', 'The recovery wave was smaller than usual',
  'The wave that appears as the heart resets between beats was flatter than usual. Your clinician will explain whether this matters in your case.', false);

INSERT INTO glossary_terms (term, plain_text) VALUES
 ('ECG', 'An ECG, or electrocardiogram, is a recording of the small electrical signals your heart makes as it beats. Sticky pads on your chest, arms and legs pick them up. It does not send anything into your body and it is not painful.'),
 ('Heart rate', 'How many times your heart beats in a minute. At rest, somewhere between 60 and 100 is usual for an adult.'),
 ('Rhythm', 'Whether your heartbeats are evenly spaced. An even rhythm means the gaps between beats are about the same each time.'),
 ('P wave', 'The small bump on the recording made by the upper chambers of your heart as they begin a beat.'),
 ('QRS complex', 'The tall spike on the recording, made by the main pumping chambers of your heart as they contract.'),
 ('T wave', 'The rounded wave after the spike, made as your heart resets electrically before the next beat.'),
 ('ST segment', 'The short flat part between the spike and the rounded wave. Clinicians look at it closely because its shape can carry useful information.'),
 ('Lead', 'Each ECG records your heart from twelve different angles at once. Each angle is called a lead. They are all views of the same heartbeat.');

COMMIT;
