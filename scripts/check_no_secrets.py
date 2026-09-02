#!/usr/bin/env python3
"""
Pre-commit guard against credential patterns in committed files.

Triggered by .pre-commit-config.yaml as a local hook. Scans staged files
for token-shaped strings and blocks the commit if any are found.

Token shapes detected (shape only — never embeds real values):
- GitHub classic PAT:    ghp_<36 alnum>
- GitHub OAuth:          gho_<36 alnum>
- GitHub server-to-srv:  ghs_<36 alnum>
- GitHub user-to-srv:    ghu_<36 alnum>
- GitHub fine-grained:   github_pat_<82 alnum/underscore>
- x-access-token URLs:   https://x-access-token:<token>@...
- AWS access key:        AKIA<16 uppercase>
- Generic JWT:           eyJ<base64>.<base64>.<base64>
- Generic "key=value" with 32+ char value: matches (api|secret|token|key|password)[:=] ["']?[<32+ chars>]

Why this exists:
- 2026-09-02: a rotated GitHub PAT was found in .git/config in a shared
  scratch dir. The user thought it was already rotated; rotation
  happened but the .git/config line was left in place.
- This hook catches future instances of the same pattern at commit time.

Per the credential-redacted-grep skill: token-shape in output = compromised.
This script intentionally does NOT echo matched values, only file paths +
shape names + count. The pattern is the shape, not the value.

Usage (called by pre-commit):
    python3 scripts/check_no_secrets.py <file1> <file2> ...

Exit codes:
    0 = no credentials detected, commit allowed
    1 = credentials detected, commit blocked
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Token shape patterns (regex) — names only, never embedded values
SHAPES: dict[str, re.Pattern[str]] = {
    "ghp_classic": re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    "ghs_server": re.compile(r"ghs_[A-Za-z0-9]{36,}"),
    "gho_oauth": re.compile(r"gho_[A-Za-z0-9]{36,}"),
    "ghu_user": re.compile(r"ghu_[A-Za-z0-9]{36,}"),
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{36,}"),
    "x-access-token": re.compile(r"x-access-token:[^@\s/]+@"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "generic_long_value": re.compile(
        r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?key|auth[_-]?token|password)\s*[:=]\s*["\']?([A-Za-z0-9+/=_-]{32,})'
    ),
}

# Files to skip (binary, generated, vendored)
SKIP_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".mp3",
    ".mp4",
    ".wav",
    ".ogg",
    ".webm",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".pyc",
    ".pyo",
    ".so",
    ".o",
    ".a",
    ".dll",
    ".dylib",
    ".sqlite",
    ".db",
    ".sqlite3",
    ".wal",
    ".shm",
    ".ico",
    ".icns",
}

# Allow-list files (legitimately contain token-shape strings)
ALLOWLIST = {
    # This very script contains the patterns as documentation
    "scripts/check_no_secrets.py",
    # Test fixtures may include placeholders
    "tests/fixtures/.gitkeep",
}


def scan_file(path: Path) -> dict[str, int]:
    """Return {shape_name: count} for matched patterns in file."""
    if path.name in ALLOWLIST or str(path) in ALLOWLIST:
        return {}
    if path.suffix.lower() in SKIP_EXTS:
        return {}
    # Skip large files
    try:
        if path.stat().st_size > 1_000_000:
            return {}
    except OSError:
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return {}
    hits: dict[str, int] = {}
    for name, pat in SHAPES.items():
        matches = pat.findall(text)
        if matches:
            hits[name] = len(matches)
    return hits


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_no_secrets.py <file1> [<file2> ...]", file=sys.stderr)
        return 2

    blocked = False
    for arg in argv[1:]:
        path = Path(arg)
        if not path.exists():
            continue
        hits = scan_file(path)
        if hits:
            blocked = True
            shapes = ", ".join(f"{name}={count}" for name, count in sorted(hits.items()))
            print(f"BLOCKED: {path} — {shapes}", file=sys.stderr)

    if blocked:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("CREDENTIAL PATTERN DETECTED IN STAGED FILES", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("", file=sys.stderr)
        print("Per AIW AGENTS.md rule + credential-redacted-grep skill:", file=sys.stderr)
        print("token-shape in committed file = compromised.", file=sys.stderr)
        print("", file=sys.stderr)
        print("What to do:", file=sys.stderr)
        print("1. If this is a REAL credential: rotate it NOW at the provider", file=sys.stderr)
        print("2. If this is a placeholder/example: move it to a test fixture", file=sys.stderr)
        print("3. If this is a false positive: add the file to ALLOWLIST in", file=sys.stderr)
        print("   scripts/check_no_secrets.py with a comment explaining why", file=sys.stderr)
        print("4. To bypass (DANGEROUS): git commit --no-verify", file=sys.stderr)
        print("", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
