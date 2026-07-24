"""Crossref collector (https://api.crossref.org).

Crossref carries the metadata of essentially every DOI-issuing publisher —
ACS, RSC, Wiley, Springer Nature, Elsevier, MDPI, Taylor & Francis, IOP, AIP
and more — so this single collector legally covers all of them.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import List

from .. import http
from ..models import RawRecord
from ..settings import Settings
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

API = "https://api.crossref.org/works"

QUERIES = (
    "photocatalysis",
    "photocatalytic degradation",
    "photocatalytic hydrogen evolution",
    "photoredox catalysis",
    "photoelectrochemical water splitting",
)


@register
class CrossrefCollector(Collector):
    name = "crossref"
    label = "Crossref (ACS, RSC, Wiley, Springer Nature, Elsevier, ...)"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        contact = Settings.load().contact_email
        rows = max(20, limit // len(QUERIES))
        records: List[RawRecord] = []
        for query in QUERIES:
            try:
                data = http.get_json(API, {
                    "query.bibliographic": query,
                    "filter": f"from-index-date:{since.isoformat()},type:journal-article",
                    "rows": rows,
                    "sort": "indexed",
                    "order": "desc",
                    "select": "DOI,title,author,container-title,publisher,"
                              "issued,created,URL,abstract",
                    "mailto": contact or None,
                })
            except http.FetchError as exc:
                log.warning("Crossref query failed (%s): %s", query, exc)
                continue
            for item in (data.get("message") or {}).get("items") or []:
                record = self._to_record(item)
                if record:
                    records.append(record)
            time.sleep(1.0)  # Crossref politeness
        return records

    def _to_record(self, item: dict) -> RawRecord:
        titles = item.get("title") or []
        title = clean_text(titles[0]) if titles else ""
        if not title:
            return None  # type: ignore[return-value]
        authors = []
        for a in item.get("author") or []:
            name = clean_text(f"{a.get('given', '')} {a.get('family', '')}")
            if name:
                authors.append(name)
        containers = item.get("container-title") or []
        doi = item.get("DOI") or ""
        return RawRecord(
            title=title,
            abstract=clean_text(item.get("abstract")),
            authors=authors,
            journal=clean_text(containers[0]) if containers else "",
            publisher=clean_text(item.get("publisher")),
            doi=doi,
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
            published=_issued_date(item),
            source=self.name,
        )


def _issued_date(item: dict) -> str:
    for key in ("issued", "created"):
        parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
        if parts and parts[0]:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
            try:
                return dt.date(year, month, day).isoformat()
            except ValueError:
                continue
    return ""
