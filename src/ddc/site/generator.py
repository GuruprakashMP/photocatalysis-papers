"""Generate the static website from the JSON paper store.

Output layout (all inside the project root, so the folder can be dropped into
any GitHub Pages repository):

    index.html                 homepage — newest papers, stats
    search.html                client-side search & filters (app.js)
    authors.html               client-side author directory / author pages
    journals.html              client-side journal directory / journal pages
    about.html                 project description, sources, data policy
    categories/index.html      category directory with counts
    archive/index.html         year list
    archive/<YYYY>/index.html  month list
    archive/<YYYY>/<MM>/index.html  papers of that month grouped by day
    assets/style.css, app.js   static assets (copied from the package)
    assets/data/manifest.json  shard manifest for the client-side pages
    assets/data/papers-<YYYY>.json  one compact shard per publication year
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from ..models import Paper
from ..settings import ASSETS_SRC_DIR, SITE_DIR, Settings
from ..store import PaperStore
from .html import esc, month_name, page, paper_card

log = logging.getLogger(__name__)


def generate_site(settings: Settings, out_dir: Path = SITE_DIR) -> None:
    papers = PaperStore().load_all()
    log.info("Generating site for %d papers -> %s", len(papers), out_dir)

    _clean_generated(out_dir)
    _copy_assets(out_dir)
    _write_data_shards(papers, out_dir)

    ctx = dict(site_title=settings.site_title, tagline=settings.site_tagline)

    _write(out_dir / "index.html",
           _homepage(papers, settings, ctx))
    _write(out_dir / "search.html",
           _js_page("Search", "search", ctx, depth=0))
    _write(out_dir / "authors.html",
           _js_page("Authors", "authors", ctx, depth=0))
    _write(out_dir / "journals.html",
           _js_page("Journals", "journals", ctx, depth=0))
    _write(out_dir / "about.html", _about_page(papers, settings, ctx))
    _write(out_dir / "categories" / "index.html", _categories_page(papers, ctx))
    _write_archive(papers, out_dir, ctx)
    log.info("Site generation complete")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clean_generated(out_dir: Path) -> None:
    """Remove fully regenerated output so stale pages never linger.

    Only touches directories the generator owns completely (archive tree and
    the JSON data shards) — never source code or stored data.
    """
    archive = out_dir / "archive"
    if archive.exists():
        _rmtree_robust(archive)
    data_dir = out_dir / "assets" / "data"
    if data_dir.exists():
        for stale in data_dir.glob("*.json"):
            stale.unlink()


def _rmtree_robust(path: Path) -> None:
    """rmtree that survives transient locks (OneDrive/antivirus on Windows).

    Falls back to deleting files individually; an empty leftover directory is
    harmless because every page below it is regenerated or removed.
    """
    import time
    for attempt in range(3):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            time.sleep(0.5 * (attempt + 1))
    for file in sorted(path.rglob("*"), reverse=True):
        try:
            if file.is_file():
                file.unlink()
            else:
                file.rmdir()
        except OSError:
            log.warning("Could not remove %s (locked); continuing", file)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_assets(out_dir: Path) -> None:
    dest = out_dir / "assets"
    dest.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS_SRC_DIR.glob("*"):
        if asset.is_file():
            shutil.copy2(asset, dest / asset.name)


def _write_data_shards(papers: List[Paper], out_dir: Path) -> None:
    """Compact per-year JSON consumed by app.js (client-side pages)."""
    data_dir = out_dir / "assets" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    by_year: Dict[int, List[dict]] = defaultdict(list)
    for p in papers:
        by_year[p.year].append({
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "journal": p.journal,
            "publisher": p.publisher,
            "published": p.published,
            "doi": p.doi,
            "url": p.url,
            "source": p.source,
            "categories": p.categories,
            "tags": p.tags,
            "score": p.relevance_score,
            "affiliations": p.affiliations,
        })
    years = []
    for year, items in sorted(by_year.items(), reverse=True):
        filename = f"papers-{year}.json"
        (data_dir / filename).write_text(
            json.dumps(items, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        years.append({"year": year, "count": len(items), "file": filename})
    manifest = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total": len(papers),
        "years": years,
    }
    (data_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def _homepage(papers: List[Paper], settings: Settings, ctx: dict) -> str:
    latest = papers[: settings.homepage_paper_count]
    cards = "\n".join(paper_card(p) for p in latest)
    content = f"""
<section>
  <h1>Latest papers</h1>
  {cards if cards else '<p class="empty">No papers indexed yet — the first pipeline run will populate this page.</p>'}
  <p class="more"><a class="btn btn-primary" href="search.html">Browse &amp; search all {len(papers):,} papers →</a></p>
</section>"""
    return page(title=ctx["site_title"], content=content, depth=0,
                active="index.html", **ctx)


def _js_page(title: str, page_kind: str, ctx: dict, depth: int) -> str:
    prefix = "../" * depth
    content = f"""
<div id="app" data-page="{page_kind}" data-root="{prefix}">
  <noscript><p>This page needs JavaScript to filter the paper index.
  Use the <a href="{prefix}archive/index.html">archive</a> for a static view.</p></noscript>
  <p class="loading">Loading paper index…</p>
