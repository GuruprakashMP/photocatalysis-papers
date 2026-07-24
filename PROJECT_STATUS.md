# Project Status

_Last updated: 2026-07-24 (initial adaptation from DataDrivenChemistryPapers)_

## Completed

- [x] Codebase adapted from the proven ddc-papers architecture (stdlib-only
      pipeline, 8 collectors, JSON storage, static site, daily automation)
- [x] Photocatalysis classifier: PRIMARY terms (photocataly…, photoredox,
      Z-scheme, PEC, photodegradation...) required; SUPPORT terms (materials,
      reactions, mechanism, DFT, ML) refine score and categories; NEGATIVE
      terms reject solar cells / LEDs / photodynamic therapy
- [x] 17 photocatalysis categories, alphabetical in all UI dropdowns
- [x] Collector + backfill queries rewritten for photocatalysis
- [x] Pioneers list: Fujishima, Domen, Wang, Li, Ye, Choi, Bahnemann,
      MacMillan, Yoon, König and more (config/pioneers.json)
- [x] Backfill default start year 1972 (Honda–Fujishima effect)
- [x] Unit tests adapted and passing

## Pending

- [ ] First live pipeline run + relevance inspection of accepted titles
- [ ] Publish to GitHub (repo `photocatalysis-papers`) + enable Pages
- [ ] Historical backfill 1972→today in year batches (large: photocatalysis
      is a big field — expect 100k+ papers, i.e. more workflow runs than the
      ddc-papers backfill needed)

## Known issues (inherited environment quirks)

- Local machine: arXiv fails (missing SSL certs) and ChemRxiv 403s
  (Cloudflare) — both work/degrade gracefully in GitHub Actions.
- Semantic Scholar keyless tier rate-limits; collector skips gracefully.
- OpenAlex quota: ~15–20k record fetches per IP per day; run backfill in
  year-sized ranges, one workflow run each.

## Next implementation step

Run `python -m ddc run --days 7`, inspect ~20 accepted titles for relevance,
then publish and start the historical backfill batches.
