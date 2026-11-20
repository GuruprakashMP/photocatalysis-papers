"""Table-of-contents graphics (graphical abstracts) for recently indexed papers.

Journal RSS feeds of ACS, Wiley and RSC link each new article's TOC graphic. Every
run reads the feeds of the journals from those publishers that have papers added to
this index in the last LOOKBACK_DAYS days, takes each feed item's DOI and image URL,
and records the URL for the papers that are in the index (data/state/toc.json).

Only the URL is stored. The image itself is never downloaded or copied: the website
shows it from the publisher's own server, and only from that publisher's own hosts
(IMAGE_HOSTS), over HTTPS.

Every feed is fetched independently and every failure is logged and skipped, so a
blocked or broken feed never stops the daily run.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit

from . import http
from .models import Paper, normalize_doi
from .settings import STATE_DIR

log = logging.getLogger(__name__)

TOC_FILE = STATE_DIR / "toc.json"            # {doi: {"img": url, "pub": "Wiley", "seen": date}}
SOURCES_FILE = STATE_DIR / "toc_sources.json"  # {"Wiley|<journal>": feed url or ""}

LOOKBACK_DAYS = 60      # journals with papers added in this window get their feed read
MAX_FEEDS = 150         # per run, the journals with the most recent papers first
PAUSE_SECONDS = 1.0     # between two feed requests
MAX_FEED_BYTES = 12 * 1024 * 1024
GIVE_UP_AFTER = 3       # a publisher whose first 3 feeds all fail is skipped for the run

PUBLISHERS = {"10.1021": "ACS", "10.1002": "Wiley", "10.1039": "RSC"}
IMAGE_HOSTS = {
    "ACS": ("pubs.acs.org",),
    "Wiley": ("onlinelibrary.wiley.com", ".onlinelibrary.wiley.com"),
    "RSC": ("pubs.rsc.org",),
}

# ACS journal feeds are addressed by CODEN; the DOI carries a short journal code instead.
ACS_CODEN = {
    "jacs": "jacsat", "acscatal": "accacs", "jcim": "jcisd8", "jctc": "jctcce",
    "jpca": "jpcafh", "jpcb": "jpcbfk", "jpcc": "jpccck", "jpclett": "jpclcd",
    "orglett": "orlef7", "joc": "joceah", "inorgchem": "inocaj", "organomet": "orgnd7",
    "est": "esthag", "chemmater": "cmatex", "jmedchem": "jmcmar",
    "langmuir": "langd5", "macromol": "mamobx", "nanolett": "nalefd", "acsnano": "ancac3",
    "acsami": "aamick", "acsaem": "aaembp", "acsanm": "aanmf6", "acsomega": "acsodf",
    "accounts": "achre4", "chemrev": "chreay", "acssuschemeng": "ascefj",
    "acsenergylett": "aelccp", "acscentsci": "acscii", "iecr": "iecred", "oprd": "oprdfk",
    "energyfuels": "enfuem", "analchem": "ancham",
}


# ---------------------------------------------------------------------------
# which feeds
# ---------------------------------------------------------------------------

def publisher_of(doi: str) -> Optional[str]:
    return PUBLISHERS.get(normalize_doi(doi).split("/", 1)[0])


def rsc_code(doi: str) -> Optional[str]:
    """RSC journal code from a DOI: 10.1039/d6cc03961h -> "cc"."""
    m = re.match(r"^10\.1039/[a-z]\d([a-z]{2})\d", normalize_doi(doi))
    return m.group(1) if m else None


def acs_code(doi: str) -> Optional[str]:
    """ACS short journal code from a DOI: 10.1021/acs.jcim.6c02183 -> "jcim"."""
    m = re.match(r"^10\.1021/(?:acs\.)?([a-z]+)\.", normalize_doi(doi))
    return m.group(1) if m else None


def wiley_feed(issn: str) -> str:
    return f"https://onlinelibrary.wiley.com/feed/{issn.replace('-', '')}/most-recent"


def feed_url(pub: str, doi: str, sources: Dict[str, str], journal: str) -> Optional[str]:
    """The RSS feed of the journal a DOI belongs to, or None when it cannot be told."""
    if pub == "RSC":
        code = rsc_code(doi)
        # feeds.rsc.org breaks off HTTPS handshakes from GitHub's runners (2026-11-20) but
        # answers over plain HTTP. Its items carried no graphic that day; the feed is still
        # read so graphics appear here if RSC adds them. Image URLs must be HTTPS (image_ok).
        return f"http://feeds.rsc.org/rss/{code}" if code else None
    if pub == "ACS":
        coden = ACS_CODEN.get(acs_code(doi) or "")
        return (f"https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc={coden}"
                if coden else None)
    if pub == "Wiley":
        key = f"Wiley|{journal}"
        if key not in sources:
            sources[key] = _wiley_feed_from_crossref(doi) or ""
        return sources[key] or None
    return None


def _wiley_feed_from_crossref(doi: str) -> Optional[str]:
    """Wiley addresses feeds by the journal's electronic ISSN, which Crossref lists."""
    try:
        msg = http.get_json(f"https://api.crossref.org/works/{normalize_doi(doi)}")["message"]
    except (http.FetchError, KeyError, TypeError) as exc:
        log.info("toc: no ISSN for %s (%s)", doi, exc)
        return None
    types = msg.get("issn-type") or []
    issn = next((t.get("value") for t in types if t.get("type") == "electronic"), None)
    issn = issn or next(iter(msg.get("ISSN") or []), None)
    return wiley_feed(issn) if issn else None


