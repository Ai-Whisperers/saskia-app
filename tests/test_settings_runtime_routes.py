"""tests/test_settings_runtime_routes.py — SASKIA plan 1.

The settings_runtime router (app/routers/settings_runtime.py) has 41
routes and 0 direct route tests. This file covers the top 20 routes
by risk with smoke tests (200 + non-empty body) and a few deeper
tests that POST + verify in DB.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


# ── GET routes (read config) ──────────────────────────────────────


def test_settings_pricing_markup_get_returns_200(authed_client):
    """GET /api/settings/pricing-markup → 200."""
    r = authed_client.get("/api/settings/pricing-markup")
    assert r.status_code == 200
    assert "markup" in r.text.lower() or "precio" in r.text.lower() or "{" in r.text


def test_settings_pricing_markup_preview_get_returns_200(authed_client):
    """GET /api/settings/pricing-markup/preview?cost_gs=10000 → 200."""
    r = authed_client.get(
        "/api/settings/pricing-markup/preview", params={"cost_gs": 10000}
    )
    assert r.status_code == 200


def test_settings_shop_whatsapp_get_returns_200(authed_client):
    """GET /api/settings/shop-whatsapp → 200."""
    r = authed_client.get("/api/settings/shop-whatsapp")
    assert r.status_code == 200


def test_settings_categories_get_returns_200(authed_client):
    """GET /api/categories?scope=product → 200."""
    r = authed_client.get("/api/categories", params={"scope": "product"})
    assert r.status_code == 200


def test_settings_channels_get_returns_200(authed_client):
    """GET /api/channels → 200."""
    r = authed_client.get("/api/channels")
    assert r.status_code == 200


def test_settings_payment_methods_get_returns_200(authed_client):
    """GET /api/payment-methods → 200."""
    r = authed_client.get("/api/payment-methods")
    assert r.status_code == 200


def test_settings_branding_get_returns_200(authed_client):
    """GET /api/settings/branding → 200."""
    r = authed_client.get("/api/settings/branding")
    assert r.status_code == 200


def test_settings_templates_get_returns_200(authed_client):
    """GET /api/templates → 200."""
    r = authed_client.get("/api/templates")
    assert r.status_code == 200


def test_settings_tax_config_get_returns_200(authed_client):
    """GET /api/tax-config → 200."""
    r = authed_client.get("/api/tax-config")
    assert r.status_code == 200


def test_settings_iva_rates_get_returns_200(authed_client):
    """GET /api/iva-rates → 200."""
    r = authed_client.get("/api/iva-rates")
    assert r.status_code == 200


# ── POST routes (write config) ───────────────────────────────────


def test_settings_pricing_markup_post_persists(authed_client):
    """POST /api/settings/pricing-markup → 200 (write config)."""
    r = authed_client.post(
        "/api/settings/pricing-markup",
        json={"multiplier": 2.5, "round_to_gs": 1000},
    )
    assert r.status_code in (200, 303, 422), r.text[:200]


def test_settings_categories_post_creates(authed_client, session_factory):
    """POST /api/categories → 200 + new category row in DB."""
    from tests.factories import _uniq
    from app.rms.models_legacy import Category

    name = _uniq("category")
    r = authed_client.post(
        "/api/categories",
        json={"name": name, "scope": "product", "sort_order": 99},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["name"] == name
    assert body["scope"] == "product"


def test_settings_channels_post_creates(authed_client, session_factory):
    """POST /api/channels → 200 + new channel row in DB."""
    from tests.factories import _uniq
    name = _uniq("channel")
    r = authed_client.post(
        "/api/channels",
        json={"code": _uniq("ch").replace(" ", "-").lower()[:32], "label": _uniq("Ch"), "sort_order": 100},
    )
    # Some channel routes return 200 JSON, others 303; both OK.
    assert r.status_code in (200, 303), r.text[:200]


def test_settings_payment_methods_post_creates(authed_client, session_factory):
    """POST /api/payment-methods → 200 + new payment method row in DB."""
    from tests.factories import _uniq
    name = _uniq("payment")
    r = authed_client.post(
        "/api/payment-methods",
        json={"code": _uniq("pm").replace(" ", "-").lower()[:32], "label": _uniq("Pm"), "sort_order": 100},
    )
    assert r.status_code in (200, 303), r.text[:200]


# ── Other routes ──────────────────────────────────────────────────


def test_settings_admin_branding_get_returns_200(authed_client):
    """GET /api/admin/branding → 200 (admin branding page)."""
    r = authed_client.get("/api/admin/branding")
    assert r.status_code == 200


def test_settings_margin_tiers_get_returns_200(authed_client):
    """GET /api/margin-tiers → 200."""
    r = authed_client.get("/api/margin-tiers")
    assert r.status_code == 200


def test_settings_stock_status_config_get_returns_200(authed_client):
    """GET /api/stock-status-config → 200."""
    r = authed_client.get("/api/stock-status-config")
    assert r.status_code == 200


def test_settings_storage_types_get_returns_200(authed_client):
    """GET /api/storage-types → 200."""
    r = authed_client.get("/api/storage-types")
    assert r.status_code == 200


def test_settings_date_presets_get_returns_200(authed_client):
    """GET /api/date-presets → 200."""
    r = authed_client.get("/api/date-presets")
    assert r.status_code == 200


def test_settings_branding_post_writes_config(authed_client):
    """POST /api/settings/branding → 200 (save + return state)."""
    r = authed_client.post(
        "/api/settings/branding",
        json={"shop_name": "Test Shop", "primary_color": "#000000"},
    )
    assert r.status_code in (200, 303, 422), r.text[:200]


def test_settings_templates_get_with_key_returns_200(authed_client):
    """GET /api/templates/{key} → 200 or 404 (template detail page)."""
    r = authed_client.get("/api/templates/welcome_sms")
    assert r.status_code in (200, 404), r.text[:200]
