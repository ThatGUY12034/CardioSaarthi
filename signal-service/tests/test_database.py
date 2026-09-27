"""Tests for the case bank schema.

A schema comment promising that computed values are never overwritten is worth
nothing unless the database refuses the overwrite. These tests check the
guarantees themselves: the immutability trigger, the constraints that stop a
half-recorded review decision, and the view that decides which number a student
is graded against.

Every test runs inside a transaction that is rolled back, so they can be run
against the development database without touching the real case bank.

Skipped when no database is reachable, so `pytest` stays runnable on a machine
with nothing but the measurement engine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.needs_postgres

REPO_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str | None:
    """Connection URL from the environment, falling back to the local .env file.

    pytest does not read .env, and requiring the variable to be exported by hand
    is the kind of friction that stops tests from being run at all.
    """
    if url := os.environ.get("CARDIO_DATABASE_URL"):
        return url
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "CARDIO_DATABASE_URL":
            return value.strip()
    return None


@pytest.fixture(scope="module")
def conn():
    url = _database_url()
    if not url:
        pytest.skip("no CARDIO_DATABASE_URL and no .env — database tests need a live PostgreSQL")
    try:
        connection = psycopg.connect(url, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"database not reachable: {exc}")
    yield connection
    connection.close()


@pytest.fixture
def cur(conn):
    """A cursor in a transaction that is always rolled back."""
    with conn.transaction(force_rollback=True), conn.cursor() as cursor:
        yield cursor


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _reviewer(cur, email: str = "test.reviewer@example.invalid") -> int:
    cur.execute(
        "INSERT INTO reviewers (email, full_name, role) VALUES (%s, %s, 'faculty') RETURNING id",
        (email, "Test Reviewer"),
    )
    return int(cur.fetchone()[0])


def _case(cur, *, ecg_id: int = -1, review_status: str = "pending") -> int:
    """A minimal case. Negative ecg_ids so a stray commit could never collide
    with a real PTB-XL record."""
    from psycopg.types.json import Jsonb

    cur.execute(
        """
        INSERT INTO cases (
            source, source_ecg_id, schema_version, engine_version, computed_at,
            sampling_rate, n_samples, measurement_status, overall_confidence,
            raw_measurement, review_status, reviewed_at
        ) VALUES (
            'test', %s, '1.0.0', '0.1.0', now(), 500, 5000, 'OK', 0.9,
            %s, %s, CASE WHEN %s = 'pending' THEN NULL ELSE now() END
        ) RETURNING id
        """,
        (ecg_id, Jsonb({"ecg_id": ecg_id}), review_status, review_status),
    )
    return int(cur.fetchone()[0])


def _measurement(cur, case_id: int, name: str = "pr_interval", value: float = 160.0) -> None:
    cur.execute(
        """
        INSERT INTO case_measurements (case_id, name, value, mad, unit, n_beats, confidence, status, flag)
        VALUES (%s, %s, %s, 4.0, 'ms', 12, 0.9, 'OK', 'NORMAL')
        """,
        (case_id, name, value),
    )


# ---------------------------------------------------------------------------
# the schema exists and is complete
# ---------------------------------------------------------------------------
EXPECTED_TABLES = {
    "reviewers",
    "conditions",
    "cases",
    "case_conditions",
    "case_measurements",
    "case_st_deviations",
    "measurement_corrections",
    "reviews",
}

EXPECTED_VIEWS = {
    "v_condition_bank_status",
    "v_review_queue",
    "v_served_measurements",
    "v_measurement_agreement",
    "v_review_outcomes",
    "v_rejection_reasons",
}


def test_all_tables_present(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
    assert {row[0] for row in cur.fetchall()} >= EXPECTED_TABLES


def test_all_views_present(cur):
    cur.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")
    assert {row[0] for row in cur.fetchall()} >= EXPECTED_VIEWS


def test_pgvector_available(cur):
    """Needed by the week-7 knowledge base. Failing now is much cheaper than
    discovering it on a database that holds faculty corrections."""
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    assert cur.fetchone() is not None


# ---------------------------------------------------------------------------
# computed values are evidence
# ---------------------------------------------------------------------------
def test_computed_measurement_cannot_be_updated(cur):
    case_id = _case(cur)
    _measurement(cur, case_id, "pr_interval", 160.0)

    with pytest.raises(psycopg.errors.RaiseException) as exc:
        cur.execute("UPDATE case_measurements SET value = 200 WHERE case_id = %s", (case_id,))
    assert "append-only" in str(exc.value)


def test_st_deviation_cannot_be_updated(cur):
    case_id = _case(cur)
    cur.execute(
        "INSERT INTO case_st_deviations (case_id, lead, deviation_mm, finding) VALUES (%s, 'V2', 1.5, 'ELEVATION')",
        (case_id,),
    )
    with pytest.raises(psycopg.errors.RaiseException):
        cur.execute("UPDATE case_st_deviations SET deviation_mm = 0 WHERE case_id = %s", (case_id,))


def test_deleting_a_case_removes_its_measurements(cur):
    """Re-ingesting replaces a case wholesale, so the cascade has to work even
    though UPDATE is blocked."""
    case_id = _case(cur)
    _measurement(cur, case_id)
    cur.execute("DELETE FROM cases WHERE id = %s", (case_id,))
    cur.execute("SELECT count(*) FROM case_measurements WHERE case_id = %s", (case_id,))
    assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# a review decision cannot be half-recorded
# ---------------------------------------------------------------------------
def test_approved_case_must_record_when_it_was_decided(cur):
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                               sampling_rate, n_samples, measurement_status, overall_confidence,
                               raw_measurement, review_status)
            VALUES ('test', -2, '1.0.0', '0.1.0', now(), 500, 5000, 'OK', 0.9, '{}'::jsonb, 'approved')
            """
        )


