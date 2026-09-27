"""Stratified case selection, and the coverage report that comes with it.

Left alone, PTB-XL is 44% normal. Sampling it at random would give a case bank
that is mostly normal sinus rhythm, which teaches a student to answer "normal"
and be right most of the time. So the bank is stratified against the nursing
syllabus: each condition gets a target count, and selection draws up to that
target from the records that pass the quality gate.

The coverage report is the more important output. It states, per condition, how
many records exist, how many survive the quality gate, how many were drawn, and
why the rest were rejected. That table is what turns open decision 16.3 --
"which twenty conditions must be in the case bank?" -- from a wish into a choice
constrained by what the data contains, and it names the conditions PTB-XL
cannot supply at all rather than letting them go missing quietly.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from cardiosignal import conditions as cond
from cardiosignal.io import ptbxl


@dataclass
class ConditionCoverage:
    key: str
    label: str
    group: str
    target: int
    n_total: int = 0  # records carrying the code, before any filtering
    n_eligible: int = 0  # ...and passing the quality gate
    n_selected: int = 0
    available: bool = True
    note: str = ""
    rejections: Counter = field(default_factory=Counter)

    @property
    def shortfall(self) -> int:
        return max(0, self.target - self.n_selected)


@dataclass
class SelectionResult:
    candidates: pd.DataFrame
    coverage: list[ConditionCoverage]
    n_records_considered: int = 0
    n_passed_gate: int = 0
    global_rejections: Counter = field(default_factory=Counter)


def select(
    require_human_validation: bool = True,
    allow_noise: bool = False,
    seed: int = 20260809,
    targets: dict[str, int] | None = None,
) -> SelectionResult:
    """Draw a stratified candidate pool from PTB-XL's metadata alone.

    Runs entirely off the two CSVs, so it can be done before any waveform is
    downloaded -- which is the point, since it then tells the downloader exactly
    which few hundred records to fetch instead of the full 21 GB archive.
    """
    meta = ptbxl.load_metadata()
    coverage = {
        c.key: ConditionCoverage(c.key, c.label, c.group, targets.get(c.key, c.target) if targets else c.target,
                                 available=c.available, note=c.note)
        for c in cond.CONDITIONS
    }

    eligible_rows: dict[str, list[int]] = {c.key: [] for c in cond.AVAILABLE}
    global_rejections: Counter = Counter()
    n_passed = 0

    for ecg_id, row in meta.iterrows():
        codes = row["scp_codes"]
        keys = cond.conditions_for(codes)
        for key in keys:
            coverage[key].n_total += 1

        ok, reason = ptbxl.passes_quality_gate(row, require_human_validation, allow_noise)
        if not ok:
            global_rejections[reason] += 1
            for key in keys:
                coverage[key].rejections[reason] += 1
            continue

        n_passed += 1
        for key in keys:
            coverage[key].n_eligible += 1
            eligible_rows[key].append(int(ecg_id))

    # Draw per condition, scarcest first. A record that satisfies both a common
    # and a rare condition should be spent on the rare one -- there are 5,360
    # eligible normals and 8 eligible second-degree blocks, so drawing in the
    # other order would let the common conditions consume the rare records.
    by_scarcity = sorted(cond.AVAILABLE, key=lambda c: len(eligible_rows[c.key]))
    chosen: dict[int, list[str]] = {}
    for condition in by_scarcity:
        pool = eligible_rows[condition.key]
        target = coverage[condition.key].target
        if target <= 0 or not pool:
            continue
        series = pd.Series(pool)
        already = set(chosen)
        # Prefer records not already drawn, so the bank stays diverse.
        fresh = series[~series.isin(already)]
        take = fresh.sample(n=min(target, len(fresh)), random_state=seed).tolist()
        if len(take) < target:
            spare = series[series.isin(already)]
            take += spare.sample(
                n=min(target - len(take), len(spare)), random_state=seed
            ).tolist()
        for ecg_id in take:
            chosen.setdefault(ecg_id, []).append(condition.key)
        coverage[condition.key].n_selected = len(take)

    rows = []
    for ecg_id, keys in sorted(chosen.items()):
        row = meta.loc[ecg_id]
        rows.append(
            {
                "ecg_id": ecg_id,
                "syllabus_conditions": ";".join(sorted(keys)),
                "scp_codes": ";".join(row["scp_codes"].keys()),
                "age": row["age"],
                "sex": {0: "male", 1: "female"}.get(int(row["sex"])) if pd.notna(row["sex"]) else None,
                "report": row.get("report"),
                "strat_fold": row.get("strat_fold"),
                "filename_hr": row.get("filename_hr"),
            }
        )

    return SelectionResult(
        candidates=pd.DataFrame(rows),
        coverage=list(coverage.values()),
        n_records_considered=len(meta),
        n_passed_gate=n_passed,
        global_rejections=global_rejections,
    )


def format_coverage(result: SelectionResult) -> str:
    """The table to put in front of the nursing faculty."""
    lines = [
        "# PTB-XL condition coverage",
        "",
        f"Records in dataset: **{result.n_records_considered:,}**  ",
        f"Passing the quality gate: **{result.n_passed_gate:,}**  ",
        f"Candidates selected: **{len(result.candidates):,}**",
        "",
        "Rejections at the gate: "
        + ", ".join(f"{reason} {count:,}" for reason, count in result.global_rejections.most_common()),
        "",
        "| condition | group | in dataset | eligible | selected | target | shortfall |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for c in result.coverage:
        if not c.available:
            continue
        mark = "" if c.shortfall == 0 else f" **{c.shortfall}**"
        lines.append(
            f"| {c.label} | {c.group} | {c.n_total:,} | {c.n_eligible:,} | "
            f"{c.n_selected:,} | {c.target:,} |{mark or ' 0'} |"
        )

    unavailable = [c for c in result.coverage if not c.available]
    if unavailable:
        lines += [
            "",
            "## Not obtainable from PTB-XL",
            "",
            "These are on the brief's condition list and **cannot be sourced from this "
            "dataset**. Each needs a decision: drop it from the committed scope, or find "
            "a second source.",
            "",
            "| condition | why |",
            "|---|---|",
        ]
        lines += [f"| {c.label} | {c.note} |" for c in unavailable]

    scarce = [c for c in result.coverage if c.available and c.shortfall > 0]
    if scarce:
        lines += [
            "",
            "## Short of target",
            "",
            "Obtainable, but the dataset does not hold enough clean examples to reach the "
            "planned count. Either accept a thinner bank for these, or relax the quality "
            "gate for them specifically and mark the cases for closer review.",
            "",
            "| condition | selected | target | note |",
            "|---|---:|---:|---|",
        ]
        lines += [
            f"| {c.label} | {c.n_selected} | {c.target} | {c.note} |" for c in scarce
        ]
    return "\n".join(lines)


def write_outputs(result: SelectionResult, out_dir: Path, docs_dir: Path | None = None) -> tuple[Path, Path]:
    """Write the candidate list and the coverage report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = out_dir / "candidates.parquet"
    result.candidates.to_parquet(candidates_path, index=False)
    result.candidates.to_csv(out_dir / "candidates.csv", index=False)

    docs_dir = docs_dir or out_dir
    docs_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = docs_dir / "condition_coverage.md"
    coverage_path.write_text(format_coverage(result), encoding="utf-8")
    return candidates_path, coverage_path


__all__ = [
    "ConditionCoverage",
    "SelectionResult",
    "format_coverage",
    "select",
    "write_outputs",
]
