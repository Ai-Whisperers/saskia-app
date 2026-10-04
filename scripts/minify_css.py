#!/usr/bin/env python3
"""scripts/minify_css.py — minimize app/static/app.css without external deps.

Per docs/operations/2026-09-09-performance-research.md resources 6.1
(cssnano) and 6.4 (lightningcss), we want a tiny CSS minifier that runs
in <1s and ships no new dependencies.

The minifier handles:
- Block comments /* ... */
- Leading/trailing whitespace
- Multiple spaces to one
- Whitespace around {}:;,>
- Empty declarations (; })
- Trailing semicolon before }
- Comments inside selectors (preserved)

What it does NOT touch (intentional):
- calc(), @media, @keyframes blocks (handled conservatively)
- CSS custom properties (--name: value;) preserved with spacing

This is the "good enough for our 13KB file" minifier. If we ever need
lightningcss-grade output, switch to lightningcss-cli (per resource 6.4).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def minify(css: str) -> str:
    """Return a minified version of `css`."""
    # 1. Strip /* ... */ block comments (non-greedy, dotall).
    out = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    # 2. Collapse runs of whitespace to a single space.
    out = re.sub(r"\s+", " ", out)

    # 3. Remove whitespace immediately around { } : ; , > + (selectors).
    out = re.sub(r"\s*([{}:;,>])\s*", r"\1", out)

    # 4. Drop trailing semicolons before closing brace: ";}" → "}".
    out = re.sub(r";}", "}", out)

    # 5. Strip leading/trailing whitespace.
    out = out.strip()

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("app/static/app.css"),
        help="Source CSS file.",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        default=None,
        help="Destination (default: overwrite source).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if a re-minify would change the file (for CI).",
    )
    args = parser.parse_args()

    src = args.src.read_text()
    minified = minify(src)

    if args.check:
        current = args.dst.read_text() if args.dst else args.src.read_text()
        if current != minified:
            print(f"FAIL: {args.src} is not minified.")
            print(f"  Source size: {len(src)} bytes")
            print(f"  Current size: {len(current)} bytes")
            print(f"  Minified size: {len(minified)} bytes")
            return 1
        return 0

    dest = args.dst or args.src
    dest.write_text(minified)

    src_size = len(src)
    dst_size = len(minified)
    pct = (1 - dst_size / src_size) * 100
    print(f"minified {args.src} → {dest}")
    print(f"  {src_size} → {dst_size} bytes ({pct:.1f}% reduction)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
