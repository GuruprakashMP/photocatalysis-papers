"""HTML building blocks shared by all generated pages.

Plain string templates (no template engine) keep the project dependency-free.
All dynamic text goes through :func:`esc`.  The index's own links are *relative*
so the pages work at any base path (e.g. ``https://user.github.io/repo/``).

The look is the shared "GP Tools" theme of guruprakashmp.github.io: every page
loads the theme's stylesheet and scripts from the main site (root-relative URLs
in :data:`GP_SHARED`), the same files every other tool there loads, so one edit
on the main site restyles every index.  Without them the pages still work, with
the index's own stylesheet (``assets/style.css``) only.
"""

from __future__ import annotations

import datetime as dt
from html import escape
from typing import List, Optional

from ..models import Paper

NAV_ITEMS = (
    ("index.html", "Latest"),
    ("search.html", "Search"),
    ("archive/index.html", "Archive"),
    ("authors.html", "Authors"),
    ("journals.html", "Journals"),
    ("categories/index.html", "Categories"),
    ("about.html", "About"),
)

# Served once by the main site, guruprakashmp.github.io (same origin as every index).
GP_SHARED = {
    "css": "/assets/css/gp-tools.css",
    "bar": "/assets/js/gp-bar.js",
    "stars": "/assets/js/starfield.js",
    "icon": "/images/gp-icon.svg",
    "home": "/",
}

AUTHORS_SHOWN = 12


def esc(value: object) -> str:
    return escape(str(value or ""), quote=True)


def page(
    *,
    title: str,
    site_title: str,
    tagline: str,
    content: str,
    depth: int = 0,
    active: str = "",
    head_extra: str = "",
    index_key: str = "",
    hero: str = "slim",
    hero_stats: str = "",
    body_page: str = "",
) -> str:
    """Full HTML document shell.  ``depth`` = directory depth below site root.

    ``hero`` is "full" (the front page: name, tagline and ``hero_stats``) or "slim".
    ``body_page`` marks a page whose static paper cards app.js should enhance.
    """
    prefix = "../" * depth
    nav_links = []
    for href, label in NAV_ITEMS:
        cur = ' aria-current="page"' if href == active else ""
        nav_links.append(f'<a href="{prefix}{href}"{cur}>{esc(label)}</a>')
    nav = "\n    ".join(nav_links)
    year = dt.date.today().year
    full = hero == "full"
    kicker = '<p class="gp-hero-kicker">Literature index · updated daily</p>' if full else ""
    stats = f'\n    <ul class="gp-hero-stats" id="hero-stats">{hero_stats}</ul>' if full and hero_stats else ""
    heading = "h1" if full else "p"
    body_attrs = (f' data-index-key="{esc(index_key)}" data-site-title="{esc(site_title)}"'
                  f' data-root="{prefix}"')
    if body_page:
        body_attrs += f' data-page="{esc(body_page)}"'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(tagline)}">
<link rel="icon" href="{GP_SHARED['icon']}" type="image/svg+xml">
<link rel="stylesheet" href="{GP_SHARED['css']}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script defer src="{GP_SHARED['bar']}"></script>
{head_extra}
</head>
<body class="gp-page"{body_attrs}>
<a class="skip" href="#main">Skip to the papers</a>
<header class="gp-bar">
  <div class="gp-bar-in">
    <a class="gp-home" href="{GP_SHARED['home']}" aria-label="Guruprakash M P: home page"><img src="{GP_SHARED['icon']}" alt="" width="30" height="30"></a>
    <span data-gp-tools data-gp-current="{esc(index_key)}"></span>
    <a class="gp-bar-title" href="{prefix}index.html">{esc(site_title)}</a>
    <nav class="gp-bar-nav" aria-label="{esc(site_title)}">
    {nav}
    </nav>
  </div>
