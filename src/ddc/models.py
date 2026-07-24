"""Core data model.

A :class:`Paper` holds *metadata only* — never full text or abstracts — so the
project stays free of copyright concerns.  Abstracts fetched from APIs are used
transiently for classification and are discarded before storage.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

_DOI_PREFIX_RE = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)\s*", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_doi(doi: Optional[str]) -> str:
    """Return a canonical lowercase DOI without URL prefixes, or ''."""
    if not doi:
        return ""
    doi = _DOI_PREFIX_RE.sub("", doi.strip()).strip().lower()
    return doi if doi.startswith("10.") else ""


def normalize_title(title: str) -> str:
    """Lowercased alphanumeric-only form of a title, for fuzzy dedup keys."""
    return _NON_ALNUM_RE.sub("", title.lower())


@dataclass
class RawRecord:
    """A paper as returned by a collector, before filtering/classification.

    ``abstract`` is transient: it is consulted by the classifier and never
    written to disk.
    """

    title: str
    source: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    journal: str = ""
    publisher: str = ""
    doi: str = ""
    url: str = ""
    published: str = ""  # ISO date YYYY-MM-DD (may be YYYY-MM or YYYY)
    affiliations: List[str] = field(default_factory=list)
    extra_tags: List[str] = field(default_factory=list)


@dataclass
class Paper:
    """A stored paper record.  Only bibliographic metadata — no content."""

    id: str
    title: str
    authors: List[str]
    journal: str
    publisher: str
    published: str  # ISO date
    year: int
    doi: str
    url: str
    source: str
    categories: List[str]
    tags: List[str]
    relevance_score: int
    affiliations: List[str] = field(default_factory=list)
    added: str = ""  # ISO date the record entered the index

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Paper":
        known = {f: d.get(f) for f in cls.__dataclass_fields__ if f in d}
        return cls(**known)  # type: ignore[arg-type]


def make_paper_id(doi: str, title: str) -> str:
    """Stable short identifier derived from the DOI (preferred) or title."""
    basis = normalize_doi(doi) or normalize_title(title)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def dedupe_keys(doi: str, title: str) -> List[str]:
    """All keys under which a paper is registered in the seen-set.

    A DOI key catches exact re-encounters across sources; a title key catches
    the same work carrying different identifiers (e.g. preprint vs journal).
    """
    keys: List[str] = []
    ndoi = normalize_doi(doi)
    if ndoi:
        keys.append("doi:" + ndoi)
    ntitle = normalize_title(title)
    if len(ntitle) >= 25:  # short titles are too collision-prone to key on
        keys.append("title:" + hashlib.sha1(ntitle.encode("utf-8")).hexdigest())
    return keys
