#!/usr/bin/env python3
"""Scan markdown files for broken relative links + images.

Checks [text](relative.md) and ![](img.png) references against the
filesystem (absolute/http links skipped). Reports per-file findings.

Usage:
  python3 scripts/check_md_links.py [paths...]     # default docs/ *.md
  python3 scripts/check_md_links.py --json         # machine-readable
Exit 0 = all links resolve; exit 1 = broken links found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# [text](target) — skip http(s), mailto, anchors-only, <>, {{ }} template refs
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s|\\ )[^)]*\)|(?<!\!)\[[^\]]*\]\(([^)]+)\)")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")

SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "tel:")


CODE_SPAN_RE = re.compile(r"`[^`\n]*`")


def extract_links(text: str) -> set[str]:
    # Links inside inline code spans (`mysql://user:pass@host/conn`) are
    # code, not markdown links — strip them first.
    text = CODE_SPAN_RE.sub("", text)
    out: set[str] = set()
    for m in MD_LINK_RE.finditer(text):
        t = m.group(1).strip()
        if t and not t.startswith(SKIP_PREFIXES) and not t.startswith("<"):
            out.add(t)
    for m in IMG_RE.finditer(text):
        t = m.group(1).strip()
        if t and not t.startswith(SKIP_PREFIXES):
            out.add(t)
    return out


def check_file(md: Path) -> list[dict]:
    findings = []
    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [{"file": str(md), "target": "", "error": f"unreadable: {exc}"}]
    for target in sorted(extract_links(text)):
        # strip template vars (Jinja placeholders in docs)
        if "{{" in target:
            continue
        # URL with query string
        path_part = target.split("?")[0]
        resolved = (md.parent / path_part).resolve()
        if not resolved.exists():
            findings.append({"file": str(md.relative_to(REPO_ROOT)), "target": target})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    roots = [Path(p) for p in args.paths] if args.paths else [REPO_ROOT / "docs"]
    files: list[Path] = []
    for r in roots:
        if r.is_file():
            files.append(r)
        elif r.is_dir():
            files.extend(sorted(r.glob("**/*.md")))
    # root md files when scanning default
    if not args.paths:
        files.extend(sorted(REPO_ROOT.glob("*.md")))

    all_findings = []
    for f in files:
        all_findings.extend(check_file(f))

    if args.json:
        print(json.dumps({"broken": all_findings, "count": len(all_findings)}, indent=2))
    else:
        from collections import Counter

        per_file = Counter(f["file"] for f in all_findings)
        for f, n in per_file.most_common():
            print(f"{n:4d}  {f}")
            for x in all_findings:
                if x["file"] == f:
                    print(f"      -> {x['target']}")
        print(f"\nTotal broken links: {len(all_findings)} in {len(per_file)} files")

    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
