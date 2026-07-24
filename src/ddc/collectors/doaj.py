"""DOAJ collector (Directory of Open Access Journals, https://doaj.org/api/).

Covers open-access journals (MDPI, Frontiers, and thousands more).
"""

from __future__ import annotations

import datetime as dt
import logging
import urllib.parse
from typing import List

from .. import http
from ..models import RawRecord
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

API = "https://doaj.org/api/search/articles/"

QUERY = 'photocatalysis OR photocatalytic OR photoredox'


@register
class DoajCollector(Collector):
    name = "doaj"
    label = "DOAJ"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        url = API + urllib.parse.quote(QUERY, safe="")
        data = http.get_json(url, {
            "pageSize": min(limit, 100),
            "sort": "created_date:desc",
        })
        records: List[RawRecord] = []
        for result in data.get("results") or []:
            bib = result.get("bibjson") or {}
            title = clean_text(bib.get("title"))
            if not title:
                continue
            published = _published_date(bib)
            if published and published < since.isoformat():
                continue
            doi, url_link = "", ""
            for ident in bib.get("identifier") or []:
                if ident.get("type", "").lower() == "doi":
                    doi = ident.get("id") or ""
            for link in bib.get("link") or []:
                if link.get("url"):
                    url_link = link["url"]
                    break
            journal_info = bib.get("journal") or {}
            records.append(RawRecord(
                title=title,
                abstract=clean_text(bib.get("abstract")),
                authors=[clean_text(a.get("name")) for a in bib.get("author") or []
                         if a.get("name")],
                journal=clean_text(journal_info.get("title")),
                publisher=clean_text(journal_info.get("publisher")),
                doi=doi,
                url=(f"https://doi.org/{doi}" if doi else url_link),
                published=published,
                source=self.name,
            ))
        return records


def _published_date(bib: dict) -> str:
    year = str(bib.get("year") or "").strip()
    if not year.isdigit():
        return ""
    month = str(bib.get("month") or "1").strip()
    month_num = int(month) if month.isdigit() and 1 <= int(month) <= 12 else 1
    return f"{int(year):04d}-{month_num:02d}-01"
