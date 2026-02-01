# sgrep Benchmark Harness

This repo runs a quick, repeatable benchmark to compare semantic search (`sgrep`) vs keyword search (`rg`).

## Quick Start
```bash
./benchmark.sh /path/to/repo
```

Outputs:
- `reports/index_profile.txt`
- `reports/results_mixed.csv`
- `reports/results_semantic.csv`
- `reports/REPORT_TEMPLATE.md`

## Notes
- Mixed queries use semantic text when available, otherwise keyword.
- Semantic-only run uses only queries derived from comments.
- You can tune query volume via `--max-items` in `scripts/build_query_set.py`.
