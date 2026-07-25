# Changelog

All notable changes to PhotocatalysisPapers.

## [1.1.0] — 2026-07-25

Historical backfill 1972→2026 complete: **179,456 papers** indexed
(from 319), spanning the field's whole history back to the Honda–Fujishima
effect. Driven as 31 + 10 year-batched workflow runs chained by a local
monitor that narrowed ranges automatically whenever a run hit the OpenAlex
daily quota.

### Added
- Early-era PRIMARY vocabulary ("photolysis of water", "photoelectrolysis",
  "photoassisted electrolysis" + variants): the founding papers predate the
  word "photocatalysis" and were being rejected. The 1972 Honda–Fujishima
  Nature paper is now indexed (relevance 49).
- Two early-era backfill topic queries ("photolysis of water",
  "photoelectrolysis"); years 1972–1988 re-swept with them.
- Classifier regression tests for founding-era papers (32 tests total).

### Fixed
- Purged 9 corrupted OpenAlex merge records (OSTI repository metadata
  fused with a different modern paper's DOI and abstract) and freed their
  dedup keys. Detection rule: OSTI journal/publisher + DOI prefix other
  than OSTI's own 10.2172. DOI-less OSTI records are genuine DOE reports
  and were kept.

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
