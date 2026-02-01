#!/usr/bin/env python3
"""Run sgrep vs rg benchmark over a query set."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_queries(path: Path) -> List[Dict[str, Any]]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    elapsed = (time.perf_counter() - start) * 1000
    return proc.returncode, proc.stdout, proc.stderr, elapsed


def parse_sgrep_json(raw: str) -> List[Dict[str, Any]]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
    return []


def extract_paths_from_sgrep(items: List[Dict[str, Any]]) -> List[str]:
    paths = []
    for item in items:
        for key in ("path", "file", "filename"):
            if key in item and isinstance(item[key], str):
                paths.append(item[key])
                break
        else:
            # Nested path?
            if isinstance(item.get("location"), dict) and "path" in item["location"]:
                paths.append(item["location"]["path"])
    return paths


def rank_from_rg_output(output: str) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for line in output.splitlines():
        if not line:
            continue
        # rg output: path:line:match
        parts = line.split(":", 2)
        if len(parts) < 2:
            continue
        path = parts[0]
        counts[path] = counts.get(path, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return ranked


def normalize_path(path: str, repo: Path) -> str:
    try:
        p = Path(path)
        if not p.is_absolute():
            p = (repo / p).resolve()
        return str(p)
    except Exception:
        return path


def evaluate_hit(target: str, candidates: List[str]) -> Tuple[int, Optional[int]]:
    for idx, path in enumerate(candidates):
        if path == target:
            return 1, idx + 1
    return 0, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to repository")
    parser.add_argument("--queries", required=True, help="Query JSONL")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mode", choices=["keyword", "semantic", "mixed"], default="mixed")
    parser.add_argument("--out", required=True, help="Output CSV")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    queries = load_queries(Path(args.queries))
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for item in queries:
        qid = item.get("id")
        target_file = normalize_path(item["file"], repo)
        query_keyword = item.get("query_keyword") or ""
        query_semantic = item.get("query_semantic") or ""

        if args.mode == "keyword":
            if not query_keyword:
                continue
            query = query_keyword
            query_type = "keyword"
        elif args.mode == "semantic":
            if not query_semantic:
                continue
            query = query_semantic
            query_type = "semantic"
        else:
            query = query_semantic or query_keyword
            if not query:
                continue
            query_type = "semantic" if query_semantic else "keyword"

        # sgrep
        sgrep_cmd = [
            "sgrep",
            "search",
            "--json",
            "-n",
            str(args.limit),
            "-p",
            str(repo),
            query,
        ]
        rc, out, err, elapsed = run_cmd(sgrep_cmd)
        sgrep_items = parse_sgrep_json(out)
        sgrep_paths = [normalize_path(p, repo) for p in extract_paths_from_sgrep(sgrep_items)]
        hit, rank = evaluate_hit(target_file, sgrep_paths[: args.limit])
        rows.append(
            {
                "id": qid,
                "engine": "sgrep",
                "query_type": query_type,
                "query": query,
                "target_file": target_file,
                "rank": rank or "",
                "hit": hit,
                "latency_ms": round(elapsed, 2),
                "exit": rc,
                "stderr": err.strip().replace("\n", " ")[:200],
            }
        )

        # rg (fixed string, count-based ranking)
        rg_cmd = [
            "rg",
            "-F",
            "--no-heading",
            "--line-number",
            "--color=never",
            query,
            str(repo),
        ]
        rc, out, err, elapsed = run_cmd(rg_cmd)
        ranked = rank_from_rg_output(out)
        rg_paths = [normalize_path(p, repo) for p, _ in ranked]
        hit, rank = evaluate_hit(target_file, rg_paths[: args.limit])
        rows.append(
            {
                "id": qid,
                "engine": "rg",
                "query_type": query_type,
                "query": query,
                "target_file": target_file,
                "rank": rank or "",
                "hit": hit,
                "latency_ms": round(elapsed, 2),
                "exit": rc,
                "stderr": err.strip().replace("\n", " ")[:200],
            }
        )

    # Write CSV
    headers = [
        "id",
        "engine",
        "query_type",
        "query",
        "target_file",
        "rank",
        "hit",
        "latency_ms",
        "exit",
        "stderr",
    ]
    with out_path.open("w", encoding="utf-8") as f:
        f.write(",".join(headers) + "\n")
        for row in rows:
            line = [str(row.get(h, "")).replace("\"", "\"\"") for h in headers]
            # basic CSV quoting
            quoted = [
                f"\"{val}\"" if "," in val or "\n" in val or "\"" in val else val
                for val in line
            ]
            f.write(",".join(quoted) + "\n")

    # Print summary
    def summarize(engine: str) -> Dict[str, float]:
        hits = [r for r in rows if r["engine"] == engine]
        if not hits:
            return {}
        hit_rate = sum(1 for r in hits if int(r["hit"]) == 1) / len(hits)
        ranks = [int(r["rank"]) for r in hits if r["rank"]]
        mrr = sum(1.0 / r for r in ranks) / len(hits) if hits else 0
        lat = [float(r["latency_ms"]) for r in hits]
        return {
            "count": len(hits),
            "hit_rate": round(hit_rate, 3),
            "mrr": round(mrr, 3),
            "latency_p50_ms": round(statistics.median(lat), 2),
            "latency_p95_ms": round(statistics.quantiles(lat, n=20)[18], 2) if len(lat) >= 20 else "",
        }

    print("Summary:")
    for engine in ("sgrep", "rg"):
        s = summarize(engine)
        if not s:
            continue
        print(f"  {engine}: {s}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
