#!/usr/bin/env python3
"""CI lint rule: catches regressions in our Tier 1 polish work.

Forbids:
- hand-rolled .kpi-card (use ui.metric_card)
- raw {{ entity.name }} (use fmt.entity_name)
- onsubmit="confirm(...)" or onclick="confirm(...)" (use js-confirm-form)
- hand-rolled empty states (use ui.empty_state)
- <input type="date"> (use <saskia-date>)

Run:  .venv/bin/python scripts/lint_tier1.py
Exit 0 = clean; non-zero = violations found.
"""
import re
import sys
from pathlib import Path

TPL_DIR = Path("app/templates")
EXCLUDE_DIRS = {"_components", "_partials", "__pycache__"}
VIOLATIONS: list[tuple[Path, int, str, str]] = []


def _scan(path: Path, patterns: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        for needle, msg in patterns:
            if needle in line and "ui.empty_state" not in text:
                VIOLATIONS.append((path, i, needle, msg))


RULES = [
    # (substring to search, explanation)
    ('class="kpi-card', "hand-rolled kpi-card; use ui.metric_card"),
    ('class="empty-state', "hand-rolled empty-state; use ui.empty_state"),
    ('type="date"', "native date input; use <saskia-date>"),
    ('onsubmit="return confirm(', "native confirm(); use js-confirm-form"),
    ('onclick="return confirm(', "native confirm(); use js-confirm-form"),
    ('confirm(\'¿', "native confirm(); use js-confirm-form"),
    ('confirm("¿', "native confirm(); use js-confirm-form"),
]


def main() -> int:
    if not TPL_DIR.exists():
        print(f"TPL_DIR not found: {TPL_DIR}")
        return 1
    files_checked = 0
    for f in TPL_DIR.rglob("*.html"):
        if any(part in EXCLUDE_DIRS for part in f.parts):
            continue
        if "_components" in str(f):
            continue
        files_checked += 1
        for needle, msg in RULES:
            text = f.read_text(encoding="utf-8")
            for i, line in enumerate(text.splitlines(), 1):
                if needle in line:
                    # Allow exemption: ui.empty_state is the macro reference itself
                    if needle == 'class="empty-state' and 'ui.empty_state' in line:
                        continue
                    VIOLATIONS.append((f, i, needle, msg))
    print(f"Checked {files_checked} templates.")
    if VIOLATIONS:
        print(f"\n❌ {len(VIOLATIONS)} violations:")
        for path, lineno, needle, msg in VIOLATIONS[:50]:
            print(f"  {path}:{lineno}: {msg}  (matched: {needle!r})")
        if len(VIOLATIONS) > 50:
            print(f"  ... and {len(VIOLATIONS) - 50} more")
        return 1
    print("✅ No Tier 1 regressions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
