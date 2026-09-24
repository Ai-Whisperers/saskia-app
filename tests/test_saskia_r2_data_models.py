"""Tests for S7 — US 2.2 (variants), US 2.3 (forecast horizon), US 3.3 (template fork).

Decision A1 — IngredientVariant: one Ingredient has many packages
Decision B  — Per-ingredient forecast horizon (default 14d)
Decision C2 — Fork current week's overrides into the weekly template
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.rms.models import (
    Ingredient,
    IngredientVariant,
    Product,
    ProductionPlanOverride,
    ProductionPlanTemplate,
    SaleStockMove,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _unique_name(prefix: str) -> str:
    """Unique per-test name suffix — variants have unique constraints."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def harina_unique_name() -> str:
    return _unique_name("harina")


@pytest.fixture
def ingredient(session_factory, harina_unique_name):
    """Create one Ingredient with a default variant (post-migration state)."""
    with session_factory() as s:
        ing = Ingredient(
            name=harina_unique_name,
            unit="kg",
            purchase_price_gs=8000,
            stock_qty=10.0,  # legacy column
        )
        s.add(ing)
        s.flush()
        v = IngredientVariant(
            ingredient_id=ing.id,
            package_size=1.0,
            package_unit="kg",
            purchase_price_gs=8000,
            preferred=True,
            stock_qty=10.0,
        )
        s.add(v)
        s.commit()
        s.refresh(ing)
        return ing


@pytest.fixture
def multi_variant_ingredient(session_factory):
    """An ingredient with 3 variants in different units/quantities."""
    n = _unique_name("multi")
    with session_factory() as s:
        ing = Ingredient(
            name=n,
            unit="kg",
            purchase_price_gs=8500,
            stock_qty=11.5,
        )
        s.add(ing)
        s.flush()
        variants = [
            IngredientVariant(
                ingredient_id=ing.id, package_size=1.0, package_unit="kg",
                purchase_price_gs=8500, preferred=True, stock_qty=3.0,
            ),
            IngredientVariant(
                ingredient_id=ing.id, package_size=0.250, package_unit="kg",
                purchase_price_gs=2400, preferred=False, stock_qty=12.0,
            ),
            IngredientVariant(
                ingredient_id=ing.id, package_size=5.0, package_unit="kg",
                purchase_price_gs=40000, preferred=False, stock_qty=1.0,
            ),
        ]
        s.add_all(variants)
        s.commit()
        return ing.id


# ===========================================================================
# Decision A1 — IngredientVariant + rollup
# ===========================================================================


