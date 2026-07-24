"""PubMed collector (NCBI E-utilities).

Two-step flow: ESearch finds recent PMIDs matching ML+chemistry terms, then a
single EFetch call retrieves their metadata as XML.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
import xml.etree.ElementTree as ET
from typing import List

from .. import http
from ..models import RawRecord
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

TERM = (
    'photocatalysis[tiab] OR photocatalytic[tiab] OR photocatalyst[tiab] '
    'OR photoredox[tiab] OR photoelectrochemical[tiab] OR '
    'photodegradation[tiab]'
)


@register
class PubmedCollector(Collector):
    name = "pubmed"
    label = "PubMed"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        days_back = max(1, (dt.date.today() - since).days)
        search = http.get_json(ESEARCH, {
            "db": "pubmed",
            "term": TERM,
            "reldate": days_back,
            "datetype": "edat",
            "retmax": min(limit, 200),
            "retmode": "json",
        })
        ids = ((search.get("esearchresult") or {}).get("idlist")) or []
        if not ids:
            return []
        time.sleep(0.4)  # NCBI rate limit: max 3 requests/second
        body = http.get_text(EFETCH, {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        })
        return self._parse(body)

    def _parse(self, body: str) -> List[RawRecord]:
        records: List[RawRecord] = []
        root = ET.fromstring(body)
        for article in root.findall(".//PubmedArticle"):
            citation = article.find("MedlineCitation")
            if citation is None:
                continue
            art = citation.find("Article")
            if art is None:
                continue
            title_node = art.find("ArticleTitle")
            title = clean_text(
                ET.tostring(title_node, encoding="unicode", method="text")
            ) if title_node is not None else ""
            if not title:
                continue
            abstract = " ".join(
                clean_text(ET.tostring(t, encoding="unicode", method="text"))
                for t in art.findall(".//AbstractText")
            )
            authors = []
            for author in art.findall(".//Author"):
                fore = author.findtext("ForeName") or ""
                last = author.findtext("LastName") or ""
                name = clean_text(f"{fore} {last}")
                if name:
                    authors.append(name)
            journal = clean_text(art.findtext("Journal/Title"))
            doi = ""
            for eloc in art.findall("ELocationID"):
                if eloc.get("EIdType") == "doi":
                    doi = clean_text(eloc.text)
            pmid = citation.findtext("PMID") or ""
            url = f"https://doi.org/{doi}" if doi else (
                f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            records.append(RawRecord(
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                doi=doi,
                url=url,
                published=_article_date(art),
                source=self.name,
            ))
        return records


def _article_date(art: ET.Element) -> str:
    node = art.find("ArticleDate")
    if node is None:
        node = art.find("Journal/JournalIssue/PubDate")
    if node is None:
        return ""
    year = node.findtext("Year")
    if not year or not year.isdigit():
        return ""
    month = _month_number(node.findtext("Month") or "1")
    day = node.findtext("Day") or "1"
    try:
        return dt.date(int(year), month, int(day)).isoformat()
    except ValueError:
        return f"{year}-01-01"


def _month_number(value: str) -> int:
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    value = value.strip().lower()
    if value.isdigit():
        return max(1, min(12, int(value)))
    return months.get(value[:3], 1)
