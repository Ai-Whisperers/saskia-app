"""Tests for the static-content audit work (Phases 1-10).

Covers:
- DB-driven catalog CRUD (categories, channels, payment methods, etc.)
- Operator-tunable thresholds (margin tiers, stock status)
- SettingsKV-backed config (pricing, branding)
- Constants module fallbacks
- Message template rendering
- /api/* endpoints
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms import settings_runtime as sr
from app.rms.db import CURRENT_SCHEMA_VERSION, init_db

# ── Fixtures ───────────────────────────────────────────────────────
# Re-uses fixtures from tests/conftest.py:
#   - tmp_db_path: fresh temp SQLite file per test
#   - app_engine: SQLAlchemy engine on tmp_db_path
#   - session_factory: sessionmaker() bound to app_engine
#   - client: FastAPI TestClient with auth bypassed + session_factory wired
#
# We additionally wrap session_factory() with init_db() so all 48 migrations run.


@pytest.fixture()
def db_engine(app_engine):
    """Engine with all migrations applied (seeded data via init_db)."""
    init_db(app_engine)
    return app_engine


@pytest.fixture()
def session(session_factory):
    """A SQLAlchemy session bound to the test DB."""
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


# ── Schema migration ──────────────────────────────────────────────


def test_schema_is_current(db_engine):
    """All migrations applied (1-48)."""
    with db_engine.connect() as c:
        row = c.execute(
            __import__("sqlalchemy").text("SELECT value FROM app_meta WHERE key='schema_version'")
        ).first()
    assert row is not None
    assert int(row[0]) == CURRENT_SCHEMA_VERSION


# ── Categories ────────────────────────────────────────────────────


def test_categories_seeded(db_engine, session):
    """Migration 039 seeded 13 product + 13 recipe family rows."""
    from app.rms.categories import list_categories

    cats = list_categories(session, scope="product")
    assert len(cats) >= 13
    assert any(c.name == "Panadería" for c in cats)
    assert all(c.is_active for c in cats)

    fams = list_categories(session, scope="recipe_family")
    assert len(fams) >= 13
    assert any(f.name == "Tortas" for f in fams)


def test_get_or_create_category_idempotent(session):
    """get_or_create_category is idempotent on (scope, name)."""
    from app.rms.categories import get_or_create_category

    a = get_or_create_category(session, "Test Category", "product", sort_order=10)
    b = get_or_create_category(session, "Test Category", "product", sort_order=999)
    assert a.id == b.id
    assert b.sort_order == 10  # original value preserved


def test_get_or_create_rejects_invalid_scope(session):
    from app.rms.categories import get_or_create_category

    with pytest.raises(ValueError, match="Unknown scope"):
        get_or_create_category(session, "x", "invalid_scope")


# ── Channels ───────────────────────────────────────────────────────


def test_channels_seeded(db_engine, session):
    """Migration 041 seeded 5 channels with mostrador default."""
    from app.rms.catalogs import default_channel_code, list_channels

    channels = list_channels(session)
    assert len(channels) == 5
    codes = {c.code for c in channels}
    assert codes == {"mostrador", "mostrador-encargo", "whatsapp", "pedidosya", "monchis"}
    assert default_channel_code(session) == "mostrador"


def test_channel_default_switching(session):
    """The mostrador channel is marked is_default=True (from migration seed)."""
    from app.rms.catalogs import default_channel_code, list_channels

    channels = list_channels(session)
    defaults = [c for c in channels if c.is_default]
    assert len(defaults) == 1
    assert defaults[0].code == "mostrador"
    assert default_channel_code(session) == "mostrador"


# ── Payment methods ──────────────────────────────────────────────


def test_payment_methods_seeded(session):
    """Migration 042 seeded 5 payment methods."""
    from app.rms.catalogs import list_payment_methods

    methods = list_payment_methods(session)
    assert len(methods) == 5
    tarjeta = next(m for m in methods if m.code == "tarjeta")
    assert tarjeta.fee_pct == 3.0
    assert tarjeta.requires_reference is True


# ── Pricing markup ────────────────────────────────────────────────


def test_pricing_markup_default(session):
    """Migration 040 seeded default markup = 3.0x, round to 1000 Gs."""
    cfg = sr.get_pricing_markup(session)
    assert cfg["multiplier"] == 3.0
    assert cfg["round_to_gs"] == 1000


def test_compute_suggested_price_rounds_up():
    """Suggested price rounds UP to the nearest step (matches Math.ceil JS)."""
    # Cost 1234 × 3 = 3702 → ceil(3702/1000)*1000 = 4000
    assert sr.compute_suggested_price(1234) == 4000
    # Cost 1000 × 3 = 3000 → ceil(3000/1000)*1000 = 3000 (exact)
    assert sr.compute_suggested_price(1000) == 3000
    # Cost 1 × 3 = 3 → ceil(3/1000)*1000 = 1000
    assert sr.compute_suggested_price(1) == 1000


def test_set_pricing_markup_persists(session):
    sr.set_pricing_markup(session, 2.5, 500)
    session.commit()
    cfg = sr.get_pricing_markup(session)
    assert cfg["multiplier"] == 2.5
    assert cfg["round_to_gs"] == 500


def test_set_pricing_markup_rejects_zero(session):
    with pytest.raises(ValueError):
        sr.set_pricing_markup(session, 0)


# ── Branding ──────────────────────────────────────────────────────


def test_branding_default(session):
    """Migration 043 seeded default branding (footer normalized — no year;
    base.html appends the current year dynamically)."""
    b = sr.get_branding(session)
    assert b["business_name"] == "Sazón"
    assert "Panadería" in b["tagline"]
    assert b["footer"] == "Sistema local"


def test_set_branding_partial_update(session):
    sr.set_branding(session, business_name="Test Bakery")
    session.commit()
    b = sr.get_branding(session)
    assert b["business_name"] == "Test Bakery"
    # Other fields preserved
    assert "Panadería" in b["tagline"]


def test_set_branding_rejects_unknown_key(session):
    with pytest.raises(ValueError, match="Unknown branding key"):
        sr.set_branding(session, rogue_key="x")


def test_set_branding_rejects_too_long(session):
    with pytest.raises(ValueError, match="too long"):
        sr.set_branding(session, business_name="x" * 501)


# ── Margin tier ───────────────────────────────────────────────────


def test_margin_tier_default_seeded(session):
    """Migration 045 seeded 3 tiers matching legacy values."""
    from app.rms.margin_tier import list_margin_tiers

    tiers = list_margin_tiers(session)
    assert len(tiers) == 3
    top_10 = next(t for t in tiers if t.code == "top_10")
    assert top_10.max_cost_gs == 10000
    top_25 = next(t for t in tiers if t.code == "top_25")
    assert top_25.max_cost_gs == 5000
    bottom_25 = next(t for t in tiers if t.code == "bottom_25")
    assert bottom_25.min_cost_gs == 1000


def test_recipe_matches_tier_boundaries(session):
    """Top_10 matches costs <= 10000 (inclusive)."""
    from app.rms.margin_tier import get_margin_tier, recipe_matches_tier

    tier = get_margin_tier(session, "top_10")
    assert recipe_matches_tier(0, tier)
    assert recipe_matches_tier(5000, tier)
    assert recipe_matches_tier(10000, tier)  # inclusive
    assert not recipe_matches_tier(10001, tier)


def test_recipe_matches_tier_no_match_for_none_cost(session):
    """None cost never matches."""
    from app.rms.margin_tier import get_margin_tier, recipe_matches_tier

    tier = get_margin_tier(session, "top_10")
    assert not recipe_matches_tier(None, tier)


def test_filter_recipes_by_tier_missing_returns_all(session):
    """Missing tier code returns all recipes (defensive default)."""
    from app.rms.margin_tier import filter_recipes_by_tier

    recipes_with_cost = [(None, 100), (None, 5000), (None, 50000)]
    out = filter_recipes_by_tier(session, recipes_with_cost, "missing_tier_code")
    assert len(out) == 3


# ── Stock status ──────────────────────────────────────────────────


def test_stock_status_default_seeded(session):
    """Migration 046 seeded 4 statuses with legacy ratios/days."""
    from app.rms.stock_status import get_thresholds

    thresholds = get_thresholds(session)
    assert set(thresholds.keys()) == {"bajo_min", "critico", "sobrestock", "muerto"}
    assert thresholds["critico"].ratio == 0.5
    assert thresholds["sobrestock"].ratio == 5.0
    assert thresholds["muerto"].days == 30


def test_categorize_prioritizes_muerto(session):
    """muerto wins over critico when both conditions apply."""
    from app.rms.stock_status import categorize, get_thresholds

    thresholds = get_thresholds(session)
    # Stock=4 (ratio=0.4 → critico), but last consumed 60 days ago (muerto)
    last = datetime.now(timezone.utc) - timedelta(days=60)
    assert categorize(4, 10, last, thresholds) == "muerto"


def test_categorize_bajo_min_for_low_stock(session):
    from app.rms.stock_status import categorize, get_thresholds

    thresholds = get_thresholds(session)
    # muerto wins: last_consumed_at=None → "never consumed" → muerto
    assert categorize(10, 10, None, thresholds) == "muerto"
    # With a recent last_consumed_at, stock=5 min=10 → bajo_min
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    assert categorize(5, 10, recent, thresholds) == "bajo_min"


def test_categorize_sobrestock_for_high_ratio(session):
    from app.rms.stock_status import categorize, get_thresholds

    thresholds = get_thresholds(session)
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    # ratio=6 (stock=60, min=10) → sobrestock (after muerto check passes)
    assert categorize(60, 10, recent, thresholds) == "sobrestock"


def test_categorize_critico_for_low_ratio(session):
    from app.rms.stock_status import categorize, get_thresholds

    thresholds = get_thresholds(session)
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    # ratio=0.4 (stock=4, min=10) → critico
    assert categorize(4, 10, recent, thresholds) == "critico"


def test_categorize_never_consumed_is_muerto(session):
    from app.rms.stock_status import categorize, get_thresholds

    thresholds = get_thresholds(session)
    # last_consumed_at=None → treated as muerto
    assert categorize(100, 10, None, thresholds) == "muerto"


# ── Storage types ─────────────────────────────────────────────────


def test_storage_types_seeded(session):
    """Migration 047 seeded 3 HACCP codes."""
    from app.rms.storage_types import list_storage_types

    types_ = list_storage_types(session)
    assert len(types_) == 3
    codes = {t.code for t in types_}
    assert codes == {"ambient", "refrigerated", "frozen"}


def test_fallback_storage_codes_when_db_empty():
    """When DB has no rows, fallback_storage_codes returns defaults."""
    from app.rms.storage_types import fallback_storage_codes

    codes = fallback_storage_codes()
    assert codes == {"ambient", "refrigerated", "frozen"}


# ── Date presets ─────────────────────────────────────────────────


def test_date_presets_seeded(session):
    """Migration 048 seeded 5 presets."""
    from app.rms.date_presets import list_presets

    presets = list_presets(session)
    assert len(presets) == 5
    codes = {p.code for p in presets}
    assert codes == {"today", "week", "month", "quarter", "year"}
    assert presets[0].code == "today"  # sort_order=10 first
    assert presets[0].is_default is True


def test_get_preset_days_returns_none_for_missing(session):
    from app.rms.date_presets import get_preset_days

    assert get_preset_days(session, "month") == 30
    assert get_preset_days(session, "missing") is None


# ── Constants module ─────────────────────────────────────────────


def test_constants_module_has_required_values():
    """Phase 10 constants module exposes all the values."""
    from app.rms.constants import (
        CURRENCY_CODE,
        CURRENCY_SYMBOL,
        DEFAULT_IVA_RATE,
        DEFAULT_LABOR_COST_PER_HOUR_GS,
        DEFAULT_OVERHEAD_MULTIPLIER_PCT,
        DEFAULT_TAX_REGIME,
        INVOICE_TYPES,
        VALID_IVA_RATES,
        VALID_TAX_REGIMES,
    )

    assert CURRENCY_CODE == "PYG"
    assert CURRENCY_SYMBOL == "Gs."
    assert DEFAULT_IVA_RATE == "10"
    assert DEFAULT_TAX_REGIME == "resimple"
    assert DEFAULT_LABOR_COST_PER_HOUR_GS == 25_000
    assert DEFAULT_OVERHEAD_MULTIPLIER_PCT == 15
    assert "10" in VALID_IVA_RATES and "5" in VALID_IVA_RATES
    assert "resimple" in VALID_TAX_REGIMES
    assert INVOICE_TYPES == frozenset({"boleta_resimple", "factura", "none"})


# ── API endpoints ────────────────────────────────────────────────


def test_api_categories_returns_seeded_data(client):
    r = client.get("/api/categories?scope=product")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 13
    assert all("name" in c and "scope" in c for c in data)


def test_api_channels_returns_seeded_data(client):
    r = client.get("/api/channels")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    assert any(c["code"] == "mostrador" for c in data)


def test_api_payment_methods_returns_seeded_data(client):
    r = client.get("/api/payment-methods")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5


def test_api_pricing_markup_roundtrip(client):
    """POST + GET pricing-markup works."""
    # Read default
    r = client.get("/api/settings/pricing-markup")
    assert r.status_code == 200
    assert r.json()["multiplier"] == 3.0

    # Change it
    r = client.post("/api/settings/pricing-markup", json={"multiplier": 2.5, "round_to_gs": 500})
    assert r.status_code == 200
    assert r.json()["multiplier"] == 2.5

    # Verify
    r = client.get("/api/settings/pricing-markup")
    assert r.json()["multiplier"] == 2.5

    # Restore
    client.post("/api/settings/pricing-markup", json={"multiplier": 3.0, "round_to_gs": 1000})


def test_api_branding_roundtrip(client):
    r = client.post(
        "/api/settings/branding",
        json={"business_name": "Test Bakery"},
    )
    assert r.status_code == 200
    assert r.json()["business_name"] == "Test Bakery"

    # Restore
    client.post(
        "/api/settings/branding",
        json={"business_name": "Sazón"},
    )


def test_api_categories_create_then_delete(client):
    """POST creates a new category, DELETE removes it (soft)."""
    # Create
    r = client.post(
        "/api/categories",
        json={"name": "Test Create Delete", "scope": "product", "sort_order": 999},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]

    # Verify visible
    r = client.get("/api/categories?scope=product")
    assert any(c["id"] == new_id for c in r.json())

    # Delete
    r = client.post(f"/api/categories/{new_id}/delete")
    assert r.status_code == 200

    # Verify gone from active list
    r = client.get("/api/categories?scope=product")
    assert not any(c["id"] == new_id for c in r.json())


def test_api_tax_config_full_snapshot(client):
    r = client.get("/api/tax-config")
    assert r.status_code == 200
    data = r.json()
    assert data["iva_rate"] == "10"
    assert data["tax_regime"] == "resimple"
    assert "labor_cost_per_hour_gs" in data
    assert "overhead_multiplier_pct" in data
    assert "10" in data["valid_iva_rates"]


def test_api_storage_types_crud(client):
    """Create, list, update, delete flow."""
    # Create
    r = client.post(
        "/api/storage-types",
        json={"code": "test_storage", "label": "Test Storage", "sort_order": 100},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]

    # Update
    r = client.post(
        f"/api/storage-types/{new_id}/update",
        json={"label": "Updated Test"},
    )
    assert r.status_code == 200

    # Delete
    r = client.post(f"/api/storage-types/{new_id}/delete")
    assert r.status_code == 200


def test_api_date_presets_crud(client):
    r = client.post(
        "/api/date-presets",
        json={"code": "test_period", "label": "Test Period", "days": 14},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]
    r = client.post(f"/api/date-presets/{new_id}/delete")
    assert r.status_code == 200


def test_api_channels_crud(client):
    r = client.post(
        "/api/channels",
        json={"code": "test_ch", "label": "Test CH", "sort_order": 100},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]
    r = client.post(f"/api/channels/{new_id}/delete")
    assert r.status_code == 200


def test_api_payment_methods_crud(client):
    r = client.post(
        "/api/payment-methods",
        json={"code": "test_pm", "label": "Test PM", "fee_pct": 2.5},
    )
    assert r.status_code == 200
    new_id = r.json()["id"]
    r = client.post(f"/api/payment-methods/{new_id}/delete")
    assert r.status_code == 200


def test_api_margin_tier_update(client):
    """Update changes persist."""
    # Get any tier
    r = client.get("/api/margin-tiers")
    assert r.status_code == 200
    tier = r.json()[0]

    # Save original
    original_max = tier["max_cost_gs"]

    # Update
    new_max = 25000 if original_max != 25000 else 50000
    r = client.post(
        f"/api/margin-tiers/{tier['id']}/update",
        json={"max_cost_gs": new_max},
    )
    assert r.status_code == 200
    assert r.json()["max_cost_gs"] == new_max

    # Restore
    client.post(
        f"/api/margin-tiers/{tier['id']}/update",
        json={"max_cost_gs": original_max} if original_max else {"max_cost_gs": 0},
    )


def test_api_templates_list(client):
    r = client.get("/api/templates")
    assert r.status_code == 200
    data = r.json()
    # 6 templates seeded
    assert len(data) >= 6
    keys = {(t["channel"], t["key"]) for t in data}
    assert ("whatsapp", "pedido_listo") in keys
    assert ("email", "resumen_diario") in keys


# ── Helper: render_template ───────────────────────────────────────


def test_render_template_substitutes_variables():
    """render_template replaces {var} tokens."""
    from app.routers.settings_runtime import render_template

    out = render_template(
        "Hola {name}, total: Gs. {total}",
        {"name": "the operator", "total": 5000},
    )
    assert out == "Hola the operator, total: Gs. 5000"


def test_render_template_falls_back_on_missing_var():
    from app.routers.settings_runtime import render_template

    body = "Hola {name}, total: Gs. {total}"
    out = render_template(body, {"name": "the operator"})  # missing total
    # Falls back to raw body
    assert out == body


# ── Unit enum (Phase 3) ──────────────────────────────────────────


def test_unit_enum_has_all_canonical_units():
    """Phase 3 — Unit enum covers all 5 canonical units."""
    from app.rms.units import Unit

    codes = {u.value for u in Unit}
    assert codes == {"g", "kg", "ml", "l", "und"}


def test_unit_coerce_handles_aliases():
    """Unit.coerce accepts aliases like 'gramos' → g."""
    from app.rms.units import Unit

    assert Unit.coerce("gramos") == Unit.G
    assert Unit.coerce("kilo") == Unit.KG
    assert Unit.coerce("mililitros") == Unit.ML
    assert Unit.coerce("litros") == Unit.L
    assert Unit.coerce("unidades") == Unit.UNIT
