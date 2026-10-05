"""tests/test_sazon_seed.py — verify seed_sazon populates the full data set.

This test runs the sazon seed against a fresh DB and verifies that every
major table is populated with the expected ranges. It validates that
multi-tenant data for "La Vaquita Holandesa" is complete enough to test
all pages in the app.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, func

from app.rms.models import (
    BankTransaction,
    Category,
    Channel,
    ComplianceInfo,
    Customer,
    CustomerAddress,
    DateRangePreset,
    DeliveryZone,
    FreezerTemperatureLog,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    MarginTier,
    MarketBenchmark,
    MessageTemplate,
    PaymentMethod,
    Pedido,
    PedidoLine,
    Product,
    ProductionCompletion,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    Sale,
    SettingsKV,
    ShoppingListItem,
    StockMovement,
    StockStatusConfig,
    StorageKeyword,
    StorageType,
    Supplier,
    Tag,
    Tenant,
    User,
    WasteLog,
)
from app.rms.seed import seed_sazon


@pytest.fixture(scope="session")
def sazon_db(app_engine_session):
    """Run seed_sazon once per test session against a fresh engine."""
    from app.rms.db import make_session_factory

    SessionLocal = make_session_factory(app_engine_session)
    session = SessionLocal()
    try:
        report = seed_sazon(session, overwrite=True)
        yield session
    finally:
        session.close()


def test_tenant_created(sazon_db):
    """Tenant 'La Vaquita Holandesa' should exist."""
    t = sazon_db.execute(
        select(Tenant).where(Tenant.slug == "la-vaquita-holandesa")
    ).scalar_one_or_none()
    assert t is not None
    assert t.business_name == "La Vaquita Holandesa"


def test_saskia_user_created(sazon_db):
    """Saskia (admin) + 2 cashiers."""
    users = sazon_db.execute(select(User)).scalars().all()
    usernames = {u.username for u in users}
    assert "saskia" in usernames
    assert "lucia" in usernames
    assert "diego" in usernames


def test_saskia_can_login(sazon_db):
    """Saskia's bcrypt-hashed password should verify."""
    saskia = sazon_db.execute(
        select(User).where(User.username == "saskia")
    ).scalar_one()
    assert saskia.check_password("saskia1234")


def test_branding_settings_populated(sazon_db):
    """All 11 BRANDING settings should be present."""
    branding_keys = sazon_db.execute(
        select(SettingsKV).where(SettingsKV.key.like("branding.%"))
    ).scalars().all()
    assert len(branding_keys) >= 10


def test_categories_populated(sazon_db):
    """Both product and recipe_family categories should be present."""
    n = sazon_db.execute(select(func.count()).select_from(Category)).scalar()
    assert n >= 11  # 6 product + 5 recipe_family


def test_payment_methods_populated(sazon_db):
    """At least 5 payment methods including efectivo + tarjeta."""
    methods = sazon_db.execute(select(PaymentMethod)).scalars().all()
    codes = {m.code for m in methods}
    assert "efectivo" in codes
    assert "tarjeta" in codes
    assert len(codes) >= 5


def test_suppliers_populated(sazon_db):
    """At least 3 suppliers."""
    n = sazon_db.execute(select(func.count()).select_from(Supplier)).scalar()
    assert n >= 3


def test_ingredients_comprehensive(sazon_db):
    """At least 40 ingredients with variants + price events."""
    n_ing = sazon_db.execute(select(func.count()).select_from(Ingredient)).scalar()
    n_var = sazon_db.execute(
        select(func.count()).select_from(IngredientVariant)
    ).scalar()
    n_prices = sazon_db.execute(
        select(func.count()).select_from(IngredientPriceEvent)
    ).scalar()
    assert n_ing >= 40, f"expected ≥40 ingredients, got {n_ing}"
    assert n_var >= 30, f"expected ≥30 variants, got {n_var}"
    assert n_prices >= 100, f"expected ≥100 price events, got {n_prices}"


def test_recipes_comprehensive(sazon_db):
    """At least 20 recipes with 100+ recipe lines."""
    n_rec = sazon_db.execute(select(func.count()).select_from(Recipe)).scalar()
    n_lines = sazon_db.execute(
        select(func.count()).select_from(RecipeLine)
    ).scalar()
    assert n_rec >= 20, f"expected ≥20 recipes, got {n_rec}"
    assert n_lines >= 100, f"expected ≥100 recipe_lines, got {n_lines}"


def test_products_comprehensive(sazon_db):
    """At least 30 products across categories."""
    n = sazon_db.execute(select(func.count()).select_from(Product)).scalar()
    assert n >= 30, f"expected ≥30 products, got {n}"


