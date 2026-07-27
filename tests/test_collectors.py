"""Tests for collector-level guards against known OpenAlex junk records."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc.collectors.openalex import work_to_record  # noqa: E402


def work(title="A photocatalytic study", doi="10.1039/d0xx00001a",
         journal="Chemical Science"):
    return {
        "display_name": title,
        "doi": f"https://doi.org/{doi}",
        "publication_date": "2024-01-01",
        "authorships": [],
        "primary_location": {"source": {"display_name": journal}},
    }


class TestOpenAlexGuards(unittest.TestCase):
    def test_normal_work_converts(self):
        self.assertIsNotNone(work_to_record(work(), "openalex"))

    def test_peer_review_report_dropped(self):
        w = work(title='Review for "A photocatalytic study"',
                 doi="10.1039/d3sc02440g/v1/review1")
        self.assertIsNone(work_to_record(w, "openalex"))

    def test_decision_letter_and_author_response_dropped(self):
        for doi in ("10.1039/d4sc00692e/v3/decision1",
                    "10.1039/d5cc05586e/v2/response1"):
            self.assertIsNone(work_to_record(work(doi=doi), "openalex"))

    def test_osti_record_with_foreign_doi_dropped(self):
        # Corrupted OpenAlex merge: OSTI metadata carrying another
        # publisher's DOI (and that paper's abstract).
        w = work(journal="OSTI OAI (U.S. Department of Energy Office of "
                         "Scientific and Technical Information)",
                 doi="10.1002/chem.202201290")
        self.assertIsNone(work_to_record(w, "openalex"))

    def test_osti_record_with_own_doi_kept(self):
        w = work(journal="OSTI OAI (U.S. Department of Energy Office of "
                         "Scientific and Technical Information)",
                 doi="10.2172/1234567")
        self.assertIsNotNone(work_to_record(w, "openalex"))


if __name__ == "__main__":
    unittest.main()
