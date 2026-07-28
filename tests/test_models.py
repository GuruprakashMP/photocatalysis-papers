"""Tests for identifiers, normalisation and dedup keys."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc.models import (  # noqa: E402
    Paper, dedupe_keys, make_paper_id, normalize_author, normalize_doi,
    normalize_title)


class TestNormalization(unittest.TestCase):
    def test_doi_url_prefixes_stripped(self):
        for raw in ("https://doi.org/10.1021/JACS.1", "doi:10.1021/jacs.1",
                    "10.1021/jacs.1", "  10.1021/Jacs.1  "):
            self.assertEqual(normalize_doi(raw), "10.1021/jacs.1")

    def test_invalid_doi_empty(self):
        self.assertEqual(normalize_doi("not-a-doi"), "")
        self.assertEqual(normalize_doi(None), "")

    def test_title_normalization(self):
        self.assertEqual(normalize_title("ML for Chemistry!"),
                         normalize_title("  ml FOR chemistry  "))


class TestAuthorNormalization(unittest.TestCase):
    def test_unicode_hyphen_matches_ascii(self):
        # The real-world bug: Crossref/Wiley ship U+2010, so the ASCII
        # spelling everyone types found an almost-empty author page.
        self.assertEqual(normalize_author("Jun‐ichi Yoshida"),
                         "Jun-ichi Yoshida")

    def test_all_dash_variants_fold_to_ascii(self):
        for dash in "‐‑‒–—―−﹘﹣－":
            self.assertEqual(normalize_author("Li%sZhu Wu" % dash), "Li-Zhu Wu")

    def test_honorifics_stripped_including_stacked(self):
        for raw in ("Prof. Dr. C. Oliver Kappe", "Professor C. Oliver Kappe",
                    "Dr C. Oliver Kappe", "DR. C. Oliver Kappe"):
            self.assertEqual(normalize_author(raw), "C. Oliver Kappe")

    def test_trailing_initial_period_preserved(self):
        # 1,339 stored names legitimately end in an initial — trimming the
        # period would corrupt them.
        self.assertEqual(normalize_author("Jain, K. K."), "Jain, K. K.")

    def test_whitespace_and_invisible_characters(self):
        self.assertEqual(normalize_author("  Steven V.   Ley​ "),
                         "Steven V. Ley")

    def test_idempotent(self):
        for raw in ("Jun‐ichi Yoshida", "Prof. Dr. Thomas Wirth",
                    "Jain, K. K.", "Li–Zhu Wu"):
            once = normalize_author(raw)
            self.assertEqual(normalize_author(once), once)

    def test_never_empties_a_name(self):
        # A bare honorific is a real record; cleanup must not delete it.
        self.assertEqual(normalize_author("DR"), "DR")
        self.assertEqual(normalize_author(""), "")
        self.assertEqual(normalize_author(None), "")

    def test_distinct_people_not_merged(self):
        # Initials and hyphen-less spellings stay distinct on purpose.
        self.assertNotEqual(normalize_author("J. Yoshida"),
                            normalize_author("Jun-ichi Yoshida"))
        self.assertNotEqual(normalize_author("Junichi Yoshida"),
                            normalize_author("Jun-ichi Yoshida"))

    def test_cjk_and_short_names_untouched(self):
        for raw in ("孙军", "Li", "Hu", "최익"):
            self.assertEqual(normalize_author(raw), raw)


class TestDedupeKeys(unittest.TestCase):
    def test_same_paper_different_sources_share_keys(self):
        a = dedupe_keys("10.1021/x", "Machine learning for catalysis discovery")
        b = dedupe_keys("https://doi.org/10.1021/X",
                        "Machine Learning for Catalysis Discovery")
        self.assertTrue(set(a) & set(b))

    def test_no_doi_falls_back_to_title(self):
        keys = dedupe_keys("", "A sufficiently long paper title about chemistry")
        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0].startswith("title:"))

    def test_short_title_without_doi_gives_no_keys(self):
        self.assertEqual(dedupe_keys("", "Short title"), [])

    def test_stable_paper_id(self):
        self.assertEqual(make_paper_id("10.1/a", "T"), make_paper_id("10.1/A", "other"))
        self.assertNotEqual(make_paper_id("10.1/a", "T"), make_paper_id("10.1/b", "T"))


class TestPaperRoundtrip(unittest.TestCase):
    def test_to_from_dict(self):
        paper = Paper(
            id="abc", title="T", authors=["A"], journal="J", publisher="P",
            published="2026-07-20", year=2026, doi="10.1/x", url="https://x",
            source="test", categories=["Catalysis"], tags=["DFT"],
            relevance_score=88, affiliations=["Uni"], added="2026-07-20")
        self.assertEqual(Paper.from_dict(paper.to_dict()), paper)

    def test_from_dict_ignores_unknown_fields(self):
        d = Paper(
            id="abc", title="T", authors=[], journal="", publisher="",
            published="2026-01-01", year=2026, doi="", url="", source="s",
            categories=[], tags=[], relevance_score=50).to_dict()
        d["future_field"] = "ignored"
        self.assertEqual(Paper.from_dict(d).id, "abc")


if __name__ == "__main__":
    unittest.main()
