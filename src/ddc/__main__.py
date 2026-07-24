"""Command-line interface.

Run from the project root (the folder containing ``src/``):

    python -m ddc run              # full daily pipeline (collect + build site)
    python -m ddc run --days 7     # look further back
    python -m ddc collect          # collect only, no site build
    python -m ddc build            # rebuild the site from stored data only
    python -m ddc stats            # print index statistics

(Requires ``src`` on the path: ``python -m ddc`` works when invoked as
``PYTHONPATH=src python -m ddc ...`` or via the provided wrapper.)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from .settings import Settings, setup_logging


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ddc", description="DataDrivenChemistryPapers pipeline")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="collect new papers and rebuild the site")
    p_run.add_argument("--days", type=int, default=0,
                       help="days to look back (default: settings value)")

    p_collect = sub.add_parser("collect", help="collect and store, skip site build")
    p_collect.add_argument("--days", type=int, default=0)

    p_back = sub.add_parser(
        "backfill", help="one-time historical harvest via OpenAlex")
    p_back.add_argument("--from", dest="from_year", type=int, default=1972)
    p_back.add_argument("--to", dest="to_year", type=int, default=0,
                        help="default: current year")
    p_back.add_argument("--max-pages", type=int, default=10,
                        help="max pages (of 200) per query per year")
    p_back.add_argument("--topics-only", action="store_true")
    p_back.add_argument("--authors-only", action="store_true")
    p_back.add_argument("--no-site", action="store_true",
                        help="skip site rebuild at the end")

    sub.add_parser("build", help="rebuild the website from stored data")
    sub.add_parser("stats", help="print index statistics")

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.command in ("run", "collect"):
        from .pipeline import run
        result = run(days_back=args.days, generate=args.command == "run")
        print(result.summary())
        return 0

    if args.command == "backfill":
        import datetime as dt
        from .backfill import backfill
        result = backfill(
            from_year=args.from_year,
            to_year=args.to_year or dt.date.today().year,
            max_pages=args.max_pages,
            topics=not args.authors_only,
            authors=not args.topics_only,
            generate=not args.no_site,
        )
        print(result.summary())
        return 0

    if args.command == "build":
        from .site.generator import generate_site
        generate_site(Settings.load())
        print("Site rebuilt.")
        return 0

    if args.command == "stats":
        from .store import PaperStore
        papers = PaperStore().load_all()
        print(f"Papers indexed : {len(papers):,}")
        if papers:
            years = Counter(p.year for p in papers)
            sources = Counter(p.source for p in papers)
            print(f"Journals       : {len({p.journal for p in papers if p.journal}):,}")
            print(f"Authors        : {len({a for p in papers for a in p.authors}):,}")
            print("By year        : " + ", ".join(
                f"{y}: {n}" for y, n in sorted(years.items(), reverse=True)))
            print("By source      : " + ", ".join(
                f"{s}: {n}" for s, n in sources.most_common()))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
