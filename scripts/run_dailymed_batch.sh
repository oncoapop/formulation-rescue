#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/openclaw/openclaw-projects/formulation-rescue"
INPUT_CSV="${INPUT_CSV:-$PROJECT_ROOT/data/processed/phase1_candidates_science_review.csv}"
RAW_DIR="${RAW_DIR:-$PROJECT_ROOT/data/raw/dailymed}"
BATCH_SIZE="${BATCH_SIZE:-100}"
REQUEST_DELAY_SECONDS="${REQUEST_DELAY_SECONDS:-0.5}"
PYTHON="${PYTHON:-/usr/bin/python3}"

cd "$PROJECT_ROOT"

if [[ ! -f "$INPUT_CSV" ]]; then
    echo "error: science-review input not found: $INPUT_CSV" >&2
    exit 1
fi

if ! [[ "$BATCH_SIZE" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: BATCH_SIZE must be a positive integer" >&2
    exit 1
fi

total_candidates=$(( $(wc -l < "$INPUT_CSV") - 1 ))
cached_candidates=0
if [[ -d "$RAW_DIR" ]]; then
    cached_candidates=$(find "$RAW_DIR" -mindepth 2 -maxdepth 2 \
        -name manifest.json -type f | wc -l)
fi

if (( cached_candidates >= total_candidates )); then
    echo "DailyMed enrichment complete: cached=$cached_candidates total=$total_candidates"
    exit 0
fi

next_limit=$(( cached_candidates + BATCH_SIZE ))
if (( next_limit > total_candidates )); then
    next_limit=$total_candidates
fi

echo "Starting DailyMed batch: cached=$cached_candidates target=$next_limit total=$total_candidates"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "DRY_RUN: limit=$next_limit delay=$REQUEST_DELAY_SECONDS"
    exit 0
fi

export PYTHONPATH="$PROJECT_ROOT/src"

"$PYTHON" -m formulation_rescue.cli download-dailymed-labels \
    --input "$INPUT_CSV" \
    --raw-dir "$RAW_DIR" \
    --limit "$next_limit" \
    --delay "$REQUEST_DELAY_SECONDS"

"$PYTHON" -m formulation_rescue.cli ingest-dailymed-labels \
    --raw-dir "$RAW_DIR"
"$PYTHON" -m formulation_rescue.cli score-label-burden
"$PYTHON" -m formulation_rescue.cli export-scientific-rescue-signals

new_cached=$(find "$RAW_DIR" -mindepth 2 -maxdepth 2 \
    -name manifest.json -type f | wc -l)
echo "Completed DailyMed batch: cached=$new_cached total=$total_candidates"
