# Project Status

_Last updated: 2026-07-25 (historical backfill complete)_

## Completed

- [x] Codebase adapted from the proven ddc-papers architecture (stdlib-only
      pipeline, 8 collectors, JSON storage, static site, daily automation)
- [x] Photocatalysis classifier: PRIMARY terms (photocataly…, photoredox,
      Z-scheme, PEC, photodegradation, plus early-era photolysis-of-water /
      photoelectrolysis vocabulary) required; SUPPORT terms (materials,
      reactions, mechanism, DFT, ML) refine score and categories; NEGATIVE
      terms reject solar cells / LEDs / photodynamic therapy
- [x] 17 photocatalysis categories, alphabetical in all UI dropdowns
- [x] Collector + backfill queries rewritten for photocatalysis
- [x] Pioneers list: Fujishima, Domen, Wang, Li, Ye, Choi, Bahnemann,
      MacMillan, Yoon, König and more (config/pioneers.json)
- [x] Unit tests adapted and passing (32, incl. founding-era regression tests)
- [x] First live pipeline run + relevance inspection (v1.0.0, 319 papers)
- [x] Published: repo `GuruprakashMP/photocatalysis-papers`, GitHub Pages
      live at https://guruprakashmp.github.io/photocatalysis-papers/
- [x] Daily workflow at 05:00 UTC collects, classifies, rebuilds, commits
- [x] **Historical backfill 1972→2026 complete (2026-07-25): 179,456 papers**
      — 41 year-batched workflow runs chained by a monitor script that
      narrowed ranges on quota exhaustion. Year curve is smooth; the 1972
      Honda–Fujishima paper is indexed and shown on Fujishima's author page.
- [x] Data-quality pass: 9 corrupted OpenAlex merges purged (OSTI metadata
      carrying foreign DOIs — see CHANGELOG 1.1.0); early-era classifier
      vocabulary added and years 1972–1988 re-swept

## Ongoing (automatic, no maintenance)

- Daily GitHub Actions run keeps the index growing from 8 sources.

## Known issues (inherited environment quirks)

- Local machine: arXiv fails (missing SSL certs) and ChemRxiv 403s
  (Cloudflare) — both work/degrade gracefully in GitHub Actions.
- Semantic Scholar keyless tier rate-limits; collector skips gracefully.
- OpenAlex quota: ~15–20k record fetches per IP per day; each workflow run
  gets a fresh runner IP. The pioneer sweep alone costs ~15k fetches — never
  bundle it with a topic-year range in one run.
- OpenAlex serves occasional corrupted merges (OSTI repository records with
  a foreign publisher's DOI + abstract). Detection: OSTI journal/publisher
  with a DOI not starting 10.2172. Re-check after any large backfill.

## Possible future work

- Re-ingest the 9 real papers whose DOIs were freed by the purge (they
  return automatically only if a backfill re-runs their publication years).
- Periodic OSTI-corruption audit of newly ingested papers.
