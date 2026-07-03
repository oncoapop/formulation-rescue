# Formulation Rescue

Reproducible formulation-rescue screening database built from the public FDA
Orange Book and Drugs@FDA downloadable data files.

The implementation provides:

- validated download of the current Orange Book ZIP;
- ingestion of Orange Book tilde-delimited tables and Drugs@FDA tab-delimited tables;
- a normalized SQLite schema with source provenance and raw JSON fields;
- idempotent source merging on application type/number and product number;
- transparent, deterministic candidate scoring;
- an `argparse` command-line interface;
- CSV and Markdown summary export;
- offline tests using representative FDA-format fixture files.

## Setup

Python 3.10 or newer is required. Runtime code has no third-party dependencies.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

Commands can also be run from a checkout without installation:

```bash
PYTHONPATH=src python3 -m formulation_rescue.cli --help
```

## CLI

```bash
PYTHONPATH=src python3 -m formulation_rescue.cli init-db
PYTHONPATH=src python3 -m formulation_rescue.cli download-orange-book
PYTHONPATH=src python3 -m formulation_rescue.cli ingest-orange-book
PYTHONPATH=src python3 -m formulation_rescue.cli ingest-drugs-fda
PYTHONPATH=src python3 -m formulation_rescue.cli score-phase1
PYTHONPATH=src python3 -m formulation_rescue.cli export-phase1-csv
PYTHONPATH=src python3 -m formulation_rescue.cli run-phase1
```

`download-orange-book` writes only to `data/raw/orange_book.zip` by default and
validates that the archive contains `products.txt`, `patent.txt`, and
`exclusivity.txt`. It never extracts or overwrites raw source contents.

FDA does not define a separate download command for Drugs@FDA in this CLI.
Download the official ZIP to this exact path:

```text
data/raw/drugsatfda.zip
```

The default full run downloads Orange Book when it is absent, requires the
Drugs@FDA ZIP above, ingests both archives, scores candidates, and creates both
deliverables. Existing archives can be selected explicitly:

```bash
PYTHONPATH=src python3 -m formulation_rescue.cli run-phase1 \
  --orange-book data/raw/orange_book.zip \
  --drugs-fda data/raw/drugsatfda.zip
```

Ingestion also accepts a directory containing the corresponding extracted text
tables, which is useful for offline testing. Both ingesters can be rerun without
duplicating database records.

## Database upgrades and snapshot behavior

`init-db` and every ingestion command apply additive schema upgrades
automatically. The derived `phase1_candidates` table is recreated when its
schema changes and must then be regenerated with `score-phase1`; raw FDA tables
are not discarded.

Product observations are retained by source snapshot so Orange Book and
Drugs@FDA disagreements remain visible. On refresh, observations from the prior
snapshot are marked inactive. Patent and exclusivity rows use
`ip_active_in_latest_snapshot`, `ip_first_seen_at`, and `ip_last_seen_at`;
records absent from the newest Orange Book snapshot are retired rather than
used for current scoring.

Ingredient-strength pairs are stored only when a single- or multi-ingredient
mapping is structurally unambiguous. Otherwise, the original ingredient and
strength strings are retained with an ambiguity flag.

## Scoring

Each component is an integer from 0 to 3:

- IP openness: higher when no future patent or exclusivity blocks are recorded.
- Route gap: higher when products are injectable-only and lower as route diversity grows.
- Discontinued/fragile: higher when discontinuation is present and sponsor count is low.
- Reformulation white space: higher when route and dosage-form diversity are low.

`score_total` is the sum of the four components. These are screening heuristics,
not legal, regulatory, investment, or medical advice.

Missing patent/exclusivity evidence is scored as unknown rather than as proof
of IP openness. Marketing-status scoring distinguishes all-products-
discontinued candidates from ingredients that still have active products.
Route-gap and dosage-form diversity use separate evidence to reduce correlated
double-counting. Each candidate also includes a data-completeness score and a
high/medium/low confidence label.

## Data layout

- `data/raw/orange_book.zip`: official Orange Book source archive
- `data/raw/drugsatfda.zip`: official Drugs@FDA source archive
- `data/interim/`: parsed intermediate data
- `data/processed/phase1_candidates.csv`: main CSV deliverable
- `data/processed/phase1_candidates_science_review.csv`: filtered scientific
  review queue
- `db/formulation_rescue.sqlite`: local screening database
- `reports/phase1_summary.md`: generated summary

Source URL, absolute local path, SHA256, file timestamp, and source-specific raw
JSON are retained in the database. Ingredient matching only normalizes case and
whitespace; it intentionally does not merge salts, synonyms, or chemical
equivalents.

## Phase 2.2 triage classification

Every candidate remains in `phase1_candidates.csv`. Deterministic rules add a
triage class/subclass, exclusion flag and reason, and science-review priority.
Rules use ingredient names, canonical route/form evidence, and application
types. Specific evidence takes precedence over broad name rules; for example,
calcium metrizoate is classified as contrast rather than as a mineral, and
iodinated I-131 albumin is classified as a radiopharmaceutical rather than as
an albumin product.

The science-review CSV removes only rows with
`exclude_from_top_science_review=1`. Controlled-substance and obsolete-
antibiotic classes remain in that review queue with moderated priority.
Classification is a reproducible screening aid, not a pharmacologic or
regulatory determination.

## Phase 3A DailyMed enrichment

DailyMed enrichment uses the public v2 SPL service and a per-ingredient cache
under `data/raw/dailymed/`. Metadata searches and selected raw SPL XML labels
are retained for reproducibility. Cached matches and no-matches are not
downloaded again unless `--refresh` is supplied.

```bash
PYTHONPATH=src python3 -m formulation_rescue.cli download-dailymed-labels --limit 100
PYTHONPATH=src python3 -m formulation_rescue.cli ingest-dailymed-labels
PYTHONPATH=src python3 -m formulation_rescue.cli score-label-burden
PYTHONPATH=src python3 -m formulation_rescue.cli export-scientific-rescue-signals
```

Omit `--limit` to process the complete science-review CSV. The downloader is
deliberately resumable; bounded passes can be increased without repeating
cached requests. Outputs are:

- `data/processed/phase3_label_enriched_candidates.csv`
- `data/processed/top_scientific_rescue_signals.csv`
- `reports/phase3_label_enrichment_summary.md`

The shortlist requires a high/exact label match and at least one extracted
administration, safety, formulation-handling, or pediatric burden signal.
Keyword evidence is hypothesis generation only and requires scientific review
against the original label and relevant product presentation.

### Scheduled DailyMed batches

`scripts/run_dailymed_batch.sh` processes the next 100 uncached candidates,
waits 0.5 seconds between candidates, then ingests, scores, and regenerates the
Phase 3 outputs. It exits cleanly after every candidate has a cached matched or
no-match manifest.

`cron/dailymed-batch.cron` is an install-ready example that runs one batch
hourly at minute 17. It uses `flock` to prevent overlapping runs and writes its
log to `data/interim/dailymed_batch.log`. The cron definition is not installed
automatically.

The runner can be checked without network access:

```bash
DRY_RUN=1 scripts/run_dailymed_batch.sh
```

Batch size and request delay can be overridden through `BATCH_SIZE` and
`REQUEST_DELAY_SECONDS`.
