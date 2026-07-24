"""HTML building blocks shared by all generated pages.

Plain string templates (no template engine) keep the project dependency-free.
All dynamic text goes through :func:`esc`.  Every link is *relative* so the
site works at any base path (e.g. ``https://user.github.io/repo/ddc_papers/``).
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
) -> str:
    """Full HTML document shell.  ``depth`` = directory depth below site root."""
    prefix = "../" * depth
    nav_links = []
    for href, label in NAV_ITEMS:
        css = ' class="active"' if href == active else ""
        nav_links.append(f'<a href="{prefix}{href}"{css}>{esc(label)}</a>')
    nav = "\n".join(nav_links)
    year = dt.date.today().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(tagline)}">
<link rel="stylesheet" href="{prefix}assets/style.css">
{head_extra}
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{prefix}index.html">{esc(site_title)}</a>
    <nav class="site-nav">{nav}</nav>
  </div>
</header>
<main class="wrap">
{content}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>{esc(site_title)} indexes bibliographic metadata only and links to the
    original publisher for every paper. No article content is hosted here.</p>
    <p>&copy; {year} · Generated automatically · Updated daily</p>
  </div>
</footer>
</body>
</html>
"""


def score_class(score: int) -> str:
    if score >= 90:
        return "score-high"
    if score >= 70:
        return "score-mid"
    return "score-low"


def paper_card(paper: Paper, search_href: str = "search.html") -> str:
    """Server-side card markup — kept in sync with renderCard() in app.js."""
    authors = ", ".join(paper.authors[:12])
    if len(paper.authors) > 12:
        authors += f" and {len(paper.authors) - 12} more"
    chips: List[str] = []
    for cat in paper.categories[:5]:
        chips.append(
            f'<a class="chip chip-cat" '
            f'href="{search_href}?category={esc(cat)}">{esc(cat)}</a>')
    for tag in paper.tags[:6]:
        if tag not in paper.categories:
            chips.append(
                f'<a class="chip" href="{search_href}?q={esc(tag)}">{esc(tag)}</a>')
    link = paper.url or _doi_url(paper)
    original = (
        f'<a class="btn btn-primary" href="{esc(link)}" target="_blank" '
        f'rel="noopener">Original paper ↗</a>' if link != "#" else "")
    journal = f'<span class="meta-journal">{esc(paper.journal)}</span> · ' if paper.journal else ""
    return f"""<article class="card">
<h3 class="card-title"><a href="{esc(paper.url or _doi_url(paper))}"
 target="_blank" rel="noopener">{esc(paper.title)}</a></h3>
<p class="card-authors">{esc(authors)}</p>
<p class="card-meta">{journal}<time datetime="{esc(paper.published)}">{esc(_pretty_date(paper.published))}</time>
 · <span class="meta-source">{esc(paper.source)}</span>
 <span class="score {score_class(paper.relevance_score)}"
 title="Relevance score">{paper.relevance_score}</span></p>
<p class="card-chips">{''.join(chips)}</p>
<p class="card-actions">{original}</p>
</article>"""


def _doi_url(paper: Paper) -> str:
    return f"https://doi.org/{paper.doi}" if paper.doi else "#"


_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def _pretty_date(iso: Optional[str]) -> str:
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


def month_name(month: int) -> str:
    return _MONTHS[month - 1]
