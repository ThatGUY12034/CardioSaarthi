"""Fetch the three PhysioNet datasets CardioSaarthi needs.

    PTB-XL  -- the case bank. Diagnoses are inherited from its cardiologist
               SCP-ECG annotations. Large (~21 GB at 500 Hz), so the default
               path is metadata-first: pull the two CSVs, run case selection
               against them, then fetch only the selected records.

    LUDB    -- answer key for delineation. 200 records, 12 leads, 500 Hz, with
               expert-marked onset/peak/offset for every P, QRS and T wave.
               This is what turns "the intervals look about right" into
               "P onset MAE is 9 ms". Small.

    QTDB    -- answer key for QT specifically. 105 records with manually
               annotated QT, the set the QT-measurement literature benchmarks
               against. Small.

Neither answer key ever enters the student case bank; they are used only by the
validation suite.

Usage
-----
    python scripts/download_data.py ludb
    python scripts/download_data.py qtdb
    python scripts/download_data.py ptbxl --metadata-only
    python scripts/download_data.py ptbxl --records-from artifacts/candidates.parquet
    python scripts/download_data.py ptbxl --all          # ~21 GB, asks first
    python scripts/download_data.py status
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import wfdb
from wfdb.io import download as wfdb_download

from cardiosignal.config import DATA_ROOT, LUDB_ROOT, PTBXL_ROOT, QTDB_ROOT

# PhysioNet database slugs. wfdb resolves the current version itself; passing
# "slug/version" would be interpreted as a *subdirectory* and 404. The version
# actually served is recorded in PROVENANCE.txt beside the data, and checked
# against the expectation below, so a silent upstream bump is visible rather
# than quietly changing what the validation report was computed against.
PTBXL_DB, PTBXL_EXPECTED_VERSION = "ptb-xl", "1.0.3"
LUDB_DB, LUDB_EXPECTED_VERSION = "ludb", "1.0.1"
QTDB_DB, QTDB_EXPECTED_VERSION = "qtdb", "1.0.0"

PTBXL_METADATA = ("ptbxl_database.csv", "scp_statements.csv")


def _record_provenance(db: str, expected: str, dest: Path) -> str:
    """Resolve and record the served version; warn loudly if it moved."""
    version = wfdb_download.get_version(db)
    if version != expected:
        print(
            f"  ! {db} is now version {version}, the code expects {expected}.\n"
            f"    Downloading {version}. Update the EXPECTED_VERSION constant and\n"
            f"    re-run the validation report before quoting any accuracy figure."
        )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "PROVENANCE.txt").write_text(
        f"physionet database: {db}\nversion served: {version}\nversion expected: {expected}\n",
        encoding="utf-8",
    )
    return version


def _fetch_files(db: str, dest: Path, files: list[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    missing = [f for f in files if not (dest / f).exists()]
    if not missing:
        print(f"  all {len(files)} file(s) already present")
        return
    print(f"  fetching {len(missing)} of {len(files)} file(s) from {db}")
    wfdb.dl_files(db, str(dest), missing, keep_subdirs=True, overwrite=False)


def download_ptbxl_metadata() -> None:
    """The two CSVs (a few MB). Everything about case selection runs off these."""
    print("PTB-XL metadata ->", PTBXL_ROOT)
    _record_provenance(PTBXL_DB, PTBXL_EXPECTED_VERSION, PTBXL_ROOT)
    _fetch_files(PTBXL_DB, PTBXL_ROOT, list(PTBXL_METADATA))


def download_ptbxl_records(ecg_ids: list[int], sampling_rate: int = 500) -> None:
    """Fetch only the given records. `filename_hr` in the CSV gives the path."""
    import pandas as pd

    db_csv = PTBXL_ROOT / "ptbxl_database.csv"
    if not db_csv.exists():
        download_ptbxl_metadata()

    df = pd.read_csv(db_csv, index_col="ecg_id")
    column = "filename_hr" if sampling_rate == 500 else "filename_lr"
    unknown = [e for e in ecg_ids if e not in df.index]
    if unknown:
        raise SystemExit(f"unknown ecg_id(s): {unknown[:10]}")

    stems = df.loc[ecg_ids, column].tolist()
    files = [f"{stem}{ext}" for stem in stems for ext in (".hea", ".dat")]
    print(f"PTB-XL: {len(ecg_ids)} record(s) at {sampling_rate} Hz -> {PTBXL_ROOT}")
    _fetch_files(PTBXL_DB, PTBXL_ROOT, files)


def download_ptbxl_all(sampling_rate: int = 500, assume_yes: bool = False) -> None:
    size = "~21 GB" if sampling_rate == 500 else "~2 GB"
    if not assume_yes:
        reply = input(f"Download the entire PTB-XL archive ({size})? [y/N] ").strip().lower()
        if reply != "y":
            print("aborted — consider --metadata-only then --records-from")
            return
    print(f"PTB-XL full archive at {sampling_rate} Hz -> {PTBXL_ROOT}")
    _record_provenance(PTBXL_DB, PTBXL_EXPECTED_VERSION, PTBXL_ROOT)
    wfdb.dl_database(PTBXL_DB, str(PTBXL_ROOT), keep_subdirs=True, overwrite=False)


def _parallel_fetch(base_url: str, dest: Path, rel_paths: list[str], workers: int = 12,
                    optional: bool = False) -> tuple[int, int]:
    """Download many small files concurrently.

    `wfdb.dl_database` walks every record's header before writing a single byte,
    which for LUDB's 200 records and 2,800 files means a very long silence
    followed by a serial download. These datasets are thousands of tiny files,
    so latency dominates entirely and a modest thread pool turns tens of minutes
    into under a minute.

    `optional=True` tolerates 404s, which is how the QT Database's uneven
    annotator coverage is handled -- not every record carries every extension.
    """
    from concurrent.futures import ThreadPoolExecutor

    import requests
    from tqdm import tqdm

    session = requests.Session()
    session.headers["User-Agent"] = "cardiosignal/0.1 (academic use)"
    done = failed = 0

    def fetch(rel: str) -> bool:
        target = dest / rel
        if target.exists() and target.stat().st_size > 0:
            return True
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = session.get(f"{base_url}/{rel}", timeout=60)
            if response.status_code == 404 and optional:
                return True
            response.raise_for_status()
        except Exception:
            return False
        target.write_bytes(response.content)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for ok in tqdm(pool.map(fetch, rel_paths), total=len(rel_paths), unit="file"):
            if ok:
                done += 1
            else:
                failed += 1

    print(f"  {done} ok, {failed} failed")
    return done, failed


# LUDB ships one annotation file per lead: expert-marked onset, peak and offset
# for every P, QRS and T wave. These twelve extensions are the dataset's point.
LUDB_ANNOTATORS = ("i", "ii", "iii", "avr", "avl", "avf", "v1", "v2", "v3", "v4", "v5", "v6")
# QTDB extensions vary by record; .q1c is the manual cardiologist annotation the
# QT literature benchmarks against, the rest are fetched opportunistically.
QTDB_ANNOTATORS = ("q1c", "q2c", "qt1", "qt2", "man", "atr", "pu0", "pu1")


def download_ludb() -> None:
    print("LUDB ->", LUDB_ROOT)
    version = _record_provenance(LUDB_DB, LUDB_EXPECTED_VERSION, LUDB_ROOT)
    base = f"https://physionet.org/files/{LUDB_DB}/{version}"
    records = wfdb.get_record_list(LUDB_DB)  # e.g. ['data/1', 'data/2', ...]
    files = [f"{r}{ext}" for r in records for ext in (".hea", ".dat")]
    files += [f"{r}.{ann}" for r in records for ann in LUDB_ANNOTATORS]
    files += ["ludb.csv", "RECORDS", "ANNOTATORS"]
    print(f"  {len(records)} records, {len(files)} files")
    _parallel_fetch(base, LUDB_ROOT, files, optional=True)


def download_qtdb() -> None:
    print("QT Database ->", QTDB_ROOT)
    version = _record_provenance(QTDB_DB, QTDB_EXPECTED_VERSION, QTDB_ROOT)
    base = f"https://physionet.org/files/{QTDB_DB}/{version}"
    records = wfdb.get_record_list(QTDB_DB)
    files = [f"{r}{ext}" for r in records for ext in (".hea", ".dat")]
    files += [f"{r}.{ann}" for r in records for ann in QTDB_ANNOTATORS]
    files += ["RECORDS", "ANNOTATORS"]
    print(f"  {len(records)} records, {len(files)} files")
    _parallel_fetch(base, QTDB_ROOT, files, optional=True)


def _dir_summary(root: Path, label: str) -> None:
    if not root.exists():
        print(f"  {label:<8} not downloaded")
        return
    files = list(root.rglob("*"))
    n = sum(1 for f in files if f.is_file())
    mb = sum(f.stat().st_size for f in files if f.is_file()) / 1e6
    print(f"  {label:<8} {n:>6} files  {mb:>9.1f} MB  {root}")


def status() -> None:
    print(f"data root: {DATA_ROOT}")
    _dir_summary(PTBXL_ROOT, "ptbxl")
    _dir_summary(LUDB_ROOT, "ludb")
    _dir_summary(QTDB_ROOT, "qtdb")


def _read_ecg_ids(path: Path) -> list[int]:
    import pandas as pd

    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise SystemExit(f"expected .parquet or .csv, got {path.suffix}")
    if "ecg_id" not in df.columns:
        raise SystemExit(f"{path} has no 'ecg_id' column")
    return sorted({int(v) for v in df["ecg_id"]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="dataset", required=True)

    p = sub.add_parser("ptbxl", help="case bank")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--metadata-only", action="store_true", help="just the two CSVs")
    group.add_argument("--records-from", type=Path, help="parquet/csv with an ecg_id column")
    group.add_argument("--all", action="store_true", help="entire archive")
    p.add_argument("--sampling-rate", type=int, default=500, choices=(100, 500))
    p.add_argument("--yes", action="store_true", help="skip the size confirmation")

    sub.add_parser("ludb", help="delineation answer key")
    sub.add_parser("qtdb", help="QT answer key")
    sub.add_parser("status", help="what is already downloaded")

    args = parser.parse_args()

    if args.dataset == "ptbxl":
        if args.metadata_only:
            download_ptbxl_metadata()
        elif args.records_from:
            download_ptbxl_records(_read_ecg_ids(args.records_from), args.sampling_rate)
        else:
            download_ptbxl_all(args.sampling_rate, assume_yes=args.yes)
    elif args.dataset == "ludb":
        download_ludb()
    elif args.dataset == "qtdb":
        download_qtdb()
    else:
        status()


if __name__ == "__main__":
    main()
