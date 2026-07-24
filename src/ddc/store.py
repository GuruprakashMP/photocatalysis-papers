"""JSON storage — no database, perfect for GitHub Pages.

Papers are sharded into monthly files ``data/papers/<YYYY>/<MM>.json`` so the
repository diff each day stays small and files never grow unbounded.  A
``data/state/seen.json`` file records every DOI/title key ever indexed, which
makes deduplication across days and sources O(1).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from .models import Paper, dedupe_keys
from .settings import PAPERS_DIR, STATE_DIR

log = logging.getLogger(__name__)

SEEN_FILE = STATE_DIR / "seen.json"


def _month_file(year: int, month: int) -> Path:
    return PAPERS_DIR / f"{year:04d}" / f"{month:02d}.json"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False),
        encoding="utf-8",
    )


class PaperStore:
    """Reads and writes the monthly paper shards and the seen-key state."""

    def load_all(self) -> List[Paper]:
        """Every stored paper, newest first."""
        papers: List[Paper] = []
        if not PAPERS_DIR.exists():
            return papers
        for shard in sorted(PAPERS_DIR.glob("*/*.json")):
            try:
                raw = json.loads(shard.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log.error("Skipping unreadable shard %s: %s", shard, exc)
                continue
            papers.extend(Paper.from_dict(d) for d in raw)
        papers.sort(key=lambda p: (p.published or "", p.id), reverse=True)
        return papers

    def add(self, new_papers: Iterable[Paper]) -> int:
        """Append papers to their monthly shards.  Returns the count added."""
        by_month: Dict[Path, List[Paper]] = defaultdict(list)
        for paper in new_papers:
            year, month = _parse_year_month(paper.published, paper.year)
            by_month[_month_file(year, month)].append(paper)

        added = 0
        for shard, papers in by_month.items():
            existing: List[dict] = []
            if shard.exists():
                try:
                    existing = json.loads(shard.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    log.error("Shard %s unreadable (%s); refusing to overwrite", shard, exc)
                    continue
            existing_ids = {d.get("id") for d in existing}
            fresh = [p.to_dict() for p in papers if p.id not in existing_ids]
            if not fresh:
                continue
            merged = existing + fresh
            merged.sort(key=lambda d: (d.get("published") or "", d.get("id")), reverse=True)
            _write_json(shard, merged)
            added += len(fresh)
        return added

    # -- seen-key state ------------------------------------------------------

    def load_seen(self) -> Dict[str, str]:
        if not SEEN_FILE.exists():
            return {}
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.error("seen.json unreadable (%s); rebuilding from shards", exc)
            return self.rebuild_seen()

    def save_seen(self, seen: Dict[str, str]) -> None:
        _write_json(SEEN_FILE, seen)

    def rebuild_seen(self) -> Dict[str, str]:
        """Reconstruct the seen-set from stored papers (recovery path)."""
        seen: Dict[str, str] = {}
        for paper in self.load_all():
            for key in dedupe_keys(paper.doi, paper.title):
                seen[key] = paper.id
        return seen


def _parse_year_month(published: str, fallback_year: int) -> tuple:
    parts = (published or "").split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        if 1900 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    except (ValueError, IndexError):
        pass
    return (fallback_year if 1900 <= fallback_year <= 2100 else 1900), 1