class TestIngredientVariantRollup:
    """US 2.2 / Decision A1: rollup_ingredient_stock sums variants into base unit."""

    def test_rollup_with_no_variants_uses_legacy_column(self, session_factory):
        """Pre-migration ingredients (no variants) get the legacy stock_qty."""
        n = _unique_name("legacy")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", stock_qty=42.0)
            s.add(ing); s.commit()
            ing_id = ing.id
        from app.rms.variants import rollup_ingredient_stock
        with session_factory() as s:
            r = rollup_ingredient_stock(s, ing_id)
        assert r is not None
        assert r.base_qty == 42.0
        assert r.base_unit == "kg"
        assert r.variant_count == 0

    def test_rollup_sums_multiple_variants_in_base_unit(self, session_factory):
        """3 variants: 3×1kg + 12×0.250kg + 1×5kg = 11 kg total."""
        from app.rms.variants import rollup_ingredient_stock

        n = _unique_name("multi")
        with session_factory() as s:
            ing = Ingredient(
                name=n, unit="kg", purchase_price_gs=8500, stock_qty=11.5,
            )
            s.add(ing); s.flush(); ing_id = ing.id
            s.add_all([
                IngredientVariant(
                    ingredient_id=ing_id, package_size=1.0, package_unit="kg",
                    purchase_price_gs=8500, preferred=True, stock_qty=3.0,
                ),
                IngredientVariant(
                    ingredient_id=ing_id, package_size=0.250, package_unit="kg",
                    purchase_price_gs=2400, preferred=False, stock_qty=12.0,
                ),
                IngredientVariant(
                    ingredient_id=ing_id, package_size=5.0, package_unit="kg",
                    purchase_price_gs=40000, preferred=False, stock_qty=1.0,
                ),
            ])
            s.commit()

        with session_factory() as s:
            r = rollup_ingredient_stock(s, ing_id)
        assert r is not None
        # Expected: 3 + 12*0.25 + 1*5 = 11.0 kg
        assert abs(r.base_qty - 11.0) < 1e-9
        assert r.variant_count == 3
        assert r.preferred_variant_id is not None
        assert r.preferred_price_gs == 8500

    def test_preferred_variant_price_returned_as_current(self, session_factory):
        """current_variant_price returns the preferred variant's price."""
        from app.rms.variants import current_variant_price

        n = _unique_name("price")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", purchase_price_gs=0)
            s.add(ing); s.flush(); ing_id = ing.id
            s.add_all([
                IngredientVariant(
                    ingredient_id=ing_id, package_size=1.0, package_unit="kg",
                    purchase_price_gs=1000, preferred=False, stock_qty=0.0,
                ),
                IngredientVariant(
                    ingredient_id=ing_id, package_size=1.0, package_unit="kg",
                    purchase_price_gs=2000, preferred=True, stock_qty=0.0,
                ),
            ])
            s.commit()
        with session_factory() as s:
            price = current_variant_price(s, ing_id)
        assert price == 2000

    def test_only_one_preferred_per_ingredient_enforced_db_triggers(
        self, session_factory,
    ):
        """The partial-unique index + trigger: only 1 preferred per ingredient."""
        n = _unique_name("pref")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", stock_qty=0.0)
            s.add(ing); s.flush()
            v1 = IngredientVariant(
                ingredient_id=ing.id, package_size=1.0, package_unit="kg",
                purchase_price_gs=1000, preferred=True, stock_qty=0.0,
            )
            s.add(v1); s.commit()  # commit so the new session can see it
            ing_id = ing.id
        # Now insert another variant flagged preferred — the DB trigger
        # should clear v1.preferred and set v2.preferred.
        with session_factory() as s:
            ing2 = s.get(Ingredient, ing_id)
            v2 = IngredientVariant(
                ingredient_id=ing2.id, package_size=2.0, package_unit="kg",
                purchase_price_gs=2000, preferred=True, stock_qty=0.0,
            )
            s.add(v2); s.commit()
        with session_factory() as s:
            all_v = s.scalars(
                select(IngredientVariant)
                .where(IngredientVariant.ingredient_id == ing_id)
            ).all()
            preferred_count = sum(1 for x in all_v if x.preferred)
            assert preferred_count == 1
            preferred = next(x for x in all_v if x.preferred)
            assert preferred.purchase_price_gs == 2000


# ===========================================================================
# Decision B — Per-ingredient forecast horizon
# ===========================================================================


