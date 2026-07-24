# Architecture

Design decisions and their rationale. The guiding constraints:
GitHub Pages (static hosting only), GitHub Actions (free CI), zero manual
work, no copyright exposure, easy to extend.

## Pipeline

```
collect (8 sources, isolated)
   ↓
deduplicate  (DOI key + normalized-title key, persisted in seen.json)
   ↓
classify     (keyword model → accept/reject, score, categories, tags)
   ↓
store        (JSON shards data/papers/YYYY/MM.json)
   ↓
generate     (static HTML + per-year JSON for client-side search)
   ↓
commit       (GitHub Actions)
```

## Key decisions

### Standard library only
The pipeline uses `urllib` instead of `requests`, `unittest` instead of
pytest, and string templates instead of Jinja. **Why:** nothing to install
locally or in CI, nothing to break in five years, and the project stays
copy-paste portable. `src/ddc/http.py` wraps urllib with retries, backoff,
gzip and a polite User-Agent.

### Aggregators instead of publisher scraping
ACS/RSC/Wiley/Elsevier/... have no free search APIs and scraping them is
fragile and legally murky. Their metadata is *already* legally distributed by
Crossref, OpenAlex, PubMed, Europe PMC, Semantic Scholar and DOAJ, which we
query instead. Publisher coverage is therefore complete while staying 100 %
legal. Papers keep their true journal/publisher fields; `source` records which
API found them first.

### Metadata only, abstracts are transient
Abstracts are fetched for classification but **never written to disk** —
`Paper` has no abstract field by design. This eliminates copyright risk while
keeping classification quality high.

### Keyword classifier, not an LLM
`keywords.py` + `classify.py` implement a weighted vocabulary model:
ML terms × chemistry terms, with negative terms for off-domain fields
(medicine, finance, generic CS) and a bonus for chemistry venues.
**Why:** free, instant, deterministic, fully explainable, tunable by editing
one file — and it needs no API key, so automation can never silently stop.
Score shape: `20 + 4·min(ml,10) + 3·min(chem,12) + venue − penalties`,
clamped to 0–100; acceptance requires evidence on *both* sides plus the
configurable `min_relevance_score` (default 40).

### Deduplication via a persisted seen-set
`data/state/seen.json` maps `doi:<normalized>` and `title:<sha1>` keys to
paper ids. Two keys catch both re-encounters across sources and
preprint-vs-journal duplicates with different DOIs. O(1) lookups, no database.
If the file is ever lost or corrupted it is rebuilt from the shards.

### JSON sharded by publication month
One file per month (`data/papers/2026/07.json`) keeps daily git diffs small
and files bounded. The site generator writes *separate* compact per-year
shards (`assets/data/papers-YYYY.json`) for the browser, so the stored format
and the served format can evolve independently.

### Hybrid static/client-side site
* **Static HTML** (SEO, works without JS): homepage with the newest papers,
  archive year→month→day, categories, about.
* **Client-side JS** (`assets/app.js`, vanilla): search with filters
  (year, category, journal, source, min-score, sort), author pages
  (`authors.html?a=Name`) and journal pages (`journals.html?j=Name`).
  **Why client-side for authors/journals:** thousands of authors would mean
  tens of thousands of static pages regenerated and committed daily; query-
  param pages give every author/journal a stable URL at zero repo cost.
* All links are **relative**, so the site works at any base path
  (e.g. `/repo/ddc_papers/`).

### Generated site lives at the project root
`index.html` etc. sit next to `src/` and `data/` so that copying the single
`ddc_papers/` folder into a Pages repository is the whole deployment. The
extra served files (`src/`, `tests/`) are harmless.

### Failure isolation
Every collector runs inside try/except in the pipeline; HTTP calls retry with
backoff and treat 429/5xx as transient. A source being down (or rate-limited,
like keyless Semantic Scholar) can never block the daily run.

### Dates
Source APIs occasionally return garbage dates (e.g. year 2035); the pipeline
clamps anything unparseable or more than a year in the future to the ingestion
date. Month-only dates (DOAJ) become the 1st of the month.

### Historical backfill
`backfill.py` complements the forward-looking daily pipeline with a one-time
(but resumable) sweep of the field's history via OpenAlex cursor pagination:
18 broad-recall topic queries per year (precision comes from the classifier,
not the query), plus the complete works of the pioneers in
`config/pioneers.json`. It checkpoints (shards + seen-set) after every query,
so interrupting and re-running is always safe — already-ingested papers are
skipped as duplicates.

### Progressive loading in the browser
`app.js` fetches the manifest, renders as soon as the newest three year-shards
arrive, then streams the remaining years in the background and refreshes
counts/filters when complete. First paint stays fast regardless of index size.

## Extension points

| Want to... | Touch |
|---|---|
| Add a source | new module in `src/ddc/collectors/` + one import + settings |
| Tune relevance | `src/ddc/keywords.py` (vocabulary), `config/settings.json` (threshold) |
| Add a category | add terms mapping to it in `keywords.py` |
| Change look | `src/ddc/site/assets/style.css` |
| Add a page | `src/ddc/site/generator.py` |
