"""Load the measured case bank into PostgreSQL.

Reads exactly what the engine wrote -- `artifacts/measurements/<ecg_id>.json`,
one serialised `MeasurementResult` per case -- so a number in the database and
the same number in `docs/validation/report.md` come from one run and cannot
disagree.

Every case enters with `review_status = 'pending'`. Nothing here approves
anything: a case becomes servable only when a reviewer says so.

Re-running is safe. A case that already exists is replaced only if nobody has
reviewed or corrected it; if a reviewer has touched it the case is left alone
and counted as protected, because re-ingesting would cascade their corrections
away and those corrections are the validation evidence for the engine. Pass
`--replace-reviewed` to override that, which is almost never what you want.

Re-measuring updates the case row in place and replaces only the rows derived
from the signal. The case id does not change, so everything attached to it
survives: the generated narrative, the review decision, faculty corrections, and
any student session worked on that case.

Usage::

    python scripts/ingest_cases.py                 # ingest everything new
    python scripts/ingest_cases.py --limit 20      # smoke test
    python scripts/ingest_cases.py --dry-run       # parse and report, write nothing
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# The scalar measures that become rows in `case_measurements`. Order is the
# order a reviewer reads them in, which is also the order of the nine-step
# interpretation sequence the platform teaches.
MEASURE_NAMES = (
    "heart_rate",
    "pr_interval",
    "qrs_duration",
    "qt_interval",
    "qtc_bazett",
    "qtc_fridericia",
    "p_duration",
)

# PTB-XL stores any age above 89 as 300 so that patients cannot be
# re-identified from it. The engine clamps the value to 89; whether a given 89
# is a real 89 or a censored 94 is only answerable from the raw distribution
# file, so that is where this flag comes from.
AGE_CENSOR_THRESHOLD = 89.0


# Docker publishes the database on 127.0.0.1 only. "localhost" can resolve to
# ::1 first, where nothing is listening, and a connect with no timeout then sits
# on a dead IPv6 handshake for minutes with no output at all. The timeout turns
# that into an error instead of a hang.
CONNECT_TIMEOUT_SECONDS = 10


def _connect(url: str):
    try:
        import psycopg
    except ImportError:  # pragma: no cover - environment guidance, not logic
        sys.exit(
            "psycopg is not installed.\n"
            "  pip install 'psycopg[binary]>=3.1'\n"
            "It is declared under the 'db' optional dependency group in pyproject.toml."
        )
    return psycopg.connect(url, autocommit=False, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def _json(value: Any):
    from psycopg.types.json import Jsonb

    return Jsonb(value)


def censored_ecg_ids(ptbxl_csv: Path) -> set[int]:
    """ecg_ids whose recorded age was censored in the source distribution.

    Returns an empty set if the raw file is absent; the flag is then simply
    unknown rather than silently wrong.
    """
    if not ptbxl_csv.exists():
        return set()
    censored: set[int] = set()
    with ptbxl_csv.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            raw = row.get("age", "")
            try:
                if float(raw) > AGE_CENSOR_THRESHOLD:
                    censored.add(int(row["ecg_id"]))
            except (TypeError, ValueError):
                continue
    return censored


def seed_conditions(cur) -> int:
    """Upsert the syllabus condition list from `cardiosignal.conditions`.

    That module is the single definition of the condition list, including the
    three entries PTB-XL cannot supply. Those are inserted with
    `available = false` rather than skipped, so the gap stays visible in
    `v_condition_bank_status` instead of disappearing from the bank silently.
    """
    from cardiosignal import conditions as cond_module

    rows = [
        (c.key, c.label, c.group, list(c.scp_codes), c.target, c.available, c.note or None)
        for c in cond_module.CONDITIONS
    ]
    cur.executemany(
        """
        INSERT INTO conditions (code, label, group_name, scp_codes, target_cases, available, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET
            label        = excluded.label,
            group_name   = excluded.group_name,
            scp_codes    = excluded.scp_codes,
            target_cases = excluded.target_cases,
            available    = excluded.available,
            note         = excluded.note
        """,
        rows,
    )
    return len(rows)


def _image_path(images_dir: Path, ecg_id: int, kind: str) -> str | None:
    """Repo-relative path to a rendered image, or None if it was not written."""
    candidate = images_dir / f"{ecg_id}_{kind}.png"
    if not candidate.exists():
        return None
    return candidate.relative_to(REPO_ROOT).as_posix()


def _existing_case(cur, source: str, ecg_id: int) -> tuple[int, int, int] | None:
    """(case_id, n_reviews, n_corrections) for an already-ingested case."""
    cur.execute(
        """
        SELECT c.id,
               (SELECT count(*) FROM reviews r WHERE r.case_id = c.id),
               (SELECT count(*) FROM measurement_corrections mc WHERE mc.case_id = c.id)
        FROM cases c
        WHERE c.source = %s AND c.source_ecg_id = %s
        """,
        (source, ecg_id),
    )
    row = cur.fetchone()
    return (row[0], row[1], row[2]) if row else None


def _existing_narrative(cur, case_id: int) -> tuple[Any, str | None, Any] | None:
    """The generated vignette for a case about to be replaced, if it has one.

    Everything else in a case row is derived from the signal and can be rebuilt
    by re-running the pipeline. A narrative cannot: it cost a model call, and it
    is the one column a re-measurement has no bearing on.
    """
    cur.execute(
        "SELECT narrative, narrative_model, narrative_generated_at FROM cases WHERE id = %s",
        (case_id,),
    )
    row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    return (row[0], row[1], row[2])


def _restore_narrative(cur, case_id: int, carried: tuple[Any, str | None, Any]) -> None:
    narrative, model, generated_at = carried
    cur.execute(
        """
        UPDATE cases
        SET narrative = %s, narrative_model = %s, narrative_generated_at = %s
        WHERE id = %s
        """,
        (_json(narrative), model, generated_at, case_id),
    )


def insert_case(cur, payload: dict[str, Any], *, censored: bool, images_dir: Path) -> int:
    ecg_id = int(payload["ecg_id"])
    rhythm = payload.get("rhythm") or {}
    axis = payload.get("axis") or {}
    quality = payload.get("quality") or {}

    cur.execute(
        """
        INSERT INTO cases (
            source, source_ecg_id,
            age, age_censored, sex, scp_codes, diagnostic_labels,
            schema_version, engine_version, computed_at, sampling_rate, n_samples,
            measurement_status, overall_confidence, n_beats, sqi_overall,
            rhythm_regularity, rr_mean_ms, axis_degrees, axis_category, warnings,
            t_wave_finding, t_wave_inverted_leads,
            raw_measurement, image_clean_path, image_annotated_path
        ) VALUES (
            %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s
        )
        RETURNING id
        """,
        (
            payload.get("source", "ptbxl"),
            ecg_id,
            payload.get("age"),
            censored,
            payload.get("sex"),
            _json(payload.get("scp_codes") or {}),
            payload.get("diagnostic_labels") or [],
            payload["schema_version"],
            payload["engine_version"],
            payload["computed_at"],
            payload["sampling_rate"],
            payload["n_samples"],
            payload["status"],
            payload["overall_confidence"],
            len(payload.get("beats") or []),
            quality.get("sqi_overall"),
            rhythm.get("regularity"),
            rhythm.get("rr_mean_ms"),
            axis.get("degrees"),
            axis.get("category"),
            payload.get("warnings") or [],
            payload.get("t_wave_finding"),
            payload.get("t_wave_inverted_leads") or [],
            _json(payload),
            _image_path(images_dir, ecg_id, "clean"),
            _image_path(images_dir, ecg_id, "annotated"),
        ),
    )
    case_id = int(cur.fetchone()[0])
    _insert_children(cur, case_id, payload)
    return case_id


def _insert_children(cur, case_id: int, payload: dict[str, Any]) -> None:
    """The rows derived from the measurement: replaced wholesale on a re-ingest."""
    measures = []
    for name in MEASURE_NAMES:
        m = payload.get(name)
        if m is None:
            continue
        ref = m.get("reference_range") or (None, None)
        measures.append(
            (
                case_id,
                name,
                m.get("value"),
                m.get("mad"),
                m.get("unit", "ms"),
                m.get("n_beats", 0),
                m.get("confidence"),
                m.get("status", "FAILED"),
                m.get("flag", "UNKNOWN"),
                ref[0],
                ref[1],
            )
        )
    if measures:
        cur.executemany(
            """
            INSERT INTO case_measurements
                (case_id, name, value, mad, unit, n_beats, confidence, status, flag, ref_low, ref_high)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            measures,
        )

    st_rows = [
        (
            case_id,
            s["lead"],
            s.get("deviation_mm"),
            s.get("deviation_mv"),
            s.get("baseline_mv"),
            s.get("threshold_mm"),
            s.get("finding", "NORMAL"),
            s.get("mad_mm"),
            s.get("n_beats", 0),
            s.get("confidence"),
        )
        for s in payload.get("st") or []
    ]
    if st_rows:
        cur.executemany(
            """
            INSERT INTO case_st_deviations
                (case_id, lead, deviation_mm, deviation_mv, baseline_mv, threshold_mm,
                 finding, mad_mm, n_beats, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            st_rows,
        )

    t_rows = [
        (
            case_id,
            t["lead"],
            t.get("amplitude_mv"),
            t.get("mad_mv"),
            t.get("finding", "FLAT"),
            t.get("normally_inverted", False),
            t.get("n_beats", 0),
            t.get("confidence"),
            t.get("status", "OK"),
        )
        for t in payload.get("t_waves") or []
    ]
    if t_rows:
        cur.executemany(
            """
            INSERT INTO case_t_waves
                (case_id, lead, amplitude_mv, mad_mv, finding, normally_inverted,
                 n_beats, confidence, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            t_rows,
        )

    links = [(case_id, code) for code in payload.get("syllabus_conditions") or []]
    if links:
        cur.executemany(
            "INSERT INTO case_conditions (case_id, condition_code) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            links,
        )


def update_case(cur, case_id: int, payload: dict[str, Any], *, censored: bool, images_dir: Path) -> None:
    """Re-measure an existing case without destroying what hangs off it.

    The case row is updated and its derived children are replaced. Everything
    that is not derived from the signal -- the narrative, the review decision,
    faculty corrections, student sessions -- is attached to the case id and
    survives because the id does.
    """
    ecg_id = int(payload["ecg_id"])
    rhythm = payload.get("rhythm") or {}
    axis = payload.get("axis") or {}
    quality = payload.get("quality") or {}

    cur.execute(
        """
        UPDATE cases SET
            age = %s, age_censored = %s, sex = %s, scp_codes = %s, diagnostic_labels = %s,
            schema_version = %s, engine_version = %s, computed_at = %s,
            sampling_rate = %s, n_samples = %s,
            measurement_status = %s, overall_confidence = %s, n_beats = %s, sqi_overall = %s,
            rhythm_regularity = %s, rr_mean_ms = %s, axis_degrees = %s, axis_category = %s,
            warnings = %s, t_wave_finding = %s, t_wave_inverted_leads = %s,
            raw_measurement = %s, image_clean_path = %s, image_annotated_path = %s
        WHERE id = %s
        """,
        (
            payload.get("age"),
            censored,
            payload.get("sex"),
            _json(payload.get("scp_codes") or {}),
            payload.get("diagnostic_labels") or [],
            payload["schema_version"],
            payload["engine_version"],
            payload["computed_at"],
            payload["sampling_rate"],
            payload["n_samples"],
            payload["status"],
            payload["overall_confidence"],
            len(payload.get("beats") or []),
            quality.get("sqi_overall"),
            rhythm.get("regularity"),
            rhythm.get("rr_mean_ms"),
            axis.get("degrees"),
            axis.get("category"),
            payload.get("warnings") or [],
            payload.get("t_wave_finding"),
            payload.get("t_wave_inverted_leads") or [],
            _json(payload),
            _image_path(images_dir, ecg_id, "clean"),
            _image_path(images_dir, ecg_id, "annotated"),
            case_id,
        ),
    )

    # The measurement tables refuse UPDATE -- a computed value is evidence and is
    # not edited in place -- so the old rows are removed and the new ones written.
    for table in ("case_measurements", "case_st_deviations", "case_t_waves", "case_conditions"):
        cur.execute(f"DELETE FROM {table} WHERE case_id = %s", (case_id,))
    _insert_children(cur, case_id, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--measurements", type=Path, default=REPO_ROOT / "artifacts" / "measurements")
    parser.add_argument("--images", type=Path, default=REPO_ROOT / "artifacts" / "images")
    parser.add_argument("--ptbxl-csv", type=Path, default=REPO_ROOT / "data" / "ptbxl" / "ptbxl_database.csv")
    parser.add_argument("--database-url", default=os.environ.get("CARDIO_DATABASE_URL"))
    parser.add_argument("--limit", type=int, default=None, help="ingest only the first N cases")
    parser.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    parser.add_argument(
        "--replace-reviewed",
        action="store_true",
        help="re-ingest cases that carry faculty reviews or corrections, DISCARDING them",
    )
    args = parser.parse_args()

    files = sorted(args.measurements.glob("*.json"), key=lambda p: int(p.stem))
    if not files:
        sys.exit(f"no measurement JSON found in {args.measurements}")
    if args.limit:
        files = files[: args.limit]

    censored = censored_ecg_ids(args.ptbxl_csv)
    print(f"{len(files)} case files, {len(censored)} censored ages known from the source distribution")

    if args.dry_run:
        statuses: dict[str, int] = {}
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            statuses[payload["status"]] = statuses.get(payload["status"], 0) + 1
        print("parsed cleanly; measurement status counts:")
        for status, n in sorted(statuses.items()):
            print(f"  {status:<16} {n}")
        return

    if not args.database_url:
        sys.exit("no database URL: set CARDIO_DATABASE_URL or pass --database-url")

    inserted = replaced = protected = 0
    with _connect(args.database_url) as conn, conn.cursor() as cur:
        n_conditions = seed_conditions(cur)
        print(f"conditions seeded: {n_conditions}")

        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ecg_id = int(payload["ecg_id"])
            source = payload.get("source", "ptbxl")

            existing = _existing_case(cur, source, ecg_id)
            if existing is not None:
                case_id, n_reviews, n_corrections = existing
                touched = n_reviews or n_corrections
                if touched and not args.replace_reviewed:
                    protected += 1
                    continue

                # The case row is updated in place and only its derived children
                # are replaced. Deleting the case would cascade away everything
                # else that hangs off it -- the generated narrative, faculty
                # reviews and corrections, and any student session worked on it,
                # which is the evidence the evaluation study rests on. None of
                # that is reproducible from the signal, and re-measuring an ECG
                # is not a reason to destroy it.
                update_case(cur, case_id, payload, censored=ecg_id in censored, images_dir=args.images)
                replaced += 1
            else:
                inserted += 1
                insert_case(cur, payload, censored=ecg_id in censored, images_dir=args.images)

        conn.commit()

    print(f"inserted {inserted}, replaced {replaced}, protected {protected}")
    if protected:
        print(
            f"{protected} case(s) already carry faculty reviews or corrections and were left "
            "untouched. Those corrections are the engine's validation evidence; pass "
            "--replace-reviewed only if you genuinely mean to discard them."
        )


if __name__ == "__main__":
    main()
