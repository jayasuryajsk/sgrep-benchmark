# sgrep Benchmark Report (Draft)

## Executive Summary
- Objective: quantify how semantic search (`sgrep`) improves code navigation vs keyword search (`rg`).
- Methods: measured indexing time, search latency, and retrieval quality (Hit@10, MRR) on opencode.
- Result snapshot (opencode, semantic queries from identifiers): `sgrep` Hit@10 0.038 vs `rg` 0.000, MRR 0.029 vs 0.000. Latency p50: 839.47 ms vs 38.97 ms.

## Environment
- Machine: MacBook Pro (M1 Pro, 10 cores, 16 GB RAM)
- OS: macOS 26.3 (Build 25D5101c)
- sgrep: 1.2.1
- ripgrep: 14.1.1

## Dataset
- Repository: opencode (`opencode`)
- Size: 2687 files, ~328,760 LOC
- Languages (by file count): SVG, TypeScript, TSX, JSON, CSS

## Methodology
1) Index repo using `sgrep index --profile`.
2) Auto-generate semantic query set from identifier names:
   - Convert `camelCase` / `snake_case` to words.
   - Prefix with “code for …” to form natural language queries.
3) For each query, run:
   - `sgrep search --json` (ranked results)
   - `rg -F` with the same natural-language query
4) Metrics:
   - Hit@10: target file appears in top 10.
   - MRR: mean reciprocal rank.
   - Latency: per-query median and p95.

## Results
### Indexing
- Index time: 1 second (1162 files, 4410 chunks)
- Index size: not reported by `sgrep`

### Search Quality (Mixed Queries)
- N/A for this run (semantic-only queries).

### Search Quality (Semantic Queries Only)
- sgrep Hit@10: 0.038 (3/80)
- rg Hit@10: 0.000 (0/80)
- sgrep MRR: 0.029
- rg MRR: 0.000

### Latency
- sgrep p50/p95: 839.47 ms / 960.66 ms
- rg p50/p95: 38.97 ms / 56.12 ms

## Limitations
- Auto-generated semantic queries from identifiers are noisy.
- Natural-language queries are not curated or human-validated.
- rg baseline is keyword-only; no semantic matching.
- Ranking method for rg is approximate (match-count based).

## Next Steps
- Add human-written queries + relevance judgments.
- Evaluate comment-derived semantic queries (docstrings / JSDoc).
- A/B agent runs (Codex vs Kaioken) with fixed prompts.
