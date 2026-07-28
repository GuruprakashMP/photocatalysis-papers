"""One-off (but idempotent) migration: canonicalize stored author names.

Publisher metadata carries Unicode dashes and honorifics, so one researcher
fragments across several author pages — "Jun‐ichi Yoshida" (U+2010) held 113
papers while the ASCII spelling everyone types held 2. Ingestion now
normalizes via :func:`ddc.models.normalize_author`; this rewrites the papers
already on disk with the same rule.

Safe by construction:

* Paper ids and dedupe keys derive from DOI/title only, never from authors
  (see ``make_paper_id`` / ``dedupe_keys``), so ``data/state/seen.json`` is
  neither read nor written here and identity cannot shift.
* Idempotent — running it twice changes nothing the second time.
* Only shards whose content actually changes are rewritten, so the git diff
  stays proportional to the fix.
* Shard JSON is re-emitted with the exact formatting ``store.py`` uses.

Usage (from the project root, the folder containing ``src/``)::

    PYTHONPATH=src py tools/normalize_authors.py            # dry run, reports only
    PYTHONPATH=src py tools/normalize_authors.py --apply    # write changes
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc.models import normalize_author  # noqa: E402
from ddc.settings import PAPERS_DIR  # noqa: E402


def _dump(payload: object) -> str:
    """Match store._write_json exactly so untouched formatting stays stable."""
    return json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False)


def migrate(apply_changes: bool) -> int:
    if not PAPERS_DIR.exists():
        print(f"No papers directory at {PAPERS_DIR}")
        return 1

    shards_changed = 0
    shards_total = 0
    papers_changed = 0
    names_rewritten = 0
    dupes_collapsed = 0
    examples: Counter = Counter()
    failed_writes: list = []

    for shard in sorted(PAPERS_DIR.glob("*/*.json")):
        shards_total += 1
        try:
            original_text = shard.read_text(encoding="utf-8")
            papers = json.loads(original_text)
        except (OSError, ValueError) as exc:
            print(f"  !! skipping unreadable shard {shard}: {exc}")
            continue

        shard_dirty = False
        for paper in papers:
            authors = paper.get("authors") or []
            cleaned = []
            changed_here = False
            for name in authors:
                canon = normalize_author(name)
                if canon != name:
                    changed_here = True
                    names_rewritten += 1
                    examples[(name, canon)] += 1
                # A paper can list the same person twice once normalized
                # (e.g. both spellings credited); keep first occurrence.
                if canon and canon not in cleaned:
                    cleaned.append(canon)
            if len(cleaned) < len([n for n in authors if n]):
                dupes_collapsed += len([n for n in authors if n]) - len(cleaned)
                changed_here = True
            if changed_here:
                paper["authors"] = cleaned
                papers_changed += 1
                shard_dirty = True

        if shard_dirty:
            shards_changed += 1
            if apply_changes:
                new_text = _dump(papers)
                if new_text != original_text:
                    # Verify the write landed. OneDrive transiently locks
                    # files in this tree, and a silently dropped shard would
                    # leave the index half-migrated with no error.
                    for attempt in (1, 2, 3):
                        try:
                            shard.write_text(new_text, encoding="utf-8")
                            if shard.read_text(encoding="utf-8") == new_text:
                                break
                        except OSError as exc:
                            if attempt == 3:
                                print(f"  !! could not write {shard}: {exc}")
                                failed_writes.append(shard)
                                break
                            continue
                    else:
                        print(f"  !! write did not stick for {shard}")
                        failed_writes.append(shard)

    verb = "Rewrote" if apply_changes else "Would rewrite"
    print(f"{verb} {shards_changed:,} of {shards_total:,} shards")
    print(f"  papers touched      : {papers_changed:,}")
    print(f"  author names fixed  : {names_rewritten:,}")
    print(f"  in-paper duplicates : {dupes_collapsed:,}")
    if examples:
        print("  most common rewrites:")
        for (before, after), n in examples.most_common(8):
            print(f"    {n:6d}  {before!r} -> {after!r}")
    if failed_writes:
        print(f"\n!! {len(failed_writes)} shard(s) could not be written — "
              "re-run --apply to finish (the pass is idempotent):")
        for shard in failed_writes[:10]:
            print(f"     {shard}")
        return 1
    if not apply_changes and shards_changed:
        print("\nDry run. Re-run with --apply to write these changes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="write changes (default: dry run)")
    return migrate(parser.parse_args().apply)


if __name__ == "__main__":
    sys.exit(main())
