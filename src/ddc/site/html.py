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
import re
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


_EM_DASH = re.compile(r"\s*\u2014\s*")


def no_dash(value: object) -> str:
    """Display form of text from the data: an em dash becomes a spaced hyphen.

    Only what the page shows changes; the stored record (and every link, search and
    match built from it) keeps the publisher's text exactly.
    """
    return _EM_DASH.sub(" - ", str(value or "")).strip()


def txt(value: object) -> str:
    """Escaped display text from the data (see :func:`no_dash`)."""
    return esc(no_dash(value))


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
    contact_email: str = "",
    hero: str = "slim",
    hero_stats: str = "",
    body_page: str = "",
    page_heading: str = "",
) -> str:
    """Full HTML document shell.  ``depth`` = directory depth below site root.

    ``hero`` is "full" (the front page: name, tagline and ``hero_stats``) or "slim"
    (the index name over ``page_heading``). ``body_page`` marks a page whose static
    paper cards app.js should enhance.
    """
    prefix = "../" * depth
    nav_links = []
    for href, label in NAV_ITEMS:
        cur = ' aria-current="page"' if href == active else ""
        nav_links.append(f'<a href="{prefix}{href}"{cur}>{esc(label)}</a>')
    nav = "\n      ".join(nav_links)
    foot_links = "".join(f'<li><a href="{prefix}{href}">{esc(label)}</a></li>'
                         for href, label in NAV_ITEMS)
    year = dt.date.today().year
    full = hero == "full"
    if full:
        band = f"""<p class="gp-hero-kicker">Open literature index · updated daily</p>
    <h1 class="gp-hero-title">{esc(site_title)}</h1>
    <p class="gp-hero-sub">{esc(tagline)}</p>
    {f'<dl class="gp-stats" id="hero-stats">{hero_stats}</dl>' if hero_stats else ''}"""
    else:
        band = f"""<p class="gp-hero-kicker"><a href="{prefix}index.html">{esc(site_title)}</a></p>
    <p class="gp-hero-title">{esc(page_heading or site_title)}</p>"""
    body_attrs = (f' data-index-key="{esc(index_key)}" data-site-title="{esc(site_title)}"'
                  f' data-root="{prefix}"')
    if body_page:
        body_attrs += f' data-page="{esc(body_page)}"'
    contact = (f'<li><a href="mailto:{esc(contact_email)}">Report a correction</a></li>'
               if contact_email else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(tagline)}">
<meta name="theme-color" content="#0f172a">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(tagline)}">
<link rel="icon" href="{GP_SHARED['icon']}" type="image/svg+xml">
<link rel="stylesheet" href="{GP_SHARED['css']}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<script defer src="{GP_SHARED['bar']}"></script>
{head_extra}
</head>
<body class="gp-page"{body_attrs}>
<a class="skip" href="#main">Skip to the content</a>
<header class="gp-bar">
  <div class="gp-bar-in">
    <a class="gp-home" href="{GP_SHARED['home']}" aria-label="Guruprakash M P: home page"><img src="{GP_SHARED['icon']}" alt="" width="30" height="30"></a>
    <span data-gp-tools data-gp-current="{esc(index_key)}" data-gp-compact></span>
    <a class="gp-bar-title" href="{prefix}index.html">{esc(site_title)}</a>
    <nav class="gp-bar-nav" aria-label="{esc(site_title)}">
      {nav}
    </nav>
  </div>
</header>
<section class="gp-hero{' gp-full' if full else ' gp-slim'}">
  <canvas class="starfield" data-density="{'0.75' if full else '0.6'}" data-max="{'170' if full else '90'}" data-meteors="0" data-speed="0.35" aria-hidden="true"></canvas>
  <div class="gp-hero-in">
    {band}
  </div>
