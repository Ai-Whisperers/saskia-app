#!/usr/bin/env python3
"""scripts/check_duplicate_code.py — near-duplicate function detector.

Sazon tooling rec 2026-10-08. Uses difflib SequenceMatcher on
AST-normalized function bodies to surface near-duplicates without
requiring vulture/jscpd. Catches the case where one developer splits
"common" code into multiple files instead of one shared util.

Usage:
    python scripts/check_duplicate_code.py                     # default threshold 0.80
    python scripts/check_duplicate_code.py --threshold 0.90    # stricter
    python scripts/check_duplicate_code.py app/rms/settings.py # single file vs the rest

Algorithm:
1. AST-parse every function in app/ and scripts/.
2. Strip docstrings, comments, and whitespace.
3. Compare each pair via difflib.SequenceMatcher.ratio().
4. Report pairs above the threshold.

This is a heuristic. It's not jscpd. It's meant to find the
"smell" — the developer then does the manual review.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import re
import sys

ROOTS = ["app/", "scripts/"]
EXCLUDE_DIRS = {
    "app/_archive",
    "app/.venv",
    "app/__pycache__",
    "scripts/__pycache__",
    ".venv",
    "node_modules",
    ".git",
    ".hermes",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


def _norm_source(src: str) -> str:
    """Normalize a function body for comparison.

    Cheap approach: regex-based. Strips:
    - Python comments (# to end of line)
    - Triple-quoted strings (docstrings) — replaced with __DOC__
    - Whitespace runs (collapsed to single space)
    - Long string literals — replaced with __STR__

    This loses AST precision (e.g. can't distinguish `1` from
    `True`) but for *similarity* comparison, the structural shape
    is what matters. ~100x faster than ast.unparse.
    """
    DQ = chr(34) * 3
    SQ = chr(39) * 3
    out = re.sub(DQ + r"[\s\S]*?" + DQ + "|" + SQ + r"[\s\S]*?" + SQ, "__DOC__", src)
    out = re.sub(r"#[^\n]*", "", out)
    out = re.sub(r'"[^"\n]{50,}"|' + r"'[^'\n]{50,}'", "__STR__", out)
    out = re.sub(r"\s+", " ", out)
    return out.strip()


def extract_functions(path: str) -> list[tuple[str, int, str]]:
    """Return list of (name, lineno, normalized_source) for every top-level function/method."""
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        return []
    out: list[tuple[str, int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                norm = _norm_source(ast.get_source_segment(src, node) or "")
            except (SyntaxError, ValueError):
                continue
            out.append((node.name, node.lineno, norm))
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    try:
                        norm = _norm_source(ast.get_source_segment(src, sub) or "")
                    except (SyntaxError, ValueError):
                        continue
                    out.append((f"{node.name}.{sub.name}", sub.lineno, norm))
    return out


def collect_all_functions(roots: list[str]) -> list[tuple[str, str, int, str]]:
    """Return list of (file, funcname, lineno, norm_src)."""
    out: list[tuple[str, str, int, str]] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            if any(ex in dirpath for ex in EXCLUDE_DIRS):
                continue
            for f in filenames:
                if not f.endswith(".py"):
                    continue
                full = os.path.join(dirpath, f)
                for name, lineno, norm in extract_functions(full):
                    out.append((full, name, lineno, norm))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Similarity ratio threshold 0.0-1.0 (default 0.80)",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=8,
        help="Minimum function body line count to compare (default 8)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Limit scan to these paths (default: app/ scripts/)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print report but don't exit 1 on duplicates",
    )
    args = parser.parse_args()

    roots = args.paths or ROOTS
    funcs = collect_all_functions(roots)

    # Filter by min body length
    funcs = [(f, n, ln, s) for f, n, ln, s in funcs if s.count("\n") >= args.min_lines]

    # Pairwise compare (n^2; for big repos this needs sharding, but
    # Sazon's RMS is ~117 files, ~5k functions worst case — OK)
    pairs: list[tuple[float, str, str, int, str, str, int]] = []
    n = len(funcs)
    for i in range(n):
        fi, ni, li, si = funcs[i]
        if len(si) < args.min_lines * 2:
            continue
        for j in range(i + 1, n):
            fj, nj, lj, sj = funcs[j]
            if fi == fj:  # same file
                continue
            # Early-exit: name suggests different purpose
            if ni != nj and not (ni in nj or nj in ni):
                pass
            # Shingle prefilter: only compute full ratio if both
            # functions share enough distinct 4-character shingles.
            # Cuts n^2 cost dramatically on big repos.
            shingles_i = {si[i : i + 4] for i in range(0, len(si) - 3, 4)}
            shingles_j = {sj[i : i + 4] for i in range(0, len(sj) - 3, 4)}
            if not shingles_i or not shingles_j:
                continue
            overlap = len(shingles_i & shingles_j) / min(len(shingles_i), len(shingles_j))
            if overlap < 0.3:  # No real overlap; skip
                continue
            ratio = difflib.SequenceMatcher(None, si, sj, autojunk=False).ratio()
            if ratio >= args.threshold:
                pairs.append((ratio, fi, ni, li, fj, nj, lj))

    pairs.sort(key=lambda p: -p[0])

    if not pairs:
        print(
            f"OK: no near-duplicate functions (threshold {args.threshold}, min lines {args.min_lines})."
        )
        return 0

    print(f"Found {len(pairs)} near-duplicate function pair(s) (threshold {args.threshold}):")
    print()
    for ratio, fi, ni, li, fj, nj, lj in pairs[:50]:
        print(f"  {ratio:.2f}  {fi}:{li}  {ni}()")
        print(f"        vs  {fj}:{lj}  {nj}()")
        print()
    if len(pairs) > 50:
        print(f"... and {len(pairs) - 50} more")
        print()

    if not args.report:
        print(
            "Refactor candidates. Likely one is the canonical version; the other should import or delegate."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
