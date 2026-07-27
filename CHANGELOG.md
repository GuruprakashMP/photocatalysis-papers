# Changelog

All notable changes to PhotocatalysisPapers.

## [1.2.0] — 2026-07-27

Recall + integrity release: **208,399 papers** after a verified full
re-sweep. Prompted by real missing papers (modern photoredox/LMCT work
that never says "photocatal…").

### Added
- Photoredox/LMCT vocabulary: PRIMARY terms for ligand-to-metal charge
  transfer, visible-light mediated, organophotocatalysis, eosin-Y
  catalysis; SUPPORT terms for named photocatalysts (eosin, rose bengal,
  4-CzIPN, acridinium, Ru(bpy), Ir(ppy)). Backfill topic queries and the
  daily OpenAlex searches extended to match.
- **Fetch-side checkpoint** (`data/state/backfill_progress.json`):
  completed (year, query) pairs are skipped on re-runs. Without it a
  retry re-fetched everything and always died on the same tail queries —
  large years could never converge.
- Backfill years with any transiently failed query now log
  `INCOMPLETE` instead of `done` (a 429'd query silently lost its
  papers before), and the run summary reports total failed queries.
- Collector guards: transparent-peer-review artifacts (review reports,
  decision letters, author responses — DOIs `…/vN/reviewM|decisionM|
  responseM`) and corrupted OSTI merges are dropped at ingestion.

### Fixed
- Re-swept 1977, 1983, 1989–2007 and 2014–2026 to verified completeness
  (~24k papers recovered from silently-holed sweeps).
- Purged 972 junk records total (peer-review artifacts + corrupt OSTI
  merges, including re-ingested ones predating the guards).

### Known limitations
- OpenAlex throttles in long daily windows (~11:00–05:00 UTC) regardless
  of runner IP; schedule backfills for the ~05:00–11:00 UTC window.
- A paper whose DOI was consumed by a corrupted OpenAlex merge
  (e.g. 10.1002/chem.202201290) has no clean OpenAlex record and cannot
  be recovered from OpenAlex.

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
