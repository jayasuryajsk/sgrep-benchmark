#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:-}"
MODE="${2:-symbols}"
if [[ -z "$REPO_PATH" ]]; then
  echo "Usage: ./benchmark.sh /path/to/repo" >&2
  exit 1
fi

REPO_PATH="$(cd "$REPO_PATH" && pwd)"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$ROOT_DIR/data"
REPORT_DIR="$ROOT_DIR/reports"

mkdir -p "$DATA_DIR" "$REPORT_DIR"

QUERY_SET="$DATA_DIR/queries.jsonl"
RESULT_MIXED="$REPORT_DIR/results_mixed.csv"
RESULT_SEM="$REPORT_DIR/results_semantic.csv"
INDEX_PROFILE="$REPORT_DIR/index_profile.txt"

# Index repo with profiling
( 
  echo "Indexing: $REPO_PATH"
  sgrep index --profile "$REPO_PATH"
) | tee "$INDEX_PROFILE"

# Build query set
python3 "$ROOT_DIR/scripts/build_query_set.py" \
  --repo "$REPO_PATH" \
  --out "$QUERY_SET" \
  --max-items 80 \
  --mode "$MODE"

# Mixed run (semantic if possible, else keyword)
python3 "$ROOT_DIR/scripts/run_benchmark.py" \
  --repo "$REPO_PATH" \
  --queries "$QUERY_SET" \
  --mode mixed \
  --limit 10 \
  --out "$RESULT_MIXED"

# Semantic-only run (only queries with comments)
python3 "$ROOT_DIR/scripts/run_benchmark.py" \
  --repo "$REPO_PATH" \
  --queries "$QUERY_SET" \
  --mode semantic \
  --limit 10 \
  --out "$RESULT_SEM"

echo "Done. Reports in: $REPORT_DIR"
