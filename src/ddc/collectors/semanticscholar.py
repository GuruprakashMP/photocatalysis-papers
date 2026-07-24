"""Semantic Scholar collector (Graph API).

The public (keyless) tier is heavily rate-limited; 429 responses are treated
as a soft skip so the rest of the pipeline is never blocked.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import List

from .. import http
from ..models import RawRecord
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = ("title,abstract,venue,year,publicationDate,authors,"
          "externalIds,url,journal")

QUERIES = (
    "photocatalysis",
    "photocatalytic hydrogen evolution",
    "photoredox catalysis",
)


@register
class SemanticScholarCollector(Collector):
    name = "semanticscholar"
    label = "Semantic Scholar"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        records: List[RawRecord] = []
        per_query = max(20, limit // len(QUERIES))
        for query in QUERIES:
            try:
                data = http.get_json(API, {
                    "query": query,
                    "fields": FIELDS,
                    "limit": min(per_query, 100),
                    # open-ended range: papers published on/after `since`
                    "publicationDateOrYear": f"{since.isoformat()}:",
                })
            except http.FetchError as exc:
                log.warning("Semantic Scholar unavailable (%s); skipping: %s",
                            query, exc)
                continue
            for item in data.get("data") or []:
                record = self._to_record(item)
                if record:
                    records.append(record)
            time.sleep(1.5)  # keyless tier is ~1 request/second
        return records

    def _to_record(self, item: dict) -> RawRecord:
        title = clean_text(item.get("title"))
        if not title:
            return None  # type: ignore[return-value]
        external = item.get("externalIds") or {}
        doi = external.get("DOI") or ""
        journal_info = item.get("journal") or {}
        journal = clean_text(journal_info.get("name") or item.get("venue"))
        return RawRecord(
            title=title,
            abstract=clean_text(item.get("abstract")),
            authors=[clean_text(a.get("name")) for a in item.get("authors") or []
                     if a.get("name")],
            journal=journal,
            doi=doi,
            url=(f"https://doi.org/{doi}" if doi else item.get("url") or ""),
            published=(item.get("publicationDate") or "")[:10],
            source=self.name,
        )
