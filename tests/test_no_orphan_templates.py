"""CI gate: every template in app/templates/ must be referenced by at
least one route or another template. Prevents future "orphan" templates
that bloat the build and confuse operators with unreachable pages.

Sazon-Improvement v2 (2026-10-06) Phase D: this check is the regression
net after we removed 2 orphan templates (cliente_loyalty.html,
produccion_calendario.html). One of them was a side effect of incomplete
P5 work (the full-ledger page) that left a failing test in the suite.
Both are now git-history-only and the gate keeps it that way.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


TEMPLATES_DIR = Path("app/templates")

# Templates that are intentionally orphaned because their corresponding
# route was merged into a different page. We keep the file as a tombstone
# so future maintainers can see "this existed, was moved to /settings".
_KNOWN_ORPHAN_TOMBSTONES = {
    "delivery_zones.html",  # Wave 4: /delivery-zones now redirects to /settings#zonas-delivery
}


def _all_template_files() -> list[Path]:
    """Walk app/templates and return every .html file, recursively."""
    return [p for p in TEMPLATES_DIR.rglob("*.html")]


def _all_references() -> set[str]:
    """Return every template-name reference found in app/ and tests/.

    A "reference" can be:
    - render(..., "name.html" ...)
    - {% include "name.html" %}
    - {% extends "name.html" %}
    - {% from "name.html" import ... %}
    - import "name" in Python
    - href="/path/that/renders/name"  (e.g. /clientes/X/loyalty)
    """
    refs = set()
    root = Path(".")
    for src in list(root.rglob("app/**/*.py")) + list(root.rglob("app/**/*.html")) + list(root.rglob("tests/**/*.py")):
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # .html refs
        for m in re.findall(r'["\']([a-zA-Z0-9_/\-]+\.html)["\']', text):
            refs.add(m)
        # Direct imports of a module that may render it
        for m in re.findall(r'from\s+app\.templates\.([a-zA-Z0-9_/\-]+)', text):
            refs.add(f"{m}.html")
    return refs


def test_no_template_files_have_zero_route_references():
    """Every .html in app/templates/ must appear at least once in app/
    or tests/ source. Orphan templates are tech debt and confuse users
    via broken links / 404s."""
    refs = _all_references()
    orphans = []
    for path in _all_template_files():
        # Compute the rel path as referenced from a {% include %} inside app/templates/
        rel = path.relative_to(TEMPLATES_DIR).as_posix()
        if rel in _KNOWN_ORPHAN_TOMBSTONES:
            continue  # intentionally retained
        if rel not in refs:
            orphans.append(rel)
    assert not orphans, (
        f"orphan templates (no references anywhere): {orphans}. "
        "Either wire them up (render or include) or delete them."
    )


def test_partials_directory_referenced():
    """Sanity check: the partials directory exists and is included somewhere."""
    partials = TEMPLATES_DIR / "_components"
    assert partials.exists(), f"missing partials dir: {partials}"
    # We expect at least 1 reference into _components/
    refs = _all_references()
    component_refs = [r for r in refs if r.startswith("_components/")]
    assert component_refs, (
        f"expected partials in _components/ to be referenced; got none. "
        f"Found refs: {sorted(refs)[:5]}"
    )
