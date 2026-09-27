"""Generate one clinical vignette per case, offline, once.

Section 4.5. This is the only place in CardioSaarthi where a model authors
content, and the only place an API key is used at all. It runs as a batch job
against the case bank, writes to `cases.narrative`, and nothing it produces
reaches a student before a reviewer has approved the case.

The rules the model has to follow, and the checks that catch it when it does
not, live in `cardiosignal.narrative`. This script is the part that makes calls
and stores results.

Cost
----
The system prompt is sent with `cache_control`, so it is billed once rather than
714 times. `max_tokens` is capped. A case that already has a narrative is
skipped unless `--force` is passed, so a re-run after a crash costs only what it
has left to do.

Credentials
-----------
Read from `CARDIO_LLM_API_KEY` (or `ANTHROPIC_API_KEY`) in the environment,
never passed on the command line, never logged. Put it in the repository's
`.env`, which is gitignored.

`CARDIO_LLM_BASE_URL` points this at a router or proxy instead of Anthropic
directly, as long as it speaks the same Messages API. The endpoint is logged so
a run can be traced to where it actually went; the key is not.

Usage::

    python scripts/generate_narratives.py --dry-run      # show a prompt, call nothing
    python scripts/generate_narratives.py --limit 5      # a costed trial
    python scripts/generate_narratives.py                # the whole bank
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cardiosignal import narrative as narrative_rules

REPO_ROOT = Path(__file__).resolve().parents[2]

# Anthropic by default; CARDIO_LLM_BASE_URL points this at a router or proxy
# that speaks the same Messages API. The key is read from CARDIO_LLM_API_KEY,
# falling back to ANTHROPIC_API_KEY, and is never logged or echoed.
DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"

# Generous for six short fields, and a hard stop on a model that will not stop.
MAX_TOKENS = 1200

# Low but not zero: the vignettes should not all read identically, but this is
# clinical prose, not creative writing.
TEMPERATURE = 0.6

CONNECT_TIMEOUT_SECONDS = 10

# A shared router rate-limits, so transport failures are retried with
# backoff. Separate from the validation rounds on purpose.
MAX_TRANSPORT_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 5

_print_lock = threading.Lock()


def log(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


# ---------------------------------------------------------------------------
# data in
# ---------------------------------------------------------------------------
def _connect(url: str):
    try:
        import psycopg
    except ImportError:  # pragma: no cover - environment guidance
        sys.exit("psycopg is not installed.\n  pip install 'psycopg[binary]>=3.1'")
    return psycopg.connect(url, autocommit=False, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def load_clinical_reports(parquet: Path) -> dict[int, str]:
    """The dataset's own clinician note, keyed by ecg_id.

    Not carried into the database by the ingest, because nothing served to a
    student uses it. It is real clinical context though -- medication, prior
    events, why the study was ordered -- so the narrative prompt is the one
    place it earns its keep.
    """
    if not parquet.exists():
        return {}
    import pandas as pd

    frame = pd.read_parquet(parquet, columns=["ecg_id", "report"])
    return {
        int(row.ecg_id): str(row.report)
        for row in frame.itertuples()
        if isinstance(row.report, str) and row.report.strip()
    }


def load_cases(cur, *, limit: int | None, force: bool) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT c.id, c.source_ecg_id, c.age, c.age_censored, c.sex, c.diagnostic_labels,
               m.value AS heart_rate
        FROM cases c
        LEFT JOIN case_measurements m ON m.case_id = c.id AND m.name = 'heart_rate'
        WHERE c.measurement_status <> 'FAILED'
          AND (%s OR c.narrative IS NULL)
        ORDER BY c.id
        LIMIT %s
        """,
        (force, limit),
    )
    return [
        {
            "case_id": row[0],
            "ecg_id": row[1],
            "age": float(row[2]) if row[2] is not None else None,
            "age_censored": row[3],
            "sex": row[4],
            "diagnostic_labels": list(row[5] or []),
            "heart_rate": float(row[6]) if row[6] is not None else None,
        }
        for row in cur.fetchall()
    ]


