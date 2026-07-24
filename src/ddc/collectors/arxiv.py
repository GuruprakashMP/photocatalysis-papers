"""arXiv collector (Atom API, https://info.arxiv.org/help/api/).

Fetches recent submissions in chemistry-adjacent categories plus ML-category
papers that mention chemistry, and lets the downstream classifier decide.
"""

from __future__ import annotations

import datetime as dt
import logging
import xml.etree.ElementTree as ET
from typing import List

from .. import http
from ..models import RawRecord
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

API = "http://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

QUERIES = (
    "all:photocatalytic",
    "all:photocatalysis",
    'abs:"photoelectrochemical water splitting" OR abs:"photoredox catalysis"',
)


@register
class ArxivCollector(Collector):
    name = "arxiv"
    label = "arXiv"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        records: List[RawRecord] = []
        per_query = max(25, limit // len(QUERIES))
        for query in QUERIES:
            try:
                body = http.get_text(API, {
                    "search_query": query,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": per_query,
                })
                records.extend(self._parse(body, since))
            except http.FetchError as exc:
                log.warning("arXiv query failed (%s): %s", query, exc)
        return records

    def _parse(self, body: str, since: dt.date) -> List[RawRecord]:
        records: List[RawRecord] = []
        root = ET.fromstring(body)
        for entry in root.findall("atom:entry", NS):
            published = (entry.findtext("atom:published", "", NS) or "")[:10]
            if published and published < since.isoformat():
                continue
            title = clean_text(entry.findtext("atom:title", "", NS))
            if not title:
                continue
            abs_url = entry.findtext("atom:id", "", NS) or ""
            doi = entry.findtext("arxiv:doi", "", NS) or ""
            journal_ref = clean_text(entry.findtext("arxiv:journal_ref", "", NS))
            authors = [
                clean_text(a.findtext("atom:name", "", NS))
                for a in entry.findall("atom:author", NS)
            ]
            records.append(RawRecord(
                title=title,
                abstract=clean_text(entry.findtext("atom:summary", "", NS)),
                authors=[a for a in authors if a],
                journal=journal_ref or "arXiv",
                publisher="arXiv",
                doi=doi,
                url=abs_url,
                published=published,
                source=self.name,
            ))
        return records