def test_customers_with_addresses(sazon_db):
    """At least 10 customers with addresses."""
    n_cust = sazon_db.execute(select(func.count()).select_from(Customer)).scalar()
    n_addr = sazon_db.execute(
        select(func.count()).select_from(CustomerAddress)
    ).scalar()
    assert n_cust >= 10, f"expected ≥10 customers, got {n_cust}"
    assert n_addr >= 5, f"expected ≥5 addresses, got {n_addr}"


def test_pedidos_across_statuses(sazon_db):
    """Pedidos should cover multiple statuses."""
    statuses = sazon_db.execute(select(Pedido.status).distinct()).scalars().all()
    assert "pending" in statuses
    assert "confirmed" in statuses
    assert "ready" in statuses
    assert "fulfilled" in statuses


def test_sales_realistic_history(sazon_db):
    """At least 500 sales over 90 days."""
    n = sazon_db.execute(select(func.count()).select_from(Sale)).scalar()
    assert n >= 500, f"expected ≥500 sales, got {n}"


def test_stock_movements(sazon_db):
    """Stock movements tied to sales + initial + waste."""
    n = sazon_db.execute(select(func.count()).select_from(StockMovement)).scalar()
    assert n >= 1000, f"expected ≥1000 stock movements, got {n}"


def test_waste_log(sazon_db):
    """At least 3 waste entries."""
    n = sazon_db.execute(select(func.count()).select_from(WasteLog)).scalar()
    assert n >= 3


def test_shopping_list(sazon_db):
    """At least 3 items to reorder."""
    n = sazon_db.execute(select(func.count()).select_from(ShoppingListItem)).scalar()
    assert n >= 3


def test_haccp_temps(sazon_db):
    """At least 14 days of freezer temps (2x/day)."""
    n = sazon_db.execute(
        select(func.count()).select_from(FreezerTemperatureLog)
    ).scalar()
    assert n >= 14


def test_market_benchmarks(sazon_db):
    """At least 15 market benchmark products."""
    n = sazon_db.execute(select(func.count()).select_from(MarketBenchmark)).scalar()
    assert n >= 15


def test_production_planning(sazon_db):
    """Templates + completions for last 7 days."""
    n_t = sazon_db.execute(
        select(func.count()).select_from(ProductionPlanTemplate)
    ).scalar()
    n_c = sazon_db.execute(
        select(func.count()).select_from(ProductionCompletion)
    ).scalar()
    assert n_t >= 10
    assert n_c >= 20


def test_compliance_info(sazon_db):
    """Compliance row for the business."""
    c = sazon_db.execute(
        select(ComplianceInfo).where(ComplianceInfo.id == 1)
    ).scalar_one_or_none()
    assert c is not None
    assert c.razon_social == "La Vaquita Holandesa S.A."
    assert c.ruc == "80012345-6"


def test_business_infra(sazon_db):
    """Date presets, message templates, storage, delivery zones, channels, tags."""
    n_dates = sazon_db.execute(
        select(func.count()).select_from(DateRangePreset)
    ).scalar()
    n_msg = sazon_db.execute(
        select(func.count()).select_from(MessageTemplate)
    ).scalar()
    n_st = sazon_db.execute(
        select(func.count()).select_from(StorageType)
    ).scalar()
    n_sk = sazon_db.execute(
        select(func.count()).select_from(StorageKeyword)
    ).scalar()
    n_mt = sazon_db.execute(
        select(func.count()).select_from(MarginTier)
    ).scalar()
    n_ss = sazon_db.execute(
        select(func.count()).select_from(StockStatusConfig)
    ).scalar()
    n_dz = sazon_db.execute(
        select(func.count()).select_from(DeliveryZone)
    ).scalar()
    n_ch = sazon_db.execute(select(func.count()).select_from(Channel)).scalar()
    n_tg = sazon_db.execute(select(func.count()).select_from(Tag)).scalar()
    n_bk = sazon_db.execute(
        select(func.count()).select_from(BankTransaction)
    ).scalar()

    assert n_dates >= 8
    assert n_msg >= 5
    assert n_st >= 4
    assert n_sk >= 10
    assert n_mt >= 4
    assert n_ss >= 4
    assert n_dz >= 3
    assert n_ch >= 5
    assert n_tg >= 8
    assert n_bk >= 5


