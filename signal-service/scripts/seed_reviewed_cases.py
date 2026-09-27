"""Approve a handful of cases so the student runtime has something to serve.

The student runtime can only serve approved cases, and nursing faculty will not
sit down to review anything until the platform is built. This approves a small,
clinically varied set so that work is not blocked.

What it is careful about
------------------------
These are not faculty approvals and must never be counted as any. Every
decision here is attributed to a reviewer whose role is ``system``, and the
migration that introduced that role rewrote ``v_review_outcomes``,
``v_measurement_agreement`` and ``v_rejection_reasons`` to exclude it in SQL.
The case becomes servable; the approval never becomes evidence.

The system account is created with a null password hash, so it exists to
attribute rows and cannot be authenticated as.

Nothing here touches a case a human has already reviewed, and ``--undo``
reverses exactly what this script did and nothing else.

Usage::

    python scripts/seed_reviewed_cases.py            # approve 5 varied cases
    python scripts/seed_reviewed_cases.py --count 8
    python scripts/seed_reviewed_cases.py --undo     # put them back in the queue
"""

from __future__ import annotations

import argparse
import os
import sys

SEED_EMAIL = "development-seed@cardiosaarthi.invalid"

SEED_NOTE = (
    "Development fixture, not a clinical review. Approved by an automated seed so the "
    "student runtime has servable cases to be built against. Excluded from every "
    "reported statistic by reviewer role."
)

# One case from each, in this order, so the seeded set spans a normal trace, a
# rate abnormality, an absent-P rhythm, a conduction delay and a wide QRS.
# Building a student runtime against five normal sinus cases would hide every
# interesting branch in it.
PREFERRED_CONDITIONS = (
    "normal_sinus",
    "sinus_bradycardia",
    "atrial_fibrillation",
    "av_block_1",
    "rbbb",
    "lbbb",
    "sinus_tachycardia",
    "lvh",
    "mi_anterior",
    "mi_inferior",
)


# Docker publishes the database on 127.0.0.1 only. "localhost" can resolve to
# ::1 first, where nothing is listening, and a connect with no timeout then sits
# on a dead IPv6 handshake for minutes with no output at all. The timeout turns
# that into an error instead of a hang.
CONNECT_TIMEOUT_SECONDS = 10


def _connect(url: str):
    try:
        import psycopg
    except ImportError:  # pragma: no cover - environment guidance
        sys.exit("psycopg is not installed.\n  pip install 'psycopg[binary]>=3.1'")
    return psycopg.connect(url, autocommit=False, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def ensure_system_reviewer(cur) -> int:
    """The account seeded approvals are attributed to.

    Null password hash: this exists to own rows, not to be logged in as.
    """
    cur.execute(
        """
        INSERT INTO reviewers (email, full_name, role, password_hash)
        VALUES (%s, 'Automated development seed', 'system', NULL)
        ON CONFLICT (lower(email)) DO UPDATE SET role = 'system', password_hash = NULL
        RETURNING id
        """,
        (SEED_EMAIL,),
    )
    return int(cur.fetchone()[0])


def pick_cases(cur, count: int) -> list[tuple[int, str, int, float]]:
    """The most confident untouched case for each preferred condition.

    Most confident on purpose: a seeded approval skips the human check, so the
    cases it is applied to should be the ones least likely to need one.
    """
    picked: list[tuple[int, str, int, float]] = []
    used: set[int] = set()

    for condition in PREFERRED_CONDITIONS:
        if len(picked) >= count:
            break
        cur.execute(
            """
            SELECT c.id, c.source_ecg_id, c.overall_confidence
            FROM cases c
            JOIN case_conditions cc ON cc.case_id = c.id AND cc.condition_code = %s
            WHERE c.review_status = 'pending'
              AND c.measurement_status = 'OK'
              AND NOT EXISTS (SELECT 1 FROM reviews r WHERE r.case_id = c.id)
              AND NOT (c.id = ANY (%s))
            ORDER BY c.overall_confidence DESC, c.id
            LIMIT 1
            """,
            (condition, list(used) or [0]),
        )
        row = cur.fetchone()
        if row is None:
            print(f"  no eligible case for {condition}; skipping")
            continue
        case_id, ecg_id, confidence = int(row[0]), int(row[1]), float(row[2])
        picked.append((case_id, condition, ecg_id, confidence))
        used.add(case_id)

    return picked


def seed(cur, reviewer_id: int, count: int) -> int:
    picked = pick_cases(cur, count)
    if not picked:
        print("nothing eligible to seed")
        return 0

    for case_id, condition, ecg_id, confidence in picked:
        cur.execute(
            """
            INSERT INTO reviews (case_id, reviewer_id, action, note)
            VALUES (%s, %s, 'approve', %s)
            """,
            (case_id, reviewer_id, SEED_NOTE),
        )
        cur.execute(
            """
            UPDATE cases
            SET review_status = 'approved', reviewed_at = now(), reviewed_by = %s
            WHERE id = %s AND review_status = 'pending'
            """,
            (reviewer_id, case_id),
        )
        print(f"  approved case {case_id:>4} (ecg {ecg_id:>5})  {condition:<22} conf {confidence:.3f}")

    return len(picked)


def undo(cur) -> int:
    """Reverse exactly what this script did, and nothing a human did.

    Scoped to reviews owned by the system account, so a case a faculty member
    has since looked at is left alone.
    """
    cur.execute("SELECT id FROM reviewers WHERE lower(email) = lower(%s)", (SEED_EMAIL,))
    row = cur.fetchone()
    if row is None:
        print("no seed account exists; nothing to undo")
        return 0
    reviewer_id = int(row[0])

    cur.execute(
        """
        UPDATE cases
        SET review_status = 'pending', reviewed_at = NULL, reviewed_by = NULL
        WHERE reviewed_by = %s
          AND NOT EXISTS (
              SELECT 1 FROM reviews r
              WHERE r.case_id = cases.id AND r.reviewer_id <> %s
          )
        """,
        (reviewer_id, reviewer_id),
    )
    reverted = cur.rowcount
    cur.execute("DELETE FROM reviews WHERE reviewer_id = %s", (reviewer_id,))
    print(f"  reverted {reverted} case(s), removed {cur.rowcount} seeded review row(s)")
    return reverted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=5, help="how many cases to approve")
    parser.add_argument("--undo", action="store_true", help="put the seeded cases back in the queue")
    parser.add_argument("--database-url", default=os.environ.get("CARDIO_DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("no database URL: set CARDIO_DATABASE_URL or pass --database-url")

    with _connect(args.database_url) as conn, conn.cursor() as cur:
        if args.undo:
            undo(cur)
        else:
            reviewer_id = ensure_system_reviewer(cur)
            seeded = seed(cur, reviewer_id, args.count)
            if seeded:
                print(
                    f"\n{seeded} case(s) are now servable for development.\n"
                    "They are attributed to a system account and excluded from "
                    "v_review_outcomes, v_measurement_agreement and v_rejection_reasons, "
                    "so they cannot be reported as faculty review."
                )
        conn.commit()

    print("\nbank status:")
    with _connect(args.database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FILTER (WHERE review_status = 'pending'),
                   count(*) FILTER (WHERE review_status = 'approved')
            FROM cases
            """
        )
        pending, approved = cur.fetchone()
        cur.execute("SELECT n_reviews FROM v_review_outcomes")
        human_reviews = cur.fetchone()[0]
        print(f"  {pending} pending, {approved} approved, {human_reviews} human review(s) on record")


if __name__ == "__main__":
    main()
