# PhotocatalysisPapers

A fully automated, continuously updated public index of **photocatalysis
research papers** — water splitting, hydrogen evolution, CO2 photoreduction,
pollutant degradation, photoredox & organic synthesis, semiconductor
photocatalysts, Z-scheme systems, photoelectrochemistry and solar fuels.
Experimental, computational (DFT) and machine-learning studies are all in
scope; neighbouring fields (photovoltaics, LEDs, photodynamic therapy) are
filtered out.

Sister project of
[DataDrivenChemistryPapers](https://github.com/GuruprakashMP/ddc-papers) —
same architecture, different scientific scope.

* **No papers are hosted.** Only bibliographic metadata (title, authors,
  journal, date, DOI, link); every card links to the original publisher.
* **Zero dependencies.** Standard-library Python; JSON + static HTML,
  perfect for GitHub Pages.
* **Fully automatic.** A GitHub Actions workflow collects, deduplicates,
  classifies, rebuilds the site and commits — every day.

## Quick start (local)

```bash
cd photocatalysis_papers
# Windows:  set PYTHONPATH=src        PowerShell:  $env:PYTHONPATH="src"
export PYTHONPATH=src

python -m ddc run            # collect + rebuild the website
python -m ddc run --days 7   # look further back
python -m ddc backfill --from 1972   # historical harvest (year batches!)
python -m ddc build          # rebuild website only
python -m ddc stats          # index statistics
python -m unittest discover -s tests

python -m http.server 8761   # then open http://localhost:8761
```

The backfill starts at **1972** — the Honda–Fujishima effect, the birth of
photocatalysis. Run it in year-sized ranges via the "Photocatalysis
historical backfill" GitHub Actions workflow: OpenAlex allows roughly
15–20k record fetches per runner per day, and every workflow run gets a
fresh runner. Each run checkpoints, so interrupting and re-running is safe.

## How papers are selected

A paper is indexed only when **photocatalysis is its primary subject**,
evidenced by unambiguous vocabulary (photocataly…, photoredox, Z-scheme,
photoelectrochemical, photodegradation, artificial photosynthesis, ...).
Supporting terms (materials, target reactions, characterization, DFT, ML)
refine the 0–100 relevance score and assign multiple categories. Papers from
neighbouring photo-fields (solar cells, OLEDs, photodynamic therapy) are
penalised out. Tune the vocabulary in `src/ddc/keywords.py`.

## Sources

Direct: **arXiv**, **ChemRxiv**. Aggregators: **Crossref**, **OpenAlex**,
**PubMed**, **Europe PMC**, **Semantic Scholar**, **DOAJ** — which legally
carry the metadata of every DOI-issuing publisher (ACS, RSC, Wiley, Springer
Nature, Elsevier, MDPI, ...).

## Deploying

1. Push this folder's contents to a public GitHub repository
   (e.g. `photocatalysis-papers`).
2. **Settings → Pages → Deploy from a branch → `main` / root → Save.**
3. Live at `https://<user>.github.io/<repo>/` a minute later; the daily
   workflow keeps it growing with no maintenance.

See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions,
[PROJECT_STATUS.md](PROJECT_STATUS.md) for current state, and
[CHANGELOG.md](CHANGELOG.md) for history.