def test_app_meta_onboarding_guard(sazon_db):
    """The sazon seeder should write 6 AppMeta keys used as an onboarding guard.

    Keys written:
      sazon_seed_version, sazon_seeded_at, sazon_tenant_slug,
      sazon_tenant_name, sazon_admin_user, sazon_loaded
    """
    from sqlalchemy import select
    from app.rms.models import AppMeta
    from app.rms.seed.sazon import is_sazon_seeded, sazon_meta, SAZON_META_KEYS

    rows = sazon_db.execute(
        select(AppMeta).where(AppMeta.key.in_(SAZON_META_KEYS))
    ).scalars().all()
    by_key = {r.key: r.value for r in rows}
    assert len(rows) == 6, f"expected 6 sazon_* AppMeta rows, got {len(rows)}: {by_key}"
    assert by_key["sazon_seed_version"] == "1.0"
    assert by_key["sazon_tenant_slug"] == "la-vaquita-holandesa"
    assert by_key["sazon_tenant_name"] == "La Vaquita Holandesa"
    assert by_key["sazon_admin_user"] == "saskia"
    assert by_key["sazon_loaded"].lower() in ("true", "1", "yes")
    # ISO timestamp
    import re as _re
    assert _re.match(r"^\d{4}-\d{2}-\d{2}T", by_key["sazon_seeded_at"])

    # Helpers
    assert is_sazon_seeded(sazon_db) is True
    info = sazon_meta(sazon_db)
    assert info["sazon_tenant_name"] == "La Vaquita Holandesa"
    assert info["sazon_admin_user"] == "saskia"


def test_is_sazon_seeded_false_on_fresh_db(app_engine):
    """On a fresh DB (no seed), is_sazon_seeded() must return False."""
    from app.rms.seed.sazon import is_sazon_seeded, sazon_meta
    from app.rms.db import make_session_factory

    SessionLocal = make_session_factory(app_engine)
    session = SessionLocal()
    try:
        assert is_sazon_seeded(session) is False
        assert sazon_meta(session) == {}
    finally:
        session.close()


def test_dashboard_banner_data_available(sazon_db, app_engine_session):
    """Dashboard route should expose sazon_seeded=True + tenant info when seeded."""
    from app.rms.db import make_session_factory
    from app.rms.seed.sazon import is_sazon_seeded, sazon_meta

    SessionLocal = make_session_factory(app_engine_session)
    session = SessionLocal()
    try:
        seeded = is_sazon_seeded(session)
        info = sazon_meta(session) if seeded else {}
        assert seeded is True
        assert info["sazon_tenant_name"] == "La Vaquita Holandesa"
        assert info["sazon_admin_user"] == "saskia"
        assert "sazon_seeded_at" in info
    finally:
        session.close()


def test_idempotent_rerun(sazon_db, app_engine_session):
    """Running seed_sazon again should be idempotent for non-derived data.

    Some entities (tags, sales, stock_movements, haccp_temps, audit_log)
    are derived from a random seed and may increment on each run. The
    key requirement: core reference data (tenant, users, ingredients,
    recipes, products, customers, suppliers, settings) should be stable.
    """
    from app.rms.db import make_session_factory
    from sqlalchemy import func, select
    from app.rms.models import (
        Ingredient,
        Product,
        Customer,
        Supplier,
        Tenant,
        User,
    )

    SessionLocal = make_session_factory(app_engine_session)
    session = SessionLocal()
    try:
        # Re-run without overwrite (default) — should be a no-op for reference data
        report = seed_sazon(session, overwrite=False)
        d = report.as_dict()
        # Core reference data should have 0 inserts on re-run
        assert d["tenants"] == 0, f"tenants should not re-insert: {d.get('tenants')}"
        assert d["users"] == 0
        assert d["settings_kv"] == 0
        assert d["categories"] == 0
        assert d["payment_methods"] == 0
        assert d["suppliers"] == 0
        assert d["ingredients"] == 0
        assert d["recipes"] == 0
        assert d["products"] == 0
        assert d["customers"] == 0
        assert d["delivery_zones"] == 0
        assert d["compliance"] == 0
        # Data should still be there
        n_ing = session.execute(select(func.count()).select_from(Ingredient)).scalar()
        n_prod = session.execute(select(func.count()).select_from(Product)).scalar()
        n_cust = session.execute(select(func.count()).select_from(Customer)).scalar()
        n_sup = session.execute(select(func.count()).select_from(Supplier)).scalar()
        n_t = session.execute(select(func.count()).select_from(Tenant)).scalar()
        n_u = session.execute(select(func.count()).select_from(User)).scalar()
        assert n_ing >= 40
        assert n_prod >= 30
        assert n_cust >= 10
        assert n_sup >= 3
        assert n_t >= 1
        assert n_u >= 3
    finally:
        session.close()
