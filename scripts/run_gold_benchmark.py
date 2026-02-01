#!/usr/bin/env python3
"""Evaluate sgrep vs rg on a gold query set."""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple

STOPWORDS = {
    "where","is","the","a","an","and","or","to","of","in","on","for","with","does","do","how",
    "are","be","implemented","handled","implemented?","implemented.","implemented!","what","when","why","which",
    "what's","its","it","this","that","via","from","into","using","use","uses","used","only",
}


def load_gold(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def run_cmd(cmd: List[str], cwd: Path | None = None) -> Tuple[int, str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = (time.perf_counter() - start) * 1000
    return proc.returncode, proc.stdout, proc.stderr, elapsed


def parse_sgrep_json(raw: str) -> List[dict]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    return []


def extract_paths_from_sgrep(items: List[dict]) -> List[str]:
    paths = []
    for item in items:
        for key in ("path", "file", "filename"):
            if key in item and isinstance(item[key], str):
                paths.append(item[key])
                break
        else:
            loc = item.get("location")
            if isinstance(loc, dict) and isinstance(loc.get("path"), str):
                paths.append(loc["path"])
    return paths


def normalize(path: str, repo: Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = (repo / p).resolve()
    return str(p)


def rank_from_rg(outputs: List[str]) -> List[str]:
    counts: Dict[str, int] = {}
    for out in outputs:
        for line in out.splitlines():
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) < 2:
                continue
            path = parts[0]
            counts[path] = counts.get(path, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [p for p, _ in ranked]


def keywordize(query: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9_\-]+", query.lower())
    kws = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    # Keep first 3 unique keywords
    seen = []
    for t in kws:
        if t not in seen:
            seen.append(t)
        if len(seen) >= 3:
            break
    return seen


def evaluate_hit(targets: List[str], candidates: List[str], k: int) -> Tuple[int, int | None]:
    target_set = set(targets)
    for idx, path in enumerate(candidates[:k]):
        if path in target_set:
            return 1, idx + 1
    return 0, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    gold = load_gold(Path(args.gold))

    rows = []
    for item in gold:
        qid = item.get("id")
        query = item.get("query")
        answers = item.get("answers", [])
        targets = [normalize(a["path"], repo) for a in answers]

        # sgrep
        sgrep_cmd = ["sgrep", "search", "--json", "-n", str(args.limit), "-p", str(repo), query]
        rc, out, err, elapsed = run_cmd(sgrep_cmd)
        s_items = parse_sgrep_json(out)
        s_paths = [normalize(p, repo) for p in extract_paths_from_sgrep(s_items)]
        hit, rank = evaluate_hit(targets, s_paths, args.limit)
        rows.append({
            "id": qid,
            "engine": "sgrep",
            "query": query,
            "targets": "|".join([a["path"] for a in answers]),
            "rank": rank or "",
            "hit": hit,
            "latency_ms": round(elapsed, 2),
            "exit": rc,
            "stderr": err.strip().replace("\n", " ")[:200],
        })

        # rg baseline (keywordized)
        keywords = keywordize(query)
        rg_outputs = []
        rg_elapsed_total = 0.0
        for kw in keywords:
            rg_cmd = ["rg", "-i", "-n", "--no-heading", "--color=never", kw, str(repo)]
            rc, out, err, elapsed = run_cmd(rg_cmd)
            rg_elapsed_total += elapsed
            rg_outputs.append(out)
        ranked = [normalize(p, repo) for p in rank_from_rg(rg_outputs)]
        hit, rank = evaluate_hit(targets, ranked, args.limit)
        rows.append({
            "id": qid,
            "engine": "rg",
            "query": query,
            "targets": "|".join([a["path"] for a in answers]),
            "rank": rank or "",
            "hit": hit,
            "latency_ms": round(rg_elapsed_total, 2),
            "exit": 0,
            "stderr": "",
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["id","engine","query","targets","rank","hit","latency_ms","exit","stderr"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)

    def summarize(engine: str) -> dict:
        subset = [r for r in rows if r["engine"] == engine]
        if not subset:
            return {}
        hit_rate = sum(1 for r in subset if int(r["hit"]) == 1) / len(subset)
        ranks = [int(r["rank"]) for r in subset if r["rank"]]
        mrr = sum(1.0 / r for r in ranks) / len(subset) if subset else 0
        lat = [float(r["latency_ms"]) for r in subset]
        return {
            "count": len(subset),
            "hit_rate": round(hit_rate, 3),
            "mrr": round(mrr, 3),
            "latency_p50_ms": round(statistics.median(lat), 2),
        }

    print("Summary:")
    for engine in ("sgrep","rg"):
        print(f"  {engine}: {summarize(engine)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
