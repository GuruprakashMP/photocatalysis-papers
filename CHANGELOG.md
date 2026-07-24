# Changelog

All notable changes to PhotocatalysisPapers.

## [1.0.0] — 2026-07-24

Initial release, adapted from the proven
[DataDrivenChemistryPapers](https://github.com/GuruprakashMP/ddc-papers)
codebase (v1.1 architecture: stdlib-only pipeline, 8 metadata collectors,
resumable OpenAlex backfill, static site with progressive loading).

### Changed from the parent project
- Scope: ALL photocatalysis research (experimental, DFT, ML) instead of
  ML-applied-to-chemistry.
- Classifier: PRIMARY photocatalysis vocabulary required; SUPPORT vocabulary
  (materials, target reactions, mechanism, computational and data-driven
  methods) refines score/categories; NEGATIVE vocabulary rejects
  photovoltaics, LEDs, photodynamic therapy.
- 17 photocatalysis-specific categories.
- All collector and backfill queries rewritten for photocatalysis.
- Pioneers list: Fujishima, Domen, Wang, Li, Ye, Zou, Choi, Bahnemann,
  Kisch, Zhang, Grätzel, Liu, Wang, Zhao, Yu, Shen, MacMillan, Yoon,
  Stephenson, König.
- Backfill default start year: 1972 (Honda–Fujishima effect).
- Site branding: PhotocatalysisPapers.