</header>
<section class="gp-hero{'' if full else ' gp-slim'}">
  <canvas class="starfield" data-density="{'1.1' if full else '0.9'}" data-max="{'260' if full else '140'}" aria-hidden="true"></canvas>
  <div class="gp-hero-in">
    {kicker}<{heading} class="gp-hero-title">{esc(site_title)}</{heading}>
    <p class="gp-hero-sub">{esc(tagline)}</p>{stats}
  </div>
</section>
<main class="wrap" id="main">
{content}
</main>
<footer class="gp-footer" data-gp-footer>
  <div class="gp-footer-in">
    <a class="gp-footer-made" href="{GP_SHARED['home']}">Made by Guruprakash M P</a>
    <p class="gp-footer-note">{esc(site_title)} indexes bibliographic metadata only and links to the
    original publisher for every paper. No article content is hosted here.
    &copy; {year} · Generated automatically · Updated daily</p>
  </div>
</footer>
<script defer src="{GP_SHARED['stars']}"></script>
</body>
</html>
"""


def score_class(score: int) -> str:
    if score >= 90:
        return "score-high"
    if score >= 70:
        return "score-mid"
    return "score-low"


def paper_card(paper: Paper, root: str = "") -> str:
    """Server-side card markup, kept in sync with renderCard() in app.js.

    ``root`` is the relative path to the site root ("../../../" on a month page).
    app.js adds the Abstract / Save / Mark read buttons to these cards.
    """
    # Plain text, as before: an author link on every name of every archive card would add
    # tens of MB to the largest index's archive. The search and author pages link them.
    authors = esc(", ".join(paper.authors[:AUTHORS_SHOWN]))
    if len(paper.authors) > AUTHORS_SHOWN:
        authors += f" and {len(paper.authors) - AUTHORS_SHOWN} more"
    chips: List[str] = []
    for cat in paper.categories[:5]:
        chips.append(
            f'<a class="chip chip-cat" '
            f'href="{root}search.html?category={esc(_q(cat))}">{esc(cat)}</a>')
    for tag in paper.tags[:6]:
        if tag not in paper.categories:
            chips.append(
                f'<a class="chip" href="{root}search.html?q={esc(_q(tag))}">{esc(tag)}</a>')
    link = paper_link(paper)
    full_text = (
        f'<a class="act act-primary" href="{esc(link)}" target="_blank" '
        f'rel="noopener">Full text</a>' if link else "")
    journal = (
        f'<a class="badge-journal" href="{root}journals.html?j={esc(_q(paper.journal))}">'
        f'{esc(paper.journal)}</a>' if paper.journal else "")
    title = (f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(paper.title)}</a>'
             if link else esc(paper.title))
    return f"""<article class="card" data-id="{esc(paper.id)}" data-doi="{esc(paper.doi)}">
<h3 class="card-title">{title}</h3>
<p class="card-authors">{authors}</p>
<p class="card-meta">{journal}<time datetime="{esc(paper.published)}">{esc(pretty_date(paper.published))}</time><span class="meta-source">{esc(paper.source)}</span><span class="score {score_class(paper.relevance_score)}" title="Relevance score">{paper.relevance_score}</span></p>
<p class="card-chips">{''.join(chips)}</p>
<div class="card-actions">{full_text}</div>
</article>"""


def paper_link(paper: Paper) -> str:
    """The "Full text" target: the DOI when there is one, else the source's URL."""
    if paper.doi:
        return f"https://doi.org/{paper.doi}"
    return paper.url or ""


def _q(value: str) -> str:
    """Query-string encoding for a link built in Python (as encodeURIComponent)."""
    from urllib.parse import quote
    return quote(str(value or ""), safe="")


_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def pretty_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    parts = iso.split("-")
    try:
        if len(parts) >= 3:
            return f"{int(parts[2])} {_MONTHS[int(parts[1]) - 1]} {parts[0]}"
        if len(parts) == 2:
            return f"{_MONTHS[int(parts[1]) - 1]} {parts[0]}"
    except (ValueError, IndexError):
        pass
    return iso


_pretty_date = pretty_date  # old name, kept for callers outside this module


def month_name(month: int) -> str:
    return _MONTHS[month - 1]
