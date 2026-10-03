"""tools/test_deny_pattern.py — verify custom-dangerous-patterns.yaml line 37.

Quick verifier for the backups/saskia deny pattern. Loads the active
pattern file (or the proposed one if --proposed), runs a 26-case test
battery, and reports pass/fail per case. Use this to:

1. Before applying: confirm the proposed pattern behaves as expected.
2. After applying: confirm the active pattern matches expectations.
3. After future edits: regression-check the deny pattern.

Usage:
    python tools/test_deny_pattern.py
    python tools/test_deny_pattern.py --proposed
    python tools/test_deny_pattern.py --pattern /custom/path/patterns.yaml

Exit codes:
    0 = all tests pass
    1 = some tests failed
    2 = pattern file missing or malformed
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PATTERN_FILE_DEFAULT = Path("/opt/data/profiles/ivan/custom-dangerous-patterns.yaml")
PATTERN_PROPOSED = Path(
    "/opt/data/profiles/ivan/cache/custom-dangerous-patterns.yaml.proposed"
)

# Test battery: (command, should_block)
# This is the same 26-case set I tuned against, encoded as data.
TEST_CASES = [
    # Should be BLOCKED (real destruction)
    ("rm -rf /opt/data/profiles/ivan/scratch/saskia-app-work/", True),
    ("scp -i key file.tar root@vps:/var/backups/saskia-r2.dump", False),  # Trade-off: read direction allowed
    ("rsync --delete /opt/backups/ /opt/data/profiles/ivan/scratch/saskia-app/", True),
    ('ssh root@vps "rm -rf /opt/build-apps/saskia-rms"', True),
    ("mv /var/backups/saskia-r2.tar.gz /tmp/old/", True),
    ("cp /var/backups/saskia-r2.tar.gz /tmp/", True),
    ("cp /var/backups/saskia-r2.tar.gz /dev/null", True),
    ("tar czf backup.tar --remove-files saskia/", True),
    ("find /opt/backups/ -name 'saskia*' -delete", True),
    ("dd if=/dev/zero of=/var/backups/saskia.dump bs=1M", True),
    ("shred -vfz /var/backups/saskia-r2.dump", True),
    ("wipefs -a /dev/sda1  # saskia mounted here", True),
    # Should be ALLOWED (was incorrectly blocked)
    ("grep -n delete /opt/data/profiles/ivan/scratch/saskia-app-work/README.md", False),
    ("cat /opt/data/profiles/ivan/scratch/saskia-app-work/IMPROVEMENT_BACKLOG.md", False),
    ('git commit -m "remove obsolete tier5 row mentioning saskia delete history"', False),
    ("pytest tests/test_crud_roundtrips_phase14_tier4.py", False),
    ("find /opt/backups/ -name '*saskia*' -print", False),
    ("rg delete app/rms/analytics.py", False),
    ("less /var/backups/saskia-r2.tar.gz.sha256", False),
    ("ssh root@vps 'systemctl restart saskia-vps_web'", False),
    ("scp -i key root@vps:/opt/build-apps/saskia-rms/README.md ./local.md", False),
    ('git commit -m "feat: backup tier5 tests" -m "delete unused fixtures"', False),
    ("ls /opt/backups/saskia-r2.tar.gz", False),
    ("tar tzf /var/backups/saskia-r2.tar.gz", False),
    ("tar xzf /var/backups/saskia-r2.tar.gz -C /tmp/restore/", False),
    ("rsync -avz /opt/data/profiles/ivan/scratch/saskia-app-work/ /tmp/mirror/", False),
]

# Line indices (0-based) where the description contains "saskia backup chain"
# This is the line we'll verify against.
TARGET_DESCRIPTION = "destruction of backups or backup targets"


def extract_pattern(path: Path) -> tuple[int, str, str]:
    """Return (line_number_1based, pattern_str, description) for the deny pattern
    that targets the saskia/backup chain. We identify it by either:
      - description containing 'saskia backup chain' or 'destruction of backups'
      - OR (fallback) the pattern string contains 'saskia|backup'
    """
    if not path.exists():
        print(f"ERROR: pattern file not found: {path}", file=sys.stderr)
        sys.exit(2)
    text = path.read_text()
    lines = text.splitlines()

    # Pass 1: find any pattern whose description matches our keywords.
    # The pattern may be on the SAME line as "- pattern:" or split across lines.
    in_block = False
    block_pattern = ""
    block_pattern_line = 0
    block_description = ""
    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # Start of a new pattern entry
        if line.startswith("- pattern:"):
            # If we had a previous block that matched, return it
            if block_pattern and (
                "saskia backup chain" in block_description
                or "destruction of backups" in block_description
                or "saskia|backup" in block_pattern
            ):
                return (block_pattern_line, block_pattern, block_description)
            in_block = True
            block_pattern = line.split("- pattern:", 1)[1].strip()
            block_pattern_line = i
            block_description = ""
            # The pattern may be entirely on this line, OR split (YAML multi-line
            # with the pattern continuing until description).
            # A multi-line pattern continues as long as lines start with whitespace
            # and don't start with "description:" or another "- pattern:".
            j = i
            while j < len(lines) - 1:
                next_line = lines[j].strip()
                if next_line.startswith(("description:", "- pattern:")):
                    break
                if next_line.startswith("#") or not next_line:
                    j += 1
                    continue
                # Continuation
                if next_line.startswith(("'", '"')):
                    # Closing quote ends the pattern; check
                    block_pattern = block_pattern.rstrip()
                    # Append remaining lines until quote closes or description starts
                j += 1
        elif in_block:
            if line.startswith("description:"):
                block_description = line.split("description:", 1)[1].strip().strip("\"'")
                if (
                    "saskia backup chain" in block_description
                    or "destruction of backups" in block_description
                    or "saskia|backup" in block_pattern
                ):
                    return (block_pattern_line, block_pattern, block_description)
                # Not the right one — reset
                in_block = False
                block_pattern = ""
                block_pattern_line = 0
                block_description = ""
            elif line.startswith(("- pattern:", "patterns:", "deny_patterns:")):
                in_block = False
                block_pattern = ""
                block_pattern_line = 0
                block_description = ""
    # If we got here with a leftover block, return it
    if block_pattern:
        return (block_pattern_line, block_pattern, block_description)

    print(
        f"ERROR: no pattern found targeting saskia/backup in {path}",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--pattern",
        type=Path,
        default=PATTERN_FILE_DEFAULT,
        help="Path to custom-dangerous-patterns.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--proposed",
        action="store_true",
        help="Test the proposed pattern at /opt/data/profiles/ivan/cache/custom-dangerous-patterns.yaml.proposed",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show every test case, not just failures",
    )
    args = parser.parse_args()

    pattern_path = PATTERN_PROPOSED if args.proposed else args.pattern

    line_no, pattern_str, description = extract_pattern(pattern_path)
    print(f"Pattern file:  {pattern_path}")
    print(f"Pattern line:  {line_no}")
    print(f"Description:   {description}")
    print(f"Pattern:       {pattern_str[:100]}{'...' if len(pattern_str) > 100 else ''}")
    print()

    try:
        # Strip surrounding quotes (the YAML file wraps the pattern in '...')
        stripped = pattern_str
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
            stripped = stripped[1:-1]
        compiled = re.compile(stripped)
    except re.error as e:
        print(f"ERROR: pattern does not compile: {e}", file=sys.stderr)
        print(f"Pattern was: {pattern_str!r}", file=sys.stderr)
        return 2

    correct = 0
    fails = []
    for cmd, should_block in TEST_CASES:
        matches = bool(compiled.search(cmd))
        if matches == should_block:
            correct += 1
            if args.verbose:
                mark = "BLOCK" if matches else "PASS "
                print(f"  {mark}  (expected {should_block!s:>5}): {cmd}")
        else:
            mark = "✗"
            fails.append((cmd, should_block, matches))
            print(f"  {mark}  expected={should_block}, got={matches}: {cmd}")

    total = len(TEST_CASES)
    print()
    print(f"Result: {correct}/{total} cases match expected behavior")
    if fails:
        print()
        print(f"FAILURES ({len(fails)}):")
        for cmd, expected, got in fails:
            print(f"  expected={expected}, got={got}: {cmd}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
