"""Tests for the table-of-contents graphics (src/ddc/toc.py): feed parsing, safety checks
and the feed chosen for each journal. No network: feeds are inline samples shaped like the
publishers' own (Wiley's checked against its live feed)."""

from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc import toc  # noqa: E402
from ddc.models import Paper  # noqa: E402

WILEY = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" version="2.0">
<channel><title>Wiley: Angewandte Chemie International Edition: Table of Contents</title>
<item>
  <link>https://onlinelibrary.wiley.com/doi/10.1002/anie.8646657?af=R</link>
  <guid isPermaLink="false">10.1002/anie.8646657</guid>
  <title>Stepwise Proximity Labeling</title>
  <content:encoded>&lt;img src="https://onlinelibrary.wiley.com/cms/asset/a3e6/anie75683-gra-0001-m.png"
     alt="Stepwise"/&gt;&lt;p&gt;Text&lt;/p&gt;</content:encoded>
  <prism:doi>10.1002/anie.8646657</prism:doi>
</item>
<item>
  <guid isPermaLink="false">10.1002/anie.1</guid>
  <content:encoded>&lt;img src="https://evil.example.com/x.png"/&gt;</content:encoded>
  <prism:doi>10.1002/anie.1</prism:doi>
</item>
<item>
  <prism:doi>10.1002/anie.2</prism:doi>
  <content:encoded>&lt;p&gt;No graphic&lt;/p&gt;</content:encoded>
</item>
</channel></rss>"""

RDF = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/">
<item rdf:about="https://pubs.rsc.org/en/Content/ArticleLanding/2026/CC/D6CC03961H">
  <title>A paper</title>
  <link>https://pubs.rsc.org/en/Content/ArticleLanding/2026/CC/D6CC03961H</link>
  <description>&lt;div&gt;&lt;img src="http://pubs.rsc.org/en/Content/Image/GA/D6CC03961H" /&gt;&lt;/div&gt;</description>
</item>
</rdf:RDF>"""


def paper(doi, journal, added="2026-11-10"):
    return Paper(id=doi, title="t", authors=[], journal=journal, publisher="", published="2026-11-01",
                 year=2026, doi=doi, url="", source="crossref", categories=[], tags=[],
                 relevance_score=50, added=added)


class TestParse(unittest.TestCase):
    def test_wiley_item_doi_and_graphic(self):
        got = toc.parse_feed("Wiley", WILEY)
        self.assertEqual(got, {"10.1002/anie.8646657":
                               "https://onlinelibrary.wiley.com/cms/asset/a3e6/anie75683-gra-0001-m.png"})

    def test_rdf_item_doi_from_landing_link_and_https_upgrade(self):
        got = toc.parse_feed("RSC", RDF)
        self.assertEqual(got, {"10.1039/d6cc03961h": "https://pubs.rsc.org/en/Content/Image/GA/D6CC03961H"})

    def test_only_the_publishers_own_https_hosts(self):
        self.assertIsNone(toc.image_ok("Wiley", "https://evil.example.com/x.png"))
        self.assertIsNone(toc.image_ok("ACS", "https://onlinelibrary.wiley.com/x.png"))
        self.assertIsNone(toc.image_ok("Wiley", "javascript:alert(1)"))
        self.assertIsNone(toc.image_ok("Wiley", "https://onlinelibrary.wiley.com.evil.com/x.png"))
        self.assertEqual(toc.image_ok("Wiley", "https://advanced.onlinelibrary.wiley.com/cms/a.png"),
                         "https://advanced.onlinelibrary.wiley.com/cms/a.png")
        self.assertEqual(toc.image_ok("ACS", "//pubs.acs.org/cms/a.gif"), "https://pubs.acs.org/cms/a.gif")


class TestFeeds(unittest.TestCase):
    def test_journal_codes_from_dois(self):
        self.assertEqual(toc.rsc_code("10.1039/D6CC03961H"), "cc")
        self.assertEqual(toc.acs_code("10.1021/acs.jcim.6c02183"), "jcim")
        self.assertEqual(toc.acs_code("10.1021/jacs.6c12519"), "jacs")
        self.assertEqual(toc.publisher_of("10.1002/anie.1"), "Wiley")
        self.assertIsNone(toc.publisher_of("10.1016/j.x.2026.1"))

    def test_choose_feeds_recent_journals_most_papers_first(self):
        papers = [paper("10.1039/d6cc00001a", "ChemComm"), paper("10.1039/d6cc00002a", "ChemComm"),
                  paper("10.1021/jacs.6c00001", "JACS"),
                  paper("10.1021/acs.unknownj.6c1", "Unknown ACS journal"),
                  paper("10.1002/anie.1", "Angewandte"),
                  paper("10.1039/d6sc00001a", "Chem. Sci.", added="2026-01-01")]   # too old
        with mock.patch.object(toc, "_wiley_feed_from_crossref", return_value=toc.wiley_feed("1521-3773")):
            feeds = toc.choose_feeds(papers, dt.date(2026, 11, 20), {})
        self.assertEqual(feeds, [
            ("RSC", "https://feeds.rsc.org/rss/cc"),
            ("ACS", "https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=jacsat"),
            ("Wiley", "https://onlinelibrary.wiley.com/feed/15213773/most-recent"),
        ])

    def test_update_records_only_indexed_papers_and_survives_failures(self):
        papers = [paper("10.1002/anie.8646657", "Angewandte"), paper("10.1039/d6cc03961h", "ChemComm")]
        tmp = pathlib.Path(self._tmp())

        def fake_get(url, **kw):
            if "rsc" in url:
                raise toc.http.FetchError("HTTP 403")
            return WILEY
        with mock.patch.object(toc, "TOC_FILE", tmp / "toc.json"), \
                mock.patch.object(toc, "SOURCES_FILE", tmp / "src.json"), \
                mock.patch.object(toc, "PAUSE_SECONDS", 0), \
                mock.patch.object(toc, "_wiley_feed_from_crossref", return_value="https://onlinelibrary.wiley.com/feed/1/most-recent"), \
                mock.patch.object(toc.http, "get_bytes", side_effect=fake_get):
            stats = toc.update(papers, dt.date(2026, 11, 20))
            saved = toc.load(tmp / "toc.json")
        self.assertEqual(list(saved), ["10.1002/anie.8646657"])
        self.assertEqual(saved["10.1002/anie.8646657"]["pub"], "Wiley")
        self.assertEqual(stats["RSC feeds failed"], 1)
        self.assertEqual(stats["Wiley graphics recorded"], 1)

    def _tmp(self):
        import tempfile
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name


if __name__ == "__main__":
    unittest.main()
