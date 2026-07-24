"""Tests for the static site generator (renders into a temp directory)."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc.models import Paper  # noqa: E402
from ddc.settings import Settings  # noqa: E402
from ddc.site import generator  # noqa: E402

SAMPLE = [
    Paper(
        id="p1", title="ML for catalysis <test>", authors=["Jane Doe", "Bo Li"],
        journal="ACS Catalysis", publisher="ACS", published="2026-07-18",
        year=2026, doi="10.1021/x", url="https://doi.org/10.1021/x",
        source="crossref", categories=["Catalysis", "Machine Learning"],
        tags=["Random Forest"], relevance_score=92, added="2026-07-19"),
    Paper(
        id="p2", title="GNNs for property prediction", authors=["Jane Doe"],
        journal="Chem. Sci.", publisher="RSC", published="2026-06-02",
        year=2026, doi="10.1039/y", url="https://doi.org/10.1039/y",
        source="openalex", categories=["Property Prediction"],
        tags=["Graph Neural Network"], relevance_score=75, added="2026-06-03"),
]


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self.tmp.name)
        fake_store = mock.Mock()
        fake_store.load_all.return_value = list(SAMPLE)
        patcher = mock.patch.object(generator, "PaperStore",
                                    return_value=fake_store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        generator.generate_site(Settings(site_title="TestSite"), out_dir=self.out)

    def test_core_pages_exist(self):
        for rel in ("index.html", "search.html", "authors.html", "journals.html",
                    "about.html", "categories/index.html", "archive/index.html",
                    "archive/2026/index.html", "archive/2026/07/index.html",
                    "assets/style.css", "assets/app.js",
                    "assets/data/manifest.json", "assets/data/papers-2026.json"):
            self.assertTrue((self.out / rel).exists(), rel)

    def test_homepage_shows_papers_and_escapes_html(self):
        html = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("ML for catalysis &lt;test&gt;", html)
        self.assertNotIn("<test>", html)
        self.assertIn("ACS Catalysis", html)
        self.assertIn("10.1021/x", html)

    def test_archive_month_page_groups_by_day(self):
        html = (self.out / "archive" / "2026" / "07" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn('id="d18"', html)
        self.assertIn("18 July 2026", html)

    def test_relative_links_at_depth(self):
        html = (self.out / "archive" / "2026" / "07" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn('href="../../../assets/style.css"', html)
        self.assertNotIn('href="/assets', html)

    def test_manifest_counts(self):
        import json
        manifest = json.loads(
            (self.out / "assets" / "data" / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["total"], 2)
        self.assertEqual(manifest["years"][0]["year"], 2026)


if __name__ == "__main__":
    unittest.main()