</section>
<main class="wrap" id="main">
{content}
</main>
<footer class="gp-footer" data-gp-footer>
  <div class="gp-footer-in gp-footer-grid">
    <div class="gp-footer-col gp-footer-brand">
      <a class="gp-footer-made" href="{GP_SHARED['home']}">Made by Guruprakash M P</a>
      <p><strong>{esc(site_title)}</strong>. {esc(tagline)}</p>
      <p>Bibliographic metadata only: every paper links to its publisher, and no article
      content is hosted here.</p>
    </div>
    <nav class="gp-footer-col" aria-label="This index">
      <h2>This index</h2>
      <ul>{foot_links}</ul>
    </nav>
    <div class="gp-footer-col">
      <h2>Data</h2>
      <ul>
        <li><a href="{prefix}about.html#sources">Sources</a></li>
        <li><a href="{prefix}about.html#method">How papers are selected</a></li>
        <li><a href="{prefix}about.html#policy">Data policy</a></li>
        <li><a href="{prefix}about.html#your-data">What your browser keeps</a></li>
        {contact}
      </ul>
    </div>
    <nav class="gp-footer-col" aria-label="Other tools">
      <h2>Tools</h2>
      <ul data-gp-toollist></ul>
    </nav>
  </div>
  <div class="gp-footer-base">
    <span>&copy; {year} Guruprakash M P</span>
    <span>Generated automatically and updated daily</span>
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


def toc_figure(toc: Optional[dict], link: str) -> str:
    """The publisher's table-of-contents graphic, shown from the publisher's server."""
    if not toc or not toc.get("toc"):
        return ""
    pub = toc.get("tp") or "the publisher"
    img = (f'<img src="{esc(toc["toc"])}" alt="Table of contents graphic" loading="lazy" '
           f'decoding="async" referrerpolicy="no-referrer" '
           f'onerror="var f=this.closest(\'figure\');if(f){{f.parentNode.classList.remove(\'has-toc\');f.remove();}}">')
    if link:
        img = f'<a href="{esc(link)}" target="_blank" rel="noopener" tabindex="-1">{img}</a>'
    return f'<figure class="card-toc">{img}<figcaption>Graphic: {esc(pub)}</figcaption></figure>'


def paper_card(paper: Paper, root: str = "", toc: Optional[dict] = None) -> str:
    """Server-side card markup, kept in sync with renderCard() in app.js.

    ``root`` is the relative path to the site root ("../../../" on a month page).
    ``toc`` is {"toc": image url, "tp": publisher} when the paper has a TOC graphic.
    app.js adds the Abstract / Save / Mark read buttons to these cards.
    """
    # Plain text, as before: an author link on every name of every archive card would add
    # tens of MB to the largest index's archive. The search and author pages link them.
    authors = txt(", ".join(paper.authors[:AUTHORS_SHOWN]))
    if len(paper.authors) > AUTHORS_SHOWN:
        authors += f" and {len(paper.authors) - AUTHORS_SHOWN} more"
    chips: List[str] = []
    for cat in paper.categories[:5]:
        chips.append(
            f'<a class="chip chip-cat" '
            f'href="{root}search.html?category={esc(_q(cat))}">{txt(cat)}</a>')
    for tag in paper.tags[:6]:
        if tag not in paper.categories:
            chips.append(
                f'<a class="chip" href="{root}search.html?q={esc(_q(tag))}">{txt(tag)}</a>')
    link = paper_link(paper)
    full_text = (
        f'<a class="act act-primary" href="{esc(link)}" target="_blank" '
        f'rel="noopener">Full text</a>' if link else "")
    journal = (
        f'<a class="badge-journal" href="{root}journals.html?j={esc(_q(paper.journal))}">'
        f'{txt(paper.journal)}</a>' if paper.journal else "")
    title = (f'<a href="{esc(link)}" target="_blank" rel="noopener">{txt(paper.title)}</a>'
             if link else txt(paper.title))
    figure = toc_figure(toc, link)
    return f"""<article class="card{' has-toc' if figure else ''}" data-id="{esc(paper.id)}" data-doi="{esc(paper.doi)}">
<div class="card-body">
<h3 class="card-title">{title}</h3>
<p class="card-authors">{authors}</p>
<p class="card-meta">{journal}<time datetime="{esc(paper.published)}">{esc(pretty_date(paper.published))}</time><span class="meta-source">{esc(paper.source)}</span><span class="score {score_class(paper.relevance_score)}" title="Relevance score">{paper.relevance_score}</span></p>
<p class="card-chips">{''.join(chips)}</p>
<div class="card-actions">{full_text}</div>
</div>{figure}
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
