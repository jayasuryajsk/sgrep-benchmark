#!/usr/bin/env python3
"""
Tool Calls Comparison: sgrep vs iterative grep
Shows how many operations needed to find relevant code
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

DEFAULT_SGREP = os.environ.get("SGREP_PATH", "sgrep")
DEFAULT_CODEBASE = os.environ.get("CODEBASE", str(Path.cwd()))

# Real exploration queries a developer would ask
QUERIES = [
    "where is the websocket connection handled",
    "how does the authentication flow work",
    "where are API routes defined",
    "how is state management implemented",
    "where is the database schema defined",
    "how are errors handled globally",
    "where is the main entry point",
    "how does the caching layer work",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare sgrep vs iterative grep tool calls.")
    parser.add_argument("--repo", default=DEFAULT_CODEBASE, help="Path to the target codebase.")
    parser.add_argument("--sgrep", default=DEFAULT_SGREP, help="Path to sgrep binary.")
    return parser.parse_args()


args = parse_args()
SGREP = os.path.expanduser(args.sgrep)
CODEBASE = os.path.expanduser(args.repo)

print("=" * 70)
print("TOOL CALLS COMPARISON: sgrep vs Iterative Grep")
print("=" * 70)
print(f"Codebase: {CODEBASE}")
print(f"Queries: {len(QUERIES)}")
print()

results = []

for i, query in enumerate(QUERIES, 1):
    print(f"\n[{i}] \"{query}\"")
    print("-" * 60)
    
    # === METHOD 1: sgrep (1 call) ===
    start = time.time()
    result = subprocess.run(
        [SGREP, "search", "--json", "--limit", "5", query],
        capture_output=True, text=True, timeout=60, cwd=CODEBASE
    )
    sgrep_time = (time.time() - start) * 1000
    
    sgrep_files = []
    if result.returncode == 0:
        resp = json.loads(result.stdout)
        for r in resp.get("results", []):
            path = r.get("path", "").replace(CODEBASE + "/", "")
            sgrep_files.append(path)
    
    print(f"  SGREP (1 call, {sgrep_time:.0f}ms):")
    print(f"    → {sgrep_files[:3]}")
    
    # === METHOD 2: Simulate iterative grep (what model does) ===
    # Extract keywords from query
    stopwords = {"where", "is", "the", "how", "does", "are", "what", "a", "an", "to", "of", "in", "for", "with"}
    keywords = [w.lower() for w in query.split() if w.lower() not in stopwords and len(w) > 2]
    
    grep_calls = 0
    grep_files = set()
    grep_start = time.time()
    
    # Simulate: grep for each keyword, narrow down
    for kw in keywords[:3]:
        grep_calls += 1
        result = subprocess.run(
            ["grep", "-r", "-l", "-i", kw, "--include=*.ts", "--include=*.tsx", "--include=*.go", "."],
            capture_output=True, text=True, timeout=30, cwd=CODEBASE
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        grep_files.update(files[:20])
    
    # Simulate: would need to read files to verify (more calls)
    read_calls = min(len(grep_files), 5)  # Model would read top 5
    total_grep_calls = grep_calls + read_calls
    grep_time = (time.time() - grep_start) * 1000
    
    print(f"  GREP ({total_grep_calls} calls, {grep_time:.0f}ms):")
    print(f"    → {grep_calls} grep + {read_calls} read calls")
    print(f"    → Found {len(grep_files)} candidate files (noisy)")
    
    # === COMPARISON ===
    savings = total_grep_calls - 1
    print(f"  SAVINGS: {savings} fewer tool calls with sgrep")
    
    results.append({
        "query": query,
        "sgrep": {"calls": 1, "time_ms": sgrep_time, "files": sgrep_files[:5]},
        "grep": {"calls": total_grep_calls, "time_ms": grep_time, "candidate_files": len(grep_files)},
        "savings": savings
    })

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

total_sgrep_calls = len(QUERIES)  # 1 call per query
total_grep_calls = sum(r["grep"]["calls"] for r in results)
avg_savings = sum(r["savings"] for r in results) / len(results)

print(f"""
                        SGREP       GREP (iterative)
Total tool calls:       {total_sgrep_calls}           {total_grep_calls}
Avg calls per query:    1.0         {total_grep_calls/len(QUERIES):.1f}
Avg savings:            {avg_savings:.1f} fewer calls per query

ESTIMATED TOKEN SAVINGS:
- Each grep call ~50 tokens (command + output)
- Each read call ~500 tokens (file content)
- sgrep returns focused results ~200 tokens

Per query savings: ~{int(avg_savings * 300)} tokens
For 100 queries: ~{int(avg_savings * 300 * 100):,} tokens saved
""")

# Save
OUT_PATH = os.path.expanduser("reports/tool_calls_comparison.json")
with open(OUT_PATH, "w") as f:
    json.dump({
        "summary": {
            "total_sgrep_calls": total_sgrep_calls,
            "total_grep_calls": total_grep_calls,
            "avg_savings_per_query": avg_savings,
            "estimated_tokens_saved_per_query": int(avg_savings * 300)
        },
        "results": results
    }, f, indent=2)
print(f"Results saved to {OUT_PATH}")
