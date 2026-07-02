# AGENTS.md — formulation-rescue project

## Working directory

/home/openclaw/openclaw-projects/formulation-rescue

## Project purpose

Build a reproducible Phase 1 screening database for drug formulation-rescue opportunities using public FDA data.

Phase 1 covers:
- FDA Orange Book
- Drugs@FDA
- active ingredients
- approved products
- patents
- exclusivities
- basic formulation/opportunity flags
- SQLite database
- CSV export

## Safety rules

- Do not read /home/dyap/.secrets.
- Do not read, print, copy, or store secrets, tokens, OAuth credentials, API keys, browser cookies, or private keys.
- Do not write Google Drive, OpenAI, Gmail, or rclone credentials into this repository.
- Do not modify /etc/fstab.
- Do not mount, unmount, format, repartition, or perform privileged storage operations.
- Do not use sudo.
- Do not delete files outside this project directory.
- Do not run destructive rclone sync commands.
- Google Drive mirroring must be documented only; Damian will configure and run rclone manually.

## Allowed actions inside this project directory

- create directories
- write Python files
- write Markdown files
- write SQL files
- create SQLite database files
- write CSV files
- run pytest
- run Python scripts
- inspect project files
- download public FDA data files into data/raw/ only, after user approval

## Preferred stack

- Python 3
- SQLite
- pandas
- requests
- pytest
- argparse CLI
- no web framework for Phase 1

## Required project structure

README.md
pyproject.toml
.gitignore
.env.example
Makefile
data/raw/
data/interim/
data/processed/
db/schema.sql
db/formulation_rescue.sqlite
src/formulation_rescue/
reports/phase1_summary.md
tests/

## Required CLI commands

python -m formulation_rescue.cli init-db
python -m formulation_rescue.cli download-orange-book
python -m formulation_rescue.cli ingest-orange-book
python -m formulation_rescue.cli ingest-drugs-fda
python -m formulation_rescue.cli score-phase1
python -m formulation_rescue.cli export-phase1-csv
python -m formulation_rescue.cli run-phase1

## Main deliverables

data/processed/phase1_candidates.csv
reports/phase1_summary.md

The CSV must include:
- ingredient_name
- product_count
- sponsor_count
- route_diversity_count
- dosage_form_diversity_count
- latest_patent_expiry
- latest_exclusivity_expiry
- has_discontinued_product
- has_iv_only_or_injectable_only
- score_ip_openness
- score_route_gap
- score_discontinued_or_fragile
- score_reformulation_white_space
- score_total
- phase1_notes

## Coding rules

- Keep functions small and testable.
- Preserve raw source records as JSON where practical.
- Keep original downloaded files in data/raw/.
- Record source file URL, local path, SHA256 hash, and download time.
- Do not over-merge ambiguous ingredient names.
- Make scoring transparent and reproducible.
- Tests must not require internet access.
- This database is screening only, not legal, regulatory, investment, or medical advice.
