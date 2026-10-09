"""tests/test_SASKIA-301_columns.py — Phase 0, step 0.6.

Locks the fix for column header abbreviations:
  - `(Gs)` → `(Gs.)` in money column headers
  - `Wholesale Gs.` / `Retail Gs.` / `Mercado promedio Gs.` / `Mercado avg Gs.` are OK
    (they end with period; just trailing-period consistency)

Also locks the placeholder `25000` → `25.000` per copy-vos.md period thousands separator.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]

from tests.conftest import REPO_ROOT

TEMPLATES = REPO_ROOT / "app" / "templates"


def test_no_bare_gs_in_money_column_headers():
    """`Precio (Gs)` and similar should be `Precio (Gs.)` (with period)."""
    for fname in ["menu_import_ocr.html"]:
        src = (TEMPLATES / fname).read_text()
        assert "(Gs)<" not in src, f"'Precio (Gs)' (no period) still in {fname}"


def test_menus_placeholder_uses_thousands_separator():
    """`/menus` placeholder must be `25.000` per copy-vos.md period thousands sep."""
    src = (TEMPLATES / "menus.html").read_text()
    assert 'placeholder="25.000"' in src, "Expected '25.000' placeholder in menus.html"
    assert 'placeholder="25000"' not in src, "Old '25000' placeholder still in menus.html"
