# sgrep Evaluation Report (opencode)

## Executive Summary
- **Efficiency:** Across 3 real Codex‑Kaioken CLI runs (8 queries each), sgrep reduced tool calls from **4.88 → 1.0** per query (‑79.5%), total tokens from **~70,508 → ~10,575** (‑85.0%), and end‑to‑end latency from **~72.3s → ~9.9s** (‑86.3%) — median values across runs.
- **Accuracy (Gold set):** On a **50‑query, line‑verified** gold set (3 runs each), sgrep shows **higher MRR** than rg in both keyword‑like and semantic‑paraphrase variants. Hit@10 is slightly higher for sgrep overall, especially on semantic paraphrases.

## Environment
- Machine: MacBook Pro (M1 Pro, 10 cores, 16 GB RAM)
- OS: macOS 26.3 (Build 25D5101c)
- sgrep: 1.2.1
- ripgrep: 14.1.1
- Repo: opencode (local path omitted; repo not included) — 2,687 files, ~328,760 LOC

## Part A: Tool‑Call Efficiency (Codex‑Kaioken CLI logs)
**Method**
- 8 real exploration queries, repeated 3 times.
- Run A: forced `semantic_search` (sgrep) only.
- Run B: forced `rg` + `sed` workflow.
- Parsed `~/.codex/sessions/...jsonl` for `function_call` events and total token counts.

**Results (median averages per query across 3 runs)**
- Tool calls: **sgrep 1.0** vs **rg 4.88** (‑79.5%)
- Tokens: **sgrep ~10,575** vs **rg ~70,508** (‑85.0%)
- End‑to‑end latency: **sgrep ~9.9s** vs **rg ~72.3s** (‑86.3%)

Artifacts:
- `reports/codex_toolcall_comparison_run1.json`
- `reports/codex_toolcall_comparison_run2.json`
- `reports/codex_toolcall_comparison_run3.json`
- `reports/codex_toolcall_summary.json`

**Same‑session check (single thread, 8 queries in one run)**
- Tool calls (total): **sgrep 8** vs **rg 18** (‑55.6%)
- Tokens (total): **sgrep 56,646** vs **rg 593,259** (‑90.5%)
- End‑to‑end latency (total): **sgrep 50.6s** vs **rg 1,219.5s (~20.3m)** (‑95.9%)

Artifacts:
- `reports/codex_toolcall_session_sgrep.json`
- `reports/codex_toolcall_session_rg.json`
- `reports/codex_toolcall_session_summary.json`

## Part B: Accuracy on a Gold Query Set
**Gold set**
- 50 natural‑language queries with verified ground‑truth files/line ranges.
- Files: `reports/gold_queries.jsonl`, review list in `reports/gold_queries_review.md`.

**Evaluation**
- sgrep: `sgrep search --json` top‑10 results.
- rg baseline: keyword‑extracted ripgrep (top 3 keywords) + file match counts.

### B1) Keyword‑like queries (direct terms) — median of 3 runs
- sgrep Hit@10: **0.38**, MRR: **0.279**, p50 latency: **~836 ms**
- rg Hit@10: **0.36**, MRR: **0.108**, p50 latency: **~118 ms**

### B2) Semantic paraphrases (reworded, fewer exact tokens) — median of 3 runs
- sgrep Hit@10: **0.30**, MRR: **0.221**, p50 latency: **~858 ms**
- rg Hit@10: **0.22**, MRR: **0.083**, p50 latency: **~118 ms**

Artifacts:
- `reports/gold_results_run1.csv`
- `reports/gold_results_run2.csv`
- `reports/gold_results_run3.csv`
- `reports/gold_results_sem_run1.csv`
- `reports/gold_results_sem_run2.csv`
- `reports/gold_results_sem_run3.csv`
- `reports/gold_summary.json`

## Interpretation
- **Efficiency gains are clear and measurable.** sgrep collapses multi‑step grep+read flows into a single call and reduces tokens significantly.
- **Accuracy is mixed on keyword‑heavy queries, but sgrep ranks relevant files higher (MRR).**
- **On semantic paraphrases, sgrep outperforms rg (higher Hit@10 + MRR).**

## Limitations / Next Steps
- Expand gold set to 75–100 queries across more subsystems.
- Add human‑authored queries from real developer tasks.
- Measure accuracy *and* time‑to‑answer in interactive runs.
