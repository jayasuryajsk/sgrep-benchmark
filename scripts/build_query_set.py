#!/usr/bin/env python3
"""Build a query set from a repo by extracting symbols + nearby comments."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Iterable, Optional

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "vendor",
    ".next",
    ".turbo",
    ".cache",
    "__pycache__",
    ".venv",
    "venv",
}

EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".m": "objc",
    ".mm": "objc",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
}

# Regex patterns by language.
PATTERNS = {
    "python": [
        re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "javascript": [
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\("),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"),
    ],
    "typescript": [
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\("),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"),
        re.compile(r"^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "go": [
        re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct\b"),
        re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+interface\b"),
    ],
    "rust": [
        re.compile(r"^\s*fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*enum\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "java": [
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "kotlin": [
        re.compile(r"^\s*(?:data\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*fun\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ],
    "csharp": [
        re.compile(r"^\s*(?:public|private|internal|protected)?\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:public|private|internal|protected)?\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "c": [
        re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_\*\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"),
    ],
    "cpp": [
        re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_:<>\*\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "objc": [
        re.compile(r"^\s*[-+]\s*\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*@interface\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "swift": [
        re.compile(r"^\s*func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "ruby": [
        re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_\!\?]*)\b"),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
    "php": [
        re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ],
}

COMMENT_PREFIX = {
    "python": "#",
    "javascript": "//",
    "typescript": "//",
    "go": "//",
    "rust": "//",
    "java": "//",
    "kotlin": "//",
    "csharp": "//",
    "c": "//",
    "cpp": "//",
    "objc": "//",
    "swift": "//",
    "ruby": "#",
    "php": "//",
}

BLOCK_COMMENT_START = "/*"
BLOCK_COMMENT_END = "*/"


def iter_files(repo: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in files:
            ext = Path(name).suffix.lower()
            if ext in EXT_LANG:
                yield Path(root) / name


def extract_comment(lines: list[str], idx: int, lang: str) -> Optional[str]:
    prefix = COMMENT_PREFIX.get(lang, "//")
    # Look at up to 8 lines above for comments or block comments.
    collected = []
    i = idx - 1
    while i >= 0 and len(collected) < 8:
        line = lines[i].rstrip("\n")
        if not line.strip():
            if collected:
                break
            i -= 1
            continue
        if line.strip().startswith(prefix):
            text = line.strip()[len(prefix):].strip()
            collected.insert(0, text)
            i -= 1
            continue
        # Block comment: scan back to start if we are on the end marker.
        if line.strip().endswith(BLOCK_COMMENT_END):
            block_lines = []
            j = i
            while j >= 0:
                l = lines[j].rstrip("\n")
                block_lines.insert(0, l)
                if l.strip().startswith(BLOCK_COMMENT_START):
                    break
                j -= 1
            block_text = " ".join(
                l.strip().lstrip("/*").rstrip("*/").strip() for l in block_lines
            ).strip()
            if block_text:
                collected = [block_text]
            break
        break
    if not collected:
        return None
    text = " ".join(collected).strip()
    # Avoid tiny or useless comments.
    if len(text.split()) < 3:
        return None
    return text


def sanitize_query(text: str, symbol: str) -> str:
    # Remove symbol name if present to keep the semantic query meaningful.
    text = re.sub(re.escape(symbol), "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def identifier_to_phrase(symbol: str) -> Optional[str]:
    # Split camelCase, PascalCase, snake_case, kebab-case into words.
    if not symbol:
        return None
    parts = re.sub(r"[_\\-]+", " ", symbol).strip()
    tokens = []
    for part in parts.split():
        # Split CamelCase: "getUserByEmail" -> "get User By Email"
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", part)
        split = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", split).split()
        tokens.extend(split)
    tokens = [t.lower() for t in tokens if t.strip()]
    if len(tokens) < 2:
        return None
    return " ".join(tokens)


def semantic_from_phrase(phrase: str) -> Optional[str]:
    if not phrase:
        return None
    return f"code for {phrase}"


def clean_comment_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:/\\*+|\\*+/|//+)", "", text).strip()
    return text


def extract_comment_blocks(lines: list[str]) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("//"):
            start = i
            texts = []
            while i < len(lines) and lines[i].strip().startswith("//"):
                texts.append(lines[i].strip().lstrip("/").strip())
                i += 1
            text = clean_comment_text(" ".join(texts))
            if text:
                blocks.append((start + 1, text))
            continue
        if "/*" in line:
            start = i
            texts = []
            # Handle single-line block comments.
            if "*/" in line and line.index("/*") < line.index("*/"):
                inner = line.split("/*", 1)[1].split("*/", 1)[0]
                texts.append(inner)
                i += 1
            else:
                # Multi-line block comment.
                inner = line.split("/*", 1)[1]
                if inner.strip():
                    texts.append(inner)
                i += 1
                while i < len(lines):
                    l = lines[i]
                    if "*/" in l:
                        texts.append(l.split("*/", 1)[0])
                        i += 1
                        break
                    texts.append(l)
                    i += 1
            text = " ".join([clean_comment_text(t) for t in texts if t.strip()])
            text = clean_comment_text(text)
            if text:
                blocks.append((start + 1, text))
            continue
        i += 1
    return blocks


def build_queries(repo: Path, max_items: int, mode: str) -> list[dict]:
    items: list[dict] = []
    for path in iter_files(repo):
        ext = path.suffix.lower()
        lang = EXT_LANG.get(ext)
        if not lang:
            continue
        try:
            raw = path.read_text(errors="ignore")
        except Exception:
            continue
        lines = raw.splitlines()
        if mode == "comments":
            blocks = extract_comment_blocks(lines)
            for line_no, text in blocks:
                if len(text.split()) < 5:
                    continue
                item = {
                    "file": str(path),
                    "line": line_no,
                    "symbol": "",
                    "lang": lang,
                    "query_keyword": "",
                    "query_semantic": text,
                    "comment": text,
                }
                items.append(item)
                if len(items) >= max_items * 3:
                    break
        else:
            patterns = PATTERNS.get(lang)
            if not patterns:
                continue
            for idx, line in enumerate(lines):
                for pattern in patterns:
                    m = pattern.match(line)
                    if not m:
                        continue
                    symbol = m.group(1)
                    comment = extract_comment(lines, idx, lang)
                    query_semantic = None
                    if mode == "semantic":
                        phrase = identifier_to_phrase(symbol)
                        if phrase:
                            sem = semantic_from_phrase(phrase)
                            if sem:
                                query_semantic = sem
                    else:
                        if comment:
                            semantic = sanitize_query(comment, symbol)
                            if semantic:
                                query_semantic = f"Where is the code that {semantic}?"
                        if not query_semantic:
                            phrase = identifier_to_phrase(symbol)
                            if phrase:
                                query_semantic = f"Where is the code that {phrase}?"
                    item = {
                        "file": str(path),
                        "line": idx + 1,
                        "symbol": symbol,
                        "lang": lang,
                        "query_keyword": symbol,
                        "query_semantic": query_semantic,
                        "comment": comment,
                    }
                    items.append(item)
                    if len(items) >= max_items * 3:
                        break
                if len(items) >= max_items * 3:
                    break
        if len(items) >= max_items * 3:
            break

    # Prefer items with semantic queries, then fill with keyword-only.
    semantic_items = [i for i in items if i["query_semantic"]]
    keyword_items = [i for i in items if not i["query_semantic"]]
    out = semantic_items[:max_items]
    if len(out) < max_items:
        out.extend(keyword_items[: max_items - len(out)])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="Path to repository")
    parser.add_argument("--out", required=True, help="Output JSONL file")
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--mode", choices=["symbols", "comments", "semantic"], default="symbols")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    items = build_queries(repo, args.max_items, args.mode)
    if not items:
        raise SystemExit("No items extracted; try another repo or increase max-items.")

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for idx, item in enumerate(items):
            item["id"] = f"q{idx:04d}"
            f.write(json.dumps(item, ensure_ascii=True) + "\n")

    print(f"Wrote {len(items)} queries to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
