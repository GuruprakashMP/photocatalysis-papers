"""Collector contract.

A collector knows how to query ONE metadata source and return
:class:`~ddc.models.RawRecord` objects.  It performs no filtering beyond what
the source API needs — classification and deduplication happen downstream in
the pipeline, so every collector stays small and independent.

To add a new source: create a module in this package with a subclass of
:class:`Collector` and decorate it with :func:`register`.  Nothing else in the
project needs to change.
"""

from __future__ import annotations

import abc
import datetime as dt
import logging
from typing import Dict, List, Type

from ..models import RawRecord

log = logging.getLogger(__name__)

_REGISTRY: Dict[str, Type["Collector"]] = {}


def register(cls: Type["Collector"]) -> Type["Collector"]:
    """Class decorator: make a collector discoverable by its ``name``."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name'")
    _REGISTRY[cls.name] = cls
    return cls


def registry() -> Dict[str, Type["Collector"]]:
    return dict(_REGISTRY)


class Collector(abc.ABC):
    """Base class for all metadata collectors."""

    #: unique machine name, e.g. "arxiv" — used in config and paper records
    name: str = ""
    #: human-readable label shown on the website's About page
    label: str = ""

    @abc.abstractmethod
    def fetch(self, since: dt.date, limit: int) -> List[RawRecord]:
        """Return records published/indexed on or after ``since``.

        Implementations should raise :class:`ddc.http.FetchError` (or let it
        propagate) on hard failures; the pipeline isolates each source so one
        failing API never blocks the others.
        """


def clean_text(value: object) -> str:
    """Collapse whitespace and strip markup-ish artifacts from API strings."""
    if not value:
        return ""
    import html
    import re
    # decode entities first (&lt;sup&gt; -> <sup>) so tag removal catches them
    text = html.unescape(str(value))
    # crude but dependency-free tag removal (JATS/HTML abstracts)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
