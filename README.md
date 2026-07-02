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

## Scoring

Each component is an integer from 0 to 3:

- IP openness: higher when no future patent or exclusivity blocks are recorded.
- Route gap: higher when products are injectable-only and lower as route diversity grows.
- Discontinued/fragile: higher when discontinuation is present and sponsor count is low.
- Reformulation white space: higher when route and dosage-form diversity are low.

`score_total` is the sum of the four components. These are screening heuristics,
not legal, regulatory, investment, or medical advice.

## Data layout

- `data/raw/orange_book.zip`: official Orange Book source archive
- `data/raw/drugsatfda.zip`: official Drugs@FDA source archive
- `data/interim/`: parsed intermediate data
- `data/processed/phase1_candidates.csv`: main CSV deliverable
- `db/formulation_rescue.sqlite`: local screening database
- `reports/phase1_summary.md`: generated summary

Source URL, absolute local path, SHA256, file timestamp, and source-specific raw
JSON are retained in the database. Ingredient matching only normalizes case and
whitespace; it intentionally does not merge salts, synonyms, or chemical
equivalents.
