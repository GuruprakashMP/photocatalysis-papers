"""Generate the static website from the JSON paper store.

Output layout (all inside the project root, so the folder can be dropped into
any GitHub Pages repository):

    index.html                 front page: the papers added most recently (app.js feed)
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
    assets/data/feed.json      the papers added in the last FEED_DAYS days (front page)
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

from ..models import Paper, normalize_doi
from ..settings import ASSETS_SRC_DIR, SITE_DIR, Settings
from ..store import PaperStore
from .html import AUTHORS_SHOWN, _q, esc, month_name, page, paper_card, pretty_date

log = logging.getLogger(__name__)

# The front page lists the papers that entered the index in the last FEED_DAYS days
# (Paper.added), at least FEED_MIN of them, newest first.
FEED_DAYS = 30
FEED_MIN = 200
FEED_CATEGORIES = 4


def generate_site(settings: Settings, out_dir: Path = SITE_DIR) -> None:
    papers = PaperStore().load_all()
    log.info("Generating site for %d papers -> %s", len(papers), out_dir)

    _clean_generated(out_dir)
    _copy_assets(out_dir)
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tocs = _load_tocs() if settings.toc_graphics else {}
    _write_data_shards(papers, out_dir, generated, tocs)
    feed = _write_feed(papers, out_dir, generated, tocs)

    ctx = dict(site_title=settings.site_title, tagline=settings.site_tagline,
               index_key=settings.index_key, contact_email=settings.contact_email)

    _write(out_dir / "index.html",
           _homepage(papers, feed, generated, settings, ctx, tocs))
    _write(out_dir / "search.html",
           _js_page("Search", "search", ctx, depth=0))
    _write(out_dir / "authors.html",
           _js_page("Authors", "authors", ctx, depth=0))
    _write(out_dir / "journals.html",
           _js_page("Journals", "journals", ctx, depth=0))
    _write(out_dir / "about.html", _about_page(papers, settings, ctx))
    _write(out_dir / "categories" / "index.html", _categories_page(papers, ctx))
    _write_archive(papers, out_dir, ctx, tocs)
    log.info("Site generation complete")


def _load_tocs() -> Dict[str, dict]:
    """{doi: {"img": url, "pub": publisher}} recorded by toc.update()."""
    from ..toc import load
    return {normalize_doi(k): v for k, v in load().items()
            if isinstance(v, dict) and isinstance(v.get("img"), str)}


def _toc_fields(p: Paper, tocs: Dict[str, dict]) -> dict:
    t = tocs.get(normalize_doi(p.doi)) if p.doi else None
    return {"toc": t["img"], "tp": t.get("pub", "")} if t else {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clean_generated(out_dir: Path) -> None:
    """Remove fully regenerated output so stale pages never linger.

    Only touches directories the generator owns completely (archive tree and
    the JSON data shards) - never source code or stored data.
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