# ---------------------------------------------------------------------------
# the call
# ---------------------------------------------------------------------------
class TransientError(RuntimeError):
    """A failure worth retrying: rate limit, server error, timeout."""


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the model's reply.

    Tolerates a fenced code block and a sentence of preamble, because a weaker
    model will sometimes write "Here is the vignette:" before the JSON. Falls
    back to the outermost balanced brace pair rather than giving up, since a
    reply that contains the object is not a reply worth discarding.
    """
    stripped = text.strip()
    if not stripped:
        raise TransientError("empty reply")

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        raise TransientError(f"no JSON object in reply: {stripped[:120]!r}")
    return json.loads(stripped[start : end + 1])


def call_model(
    api_key: str,
    model: str,
    user_prompt: str,
    repair_note: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    import requests

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    if repair_note:
        # A second attempt is cheaper than a discarded case, and telling the
        # model exactly what was wrong works far better than asking again.
        messages.append({"role": "assistant", "content": "{}"})
        messages.append({
            "role": "user",
            "content": (
                "That response was rejected by the platform's validator for these reasons:\n"
                f"{repair_note}\n\n"
                "Rewrite the whole JSON object, fixing every one of them. Return only the JSON."
            ),
        })

    response = requests.post(
        base_url.rstrip("/") + "/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            # Cached, so the instructions are billed once for the whole batch
            # rather than once per case.
            "system": [
                {
                    "type": "text",
                    "text": narrative_rules.SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": messages,
        },
        timeout=120,
    )
    if response.status_code == 429 or response.status_code >= 500:
        # A shared router rate-limits. Worth waiting for, not worth discarding a
        # case over.
        raise TransientError(f"API returned {response.status_code}: {response.text[:200]}")
    if response.status_code != 200:
        # 401, 403, 400: waiting will not help, and retrying 714 times would
        # only make the same mistake louder.
        raise RuntimeError(f"API returned {response.status_code}: {response.text[:300]}")

    body = response.json()
    text = "".join(block.get("text", "") for block in body.get("content", []))
    return _extract_json(text)


def generate_one(
    case: dict[str, Any],
    reports: dict[int, str],
    api_key: str,
    model: str,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any] | None:
    """One vignette, validated, with a single repair attempt.

    Returns None when the model could not produce something that passes. A case
    with no narrative is a case a reviewer sees without one; a case with a
    narrative that states the answer is a broken exercise.
    """
    prompt = narrative_rules.build_user_prompt(
        age=case["age"],
        sex=case["sex"],
        age_censored=case["age_censored"],
        diagnostic_labels=case["diagnostic_labels"],
        clinical_report=reports.get(case["ecg_id"]),
    )

    repair_note = None
    for validation_round in (1, 2):
        drafted = None
        # Transport failures get their own retries with backoff, separately from
        # the validation rounds: a rate limit is not the model's mistake and
        # should not consume the one chance it has to fix its output.
        for transport_attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            try:
                drafted = call_model(api_key, model, prompt, repair_note, base_url)
                break
            except TransientError as exc:
                if transport_attempt == MAX_TRANSPORT_ATTEMPTS:
                    log(f"  case {case['case_id']}: giving up after {transport_attempt} attempts: {exc}")
                    return None
                delay = BACKOFF_BASE_SECONDS * (2 ** (transport_attempt - 1))
                time.sleep(delay)
            except Exception as exc:
                # Deliberately broad, but not retried: a 403 or a bad request
                # will fail identically every time.
                log(f"  case {case['case_id']}: call failed: {exc}")
                return None

        if drafted is None:
            return None

        problems = narrative_rules.validate(
            drafted,
            age=case["age"],
            sex=case["sex"],
            diagnostic_labels=case["diagnostic_labels"],
        )
        if not problems:
            return narrative_rules.inject_computed_vitals(drafted, heart_rate=case["heart_rate"])

        repair_note = "\n".join(f"- {problem}" for problem in problems)
        if validation_round == 2:
            log(f"  case {case['case_id']}: rejected after repair:\n    " + "\n    ".join(problems))

    return None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="generate for the first N cases only")
    parser.add_argument("--force", action="store_true", help="regenerate cases that already have a narrative")
    parser.add_argument("--model", default=os.environ.get("CARDIO_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CARDIO_LLM_BASE_URL", DEFAULT_BASE_URL),
        help="API root for a Messages-API-compatible service",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true", help="show a prompt and call nothing")
    parser.add_argument("--database-url", default=os.environ.get("CARDIO_DATABASE_URL"))
    parser.add_argument("--candidates", type=Path, default=REPO_ROOT / "artifacts" / "candidates.parquet")
    args = parser.parse_args()

    if not args.database_url:
        sys.exit("no database URL: set CARDIO_DATABASE_URL or pass --database-url")

    reports = load_clinical_reports(args.candidates)
    log(f"{len(reports)} clinician notes available for prompt context")

    with _connect(args.database_url) as conn, conn.cursor() as cur:
        cases = load_cases(cur, limit=args.limit, force=args.force)

    if not cases:
        log("every case already has a narrative; pass --force to regenerate")
        return

    log(f"{len(cases)} case(s) to generate")

    if args.dry_run:
        case = cases[0]
        log("\n=== system prompt ===\n" + narrative_rules.SYSTEM_PROMPT)
        log(f"\n=== user prompt for case {case['case_id']} (ecg {case['ecg_id']}) ===")
        log(
            narrative_rules.build_user_prompt(
                age=case["age"],
                sex=case["sex"],
                age_censored=case["age_censored"],
                diagnostic_labels=case["diagnostic_labels"],
                clinical_report=reports.get(case["ecg_id"]),
            )
        )
        log(f"\nno API call made. {len(cases)} case(s) would be generated with {args.model}.")
        return

    api_key = os.environ.get("CARDIO_LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "No API key. Set CARDIO_LLM_API_KEY (or ANTHROPIC_API_KEY) in the repository's\n"
            ".env, which is gitignored, and re-run."
        )

    # The endpoint is logged so a run is traceable to where it actually went.
    # The key never is.
    log(f"calling {args.base_url} as {args.model}")

    written = 0
    rejected = 0
    generated_at = datetime.now(UTC)

    def work(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        return case, generate_one(case, reports, api_key, args.model, args.base_url)

    with _connect(args.database_url) as conn:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for case, result in pool.map(work, cases):
                if result is None:
                    rejected += 1
                    continue
                from psycopg.types.json import Jsonb

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cases
                        SET narrative = %s, narrative_model = %s, narrative_generated_at = %s
                        WHERE id = %s
                        """,
                        (Jsonb(result), args.model, generated_at, case["case_id"]),
                    )
                # Committed one at a time. Batching was saving nothing and
                # meant that a stall discarded up to 25 narratives that had
                # already been paid for.
                conn.commit()
                written += 1
                if written % 10 == 0:
                    log(f"  {written} written")
        conn.commit()

    log(f"\nwritten {written}, rejected {rejected}")
    if rejected:
        log(
            f"{rejected} case(s) have no narrative. They stay in the review queue without one "
            "rather than with a vignette that gives the answer away."
        )


if __name__ == "__main__":
    main()