def test_pending_case_must_not_claim_a_reviewer(cur):
    reviewer_id = _reviewer(cur)
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                               sampling_rate, n_samples, measurement_status, overall_confidence,
                               raw_measurement, review_status, reviewed_by)
            VALUES ('test', -3, '1.0.0', '0.1.0', now(), 500, 5000, 'OK', 0.9, '{}'::jsonb, 'pending', %s)
            """,
            (reviewer_id,),
        )


def test_rejection_without_a_reason_is_refused(cur):
    """A rejection with no reason is not a pipeline-accuracy measure, just a
    missing case."""
    case_id = _case(cur)
    reviewer_id = _reviewer(cur)
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            "INSERT INTO reviews (case_id, reviewer_id, action) VALUES (%s, %s, 'reject')",
            (case_id, reviewer_id),
        )


def test_approval_must_not_carry_a_rejection_reason(cur):
    case_id = _case(cur)
    reviewer_id = _reviewer(cur)
    with pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            "INSERT INTO reviews (case_id, reviewer_id, action, rejection_reason) "
            "VALUES (%s, %s, 'approve', 'other')",
            (case_id, reviewer_id),
        )


# ---------------------------------------------------------------------------
# what a student is graded against
# ---------------------------------------------------------------------------
def test_pending_case_is_never_served(cur):
    case_id = _case(cur, review_status="pending")
    _measurement(cur, case_id)
    cur.execute("SELECT count(*) FROM v_served_measurements WHERE case_id = %s", (case_id,))
    assert cur.fetchone()[0] == 0


def test_approved_case_serves_the_computed_value_when_uncorrected(cur):
    case_id = _case(cur, ecg_id=-10, review_status="approved")
    _measurement(cur, case_id, "pr_interval", 164.0)
    cur.execute(
        "SELECT value, faculty_corrected FROM v_served_measurements WHERE case_id = %s AND name = 'pr_interval'",
        (case_id,),
    )
    value, corrected = cur.fetchone()
    assert float(value) == 164.0
    assert corrected is False


def test_faculty_correction_overrides_the_computed_value(cur):
    case_id = _case(cur, ecg_id=-11, review_status="approved")
    reviewer_id = _reviewer(cur)
    _measurement(cur, case_id, "pr_interval", 164.0)
    cur.execute(
        """
        INSERT INTO measurement_corrections
            (case_id, name, computed_value, corrected_value, unit, engine_version, reviewer_id)
        VALUES (%s, 'pr_interval', 164.0, 200.0, 'ms', '0.1.0', %s)
        """,
        (case_id, reviewer_id),
    )
    cur.execute(
        "SELECT value, computed_value, faculty_corrected FROM v_served_measurements "
        "WHERE case_id = %s AND name = 'pr_interval'",
        (case_id,),
    )
    value, computed, corrected = cur.fetchone()
    assert float(value) == 200.0, "the reviewer's number must win"
    assert float(computed) == 164.0, "the engine's number must still be visible"
    assert corrected is True


def test_the_latest_correction_wins_and_earlier_ones_survive(cur):
    case_id = _case(cur, ecg_id=-12, review_status="approved")
    reviewer_id = _reviewer(cur)
    _measurement(cur, case_id, "qt_interval", 400.0)
    for corrected_value in (420.0, 430.0):
        cur.execute(
            """
            INSERT INTO measurement_corrections
                (case_id, name, computed_value, corrected_value, unit, engine_version, reviewer_id)
            VALUES (%s, 'qt_interval', 400.0, %s, 'ms', '0.1.0', %s)
            """,
            (case_id, corrected_value, reviewer_id),
        )
    cur.execute("SELECT value FROM v_served_measurements WHERE case_id = %s AND name = 'qt_interval'", (case_id,))
    assert float(cur.fetchone()[0]) == 430.0

    cur.execute("SELECT count(*) FROM measurement_corrections WHERE case_id = %s", (case_id,))
    assert cur.fetchone()[0] == 2, "history must not be collapsed"


# ---------------------------------------------------------------------------
# the engine's report card
# ---------------------------------------------------------------------------
def test_measurement_agreement_reports_bias_and_scatter_separately(cur):
    """Two corrections of +20 ms and -20 ms are 20 ms of scatter and zero bias.
    A view that conflated them would report 0 error and hide the problem."""
    case_a = _case(cur, ecg_id=-20, review_status="approved")
    case_b = _case(cur, ecg_id=-21, review_status="approved")
    reviewer_id = _reviewer(cur)
    for case_id, corrected in ((case_a, 180.0), (case_b, 140.0)):
        _measurement(cur, case_id, "pr_interval", 160.0)
        cur.execute(
            """
            INSERT INTO measurement_corrections
                (case_id, name, computed_value, corrected_value, unit, engine_version, reviewer_id)
            VALUES (%s, 'pr_interval', 160.0, %s, 'ms', '0.1.0', %s)
            """,
            (case_id, corrected, reviewer_id),
        )
    cur.execute("SELECT n_corrections, mae, bias, worst FROM v_measurement_agreement WHERE name = 'pr_interval'")
    n, mae, bias, worst = cur.fetchone()
    assert n == 2
    assert float(mae) == 20.0
    assert float(bias) == 0.0
    assert float(worst) == 20.0


# ---------------------------------------------------------------------------
# bank status and queue
# ---------------------------------------------------------------------------
def test_conditions_unavailable_in_ptbxl_are_present_with_a_zero_bank(cur):
    """Ventricular tachycardia and the two electrolyte disturbances are on the
    syllabus and absent from PTB-XL. They must appear as a visible gap, not
    vanish from the condition list."""
    cur.execute("SELECT code, candidates, approved FROM v_condition_bank_status WHERE available = false ORDER BY code")
    rows = cur.fetchall()
    assert {row[0] for row in rows} >= {"hyperkalaemia", "hypokalaemia", "ventricular_tachycardia"}
    for code, candidates, approved in rows:
        assert candidates == 0 and approved == 0, f"{code} should have no cases"


def test_approving_a_case_reduces_the_shortfall(cur):
    cur.execute("SELECT shortfall FROM v_condition_bank_status WHERE code = 'atrial_flutter'")
    before = cur.fetchone()[0]

    case_id = _case(cur, ecg_id=-30, review_status="approved")
    cur.execute(
        "INSERT INTO case_conditions (case_id, condition_code) VALUES (%s, 'atrial_flutter')",
        (case_id,),
    )
    cur.execute("SELECT shortfall FROM v_condition_bank_status WHERE code = 'atrial_flutter'")
    after = cur.fetchone()[0]
    assert after == max(before - 1, 0)


def test_review_queue_holds_only_pending_cases(cur):
    pending = _case(cur, ecg_id=-40, review_status="pending")
    approved = _case(cur, ecg_id=-41, review_status="approved")
    cur.execute("SELECT case_id FROM v_review_queue WHERE case_id IN (%s, %s)", (pending, approved))
    assert [row[0] for row in cur.fetchall()] == [pending]


def test_review_queue_exposes_the_warnings_a_reviewer_needs(cur):
    """A reviewer should see why a case was held back before opening it."""
    cur.execute(
        """
        INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                           sampling_rate, n_samples, measurement_status, overall_confidence,
                           warnings, raw_measurement)
        VALUES ('test', -50, '1.0.0', '0.1.0', now(), 500, 5000, 'NEEDS_REVIEW', 0.4,
                ARRAY['p_wave_absent_in_3_of_14_beats'], '{}'::jsonb)
        RETURNING id
        """
    )
    case_id = int(cur.fetchone()[0])
    cur.execute("SELECT warnings, overall_confidence FROM v_review_queue WHERE case_id = %s", (case_id,))
    warnings, confidence = cur.fetchone()
    assert warnings == ["p_wave_absent_in_3_of_14_beats"]
    assert float(confidence) == 0.4


# ---------------------------------------------------------------------------
# the ingest's own logic, without a database
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw_age", "expected"),
    [("300", True), ("300.0", True), ("89", False), ("88.0", False), ("", False), ("unknown", False)],
)
def test_censored_age_detection(tmp_path, raw_age, expected):
    """PTB-XL stores ages above 89 as 300. Anything unparseable is not censored,
    it is unknown, and must not be guessed either way."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "signal-service" / "scripts"))
    from ingest_cases import censored_ecg_ids

    csv_file = tmp_path / "ptbxl_database.csv"
    csv_file.write_text(f"ecg_id,age\n1,{raw_age}\n", encoding="utf-8")
    assert (1 in censored_ecg_ids(csv_file)) is expected


def test_censored_age_detection_tolerates_a_missing_file(tmp_path):
    import sys

    sys.path.insert(0, str(REPO_ROOT / "signal-service" / "scripts"))
    from ingest_cases import censored_ecg_ids

    assert censored_ecg_ids(tmp_path / "absent.csv") == set()


def test_real_measurement_json_has_every_field_the_ingest_reads():
    """Guards against a schema change in the engine silently breaking ingest."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "signal-service" / "scripts"))
    from ingest_cases import MEASURE_NAMES

    directory = REPO_ROOT / "artifacts" / "measurements"
    files = sorted(directory.glob("*.json"))
    if not files:
        pytest.skip("no pipeline output in artifacts/measurements")

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    for key in ("ecg_id", "schema_version", "engine_version", "computed_at",
                "sampling_rate", "n_samples", "status", "overall_confidence",
                "scp_codes", "diagnostic_labels", "syllabus_conditions",
                "warnings", "rhythm", "axis", "quality", "st", "beats"):
        assert key in payload, f"ingest reads {key!r} and the engine no longer writes it"
    for name in MEASURE_NAMES:
        assert name in payload, f"ingest reads the measure {name!r} and the engine no longer writes it"
        assert "unit" in payload[name]