def _write_data_shards(papers: List[Paper], out_dir: Path, generated: str,
                       tocs: Dict[str, dict]) -> None:
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
            **_toc_fields(p, tocs),
        })
    years = []
    for year, items in sorted(by_year.items(), reverse=True):
        filename = f"papers-{year}.json"
        (data_dir / filename).write_text(
            json.dumps(items, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        years.append({"year": year, "count": len(items), "file": filename})
    manifest = {
        "generated": generated,
        "total": len(papers),
        "years": years,
    }
    (data_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def feed_papers(papers: List[Paper], today: dt.date) -> List[Paper]:
    """Papers added in the FEED_DAYS days up to ``today``, newest first.

    Fewer than FEED_MIN there: the newest FEED_MIN additions, plus the rest of the oldest
    day taken, so the list always holds every paper added since its oldest date (the
    front page says "added since <that date>").
    """
    since = (today - dt.timedelta(days=FEED_DAYS - 1)).isoformat()
    ordered = sorted(papers, key=lambda p: (p.added or "", p.published or "", p.id),
                     reverse=True)
    recent = [p for p in ordered if (p.added or "") >= since]
    if len(recent) >= FEED_MIN or len(ordered) <= FEED_MIN:
        return recent if len(recent) >= FEED_MIN else ordered
    last_day = ordered[FEED_MIN - 1].added or ""
    return [p for p in ordered if (p.added or "") >= last_day]


def _write_feed(papers: List[Paper], out_dir: Path, generated: str,
                tocs: Dict[str, dict]) -> List[Paper]:
    """assets/data/feed.json: what the front page (app.js) lists, small enough to load at once.

    Only what a feed card shows: no affiliations or tags, the first AUTHORS_SHOWN authors
    and the number of the others ("na"), and the URL only for a paper without a DOI.
    """
    today = dt.datetime.now(dt.timezone.utc).date()
    feed = feed_papers(papers, today)
    items = []
    for p in feed:
        item = {
            "id": p.id, "title": p.title, "authors": p.authors[:AUTHORS_SHOWN],
            "journal": p.journal, "published": p.published, "added": p.added,
            "doi": p.doi, "score": p.relevance_score,
            "categories": p.categories[:FEED_CATEGORIES],
        }
        if p.url and not p.doi:      # with a DOI the page links https://doi.org/<doi>
            item["url"] = p.url
        if len(p.authors) > AUTHORS_SHOWN:
            item["na"] = len(p.authors) - AUTHORS_SHOWN
        item.update(_toc_fields(p, tocs))
        items.append(item)
    payload = {"generated": generated, "days": FEED_DAYS, "total": len(papers),
               "count": len(items), "papers": items}
    path = out_dir / "assets" / "data" / "feed.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    return feed


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def _short_date(iso: str) -> str:
    """2026-10-22 -> 22 Oct 2026."""
    full = pretty_date(iso).split(" ")
    return " ".join([full[0], full[1][:3], full[2]]) if len(full) == 3 else pretty_date(iso)


def _homepage(papers: List[Paper], feed: List[Paper], generated: str,
              settings: Settings, ctx: dict, tocs: Dict[str, dict]) -> str:
    oldest = min((p.added for p in feed if p.added), default="")
    n_sources = len(settings.enabled_sources)
    stats = (f'<div class="gp-stat"><dt>Papers indexed</dt><dd>{len(papers):,}</dd></div>'
             f'<div class="gp-stat"><dt>Added since {esc(_short_date(oldest))}</dt>'
             f'<dd>{len(feed):,}</dd></div>'
             f'<div class="gp-stat"><dt>Last update</dt><dd id="hero-updated">{esc(generated)}</dd></div>'
             + (f'<div class="gp-stat"><dt>Open metadata sources</dt>'
                f'<dd><a href="about.html#sources">{n_sources}</a></dd></div>' if n_sources else "")
             ) if papers else ""
    fallback = "\n".join(paper_card(p, toc=_toc_fields(p, tocs))
                         for p in feed[: settings.homepage_paper_count])
    content = f"""
<div id="app" data-page="feed" data-root="">
  <p class="loading">Loading the latest papers…</p>
  <noscript>
  <h2 class="page-title">Recently added papers</h2>
  <p>This list needs JavaScript to mark papers read or saved. The newest additions are below;
  the <a href="archive/index.html">archive</a> lists every paper by date.</p>
  {fallback if fallback else '<p class="empty">No papers indexed yet. The first pipeline run will populate this page.</p>'}
  <p class="more"><a class="btn btn-primary" href="search.html">Search all {len(papers):,} papers</a></p>
  </noscript>
</div>"""
    head = '<script defer src="assets/app.js"></script>'
    return page(title=ctx["site_title"], content=content, depth=0,
                active="index.html", head_extra=head, hero="full",
                hero_stats=stats, **ctx)


def _js_page(title: str, page_kind: str, ctx: dict, depth: int) -> str:
    prefix = "../" * depth
    content = f"""
<div id="app" data-page="{page_kind}" data-root="{prefix}">
  <noscript><p>This page needs JavaScript to filter the paper index.
  Use the <a href="{prefix}archive/index.html">archive</a> for a static view.</p></noscript>
  <p class="loading">Loading the paper index…</p>
</div>"""
    head = f'<script defer src="{prefix}assets/app.js"></script>'
    active = {"search": "search.html", "authors": "authors.html",
              "journals": "journals.html"}.get(page_kind, "")
    return page(title=f"{title} · {ctx['site_title']}", content=content,
                depth=depth, active=active, head_extra=head, page_heading=title, **ctx)


def _categories_page(papers: List[Paper], ctx: dict) -> str:
    counts = Counter(cat for p in papers for cat in p.categories)
    items = "\n".join(
        f'<li><a href="../search.html?category={esc(_q(cat))}">{esc(cat)}</a>'
        f'<span class="count">{count:,}</span></li>'
        for cat, count in sorted(counts.items()))  # alphabetical for findability
    content = f"""
<p>Every paper has one or more categories, from the reaction or application
it reports to the photocatalyst materials, mechanisms and methods behind it.
Click one to browse.</p>
<ul class="tile-list">{items or '<li>No categories yet.</li>'}</ul>"""
    return page(title=f"Categories · {ctx['site_title']}", content=content,
                depth=1, active="categories/index.html", page_heading="Categories", **ctx)


def _toc_about(papers: List[Paper]) -> str:
    tocs = _load_tocs()
    by_pub = Counter(tocs[normalize_doi(p.doi)].get("pub", "")
                     for p in papers if p.doi and normalize_doi(p.doi) in tocs)
    n = sum(by_pub.values())
    counts = ", ".join(f"{esc(k)} {v:,}" for k, v in by_pub.most_common() if k)
    so_far = (f"So far {n:,} paper{'s' if n != 1 else ''} here {'have' if n != 1 else 'has'} "
              f"one ({counts})." if n else "No paper here has one yet.")
    return f"""<h2 id="toc">Table-of-contents graphics</h2>
<p>Every day the index reads the RSS feeds of the ACS, Wiley and RSC journals that
publish papers listed here, and keeps, for those papers, only the address of the
table-of-contents graphic the feed links. The image is not copied: your browser loads it
from the publisher's own server, which therefore sees that request, as it would on the
journal's website. A paper gets a graphic only while it is in its journal's feed, so
mostly recent papers have one. {so_far} Each graphic remains the property of its
publisher or authors, is credited under it, and links to the paper.</p>"""


def _about_page(papers: List[Paper], settings: Settings, ctx: dict) -> str:
    from ..collectors import registry
    toc_section = _toc_about(papers) if settings.toc_graphics else ""
    sources = "\n".join(
        f"<li><strong>{esc(cls.label)}</strong> (<code>{esc(name)}</code>)</li>"
        for name, cls in sorted(registry().items()))
    content = f"""
<p><strong>{esc(ctx['site_title'])}</strong> is an automatically updated index of
photocatalysis research papers: water splitting, hydrogen evolution, CO2
photoreduction, pollutant degradation, photoredox and organic synthesis,
semiconductor photocatalysts, Z-scheme systems, photoelectrochemistry and
solar fuels, covering experimental, computational and data-driven studies
alike.</p>
<h2 id="method">How it works</h2>
<p>Every day an automated pipeline queries open scholarly metadata APIs,
removes duplicates, classifies each paper with a photocatalysis relevance
model, assigns categories and a relevance score, and regenerates this site.</p>
<h2 id="sources">Sources</h2>
<ul>{sources}</ul>
<p>Papers from publishers such as ACS, RSC, Wiley, Springer Nature, Elsevier,
MDPI, Frontiers, Taylor &amp; Francis, IOP and AIP reach this index through
Crossref, OpenAlex, PubMed, Europe PMC, Semantic Scholar and DOAJ, which
legally distribute their bibliographic metadata.</p>
<h2 id="policy">Data policy</h2>
<p>This site stores <em>metadata only</em>: title, authors, journal, date, DOI
and link, and for some papers the address of the publisher's table-of-contents
graphic. No abstracts, no full text, no PDFs, no images. Every paper links to the
original publisher page. To have a record corrected or removed, contact
<a href="mailto:{esc(settings.contact_email)}">{esc(settings.contact_email)}</a>.</p>
<h2 id="abstracts">Abstracts</h2>
<p>A paper's <strong>Abstract</strong> button asks <a href="https://openalex.org/">OpenAlex</a>
for the abstract by the paper's DOI, and <a href="https://www.crossref.org/">Crossref</a> when
OpenAlex has none. Your browser sends that request itself, only when you click, and the
abstract is shown with its source. Nothing is stored, here or in your browser. Papers
without a DOI, or whose abstract neither service has, show "No abstract available".</p>
{toc_section}
<h2 id="your-data">What your browser keeps</h2>
<p>Marking a paper read or saved, the journals you follow and the time of your last
visit are kept in your browser's local storage on this computer, for this index only.
They are never sent anywhere. Clearing this site's data in your browser removes them.</p>
<p class="stats"><span><strong>{len(papers):,}</strong> papers indexed so far.</span></p>"""
    return page(title=f"About · {ctx['site_title']}", content=content,
                depth=0, active="about.html", page_heading="About this index", **ctx)


def _write_archive(papers: List[Paper], out_dir: Path, ctx: dict,
                   tocs: Dict[str, dict]) -> None:
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
<p>Browse the index by publication date: year, then month, then day.</p>
<ul class="tile-list">{year_items or '<li>Empty archive.</li>'}</ul>"""
    _write(out_dir / "archive" / "index.html",
           page(title=f"Archive · {ctx['site_title']}", content=content,
                depth=1, active="archive/index.html", page_heading="Archive", **ctx))

    for year, months in by_year.items():
        month_items = "\n".join(
            f'<li><a href="{m:02d}/index.html">{esc(month_name(m))}</a>'
            f'<span class="count">{len(month_papers):,}</span></li>'
            for m, month_papers in sorted(months.items(), reverse=True))
        content = f"""
<p><a href="../index.html">← All years</a></p>
<ul class="tile-list">{month_items}</ul>"""
        _write(out_dir / "archive" / str(year) / "index.html",
               page(title=f"{year} · {ctx['site_title']}", content=content,
                    depth=2, active="archive/index.html", page_heading=f"Archive · {year}", **ctx))

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
                    + "\n".join(paper_card(p, root="../../../", toc=_toc_fields(p, tocs))
                                for p in day_papers)
                    + "</section>")
            content = f"""
<p><a href="../index.html">← {year}</a></p>
{''.join(sections)}"""
            _write(out_dir / "archive" / str(year) / f"{m:02d}" / "index.html",
                   page(title=f"{month_name(m)} {year} · {ctx['site_title']}",
                        content=content, depth=3, active="archive/index.html",
                        head_extra='<script defer src="../../../assets/app.js"></script>',
                        body_page="static", page_heading=f"{month_name(m)} {year}", **ctx))