def choose_feeds(papers: Iterable[Paper], today: dt.date,
                 sources: Dict[str, str]) -> List[Tuple[str, str]]:
    """(publisher, feed url) for the journals with papers added in the last LOOKBACK_DAYS."""
    since = (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    counts: Counter = Counter()
    sample: Dict[Tuple[str, str], str] = {}
    for p in papers:
        pub = publisher_of(p.doi)
        if not pub or (p.added or "") < since:
            continue
        key = (pub, p.journal)
        counts[key] += 1
        sample.setdefault(key, p.doi)
    feeds: List[Tuple[str, str]] = []
    seen = set()
    for (pub, journal), _n in counts.most_common():
        url = feed_url(pub, sample[(pub, journal)], sources, journal)
        if url and url not in seen:
            seen.add(url)
            feeds.append((pub, url))
        if len(feeds) >= MAX_FEEDS:
            break
    return feeds


# ---------------------------------------------------------------------------
# reading a feed
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>?#&]+", re.I)
_RSC_LANDING_RE = re.compile(r"/articlelanding/\d{4}/[a-z]+/([a-z0-9]+)", re.I)
_IMG_RE = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def image_ok(pub: str, url: str) -> Optional[str]:
    """The URL, upgraded to HTTPS, when it points at the publisher's own host; else None."""
    url = html.unescape(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return None
    if not url.startswith("https://") or len(url) > 600:
        return None
    for allowed in IMAGE_HOSTS.get(pub, ()):
        if host == allowed or (allowed.startswith(".") and host.endswith(allowed)):
            return url
    return None


def parse_feed(pub: str, data: bytes) -> Dict[str, str]:
    """{doi: image url} for the items of an RSS 2.0, RSS 1.0 (RDF) or Atom feed."""
    root = ET.fromstring(data)
    out: Dict[str, str] = {}
    for item in root.iter():
        if _local(item.tag) not in ("item", "entry"):
            continue
        fields: Dict[str, List[str]] = {}
        for child in item:
            name = _local(child.tag)
            text = (child.text or "").strip()
            if name == "link" and not text:
                text = child.get("href", "")
            fields.setdefault(name, []).append(text)
            if name in ("enclosure", "content", "thumbnail") and child.get("url"):
                fields.setdefault("_media", []).append(child.get("url", ""))
        doi = _item_doi(pub, fields)
        img = _item_image(pub, fields)
        if doi and img:
            out[doi] = img
    return out


def describe_first_item(data: bytes) -> str:
    """What the first item of a feed holds (element names, a little of each text), so a
    feed in a format parse_feed does not read yet shows up in the run's log."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return f"not XML ({exc}): {data[:200]!r}"
    for item in root.iter():
        if _local(item.tag) in ("item", "entry"):
            parts = []
            for child in item:
                text = (child.text or "").strip().replace("\n", " ")
                attrs = " ".join(f"{k}={v}" for k, v in child.attrib.items())[:120]
                parts.append(f"<{child.tag} {attrs}> {text[:160]}")
            return " | ".join(parts)[:1500]
    return f"no item; root <{root.tag}>, {len(data)} bytes"


def _item_doi(pub: str, fields: Dict[str, List[str]]) -> str:
    for name in ("doi", "identifier", "guid", "link", "about"):
        for text in fields.get(name, []):
            m = _DOI_RE.search(text)
            if m:
                return normalize_doi(m.group(0).rstrip(".,;)"))
            if pub == "RSC":
                m = _RSC_LANDING_RE.search(text)
                if m:
                    return "10.1039/" + m.group(1).lower()
    return ""


def _item_image(pub: str, fields: Dict[str, List[str]]) -> Optional[str]:
    for name in ("encoded", "description", "summary", "content"):
        for text in fields.get(name, []):
            for src in _IMG_RE.findall(html.unescape(text)):
                ok = image_ok(pub, src)
                if ok:
                    return ok
    for src in fields.get("_media", []):
        ok = image_ok(pub, src)
        if ok:
            return ok
    return None


# ---------------------------------------------------------------------------
# the daily update
# ---------------------------------------------------------------------------

def load(path: Optional[Path] = None) -> Dict[str, dict]:
    path = path or TOC_FILE      # read at call time, so a changed TOC_FILE is honoured
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True),
                    encoding="utf-8")


def _fetch_feed(pub: str, url: str) -> bytes:
    return http.get_bytes(url, headers={"Accept": "application/rss+xml, application/xml, text/xml"},
                          retries=2)


def update(papers: List[Paper], today: Optional[dt.date] = None) -> Dict[str, int]:
    """Read the feeds and record the TOC graphics of indexed papers. Returns counts."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    sources = load(SOURCES_FILE)
    toc = load()
    indexed = {normalize_doi(p.doi) for p in papers if p.doi}
    feeds = choose_feeds(papers, today, sources)
    _save(SOURCES_FILE, sources)
    stats: Counter = Counter()
    misses: Counter = Counter()      # failures in a row, per publisher, before any success
    for i, (pub, url) in enumerate(feeds):
        if misses[pub] >= GIVE_UP_AFTER:
            stats[f"{pub} feeds skipped"] += 1
            continue
        if i:
            time.sleep(PAUSE_SECONDS)
        try:
            data = _fetch_feed(pub, url)
            if len(data) > MAX_FEED_BYTES:
                raise ValueError(f"{len(data)} bytes")
            items = parse_feed(pub, data)
        except (http.FetchError, ET.ParseError, ValueError) as exc:
            stats[f"{pub} feeds failed"] += 1
            if not stats[f"{pub} feeds read"]:
                misses[pub] += 1
            log.info("toc: %s feed %s failed: %s", pub, url, str(exc)[:160])
            continue
        stats[f"{pub} feeds read"] += 1
        stats[f"{pub} items with a graphic"] += len(items)
        if not items and not stats[f"{pub} diagnosed"]:
            stats[f"{pub} diagnosed"] += 1
            log.info("toc: %s feed %s gave no DOI with a graphic; first item: %s",
                     pub, url, describe_first_item(data))
        for doi, img in items.items():
            if doi not in indexed:
                continue
            old = toc.get(doi)
            if not old or old.get("img") != img:
                stats[f"{pub} graphics recorded"] += 1
            toc[doi] = {"img": img, "pub": pub, "seen": today.isoformat()}
    _save(TOC_FILE, toc)
    stats["papers with a graphic"] = len(toc)
    log.info("toc: %s", ", ".join(f"{k}: {v}" for k, v in sorted(stats.items())) or "no feeds")
    return dict(stats)
