"""Tests for the core filtering rule: photocatalysis as the primary subject."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ddc.classify import classify  # noqa: E402
from ddc.models import RawRecord  # noqa: E402


def record(title: str, abstract: str = "", journal: str = "") -> RawRecord:
    return RawRecord(title=title, abstract=abstract, journal=journal, source="test")


class TestClassify(unittest.TestCase):
    def test_accepts_experimental_photocatalysis(self):
        r = record(
            "Visible-light photocatalytic hydrogen evolution over g-C3N4",
            "Graphitic carbon nitride modified with a Pt cocatalyst shows "
            "enhanced charge separation and hydrogen evolution under visible "
            "light irradiation.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertGreaterEqual(verdict.score, 80)
        self.assertIn("Hydrogen Evolution", verdict.categories)
        self.assertIn("g-C3N4 & Carbon Materials", verdict.categories)

    def test_accepts_dft_photocatalysis(self):
        r = record(
            "First-principles study of band alignment in TiO2 heterojunction "
            "photocatalysts",
            "Density functional theory reveals the band structure and charge "
            "transfer at anatase interfaces relevant to photocatalytic water "
            "splitting.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Computational & DFT", verdict.categories)

    def test_accepts_ml_photocatalysis(self):
        r = record(
            "Machine learning screening of semiconductor photocatalysts for "
            "CO2 reduction",
            "A neural network trained on band gaps accelerates discovery of "
            "photocatalytic CO2 reduction materials.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Machine Learning for Photocatalysis", verdict.categories)

    def test_accepts_photoredox_synthesis(self):
        r = record(
            "Photoredox-catalyzed C-H functionalization of heteroarenes",
            "Visible light photoredox catalysis enables radical cross-coupling "
            "under mild conditions.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Photoredox & Organic Synthesis", verdict.categories)

    def test_rejects_solar_cell_paper(self):
        r = record(
            "High power conversion efficiency perovskite solar cells",
            "We report perovskite solar cells with improved photovoltaic "
            "performance and power conversion efficiency of 26%.")
        verdict = classify(r)
        self.assertTrue(not verdict.accepted or verdict.score < 40)

    def test_rejects_photodynamic_therapy(self):
        r = record(
            "Singlet-oxygen photosensitizers for photodynamic therapy of tumors",
            "Photosensitizers generate reactive oxygen species for cancer "
            "photodynamic therapy and bioimaging.")
        verdict = classify(r)
        self.assertTrue(not verdict.accepted or verdict.score < 40)

    def test_rejects_generic_ml_chemistry(self):
        r = record(
            "Machine learning prediction of molecular properties",
            "Graph neural networks predict solubility and toxicity of organic "
            "molecules.")
        self.assertFalse(classify(r).accepted)

    def test_rejects_thermal_catalysis(self):
        r = record(
            "Heterogeneous catalytic hydrogenation over Pd nanoparticles",
            "Thermal catalytic hydrogenation of alkenes with supported "
            "palladium catalysts.")
        self.assertFalse(classify(r).accepted)

    def test_venue_boosts_score(self):
        base = record("Photocatalytic degradation of tetracycline",
                      "Visible light photocatalysis degrades antibiotics.")
        boosted = record("Photocatalytic degradation of tetracycline",
                         "Visible light photocatalysis degrades antibiotics.",
                         journal="Applied Catalysis B: Environmental")
        self.assertGreater(classify(boosted).score, classify(base).score)

    def test_empty_title_rejected(self):
        self.assertFalse(classify(record("")).accepted)

    def test_score_bounds(self):
        r = record(
            "Z-scheme g-C3N4/TiO2 photocatalyst for solar water splitting and "
            "CO2 photoreduction",
            "photocatalytic hydrogen evolution cocatalyst charge separation "
            "visible light band alignment oxygen vacancies")
        verdict = classify(r)
        self.assertLessEqual(verdict.score, 100)
        self.assertGreaterEqual(verdict.score, 90)

    def test_accepts_honda_fujishima_1972(self):
        # The field's founding paper predates the word "photocatalysis";
        # early-era vocabulary must be enough to index it.
        r = record(
            "Electrochemical Photolysis of Water at a Semiconductor Electrode",
            journal="Nature")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Water Splitting", verdict.categories)

    def test_accepts_lmct_synthesis(self):
        # Modern LMCT photochemistry often never says "photocatal…"
        r = record(
            "Expedient radical phosphonylations via ligand to metal charge "
            "transfer",
            "Efficient radical phosphonylations tailored upon visible-light "
            "mediated LMCT on bismuth.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Photoredox & Organic Synthesis", verdict.categories)

    def test_accepts_eosin_photoredox_without_photo_words(self):
        r = record(
            "A highly diastereoselective one-pot Ugi/radical spirocyclization",
            "Eosin-Y catalyzed radical spirocyclization of post-Ugi adducts "
            "with aryl thiols provided access to complex azaspirotricycles.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)

    def test_accepts_photoelectrolysis_era_paper(self):
        r = record(
            "Photoelectrolysis of water in cells with SrTiO3 anodes",
            "Hydrogen and oxygen are evolved under ultraviolet illumination "
            "without external bias.")
        verdict = classify(r)
        self.assertTrue(verdict.accepted)
        self.assertIn("Photoelectrochemistry", verdict.categories)


if __name__ == "__main__":
    unittest.main()
