"""Core data model.

A :class:`Paper` holds *metadata only* — never full text or abstracts — so the
project stays free of copyright concerns.  Abstracts fetched from APIs are used
transiently for classification and are discarded before storage.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

_DOI_PREFIX_RE = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)\s*", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Dash-like codepoints publishers substitute for an ASCII hyphen-minus:
# U+2010..U+2015 (hyphen…horizontal bar), U+2212 (minus), U+FE58/U+FE63
# (small forms) and U+FF0D (fullwidth). Crossref/Wiley metadata routinely
# carries U+2010, which silently splits "Jun‐ichi Yoshida" from the ASCII
# spelling everyone actually types.
_DASH_RE = re.compile("[‐-―−﹘﹣－]")
_ZERO_WIDTH_RE = re.compile("[​‌‍﻿]")
# Leading titles. Applied repeatedly so "Prof. Dr. X" fully unwraps.
_HONORIFIC_RE = re.compile(
    r"^(?:prof(?:essor)?|dr|doctor|mr|mrs|ms|miss|sir|dame|rev)\.?\s+",
    re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def normalize_author(name: Optional[str]) -> str:
    """Canonical form of an author display name.

    Mechanical only — it fixes encoding and formatting noise so the *same*
    person stops fragmenting across author pages, and never tries to decide
    that two differently-spelled names are the same human:

    * Unicode dashes -> ASCII "-"  ("Jun‐ichi" -> "Jun-ichi")
    * NFC, non-breaking/zero-width space cleanup, whitespace collapsed
    * leading honorifics dropped   ("Prof. Dr. C. Oliver Kappe" -> "C. Oliver Kappe")

    Deliberately NOT done: merging initials with full given names
    ("J. Yoshida" vs "Jun-ichi Yoshida") or removing a hyphen entirely
    ("Junichi" vs "Jun-ichi"). Those are judgement calls that would silently
    fuse distinct researchers — surnames like "Li", "Hu" and "Wu" appear as
    complete names in this data, so any surname-collapsing rule is unsafe.

    A trailing period is preserved: 1,339 stored names legitimately end in an
    initial ("Jain, K. K."), and trimming it would corrupt them.
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFC", str(name))
    text = text.replace(" ", " ")
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _DASH_RE.sub("-", text)
    text = _SPACE_RE.sub(" ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _HONORIFIC_RE.sub("", text).strip()
        text = text.lstrip(".,; ").strip()
    text = text.rstrip(",; ").strip()
    # Never let cleanup delete a name outright (e.g. a bare "DR" record).
    return text or _SPACE_RE.sub(" ", str(name)).strip()


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