</div>"""
    head = f'<script defer src="{prefix}assets/app.js"></script>'
    active = {"search": "search.html", "authors": "authors.html",
              "journals": "journals.html"}.get(page_kind, "")
    return page(title=f"{title} · {ctx['site_title']}", content=content,
                depth=depth, active=active, head_extra=head, **ctx)


def _categories_page(papers: List[Paper], ctx: dict) -> str:
    counts = Counter(cat for p in papers for cat in p.categories)
    items = "\n".join(
        f'<li><a href="../search.html?category={esc(cat)}">{esc(cat)}</a>'
        f'<span class="count">{count:,}</span></li>'
        for cat, count in sorted(counts.items()))  # alphabetical for findability
    content = f"""
<h1>Categories</h1>
<p>Every paper belongs to several categories — a chemistry field and the
data-driven methods it uses. Click one to browse.</p>
<ul class="tile-list">{items or '<li>No categories yet.</li>'}</ul>"""
    return page(title=f"Categories · {ctx['site_title']}", content=content,
                depth=1, active="categories/index.html", **ctx)


def _about_page(papers: List[Paper], settings: Settings, ctx: dict) -> str:
    from ..collectors import registry
    sources = "\n".join(
        f"<li><strong>{esc(cls.label)}</strong> (<code>{esc(name)}</code>)</li>"
        for name, cls in sorted(registry().items()))
    content = f"""
<h1>About</h1>
<p><strong>{esc(ctx['site_title'])}</strong> is an automatically updated index of
photocatalysis research papers — water splitting, hydrogen evolution, CO2
photoreduction, pollutant degradation, photoredox and organic synthesis,
semiconductor photocatalysts, Z-scheme systems, photoelectrochemistry and
solar fuels — covering experimental, computational and data-driven studies
alike.</p>
<h2>How it works</h2>
<p>Every day an automated pipeline queries open scholarly metadata APIs,
removes duplicates, classifies each paper with a chemistry-and-ML relevance
model, assigns categories and a relevance score, and regenerates this site.</p>
<h2>Sources</h2>
<ul>{sources}</ul>
<p>Papers from publishers such as ACS, RSC, Wiley, Springer Nature, Elsevier,
MDPI, Frontiers, Taylor &amp; Francis, IOP and AIP reach this index through
Crossref, OpenAlex, PubMed, Europe PMC, Semantic Scholar and DOAJ, which
legally distribute their bibliographic metadata.</p>
<h2>Data policy</h2>
<p>This site stores <em>metadata only</em>: title, authors, journal, date, DOI
and link. No abstracts, no full text, no PDFs. Every paper links to the
original publisher page. To have a record corrected or removed, contact
<a href="mailto:{esc(settings.contact_email)}">{esc(settings.contact_email)}</a>.</p>
<p class="stats"><span><strong>{len(papers):,}</strong> papers indexed so far.</span></p>"""
    return page(title=f"About · {ctx['site_title']}", content=content,
                depth=0, active="about.html", **ctx)


def _write_archive(papers: List[Paper], out_dir: Path, ctx: dict) -> None:
    by_year: Dict[int, Dict[int, List[Paper]]] = defaultdict(lambda: defaultdict(list))
    for p in papers:
        parts = (p.published or "").split("-")
        month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        by_year[p.year][month].append(p)

    # archive root: years
    year_items = "\n".join(
        f'<li><a href="{y}/index.html">{y}</a>'
        f'<span class="count">{sum(len(v) for v in months.values()):,}</span></li>'
        for y, months in sorted(by_year.items(), reverse=True))
    content = f"""
<h1>Archive</h1>
<p>Browse the index by publication date: year → month → day.</p>
<ul class="tile-list">{year_items or '<li>Empty archive.</li>'}</ul>"""
    _write(out_dir / "archive" / "index.html",
           page(title=f"Archive · {ctx['site_title']}", content=content,
                depth=1, active="archive/index.html", **ctx))

    for year, months in by_year.items():
        month_items = "\n".join(
            f'<li><a href="{m:02d}/index.html">{esc(month_name(m))}</a>'
            f'<span class="count">{len(month_papers):,}</span></li>'
            for m, month_papers in sorted(months.items(), reverse=True))
        content = f"""
<h1>{year}</h1>
<p><a href="../index.html">← All years</a></p>
<ul class="tile-list">{month_items}</ul>"""
        _write(out_dir / "archive" / str(year) / "index.html",
               page(title=f"{year} · {ctx['site_title']}", content=content,
                    depth=2, active="archive/index.html", **ctx))

        for m, month_papers in months.items():
            by_day: Dict[str, List[Paper]] = defaultdict(list)
            for p in month_papers:
                by_day[p.published or f"{year}-{m:02d}"].append(p)
            sections = []
            for day, day_papers in sorted(by_day.items(), reverse=True):
                day_label = day.split("-")[2].lstrip("0") if day.count("-") == 2 else "?"
                sections.append(
                    f'<section id="d{esc(day_label)}">'
                    f"<h2>{esc(day_label)} {esc(month_name(m))} {year} "
                    f'<span class="count">{len(day_papers)}</span></h2>'
                    + "\n".join(paper_card(p, search_href="../../../search.html")
                                for p in day_papers)
                    + "</section>")
            content = f"""
<h1>{esc(month_name(m))} {year}</h1>
<p><a href="../index.html">← {year}</a></p>
{''.join(sections)}"""
            _write(out_dir / "archive" / str(year) / f"{m:02d}" / "index.html",
                   page(title=f"{month_name(m)} {year} · {ctx['site_title']}",
                        content=content, depth=3, active="archive/index.html",
                        **ctx))
