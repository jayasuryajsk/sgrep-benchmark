# sgrep benchmark for Codex-Kaioken

This repo contains a reproducible benchmark showing how sgrep (semantic search) improves Codex-Kaioken code exploration versus an rg + file-read workflow.

At a glance (opencode repo, 8 queries, 3 runs median):

| Metric (per-query) | sgrep | rg | delta |
| --- | --- | --- | --- |
| Tool calls | 1.00 | 4.88 | -79.5% |
| Tokens | 10,575 | 70,508 | -85.0% |
| End-to-end latency | 9.9s | 72.3s | -86.3% |

Same-session sanity check (8 queries, single thread):

| Metric (total) | sgrep | rg | delta |
| --- | --- | --- | --- |
| Tool calls | 8 | 18 | -55.6% |
| Tokens | 56,646 | 593,259 | -90.5% |
| End-to-end latency | 50.6s | 1,219.5s (~20.3m) | -95.9% |

Accuracy (50-query gold set, 3 runs median):

| Metric | sgrep | rg |
| --- | --- | --- |
| Hit@10 (keyword-like) | 0.38 | 0.36 |
| MRR (keyword-like) | 0.279 | 0.108 |
| Hit@10 (semantic) | 0.30 | 0.22 |
| MRR (semantic) | 0.221 | 0.083 |

Full report: `reports/SGREP_REPORT.md`

## What is included
- Benchmark scripts under `scripts/`
- Gold query set under `reports/gold_queries.jsonl`
- Results and summaries under `reports/`

Note: The target codebase (opencode) is not included in this repo.

## How to run
Prereqs:
- sgrep installed and indexed
- ripgrep installed
- codex-kaioken installed and configured (for tool-call benchmarks)

Commands:

1) Build a gold query set
```
python3 scripts/build_query_set.py /path/to/repo
```

2) Run accuracy benchmarks
```
python3 scripts/run_gold_benchmark.py /path/to/repo
```

3) Run Codex tool-call benchmarks (per-query sessions)
```
python3 scripts/codex_toolcall_benchmark.py /path/to/repo
```

4) Run Codex tool-call benchmark (single session)
```
python3 scripts/codex_toolcall_benchmark_session.py /path/to/repo sgrep
python3 scripts/codex_toolcall_benchmark_session.py /path/to/repo rg
```

## Notes
- Benchmark date: 2026-02-01
- Environment: MacBook Pro (M1 Pro, 10 cores, 16 GB RAM), macOS 26.3
- sgrep: 1.2.1, ripgrep: 14.1.1

