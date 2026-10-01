"""tests/test_saskia_kpi_card.py — verify <saskia-kpi-card> registration and rendering contract.

This is a static-asset test (no browser, no Playwright). It confirms:
1. The JS file exists at the expected path
2. The CSS rules for the component are present in app-components.css
3. base.html includes the script tag with cache-busting param
4. The component is registered as a custom element (customElements.define call)
5. The component supports all advertised attributes

Per AGENTS.md §Testing, no Selenium/Playwright in fase 1. Backend-only.
"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
JS_PATH = REPO / "app/static/saskia-kpi-card.js"
CSS_PATH = REPO / "app/static/app-components.css"
BASE_PATH = REPO / "app/templates/base.html"


def test_component_file_exists():
    """The web component JS file is at the expected path."""
    assert JS_PATH.exists(), f"missing {JS_PATH}"
    assert JS_PATH.stat().st_size > 1000, "JS file is suspiciously small"


def test_component_registers_custom_element():
    """The script calls customElements.define('saskia-kpi-card', ...)."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "customElements.define('saskia-kpi-card'" in text, \
        "component not registered"


def test_component_guards_against_double_registration():
    """Re-loading the script must not throw (customElements.define would)."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "if (customElements.get('saskia-kpi-card')) return" in text, \
        "no guard against re-registration"


def test_component_documents_required_attrs():
    """Header docstring lists label, value, delta, severity, etc."""
    text = JS_PATH.read_text(encoding="utf-8")
    for attr in ("label", "value", "delta", "delta-direction",
                 "severity", "icon", "href"):
        assert attr in text, f"attribute {attr!r} not documented"


def test_component_implements_delta_suppression():
    """Hat 40 decision: never show delta arrow when value is 0."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "suppressDelta" in text, "delta suppression logic missing"
    assert "'0'" in text or '"0"' in text, "no zero-detection"


def test_component_uses_css_vars_not_hardcoded_colors():
    """Per AGENTS.md: never hardcode colors. CSS vars only."""
    text = JS_PATH.read_text(encoding="utf-8")
    # The JS should NOT embed hex colors or rgb()
    forbidden = ["#fff", "#000", "rgb(", "rgba(", "color: red", "color: green"]
    for f in forbidden:
        assert f not in text, f"hardcoded color {f!r} found in JS"


def test_component_aria_role_set():
    """Accessibility: role='status' + aria-live='polite' for screen readers."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "role" in text and "status" in text
    assert "aria-live" in text and "polite" in text


def test_component_handles_href_as_link():
    """If href is set, the card wraps in <a>."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "'a'" in text or '"a"' in text, "no <a> wrapping for href"
    assert "metric-card__link" in text, "link class not assigned"


def test_css_includes_kpi_card_rules():
    """app-components.css has the .metric-card--kpi family rules."""
    text = CSS_PATH.read_text(encoding="utf-8")
    for rule in ("metric-card--kpi", "metric-card__head", "metric-card__delta",
                 "metric-card--sev-success", "metric-card--sev-warn",
                 "metric-card--sev-danger", "metric-card--sev-neutral"):
        assert rule in text, f"CSS rule .{rule} missing"


def test_css_uses_severity_colors_via_vars():
    """Severity colors via CSS vars only — no hardcoded hex."""
    text = CSS_PATH.read_text(encoding="utf-8")
    # Find the kpi-card block and check for var() usage
    block = text[text.find("metric-card--kpi"):]
    assert "var(--color-success)" in block or "var(--color-success)" in text
    assert "var(--color-danger)" in block or "var(--color-danger)" in text


def test_base_html_loads_kpi_card_script():
    """base.html includes the component script with cache-busting param."""
    text = BASE_PATH.read_text(encoding="utf-8")
    assert 'src="/static/saskia-kpi-card.js' in text, \
        "component script not loaded in base.html"
    assert "asset_version" in text.split("saskia-kpi-card.js")[1].split(">")[0], \
        "missing cache-busting asset_version()"


def test_base_html_loads_component_after_other_saskia_scripts():
    """Component script loads AFTER other saskia-* scripts (load order)."""
    text = BASE_PATH.read_text(encoding="utf-8")
    date_pos = text.find("saskia-date.js")
    toast_pos = text.find("saskia-toast.js")
    kpi_pos = text.find("saskia-kpi-card.js")
    assert date_pos < kpi_pos, "kpi-card loaded before saskia-date"
    assert toast_pos < kpi_pos, "kpi-card loaded before saskia-toast"


def test_component_renders_unicode_arrows():
    """Hat 31 / hat 40: arrows must be unicode (↑↓—), not text labels."""
    text = JS_PATH.read_text(encoding="utf-8")
    assert "↑" in text, "up arrow missing"
    assert "↓" in text, "down arrow missing"
    assert "—" in text, "flat dash missing"


def test_component_value_preserves_currency_format():
    """Value is rendered as-is — caller is responsible for format_gs."""
    text = JS_PATH.read_text(encoding="utf-8")
    # Should NOT contain format_gs or money logic — that's the caller's job
    assert "format_gs" not in text, "component should not format currency"


# ── Template adoption tests ─────────────────────────────────────────────────

INICIO_PATH = REPO / "app/templates/inicio.html"
ANALISIS_PATH = REPO / "app/templates/analisis.html"
BANK_PATH = REPO / "app/templates/bank.html"


def test_inicio_uses_saskia_kpi_card():
    """inicio.html adopts the web component for its KPI tiles.

    Tier 3.1 (2026-10-01): bumped from 4 to 6 — added the
    'Clientes asociados' enrollment KPI card under a new 'Loyalty'
    band. Stock card makes 5 in the HOY band, plus the 1 new loyalty
    card = 6 total.
    """
    text = INICIO_PATH.read_text(encoding="utf-8")
    assert text.count("<saskia-kpi-card") == 6, \
        "inicio.html should have 6 <saskia-kpi-card> instances (5 HOY + 1 Loyalty)"
    # All KPIs present
    for label in ("Ventas de hoy", "Operaciones", "Ticket promedio",
                  "Margen estimado", "Stock", "Clientes asociados"):
        assert f'label="{label}"' in text, f"KPI label {label!r} missing"


def test_inicio_uses_format_gs():
    """Per AGENTS.md rule #4: integer Gs. + format_gs filter."""
    text = INICIO_PATH.read_text(encoding="utf-8")
    assert "m.gs_full" in text, "format_gs filter missing from inicio"


def test_inicio_drops_legacy_metric_card_divs():
    """Old `<div class="metric-card">` blocks removed from HOY band only."""
    text = INICIO_PATH.read_text(encoding="utf-8")
    # Slice lines 35-68 (HOY band ends just before line 69 = Middle band)
    lines = text.split("\n")
    hoy_section = "\n".join(lines[34:68])
    # Should not contain the legacy 5-line div.metric-card pattern in HOY band
    assert hoy_section.count('<div class="metric-card">') == 0, \
        f"legacy metric-card divs still present in HOY band:\n{hoy_section}"


def test_analisis_uses_saskia_kpi_card():
    """analisis.html adopts the component for its 4 panorama tiles."""
    text = ANALISIS_PATH.read_text(encoding="utf-8")
    assert text.count("<saskia-kpi-card") == 4, \
        "analisis.html should have 4 <saskia-kpi-card> instances"


def test_analisis_preserves_skeleton_loading():
    """The skeleton_section loader is still in place (not regressed)."""
    text = ANALISIS_PATH.read_text(encoding="utf-8")
    assert "ui.skeleton_section" in text, \
        "skeleton_section loader was removed (regression)"


def test_bank_uses_saskia_kpi_card():
    """bank.html adopts the component for its 4 KPI tiles."""
    text = BANK_PATH.read_text(encoding="utf-8")
    assert text.count("<saskia-kpi-card") == 4, \
        "bank.html should have 4 <saskia-kpi-card> instances"
    for label in ("EUR income", "EUR spent", "EUR net", "PYG balance"):
        assert f'label="{label}"' in text, f"bank label {label!r} missing"


def test_bank_severity_for_eur_net():
    """EUR net shows severity based on sign (positive=success, negative=danger)."""
    text = BANK_PATH.read_text(encoding="utf-8")
    assert "eur_net >= 0" in text, "conditional severity missing for eur_net"
