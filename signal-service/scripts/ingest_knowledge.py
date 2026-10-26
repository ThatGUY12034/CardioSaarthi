"""Build the tutor's candidate corpus from openly licensed sources.

Nothing here decides what a student sees. Every paragraph lands as `pending`
and stays invisible until a named reviewer approves it, exactly as a measured
case does. The point of this script is to spare faculty the writing, not the
judgement.

Sources, and why these
----------------------
* **Wikipedia** (CC BY-SA 4.0) via the public REST API. Unambiguous licence,
  broad coverage of the nine concepts, and the API is the documented way to
  read it rather than scraping the rendered page.
* **PubMed Central Open Access subset** (CC BY and CC BY-NC variants) via the
  NCBI E-utilities. Peer reviewed and properly citable, which matters for a
  report that already cites the same literature.

Deliberately excluded: StatPearls and anything else under a no-derivatives
licence. Splitting an article into retrievable paragraphs is arguably a
derivative work, and a corpus whose licence is arguable is one that has to be
unpicked later.

Run with --dry-run first to see what would be imported.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import psycopg

# A real contact address is what the NCBI and Wikimedia terms of use ask for.
USER_AGENT = (
    "CardioSaarthi/1.0 (Terna Engineering College major project; "
    "educational use; contact via project repository)"
)

MIN_CHUNK = 80
MAX_CHUNK = 4000

# The nine concepts, and the search terms that find material about each. A
# concept with no obvious article is left to the free-text search instead.
WIKIPEDIA_TOPICS: list[tuple[str | None, str]] = [
    ("rate", "Heart rate"),
    ("rhythm", "Sinus rhythm"),
    ("rhythm", "Atrial fibrillation"),
    ("rhythm", "Cardiac arrhythmia"),
    ("axis", "QRS axis"),
    ("axis", "Electrical axis"),
    ("axis", "Right axis deviation"),
    ("axis", "Left axis deviation"),
    ("p_waves", "P wave (electrocardiography)"),
    ("p_waves", "Atrial enlargement"),
    ("pr_interval", "PR interval"),
    ("pr_interval", "Atrioventricular block"),
    ("qrs", "QRS complex"),
    ("qrs", "Bundle branch block"),
    ("st_segment", "ST segment"),
    ("st_segment", "ST elevation"),
    ("t_waves", "T wave"),
    ("qt_interval", "QT interval"),
    ("qt_interval", "Long QT syndrome"),
    (None, "Electrocardiography"),
    (None, "Einthoven's triangle"),
]

PMC_QUERIES: list[tuple[str | None, str]] = [
    ("rhythm", "electrocardiogram rhythm interpretation education"),
    ("st_segment", "ST segment deviation measurement electrocardiography"),
    ("qt_interval", "QT interval measurement correction methods"),
    (None, "electrocardiogram interpretation teaching undergraduate"),
]


@dataclass
class Source:
    title: str
    publisher: str
    url: str
    licence: str
    licence_url: str | None
    attribution: str


@dataclass
class Chunk:
    concept: str | None
    heading: str | None
    body: str


def fetch(url: str, *, retries: int = 3) -> bytes:
    """One GET, politely. Rate limited because both APIs ask for it."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as exception:  # noqa: BLE001 - retried, then reported
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
            print(f"    retrying ({exception.__class__.__name__})", file=sys.stderr)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text)          # citation markers
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def split_into_chunks(plain: str, concept: str | None) -> list[Chunk]:
    """Section by section, so a retrieved paragraph keeps its heading."""
    chunks: list[Chunk] = []
    heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = clean(" ".join(buffer))
        if MIN_CHUNK <= len(body) <= MAX_CHUNK:
            chunks.append(Chunk(concept, heading, body))
        elif len(body) > MAX_CHUNK:
            # Long sections split on sentence boundaries rather than mid-word.
            sentences = re.split(r"(?<=[.!?]) +", body)
            current = ""
            for sentence in sentences:
                if len(current) + len(sentence) + 1 > MAX_CHUNK:
                    if len(current) >= MIN_CHUNK:
                        chunks.append(Chunk(concept, heading, current.strip()))
                    current = sentence
                else:
                    current = f"{current} {sentence}".strip()
            if len(current) >= MIN_CHUNK:
                chunks.append(Chunk(concept, heading, current.strip()))

    for line in plain.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # The REST extract marks sections with == Heading ==
        match = re.fullmatch(r"=+\s*(.+?)\s*=+", stripped)
        if match:
            flush()
            buffer = []
            heading = match.group(1)
            # Sections that are never teaching content.
            if heading.lower() in {"references", "external links", "see also",
                                   "further reading", "notes", "bibliography"}:
                heading = None
                buffer = []
                break
            continue
        buffer.append(stripped)
    flush()
    return chunks


