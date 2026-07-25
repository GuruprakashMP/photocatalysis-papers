"""Historical backfill — index the whole history of ML applied to chemistry.

Walks OpenAlex (which aggregates Crossref, PubMed, arXiv and more, with
abstracts for classification) using cursor pagination:

* **Topic sweep**: a set of broad ML×chemistry search queries, one year at a
  time, oldest publications to newest.
* **Pioneer sweep**: the complete publication lists of the researchers named
  in ``config/pioneers.json`` (their papers still pass the same classifier).

Progress is checkpointed after every query: papers are flushed to the monthly
shards and the seen-set is saved, so an interrupted backfill can simply be
re-run and will skip everything already ingested.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterator, List, Optional

from . import http
from .collectors.openalex import work_to_record
from .models import RawRecord
from .pipeline import PipelineResult, process_records
from .settings import PROJECT_ROOT, Settings
from .store import PaperStore

log = logging.getLogger(__name__)

API = "https://api.openalex.org/works"
PER_PAGE = 200
REQUEST_PAUSE = 1.0  # gentle pacing; OpenAlex enforces a daily quota
PIONEERS_FILE = PROJECT_ROOT / "config" / "pioneers.json"
# Abort the whole backfill after this many consecutive failed queries —
# it means the API quota is exhausted and hammering on is pointless.
MAX_CONSECUTIVE_FAILURES = 12

# Fields we actually read — trimming the payload makes paging ~5x faster.
SELECT = ("id,display_name,authorships,primary_location,doi,"
          "publication_date,abstract_inverted_index")

# Broad-recall queries; precision comes from the classifier, not the query.
TOPIC_QUERIES = (
    "photocatalysis",
    "photocatalytic",
    "photocatalytic degradation",
    "photocatalytic hydrogen",
    "photocatalytic co2 reduction",
    "photoredox",
    "photoelectrochemical water splitting",
    '"z-scheme"',
    '"g-c3n4"',
    '"carbon nitride" photocatalytic',
    "tio2 photocatalytic",
    '"artificial photosynthesis"',
    '"solar fuel"',
    "photoanode",
    "plasmonic photocatalysis",
    "photocatalyst visible light",
    # early-era terminology (pre-dates the word "photocatalysis")
    '"photolysis of water"',
    "photoelectrolysis",
    # modern photoredox / LMCT synthesis, which often never says "photocatal…"
    '"visible light mediated"',
    '"ligand to metal charge transfer"',
    "photocatalyst",
    "organophotocatalyst",
    '"eosin y"',
)


class QuotaExhausted(Exception):
    """The API is persistently refusing requests (e.g. daily quota hit)."""


def _paged_works(
    filter_expr: str,
    max_pages: int,
    mailto: Optional[str],
) -> Iterator[List[dict]]:
    """Yield successive pages of OpenAlex works for a filter expression."""
    cursor = "*"
    for _ in range(max_pages):
        data = http.get_json(API, {
            "filter": filter_expr,
            "per-page": PER_PAGE,
            "cursor": cursor,
            "select": SELECT,
            "mailto": mailto or None,
        })
        results = data.get("results") or []
        if results:
            yield results
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor or len(results) < PER_PAGE:
            return
        time.sleep(REQUEST_PAUSE)


def _ingest_pages(
    filter_expr: str,
    label: str,
    max_pages: int,
    settings: Settings,
    store: PaperStore,
    seen: dict,
    source: str,
    failures: List[int],
) -> PipelineResult:
    """Fetch all pages for one filter and ingest them, with checkpointing.

    ``failures`` is a single-element counter of consecutive failed queries,
    shared across the sweep; sustained failure raises :class:`QuotaExhausted`.
    """
    total = PipelineResult()
    try:
        for page in _paged_works(filter_expr, max_pages, settings.contact_email):
            records: List[RawRecord] = []
            for work in page:
                record = work_to_record(work, source)
                if record:
                    records.append(record)
            total.merge(process_records(records, settings, store, seen))
        failures[0] = 0
    except http.FetchError as exc:
        failures[0] += 1
        log.warning("OpenAlex query failed (%s): %s [consecutive failures: %d]",
                    label, exc, failures[0])
        if failures[0] >= MAX_CONSECUTIVE_FAILURES:
            raise QuotaExhausted(
                f"{failures[0]} consecutive failed queries — API quota "
                "exhausted; re-run the backfill later to resume") from exc
    store.save_seen(seen)  # checkpoint: re-running skips everything ingested
    if total.collected:
        log.info("%-45s %5d fetched, %4d added, %4d dup, %4d off-topic",
                 label, total.collected, total.added, total.duplicates,
                 total.rejected)
    return total


def load_pioneers() -> List[str]:
    try:
        data = json.loads(PIONEERS_FILE.read_text(encoding="utf-8"))
        return [a for a in data.get("authors", []) if isinstance(a, str)]
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s (%s); skipping pioneer sweep",
                    PIONEERS_FILE, exc)
        return []


def backfill(
    from_year: int,
    to_year: int,
    max_pages: int = 10,
    topics: bool = True,
    authors: bool = True,
    generate: bool = True,
) -> PipelineResult:
    """Run the historical backfill and (optionally) rebuild the site."""
    settings = Settings.load()
    store = PaperStore()
    seen = store.load_seen()
    grand = PipelineResult()
    failures = [0]  # consecutive failed queries, shared across the sweep

    try:
        if authors:
            # Pioneers first: a bounded, high-value sweep that should never be
            # starved by the (much larger) topic sweep hitting the quota.
            pioneers = load_pioneers()
            log.info("Pioneer sweep: %d researchers", len(pioneers))
            for name in pioneers:
                filter_expr = f'raw_author_name.search:"{name}"'
                result = _ingest_pages(
                    filter_expr, f"author [{name}]", max_pages,
                    settings, store, seen, source="openalex", failures=failures)
                grand.merge(result)
                time.sleep(REQUEST_PAUSE)

        if topics:
            log.info("Topic sweep %d-%d (%d queries/year, <=%d pages each)",
                     from_year, to_year, len(TOPIC_QUERIES), max_pages)
            for year in range(to_year, from_year - 1, -1):
                year_total = PipelineResult()
                for query in TOPIC_QUERIES:
                    filter_expr = (
                        f"from_publication_date:{year}-01-01,"
                        f"to_publication_date:{year}-12-31,"
                        f"title_and_abstract.search:{query}"
                    )
                    result = _ingest_pages(
                        filter_expr, f"{year} [{query}]", max_pages,
                        settings, store, seen, source="openalex",
                        failures=failures)
                    year_total.merge(result)
                    time.sleep(REQUEST_PAUSE)
                grand.merge(year_total)
                log.info("=== %d done: %d papers added (running total %d) ===",
                         year, year_total.added, grand.added)
    except QuotaExhausted as exc:
        log.error("Backfill stopped early: %s", exc)

    log.info("Backfill finished: %s", grand.summary())
    if generate:
        from .site.generator import generate_site
        generate_site(settings)
    return grand
