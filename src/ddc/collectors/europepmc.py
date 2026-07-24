"""Europe PMC collector (https://europepmc.org/RestfulWebService).

Covers biomedical and life-science chemistry (PubMed content plus preprints
and Agricola), with full abstracts for classification.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import List

from .. import http
from ..models import RawRecord
from .base import Collector, clean_text, register

log = logging.getLogger(__name__)

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


@register
class EuropePmcCollector(Collector):
    name = "europepmc"
    label = "Europe PMC"

    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        query = (
            '(photocatalysis OR photocatalytic OR photocatalyst OR '
            'photoredox OR photoelectrochemical OR photodegradation) AND '
            f'FIRST_PDATE:[{since.isoformat()} TO {dt.date.today().isoformat()}]'
        )
        data = http.get_json(API, {
            "query": query,
            "format": "json",
            "resultType": "core",  # includes abstractText
            "pageSize": min(limit, 100),
            "sort": "P_PDATE_D desc",
        })
        records: List[RawRecord] = []
        for item in ((data.get("resultList") or {}).get("result")) or []:
            title = clean_text(item.get("title"))
            if not title:
                continue
            doi = item.get("doi") or ""
            if doi:
                url = f"https://doi.org/{doi}"
            else:
                url = f"https://europepmc.org/article/{item.get('source')}/{item.get('id')}"
            authors = [
                clean_text(a) for a in (item.get("authorString") or "").split(", ") if a
            ]
            records.append(RawRecord(
                title=title,
                abstract=clean_text(item.get("abstractText")),
                authors=authors,
                journal=clean_text(
                    ((item.get("journalInfo") or {}).get("journal") or {}).get("title")
                    or item.get("journalTitle")
                ),
                publisher="",
                doi=doi,
                url=url,
                published=(item.get("firstPublicationDate") or "")[:10],
                source=self.name,
            ))
        return records