def from_wikipedia(concept: str | None, title: str) -> tuple[Source, list[Chunk]] | None:
    api = ("https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
           "&explaintext=1&format=json&redirects=1&titles=" + urllib.parse.quote(title))
    import json

    data = json.loads(fetch(api))
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    if not page or "extract" not in page or page.get("missing") is not None:
        print(f"    no article for {title!r}", file=sys.stderr)
        return None

    resolved = page.get("title", title)
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(resolved.replace(" ", "_"))
    source = Source(
        title=resolved,
        publisher="Wikipedia, the free encyclopedia",
        url=url,
        licence="CC BY-SA 4.0",
        licence_url="https://creativecommons.org/licenses/by-sa/4.0/",
        attribution=f'"{resolved}", Wikipedia, licensed CC BY-SA 4.0. Source: {url}',
    )
    return source, split_into_chunks(page["extract"], concept)


# ---------------------------------------------------------------------------
# PubMed Central Open Access subset
# ---------------------------------------------------------------------------
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Detected from the licence URL, which is the machine-readable part of the
# record, with the prose as a fallback. PMC writes "Creative Commons
# Attribution 4.0 International License" and never the string "CC BY", so
# matching on the short form found nothing at all.
LICENCE_URL = re.compile(r"creativecommons\.org/licenses/(by(?:-nc)?(?:-sa)?)/", re.I)
LICENCE_PROSE = re.compile(
    r"creative commons attribution(?!\s+[\w-]*no\s*deriv)", re.I)
# "No derivatives", however it is spelled. Matching the bare letters ND would
# fire on "under" and on "and", which is how the first version of this check
# rejected every article it was given.
NO_DERIVATIVES = re.compile(r"(/by[\w-]*-nd/)|(no\s*deriv)", re.I)


def from_pmc(concept: str | None, query: str, limit: int = 2) -> list[tuple[Source, list[Chunk]]]:
    search = (f"{EUTILS}/esearch.fcgi?db=pmc&retmode=json&retmax={limit}"
              f"&term={urllib.parse.quote(query + ' AND open access[filter]')}")
    import json

    ids = json.loads(fetch(search)).get("esearchresult", {}).get("idlist", [])
    results: list[tuple[Source, list[Chunk]]] = []

    for pmcid in ids:
        time.sleep(0.4)                                  # NCBI asks for <3 req/s
        xml = fetch(f"{EUTILS}/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml")
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            continue

        licence_text = " ".join(
            "".join(node.itertext()) for node in root.iter()
            if node.tag.endswith("license")
        )
        # Also sweep the href attributes: the licence URL often lives there
        # rather than in the element's text.
        licence_text += " " + " ".join(
            value for node in root.iter() for key, value in node.attrib.items()
            if "href" in key and "creativecommons" in value
        )

        if NO_DERIVATIVES.search(licence_text):
            print(f"    PMC{pmcid}: no-derivatives licence, skipped", file=sys.stderr)
            continue

        url_match = LICENCE_URL.search(licence_text)
        if url_match:
            licence = "CC " + url_match.group(1).upper().replace("-", "-")
        elif LICENCE_PROSE.search(licence_text):
            licence = "CC BY"
        else:
            # An article whose licence cannot be read off the record is skipped
            # rather than guessed at.
            print(f"    PMC{pmcid}: licence not clearly open, skipped", file=sys.stderr)
            continue

        title_node = next((n for n in root.iter() if n.tag.endswith("article-title")), None)
        title = "".join(title_node.itertext()).strip() if title_node is not None else f"PMC{pmcid}"
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/"
        source = Source(
            title=title[:300],
            publisher="PubMed Central Open Access subset",
            url=url,
            licence=licence,
            licence_url=None,
            attribution=f'"{title[:200]}", PubMed Central PMC{pmcid}, licensed {licence}. Source: {url}',
        )

        chunks: list[Chunk] = []
        for sec in root.iter():
            if not sec.tag.endswith("sec"):
                continue
            head = next((n for n in sec if n.tag.endswith("title")), None)
            heading = "".join(head.itertext()).strip() if head is not None else None
            body = clean(" ".join(
                "".join(p.itertext()) for p in sec if p.tag.endswith("p")
            ))
            if MIN_CHUNK <= len(body) <= MAX_CHUNK:
                chunks.append(Chunk(concept, heading, body))
        if chunks:
            results.append((source, chunks))
    return results


