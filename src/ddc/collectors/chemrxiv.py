"""ChemRxiv collector (Cambridge Open Engage public API).

Every ChemRxiv preprint is chemistry by definition; the classifier keeps only
the data-driven ones.
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

API = "https://chemrxiv.org/engage/chemrxiv/public-api/v1/items"
PAGE_SIZE = 50


@register
class ChemrxivCollector(Collector):
    name = "chemrxiv"
    label = "ChemRxiv"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        records: List[RawRecord] = []
        skip = 0
        while len(records) < limit:
            data = http.get_json(API, {
                "limit": PAGE_SIZE,
                "skip": skip,
                "sort": "PUBLISHED_DATE_DESC",
            })
            hits = data.get("itemHits") or []
            if not hits:
                break
            reached_old = False
            for hit in hits:
                item = hit.get("item") or {}
                published = (item.get("publishedDate") or "")[:10]
                if published and published < since.isoformat():
                    reached_old = True
                    break
                title = clean_text(item.get("title"))
                if not title:
                    continue
                authors = [
                    clean_text(f"{a.get('firstName', '')} {a.get('lastName', '')}")
                    for a in item.get("authors") or []
                ]
                item_id = item.get("id") or ""
                doi = item.get("doi") or ""
                url = (
                    f"https://chemrxiv.org/engage/chemrxiv/article-details/{item_id}"
                    if item_id else (f"https://doi.org/{doi}" if doi else "")
                )
                records.append(RawRecord(
                    title=title,
                    abstract=clean_text(item.get("abstract")),
                    authors=[a for a in authors if a],
                    journal="ChemRxiv",
                    publisher="Cambridge Open Engage",
                    doi=doi,
                    url=url,
                    published=published,
                    source=self.name,
                ))
            if reached_old:
                break
            skip += PAGE_SIZE
            time.sleep(0.5)  # politeness between pages
        return records
