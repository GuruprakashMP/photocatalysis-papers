"""Project settings and filesystem layout.

All paths are derived from the project root (the ``ddc_papers`` folder) so the
project is fully self-contained and relocatable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

# src/ddc/settings.py -> project root is two levels above src/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "settings.json"
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"
STATE_DIR = DATA_DIR / "state"
SITE_DIR = PROJECT_ROOT  # generated pages live at the project root
ASSETS_SRC_DIR = Path(__file__).resolve().parent / "site" / "assets"


@dataclass
class Settings:
    site_title: str = "PhotocatalysisPapers"
    site_tagline: str = ""
    site_base_url: str = ""
    contact_email: str = ""
    min_relevance_score: int = 40
    collect_days_back: int = 3
    max_results_per_source: int = 200
    homepage_paper_count: int = 50
    enabled_sources: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "Settings":
        """Load settings from JSON, falling back to defaults on any problem."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Could not read %s (%s); using defaults", path, exc)
            return cls()
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
