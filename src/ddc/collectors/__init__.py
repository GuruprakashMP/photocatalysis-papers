"""Collector package — importing it registers every built-in collector.

Adding a new source is a one-file change: drop a module here containing a
``@register``-decorated :class:`~ddc.collectors.base.Collector` subclass and
import it below, then (optionally) enable it in ``config/settings.json``.
"""

from __future__ import annotations

from typing import Dict, List, Type

from .base import Collector, register, registry  # noqa: F401

# Import for side effect: each module registers its collector class.
from . import arxiv  # noqa: F401
from . import chemrxiv  # noqa: F401
from . import crossref  # noqa: F401
from . import doaj  # noqa: F401
from . import europepmc  # noqa: F401
from . import openalex  # noqa: F401
from . import pubmed  # noqa: F401
from . import semanticscholar  # noqa: F401


def enabled_collectors(enabled_names: List[str]) -> List[Collector]:
    """Instantiate the collectors named in the settings, preserving order."""
    available: Dict[str, Type[Collector]] = registry()
    collectors: List[Collector] = []
    for name in enabled_names:
        cls = available.get(name)
        if cls is None:
            import logging
            logging.getLogger(__name__).warning(
                "Unknown source '%s' in settings; available: %s",
                name, ", ".join(sorted(available)))
            continue
        collectors.append(cls())
    return collectors