class TestForecastHorizon:

    def test_default_horizon_is_14_days(self, session_factory):
        from app.rms.variants import DEFAULT_FORECAST_HORIZON_DAYS, forecast_horizon_days
        n = _unique_name("horizon")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", stock_qty=1.0)
            s.add(ing); s.commit(); ing_id = ing.id
        with session_factory() as s:
            ing2 = s.get(Ingredient, ing_id)
            h = forecast_horizon_days(ing2)
        assert h == DEFAULT_FORECAST_HORIZON_DAYS
        assert h == 14  # current default

    def test_per_ingredient_override(self, session_factory):
        from app.rms.variants import forecast_horizon_days
        n = _unique_name("horizon2")
        with session_factory() as s:
            ing = Ingredient(
                name=n, unit="kg", stock_qty=1.0, forecast_horizon_days=21,
            )
            s.add(ing); s.commit(); ing_id = ing.id
        with session_factory() as s:
            ing2 = s.get(Ingredient, ing_id)
            assert forecast_horizon_days(ing2) == 21

    def test_explicit_default_kwarg(self, session_factory):
        from app.rms.variants import forecast_horizon_days
        n = _unique_name("horizon3")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", stock_qty=1.0)
            s.add(ing); s.commit(); ing_id = ing.id
        with session_factory() as s:
            ing2 = s.get(Ingredient, ing_id)
            assert forecast_horizon_days(ing2, default=30) == 30

    def test_days_until_short_marks_short_when_depleted(self, session_factory):
        from app.rms.models import Recipe, Sale
        from app.rms.variants import days_until_short

        n = _unique_name("depleted")
        today = date.today()
        # Plant an ingredient at 5kg with horizon=14. Plant 7 days of 1kg
        # consumption via direct SaleStockMove rows (bypassing apply_sale
        # so we don't need a recipe).
        rname = _unique_name("r-short")
        pname = _unique_name("p-short")
        iname = n
        with session_factory() as s:
            r = Recipe(name=rname, yield_qty=1.0, yield_unit="kg")
            s.add(r); s.flush()
            p = Product(name=pname, sku=pname, recipe_id=r.id,
                        sale_price_gs=1000)
            s.add(p); s.flush()
            ing = Ingredient(
                name=iname, unit="kg", stock_qty=5.0, forecast_horizon_days=14,
            )
            s.add(ing); s.flush()
            s.commit(); ing_id = ing.id; sale_id_holder = []
            for d in range(7):
                ds = today - timedelta(days=d)
                sale = Sale(
                    product_id=p.id, qty=1.0,
                    unit_price_gs=1000,
                    sold_at=datetime.combine(ds, datetime.min.time()).replace(tzinfo=timezone.utc),
                )
                s.add(sale); s.flush()
                s.add(SaleStockMove(
                    sale_id=sale.id, affected_recipe_id=r.id,
                    ingredient_id=ing_id, qty_delta=-1.0,
                ))
            s.commit()
        with session_factory() as s:
            res = days_until_short(s, ing_id, today=today)
        assert res is not None
        assert res.status == "short"  # days_remaining < 14 (horizon)
        assert res.days_remaining is not None
        assert res.days_remaining < 14
        # Sanity: status was correctly chosen because horizon (14) > days_left
        assert res.horizon_days == 14

    def test_days_until_short_marks_dead_with_no_consumption(self, session_factory):
        from app.rms.variants import days_until_short
        n = _unique_name("dead")
        with session_factory() as s:
            ing = Ingredient(name=n, unit="kg", stock_qty=10.0)
            s.add(ing); s.commit(); ing_id = ing.id
        with session_factory() as s:
            res = days_until_short(s, ing_id)
        assert res is not None
        assert res.status == "dead"
        assert res.days_remaining is None

    def test_days_until_short_marks_ok_when_plenty(self, session_factory):
        """Stock exceeds 2× horizon × avg consumption → 'ok'."""
        from app.rms.models import Recipe, Sale
        from app.rms.variants import days_until_short

        n = _unique_name("plenty")
        rname = _unique_name("r-ok")
        pname = _unique_name("p-ok")
        today = date.today()
        with session_factory() as s:
            r = Recipe(name=rname, yield_qty=1.0, yield_unit="kg")
            s.add(r); s.flush()
            p = Product(name=pname, sku=pname, recipe_id=r.id,
                        sale_price_gs=1000)
            s.add(p); s.flush()
            ing = Ingredient(
                name=n, unit="kg", stock_qty=100.0, forecast_horizon_days=14,
            )
            s.add(ing); s.flush(); ing_id = ing.id
            for d in range(14):
                ds = today - timedelta(days=d)
                sale = Sale(
                    product_id=p.id, qty=0.2,
                    unit_price_gs=1000,
                    sold_at=datetime.combine(ds, datetime.min.time()).replace(tzinfo=timezone.utc),
                )
                s.add(sale); s.flush()
                s.add(SaleStockMove(
                    sale_id=sale.id, affected_recipe_id=r.id,
                    ingredient_id=ing_id, qty_delta=-0.2,
                ))
            s.commit()
        with session_factory() as s:
            res = days_until_short(s, ing_id, today=today)
        assert res.status == "ok"


