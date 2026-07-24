"""Daily pipeline orchestrator.

    collect -> deduplicate -> classify -> store -> generate site

Each source is isolated: a failing API is logged and skipped, never fatal.
:func:`process_records` is the shared ingestion path used by both the daily
run and the historical backfill (see :mod:`ddc.backfill`).
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Dict, List

from .classify import classify
from .collectors import enabled_collectors
from .models import Paper, RawRecord, dedupe_keys, make_paper_id, normalize_doi
from .settings import Settings
from .store import PaperStore

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    collected: int = 0
    duplicates: int = 0
    rejected: int = 0
    added: int = 0
    per_source: Dict[str, int] = field(default_factory=dict)

    def merge(self, other: "PipelineResult") -> None:
        self.collected += other.collected
        self.duplicates += other.duplicates
        self.rejected += other.rejected
        self.added += other.added
        for k, v in other.per_source.items():
            self.per_source[k] = self.per_source.get(k, 0) + v

    def summary(self) -> str:
        per_source = ", ".join(f"{k}: {v}" for k, v in sorted(self.per_source.items()))
        return (f"collected {self.collected} ({per_source}); "
                f"{self.duplicates} duplicates, {self.rejected} off-topic, "
                f"{self.added} added to index")


def _sane_date(published: str, today: str) -> str:
    """Guard against garbage dates from source APIs (e.g. year 2035).

    Journal issues are often dated a few months ahead, so allow up to one year
    in the future; anything beyond that (or unparseable) falls back to today.
    """
    try:
        year = int((published or "")[:4])
    except ValueError:
        return today
    if not published or not (1900 <= year <= int(today[:4]) + 1):
        return today
    return published


def collect_records(settings: Settings, since: dt.date) -> List[RawRecord]:
    """Query every enabled source, isolating failures per source."""
    records: List[RawRecord] = []
    for collector in enabled_collectors(settings.enabled_sources):
        try:
            found = collector.fetch(since, settings.max_results_per_source)
            log.info("%s: %d records", collector.name, len(found))
            records.extend(found)
        except Exception as exc:  # noqa: BLE001 — one source must never kill the run
            log.error("%s failed, continuing without it: %s", collector.name, exc)
    return records


def process_records(
    records: List[RawRecord],
    settings: Settings,
    store: PaperStore,
    seen: Dict[str, str],
) -> PipelineResult:
    """Dedupe, classify and store a batch of raw records.

    Mutates ``seen`` in place; the caller is responsible for persisting it
    (so a backfill can checkpoint between batches).
    """
    today = dt.date.today().isoformat()
    result = PipelineResult(collected=len(records))
    accepted: List[Paper] = []

    for record in records:
        keys = dedupe_keys(record.doi, record.title)
        if not keys:  # no DOI and a too-short title: cannot dedupe safely
            continue
        if any(k in seen for k in keys):
            result.duplicates += 1
            continue

        verdict = classify(record)
        if not verdict.accepted or verdict.score < settings.min_relevance_score:
            result.rejected += 1
            continue

        published = _sane_date(record.published, today)
        paper = Paper(
            id=make_paper_id(record.doi, record.title),
            title=record.title,
            authors=record.authors[:30],
            journal=record.journal,
            publisher=record.publisher,
            published=published,
            year=int(published[:4]),
            doi=normalize_doi(record.doi),
            url=record.url,
            source=record.source,
            categories=verdict.categories,
            tags=sorted(set(verdict.tags + record.extra_tags)),
            relevance_score=verdict.score,
            affiliations=record.affiliations,
            added=today,
        )
        for key in keys:
            seen[key] = paper.id
        accepted.append(paper)
        result.per_source[record.source] = result.per_source.get(record.source, 0) + 1

    result.added = store.add(accepted)
    return result


def run(days_back: int = 0, generate: bool = True) -> PipelineResult:
    """Execute the full daily pipeline and return a summary."""
    settings = Settings.load()
    since = dt.date.today() - dt.timedelta(
        days=days_back or settings.collect_days_back)
    log.info("Collecting papers published since %s", since.isoformat())

    records = collect_records(settings, since)

    store = PaperStore()
    seen = store.load_seen()
    result = process_records(records, settings, store, seen)
    store.save_seen(seen)
    log.info("Pipeline: %s", result.summary())

    if generate:
        from .site.generator import generate_site
        generate_site(settings)
    return result
