"""tests/test_SASKIA-309_dev_pages_not_in_nav.py — SASKIA-309 regression lock.

Locks Phase 8.2 of the copy/UX hardening program.

The `/dev/*` routes are developer-only smoke pages (e.g.
`/dev/combo-smoke`). They must NOT appear in operator-facing navigation
(base.html sidebar/topbar, inicio.html, the nav definitions in
settings_kv/operator-sidebar, etc.).

This test scans every template for `href="/dev/...` patterns and
excludes only the dev page ITSELF (the page that owns the link —
a developer can still reach it by typing the URL).
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"

# Templates that are ALLOWED to reference /dev/* (the dev pages themselves)
SELF_REFS: set[str] = {
    "dev_combo_smoke.html",
}


def _all_template_files() -> list[Path]:
    return sorted(TEMPLATES_DIR.rglob("*.html"))


def _is_operator_facing(path: Path) -> bool:
    """A template is operator-facing if it's in the top-level templates
    directory (not under _components/, errors/, components/, etc.).
    The exact list of operator-facing files is the set we surface
    in the operator's left nav — for the test's purposes, that's
    '*.html' at the top level of app/templates/.
    """
    rel = path.relative_to(TEMPLATES_DIR)
    return len(rel.parts) == 1  # top-level only


def test_no_dev_links_in_operator_templates() -> None:
    """No operator-facing template may href to /dev/*."""
    offenders: list[str] = []
    for path in _all_template_files():
        if not _is_operator_facing(path):
            continue
        if path.name in SELF_REFS:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if 'href="/dev/' in line or "href='/dev/" in line:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        f"{len(offenders)} operator-facing templates link to /dev/*.\n"
        "Remove the link (developer pages should not be in operator nav).\n"
        + "\n".join(offenders[:10])
    )


def test_no_dev_links_in_base_html_specifically() -> None:
    """Specific check on base.html — the source of operator nav."""
    base = TEMPLATES_DIR / "base.html"
    if not base.exists():
        pytest.skip("base.html missing")
    text = base.read_text(encoding="utf-8")
    if 'href="/dev/' in text:
        first_line = next(line for line in text.splitlines() if 'href="/dev/' in line)
    else:
        first_line = "(none found)"
    assert 'href="/dev/' not in text, (
        f"base.html links to /dev/* — remove from operator nav.\nFirst occurrence: {first_line}"
    )


def test_no_dev_links_in_inicio_html() -> None:
    """Specific check on inicio.html — the operator's home dashboard."""
    inicio = TEMPLATES_DIR / "inicio.html"
    if not inicio.exists():
        pytest.skip("inicio.html missing")
    text = inicio.read_text(encoding="utf-8")
    assert 'href="/dev/' not in text, (
        "inicio.html links to /dev/* — operator dashboard must not surface dev URLs"
    )


def test_dev_pages_themselves_still_exist() -> None:
    """Lock that we don't accidentally delete the dev pages — they're
    still useful to developers, just not linked from operator UI."""
    for name in ("dev_combo_smoke.html",):
        p = TEMPLATES_DIR / name
        assert p.exists(), f"dev page missing: {p}"
