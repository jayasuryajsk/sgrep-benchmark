#!/usr/bin/env python3
"""Run Codex-Kaioken CLI in a single session for multiple queries and summarize tool calls/tokens."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

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


def build_prompt(preset: str, mode: str) -> str:
    items = "\n".join([f"{i+1}. {q}" for i, q in enumerate(QUERIES)])
    if preset == "forced" and mode == "sgrep":
        return (
            "Answer the following queries in order.\n"
            "Rules: For EACH query, use the semantic_search tool exactly once. "
            "Do not run any shell commands and do not read files. "
            "Return top 3 file paths for each query.\n\n"
            f"Queries:\n{items}\n\n"
            "Output format:\n"
            "Q1: <path1>, <path2>, <path3>\n"
            "Q2: ..."
        )
    if preset == "forced" and mode == "rg":
        return (
            "Answer the following queries in order.\n"
            "Rules: For EACH query, do NOT use semantic_search or sgrep. "
            "Use rg to search in *.ts and *.tsx (2-3 rg commands). "
            "Then read up to 3 files with sed -n '1,160p'. "
            "Return top 3 file paths for each query.\n\n"
            f"Queries:\n{items}\n\n"
            "Output format:\n"
            "Q1: <path1>, <path2>, <path3>\n"
            "Q2: ..."
        )
    if preset == "natural" and mode == "sgrep_rg":
        return (
            "Answer the following queries in order.\n"
            "Rules: Prefer semantic_search first if available, then use rg or read files only if needed. "
            "Do not edit files. Keep tool calls minimal. "
            "Return only the most relevant file paths for each query.\n\n"
            f"Queries:\n{items}\n\n"
            "Output format:\n"
            "Q1: <paths>\n"
            "Q2: ..."
        )
    if preset == "natural" and mode == "rg_only":
        return (
            "Answer the following queries in order.\n"
            "Rules: Do NOT use semantic_search or sgrep. Use rg and read files as needed. "
            "Do not edit files. Keep tool calls minimal. "
            "Return only the most relevant file paths for each query.\n\n"
            f"Queries:\n{items}\n\n"
            "Output format:\n"
            "Q1: <paths>\n"
            "Q2: ..."
        )
    raise ValueError("invalid preset/mode")


def run_codex(prompt: str, repo: Path) -> Tuple[str, float]:
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
    if len(sys.argv) < 4:
        print("Usage: codex_toolcall_benchmark_session.py /path/to/repo <forced|natural> <mode>")
        return 1
    repo = Path(sys.argv[1]).resolve()
    preset = sys.argv[2]
    mode = sys.argv[3]
    if preset not in {"forced", "natural"}:
        print("preset must be forced or natural")
        return 1
    if preset == "forced" and mode not in {"sgrep", "rg"}:
        print("mode must be sgrep or rg for forced preset")
        return 1
    if preset == "natural" and mode not in {"sgrep_rg", "rg_only"}:
        print("mode must be sgrep_rg or rg_only for natural preset")
        return 1

    prompt = build_prompt(preset, mode)
    thread_id, elapsed = run_codex(prompt, repo)
    session_path = find_session_file(thread_id)
    tool_calls, tool_names, total_tokens = parse_session(session_path)

    out = {
        "repo": str(repo),
        "preset": preset,
        "mode": mode,
        "queries": QUERIES,
        "thread_id": thread_id,
        "session_path": str(session_path),
        "tool_calls_total": tool_calls,
        "tool_calls_by_name": tool_names,
        "total_tokens": total_tokens,
        "latency_ms": round(elapsed, 2),
        "avg_tool_calls_per_query": round(tool_calls / len(QUERIES), 2),
        "avg_tokens_per_query": int(total_tokens / len(QUERIES)) if len(QUERIES) else 0,
        "avg_latency_ms_per_query": round(elapsed / len(QUERIES), 2) if len(QUERIES) else 0,
    }

    out_path = Path(f"reports/codex_toolcall_session_{mode}.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
