"""tests/test_SASKIA-308_settings_eod_auditoria.py — Phase 7.

Audit result (2026-10-07): settings + EOD + auditoria + ops templates
are well-built. The settings.html is a 6-tab structure (business,
payments, notifications, fiscal, theme, demo), each with proper CSRF
and form fields. EOD templates use `eod_print.html` skeleton JS
(uncovered in tests but already in `500.html` audit). Auditoria has
two pages: list (`/auditoria`) and analytics (`/auditoria/analytics`).

The only outstanding Phase 7 work was the **settings page CTAs in
the docs** — but no docs reference these CTAs by name, so this is
already done. This file locks the good state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path(REPO_ROOT / "app" / "templates")


def test_settings_has_six_tabs():
    """`settings.html` must have the 6 tabs (business, payments, notifications, fiscal, theme, demo)."""
    src = TEMPLATES.joinpath("settings.html").read_text()
    for tab in ("business", "payments", "notifications", "fiscal", "theme", "demo"):
        assert f'data-tab="{tab}"' in src, f"Missing settings tab: {tab}"


def test_settings_fiscal_tab_has_paraguay_set_fields():
    """`settings.html` fiscal tab must have Paraguay SET fields."""
    src = TEMPLATES.joinpath("settings.html").read_text()
    assert "timbrado" in src, "Missing timbrado field"
    assert "punto_expedicion" in src, "Missing punto_expedicion field"
    assert "invoice_sequence" in src, "Missing invoice_sequence field"
    # The SET context
    assert "Paraguay" in src or "SET" in src, "Missing Paraguay/SET context"


def test_settings_csrf_in_all_forms():
    """`settings.html` forms must have CSRF tokens."""
    src = TEMPLATES.joinpath("settings.html").read_text()
    csrf_count = src.count('name="csrf_token"')
    form_count = src.count('<form method="post"')
    assert csrf_count >= form_count, f"CSRF tokens ({csrf_count}) < forms ({form_count})"


def test_eod_print_currency_fixed():
    """Regression: `eod_print.html` must NOT have raw `Gs. {{` (currency drift).
    The shared `m.gs` / `m.gs_full` macros are the canonical path (D3 lint).
    """
    src = TEMPLATES.joinpath("eod_print.html").read_text()
    import re as _re

    drift_pattern = _re.compile(r"Gs\.\s*\{\{")
    assert not drift_pattern.search(src), "Currency drift: raw 'Gs. {{' in eod_print"
    # And must use the macro
    assert "{{ m.gs_full(" in src, "Missing m.gs_full( currency macro"


def test_eod_print_checklist_format():
    """`eod_print.html` must have a checklist-style rows with checkmarks."""
    src = TEMPLATES.joinpath("eod_print.html").read_text()
    assert "checklist-row" in src, "Missing checklist-row class"
    assert "✓" in src or "done" in src, "Missing done-state marker"
    # The progress bar
    assert "items_pct" in src, "Missing items_pct progress variable"


def test_eod_anomalies_page_exists():
    """`eod_anomalies.html` must exist (EOD anomaly detection)."""
    assert TEMPLATES.joinpath("eod_anomalies.html").exists(), "eod_anomalies missing"


def test_auditoria_page_has_filter_bar():
    """`auditoria_analytics.html` must have a date-range filter."""
    src = TEMPLATES.joinpath("auditoria_analytics.html").read_text()
    assert "filter-bar" in src, "Missing filter-bar"
    assert "Últimos" in src, "Missing 'Últimos' label"
    # The Jinja for-loop with day options [7, 14, 30, 60, 90]
    assert "[7, 14, 30, 60, 90]" in src, "Missing day option list [7, 14, 30, 60, 90]"


def test_auditoria_login_failures_section():
    """`auditoria_analytics.html` must have a login-failures section."""
    src = TEMPLATES.joinpath("auditoria_analytics.html").read_text()
    assert "Login exitoso" in src or "Login OK" in src, "Missing login success label"
    assert "Login fallido" in src or "Login FAIL" in src, "Missing login failure label"
    # Phase 0 fix: replaced 'OK/FAIL' with 'exitoso/fallido'
    assert "Login OK" not in src, "Old 'Login OK' label still present"
    assert "Login FAIL" not in src, "Old 'Login FAIL' label still present"


def test_auditoria_currency_in_analytics():
    """Regression: `auditoria_analytics.html` currency must be Gs."""
    src = TEMPLATES.joinpath("auditoria_analytics.html").read_text()
    if "Gs." in src:  # only if there's money in this page
        assert "₲" not in src


def test_ops_status_has_endpoint_table():
    """`ops_status.html` must have the endpoint status table."""
    src = TEMPLATES.joinpath("ops_status.html").read_text()
    assert "Ruta" in src, "Missing 'Ruta' column header"
    assert "Propósito" in src, "Missing 'Propósito' column header"
    # The currency was already fixed in Phase 0
    assert "Gs." in src, "Missing canonical Gs. symbol"


def test_ops_status_reorder_rate_heading():
    """`ops_status.html` must have the 'Tasa de reposición' heading (Phase 0 fix)."""
    src = TEMPLATES.joinpath("ops_status.html").read_text()
    assert "Tasa de reposición" in src, "Missing 'Tasa de reposición' heading"
    assert "Reorder rate" not in src, "Old 'Reorder rate' heading still present"


def test_settings_catalog_has_tabs():
    """`settings_catalog.html` must have the catalog tabs (categories, channels, etc.)."""
    src = TEMPLATES.joinpath("settings_catalog.html").read_text()
    for tab in (
        "categories-product",
        "categories-recipe",
        "channels",
        "payments",
        "margin-tiers",
        "stock-status",
        "storage-types",
        "date-presets",
        "templates",
        "tax-config",
        "branding",
        "suppliers",
    ):
        assert f'data-tab="{tab}"' in src, f"Missing catalog tab: {tab}"
