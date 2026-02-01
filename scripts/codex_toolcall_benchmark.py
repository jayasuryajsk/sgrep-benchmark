#!/usr/bin/env python3
"""Run Codex-Kaioken CLI benchmarks for tool-call counts with/without sgrep."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CODEX = "codex-kaioken"
SESSIONS_DIR = Path.home() / ".codex" / "sessions"

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


@dataclass
class RunResult:
    query: str
    mode: str
    thread_id: str
    session_path: str
    tool_calls_total: int
    tool_calls_by_name: Dict[str, int]
    total_tokens: int
    latency_ms: float


def run_codex(query: str, repo: Path, mode: str) -> Tuple[str, float]:
    if mode == "sgrep":
        prompt = (
            "Find: " + query + ". "
            "Use the semantic_search tool exactly once. "
            "Do not run any shell commands and do not read files. "
            "Return top 3 file paths."
        )
    else:
        prompt = (
            "Find: " + query + ". "
            "Do NOT use semantic_search or sgrep. "
            "Use rg to search for relevant keywords in *.ts and *.tsx (2-3 rg commands). "
            "Then read up to 3 files with sed -n '1,160p'. "
            "Return top 3 file paths."
        )

    cmd = [
        CODEX,
        "exec",
        "--json",
        "-s",
        "read-only",
        "-C",
        str(repo),
        prompt,
    ]
    start = time.perf_counter()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        raise RuntimeError(f"codex-kaioken failed: {proc.stderr.strip()}")

    thread_id = None
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "thread.started":
            thread_id = obj.get("thread_id")
            break
    if not thread_id:
        raise RuntimeError("Could not find thread_id in codex output.")
    return thread_id, elapsed


def find_session_file(thread_id: str) -> Path:
    matches = list(SESSIONS_DIR.rglob(f"*{thread_id}*.jsonl"))
    if not matches:
        raise RuntimeError(f"Session log not found for thread {thread_id}")
    # Pick most recent
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def parse_session(path: Path) -> Tuple[int, Dict[str, int], int]:
    tool_calls = 0
    tool_names: Dict[str, int] = {}
    total_tokens = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload") or {}
            if payload.get("type") == "function_call":
                tool_calls += 1
                name = payload.get("name", "unknown")
                tool_names[name] = tool_names.get(name, 0) + 1
            if payload.get("type") == "token_count":
                info = payload.get("info") or {}
                total = info.get("total_token_usage")
                if total and isinstance(total, dict):
                    total_tokens = max(total_tokens, int(total.get("total_tokens", 0)))
    return tool_calls, tool_names, total_tokens


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: codex_toolcall_benchmark.py /path/to/repo")
        return 1
    repo = Path(sys.argv[1]).resolve()
    if not repo.exists():
        print(f"Repo not found: {repo}")
        return 1

    results: List[RunResult] = []
    for mode in ("sgrep", "rg"):
        for query in QUERIES:
            thread_id, elapsed = run_codex(query, repo, mode)
            session_path = find_session_file(thread_id)
            tool_calls, tool_names, total_tokens = parse_session(session_path)
            results.append(
                RunResult(
                    query=query,
                    mode=mode,
                    thread_id=thread_id,
                    session_path=str(session_path),
                    tool_calls_total=tool_calls,
                    tool_calls_by_name=tool_names,
                    total_tokens=total_tokens,
                    latency_ms=round(elapsed, 2),
                )
            )

    # Summaries
    summary = {}
    for mode in ("sgrep", "rg"):
        subset = [r for r in results if r.mode == mode]
        if not subset:
            continue
        avg_calls = sum(r.tool_calls_total for r in subset) / len(subset)
        avg_tokens = sum(r.total_tokens for r in subset) / len(subset) if subset else 0
        summary[mode] = {
            "queries": len(subset),
            "avg_tool_calls": round(avg_calls, 2),
            "avg_total_tokens": int(avg_tokens),
        }

    out = {
        "repo": str(repo),
        "queries": QUERIES,
        "results": [r.__dict__ for r in results],
        "summary": summary,
    }

    out_path = Path("reports/codex_toolcall_comparison.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