# ---------------------------------------------------------------------------
# Storing
# ---------------------------------------------------------------------------
def store(connection, source: Source, chunks: list[Chunk], dry_run: bool) -> int:
    if dry_run:
        print(f"  [dry run] {source.title}: {len(chunks)} chunks ({source.licence})")
        return 0
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge_sources (title, publisher, url, licence, licence_url, attribution)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET retrieved_at = now()
            RETURNING id
            """,
            (source.title, source.publisher, source.url, source.licence,
             source.licence_url, source.attribution),
        )
        source_id = cur.fetchone()[0]

        stored = 0
        for chunk in chunks:
            # Re-running must not duplicate the corpus, and must never resurrect
            # a paragraph a reviewer has already rejected.
            cur.execute(
                "SELECT 1 FROM knowledge_chunks WHERE source_id = %s AND body = %s",
                (source_id, chunk.body),
            )
            if cur.fetchone():
                continue
            cur.execute(
                """
                INSERT INTO knowledge_chunks (source_id, concept, heading, body)
                VALUES (%s, %s, %s, %s)
                """,
                (source_id, chunk.concept, chunk.heading, chunk.body),
            )
            stored += 1
    return stored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and report, write nothing")
    parser.add_argument("--skip-pmc", action="store_true",
                        help="Wikipedia only; PMC fetches are slower")
    args = parser.parse_args()

    url = os.environ.get("CARDIO_DATABASE_URL")
    if not url and not args.dry_run:
        print("CARDIO_DATABASE_URL is not set", file=sys.stderr)
        return 2

    connection = None if args.dry_run else psycopg.connect(url, connect_timeout=10)
    total = 0
    try:
        print("Wikipedia (CC BY-SA 4.0)")
        for concept, title in WIKIPEDIA_TOPICS:
            print(f"  {title}")
            try:
                found = from_wikipedia(concept, title)
            except Exception as exception:  # noqa: BLE001
                print(f"    failed: {exception}", file=sys.stderr)
                continue
            if found:
                total += store(connection, *found, dry_run=args.dry_run)
            time.sleep(1.1)

        if not args.skip_pmc:
            print("PubMed Central Open Access subset")
            for concept, query in PMC_QUERIES:
                print(f"  {query}")
                try:
                    for source, chunks in from_pmc(concept, query):
                        total += store(connection, source, chunks, dry_run=args.dry_run)
                except Exception as exception:  # noqa: BLE001
                    print(f"    failed: {exception}", file=sys.stderr)

        if connection:
            connection.commit()
    finally:
        if connection:
            connection.close()

    print(f"\n{total} new chunks imported, all pending review.")
    print("Nothing is retrievable by the tutor until a reviewer approves it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
