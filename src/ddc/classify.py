"""Relevance classification.

Implements the project's core filtering rule: a paper is indexed only when
*photocatalysis is its primary subject* — any methodology (experimental,
computational/DFT, machine learning) qualifies, but neighbouring fields such
as photovoltaics, LEDs or photodynamic therapy are rejected.

The classifier only ever sees text transiently (title + abstract); the
abstract is never stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .keywords import CHEM_VENUE_HINTS, NEGATIVE_TERMS, PRIMARY_TERMS, SUPPORT_TERMS
from .models import RawRecord

# Scoring shape: base + 4*primary + 3*support, capped at 100.  The caps keep
# a paper with many weak matches from outscoring one with strong evidence.
_BASE = 20
_PRIMARY_CAP = 10
_SUPPORT_CAP = 12
_VENUE_BONUS = 6
_TITLE_BONUS = 1  # extra point when a term appears in the title

# Minimum evidence that photocatalysis is the primary subject: one
# unambiguous term ("photocatal…", "photoredox", "z-scheme"...) suffices;
# weak circumstantial matches alone do not.
_MIN_PRIMARY_POINTS = 4


def _compile(vocab: Dict[str, object]) -> List[Tuple[re.Pattern, str]]:
    """Compile phrases to word-boundary patterns allowing suffixes.

    "photocatal" matches "photocatalysis" / "photocatalytic" /
    "photocatalyst(s)".
    """
    compiled = []
    for phrase in vocab:
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\w*", re.IGNORECASE)
        compiled.append((pattern, phrase))
    return compiled


_PRIMARY_PATTERNS = _compile(PRIMARY_TERMS)
_SUPPORT_PATTERNS = _compile(SUPPORT_TERMS)
_NEG_PATTERNS = _compile(NEGATIVE_TERMS)


@dataclass
class Classification:
    accepted: bool
    score: int
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    reason: str = ""


def _match_side(
    patterns: List[Tuple[re.Pattern, str]],
    vocab: Dict[str, Tuple[int, str, str]],
    title: str,
    text: str,
) -> Tuple[int, Dict[str, int], Dict[str, int]]:
    """Score one vocabulary side.

    Returns (points, tag_points, category_points).  Multiple phrases mapping
    to the same tag (spelling variants) count once, at their best weight.
    """
    tag_points: Dict[str, int] = {}
    category_points: Dict[str, int] = {}
    for pattern, phrase in patterns:
        if not pattern.search(text):
            continue
        weight, tag, category = vocab[phrase]
        if pattern.search(title):
            weight += _TITLE_BONUS
        if weight > tag_points.get(tag, 0):
            tag_points[tag] = weight
        category_points[category] = max(category_points.get(category, 0), weight)
    return sum(tag_points.values()), tag_points, category_points


def classify(record: RawRecord) -> Classification:
    """Score a raw record and derive its categories and tags."""
    title = record.title or ""
    text = f"{title}\n{record.abstract or ''}"
    if not title.strip():
        return Classification(False, 0, reason="empty title")

    prim_pts, prim_tags, prim_cats = _match_side(
        _PRIMARY_PATTERNS, PRIMARY_TERMS, title, text)
    sup_pts, sup_tags, sup_cats = _match_side(
        _SUPPORT_PATTERNS, SUPPORT_TERMS, title, text)

    if prim_pts < _MIN_PRIMARY_POINTS:
        return Classification(False, 0, reason="no photocatalysis evidence")

    journal_lower = (record.journal or "").lower()
    venue_is_relevant = any(h in journal_lower for h in CHEM_VENUE_HINTS)

    penalty = 0
    for pattern, phrase in _NEG_PATTERNS:
        if pattern.search(text):
            p = NEGATIVE_TERMS[phrase]
            if pattern.search(title):
                p *= 2  # off-domain signal in the title is strong evidence
            penalty += p

    score = (_BASE + 4 * min(prim_pts, _PRIMARY_CAP)
             + 3 * min(sup_pts, _SUPPORT_CAP))
    if venue_is_relevant:
        score += _VENUE_BONUS
    score -= penalty
    score = max(0, min(100, score))

    # Categories/tags ordered by evidence strength; primary side first so a
    # paper reads as "photocatalysis topic + supporting details".
    categories = _ranked(prim_cats) + [c for c in _ranked(sup_cats)
                                       if c not in prim_cats]
    tags = _ranked(prim_tags) + [t for t in _ranked(sup_tags)
                                 if t not in prim_tags]

    # Drop the generic umbrella category when specific ones exist.
    if "General Photocatalysis" in categories and len(categories) > 1:
        categories.remove("General Photocatalysis")

    return Classification(
        accepted=True,
        score=score,
        categories=categories[:8],
        tags=tags[:12],
    )


def _ranked(points: Dict[str, int]) -> List[str]:
    return [k for k, _ in sorted(points.items(), key=lambda kv: (-kv[1], kv[0]))]
