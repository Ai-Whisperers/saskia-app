#!/usr/bin/env python3
"""Pin every GitHub Actions `uses:` reference to its commit SHA.

Reads the workflows directory, replaces `uses: foo/bar@vN` with
`uses: foo/bar@<sha>  # vN` per zizmor's recommended convention.

Reference: https://docs.zizmor.sh/audits/#unpinned-uses
"""
import re
import sys
from pathlib import Path

# (action, version) -> sha
SHAS = {
    ("actions/checkout", "v7"): "3d3c42e5aac5ba805825da76410c181273ba90b1",
    ("actions/setup-python", "v5"): "a26af69be951a213d495a4c3e4e4022e16d87065",
    ("actions/download-artifact", "v7"): "37930b1c2abaa49bbe596cd826c3c89aef350131",
    ("actions/setup-python", "v6"): "ece7cb06caefa5fff74198d8649806c4678c61a1",
    ("actions/upload-artifact", "v4"): "ea165f8d65b6e75b540449e92b4886f43607fa02",
    ("actions/upload-artifact", "v7"): "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    ("astral-sh/setup-uv", "v7"): "94527f2e458b27549849d47d273a16bec83a01e9",
    ("zaproxy/action-api-scan", "v0.10.0"): "bd24b11e76da11ab60302c8ae87f091cbb11f034",
}

# Match: uses: <action>@<version>
# Skip if already pinned (40-char hex). Skip local paths.
PATTERN = re.compile(
    r"uses:\s+(?P<action>[\w\-]+/[\w\-]+)@(?P<version>[\w\.\-]+)"
)


def pin(content: str) -> tuple[str, int, int, int]:
    """Return (new_content, pinned_count, skipped_count, error_count)."""
    pinned_count = 0
    skipped_count = 0
    error_count = 0

    def replace(match: re.Match) -> str:
        nonlocal pinned_count, skipped_count, error_count
        action = match.group("action")
        version = match.group("version")

        # Skip already-pinned SHAs
        if re.match(r"^[a-f0-9]{40}$", version):
            skipped_count += 1
            return match.group(0)

        sha = SHAS.get((action, version))
        if sha is None:
            print(f"  ! NO SHA for {action}@{version}", file=sys.stderr)
            error_count += 1
            return match.group(0)

        pinned_count += 1
        return f"uses: {action}@{sha}  # {version}"

    new_content = PATTERN.sub(replace, content)
    return new_content, pinned_count, skipped_count, error_count


def main() -> int:
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.is_dir():
        print(f"ERROR: {workflows_dir} not found; run from repo root", file=sys.stderr)
        return 1

    total_pinned = 0
    total_skipped = 0
    total_errors = 0

    for path in sorted(workflows_dir.glob("*.yml")):
        content = path.read_text()
        new_content, pinned, skipped, errors = pin(content)
        if new_content != content:
            path.write_text(new_content)
            print(f"  {path.name}: pinned={pinned} skipped={skipped} errors={errors}")
        total_pinned += pinned
        total_skipped += skipped
        total_errors += errors

    print(f"\nPinned: {total_pinned}, Already pinned: {total_skipped}, Errors: {total_errors}")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