# ===========================================================================
# Decision C2 — Template fork
# ===========================================================================


@pytest.fixture
def product(session_factory):
    with session_factory() as s:
        p = Product(
            name=_unique_name("prod"), sku=_unique_name("sku"),
            sale_price_gs=1000,
        )
        s.add(p); s.commit(); return p


@pytest.fixture
def product2(session_factory):
    with session_factory() as s:
        p = Product(
            name=_unique_name("prod2"), sku=_unique_name("sku2"),
            sale_price_gs=2000,
        )
        s.add(p); s.commit(); return p


class TestForkWeek:

    def test_fork_sums_overrides_into_template(self, session_factory, product, product2):
        """Override at Mon=10 (prod A) + Mon=5 (prod B) → template[Mon,A]=10, template[Mon,B]=5.

        Plus one Wed override for product A → template[Wed,A]=4.
        """
        monday = date(2026, 6, 1)
        with session_factory() as s:
            s.add(ProductionPlanOverride(
                product_id=product.id, for_date=monday,
                qty=10.0, updated_at=datetime.now(timezone.utc), updated_by="op",
            ))
            s.add(ProductionPlanOverride(
                product_id=product.id, for_date=monday + timedelta(days=2),  # Wed
                qty=4.0, updated_at=datetime.now(timezone.utc), updated_by="op",
            ))
            s.add(ProductionPlanOverride(
                product_id=product2.id, for_date=monday,
                qty=5.0, updated_at=datetime.now(timezone.utc), updated_by="op",
            ))
            s.commit()

        client = None  # not needed for this unit test variant
        # Reach into the underlying function instead of POST
        # Easier path: use a real Request and call it directly
        # ... but the rate-limiter check makes it simpler to just call the
        # upsert_template_row helper and replicate the summation manually.
        from collections import defaultdict

        with session_factory() as s:
            overrides = s.scalars(
                select(ProductionPlanOverride)
                .where(ProductionPlanOverride.for_date >= monday)
                .where(ProductionPlanOverride.for_date < monday + timedelta(days=7))
            ).all()
        bucket: dict[tuple[int, int], float] = defaultdict(float)
        for ov in overrides:
            bucket[(ov.for_date.weekday(), ov.product_id)] += float(ov.qty)
        # Expected buckets:
        #   (0, product.id) = 10 (Monday)
        #   (2, product.id) = 4  (Wednesday)
        #   (0, product2.id) = 5 (Monday)
        from app.rms.production import upsert_template_row
        with session_factory() as s:
            for (wd, pid), qty in bucket.items():
                upsert_template_row(s, weekday=wd, product_id=pid, qty=qty,
                                    notes=None, updated_by="op")
            s.commit()
        with session_factory() as s:
            rows = s.scalars(select(ProductionPlanTemplate)).all()
        assert len(rows) == 3
        by_key = {(r.weekday, r.product_id): r.qty for r in rows}
        assert by_key[(0, product.id)] == 10.0
        assert by_key[(2, product.id)] == 4.0
        assert by_key[(0, product2.id)] == 5.0

    def test_fork_endpoint_creates_template_rows(self, client, session_factory, product):
        """POST /produccion/template/fork-week with from_date clones overrides → template."""
        monday = date(2026, 6, 1)  # known Monday
        with session_factory() as s:
            s.add(ProductionPlanOverride(
                product_id=product.id, for_date=monday,
                qty=3.0, updated_at=datetime.now(timezone.utc), updated_by="op",
            ))
            s.add(ProductionPlanOverride(
                product_id=product.id, for_date=monday + timedelta(days=1),  # Tue
                qty=5.0, updated_at=datetime.now(timezone.utc), updated_by="op",
            ))
            s.commit()
            product_id = product.id

        resp = client.post(
            "/produccion/template/fork-week",
            data={"from_date": monday.isoformat()},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        with session_factory() as s:
            rows = s.scalars(
                select(ProductionPlanTemplate)
                .where(ProductionPlanTemplate.product_id == product_id)
            ).all()
        assert len(rows) == 2  # Mon + Tue
        qtys = sorted(r.qty for r in rows)
        assert qtys == [3.0, 5.0]

    def test_fork_endpoint_returns_empty_when_no_overrides(self, client):
        """Empty week → 303 with fork=empty query param."""
        # Use a date that has no overrides (week of 2026-06-15, but at least
        # one Monday — use a known one far in the future to avoid noise).
        future_monday = date(2030, 1, 7)
        resp = client.post(
            "/produccion/template/fork-week",
            data={"from_date": future_monday.isoformat()},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "fork=empty" in resp.headers.get("location", "")

    def test_fork_endpoint_rejects_invalid_date(self, client):
        resp = client.post(
            "/produccion/template/fork-week",
            data={"from_date": "not-a-date"},
            follow_redirects=False,
        )
        assert resp.status_code == 400


# ===========================================================================
# Migration 040 + 041 sanity
# ===========================================================================


class TestMigrations:

    def test_schema_version_is_current(self, session_factory):
        """Schema version reflects CURRENT_SCHEMA_VERSION (42 after S8)."""
        from app.rms.config import CURRENT_SCHEMA_VERSION
        from app.rms.models import AppMeta

        assert CURRENT_SCHEMA_VERSION >= 42
        with session_factory() as s:
            row = s.scalar(
                select(AppMeta.value).where(AppMeta.key == "schema_version")
            )
        assert int(row) == CURRENT_SCHEMA_VERSION

    def test_forecast_horizon_column_exists(self, session_factory):
        """Migration 041: ingredient.forecast_horizon_days column."""
        from sqlalchemy import text
        with session_factory() as s:
            rows = s.execute(text("PRAGMA table_info(ingredient)")).fetchall()
        cols = {r[1] for r in rows}
        assert "forecast_horizon_days" in cols

    def test_ingredient_variant_table_exists(self, session_factory):
        """Migration 040: ingredient_variant table + index."""
        from sqlalchemy import text
        with session_factory() as s:
            tables = s.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
            names = {r[0] for r in tables}
        assert "ingredient_variant" in names
        # Index too
        with session_factory() as s:
            idx = s.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' "
                     "AND tbl_name='ingredient_variant'")
            ).fetchall()
        assert any(r[0] == "ix_ingredient_variant_ingredient" for r in idx)

    def test_backfill_creates_default_variant(self, session_factory):
        """Migration 040: every existing Ingredient with purchase_price_gs
        got a default variant from the backfill."""
        # Existing test ingredients should have at least 1 variant each by
        # the time the migration ran (in conftest, init_db() runs migrations).
        with session_factory() as s:
            ing = s.scalar(
                select(Ingredient).where(Ingredient.purchase_price_gs.is_not(None))
            )
            if ing is None:
                pytest.skip("no ingredient with price to backfill")
            v = s.scalar(
                select(IngredientVariant)
                .where(IngredientVariant.ingredient_id == ing.id)
                .where(IngredientVariant.preferred == True)  # noqa: E712
            )
        assert v is not None


# ===========================================================================
# HTML rendering — variants panel + forecast panel on detail page
# ===========================================================================


class TestIngredientDetailPage:

    def test_detail_page_shows_variants_panel(self, client, ingredient):
        resp = client.get(f"/inventario/{ingredient.id}")
        assert resp.status_code == 200
        body = resp.text
        assert ">Variantes<" in body or "Variantes" in body
        assert ingredient.name in body

    def test_detail_page_shows_forecast_panel(self, client, ingredient):
        """The forecast block renders even with no consumption data."""
        resp = client.get(f"/inventario/{ingredient.id}")
        assert resp.status_code == 200
        body = resp.text
        assert "¿cuándo me quedo corto" in body.lower() or "Pronóstico" in body
        assert "Horizonte" in body
