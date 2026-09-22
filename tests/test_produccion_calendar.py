"""tests/test_produccion_calendar.py — Phase D Q2-calendar (+Q3 folded in).

Covers:
- Quantity-multiplication regression (Saskia's reported bug): producing N
  portions of a recipe with yield_qty per batch must consume
  (N / yield_qty) × line.qty of each ingredient.
- /produccion view modes (day | week | month) wired to the Phase B
  calendar macros, with per-day product counts and nav params.
- Per-day manual qty override (POST /produccion/override).
- forecast_source Spanish labels (Q3).

Refs: Saskia review round 1 (Thu 18-sep) — Q2 (c) calendar dashboard.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.rms.models import Ingredient, Product, Recipe, RecipeLine, Sale
from app.rms.production import plan_production


# --- Shared helpers ---


def _seed_product_with_recipe_and_sales(session_factory) -> int:
    """One muffin product (recipe yield 12, 0.3 kg flour/batch) + sales
    history so the rolling forecast is > 0. Returns product id."""
    s = session_factory()
    try:
        ing = Ingredient(
            name="Harina", unit="kg", stock_qty=0.0, purchase_price_gs=4500
        )
        rec = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.3,
            )
        )
        prod = Product(name="Muffin", sale_price_gs=2500, recipe_id=rec.id)
        s.add(prod)
        s.flush()
        now = datetime.now(timezone.utc)
        for i in range(5):
            s.add(
                Sale(
                    sold_at=now - timedelta(days=i),
                    product_id=prod.id,
                    qty=2,
                    unit_price_gs=2500,
                )
            )
        s.commit()
        return prod.id
    finally:
        s.close()


# --- Deliverable 3: quantity-multiplication regression (Saskia's bug) ---


def test_production_math_multiplication(session_factory):
    """Recipe lines are per BATCH: yield_qty=12 muffins, 0.3 kg flour per
    batch. Producing qty_to_produce PORTIONS must consume
    (qty_to_produce / yield_qty) × line.qty of each ingredient.

    Saskia's bug report (review round 1, Q2): the sheet was multiplying
    portions × per-batch line qty directly (12× too much flour here).
    """
    s = session_factory()
    try:
        ing = Ingredient(
            name="Harina", unit="kg", stock_qty=0.0, purchase_price_gs=4500
        )
        rec = Recipe(name="Muffin", yield_qty=12.0, yield_unit="und")
        s.add_all([ing, rec])
        s.flush()
        s.add(
            RecipeLine(
                recipe_id=rec.id,
                line_kind="ingredient",
                line_ref_id=ing.id,
                qty=0.3,
            )
        )
        prod = Product(name="Muffin", sale_price_gs=2500, recipe_id=rec.id)
        s.add(prod)
        s.commit()

        # 2x: 24 portions = 2 batches -> 2 * 0.3 = 0.6 kg flour
        plan_2x = plan_production(
            s,
            for_date=date(2026, 6, 1),
            manual_forecast={prod.id: 24.0},
        )
        assert len(plan_2x.lines) == 1
        assert abs(plan_2x.lines[0].qty_required - 0.6) < 1e-6

        # 0.5x: 6 portions = 0.5 batch -> 0.15 kg flour
        plan_half = plan_production(
            s,
            for_date=date(2026, 6, 1),
            manual_forecast={prod.id: 6.0},
        )
        assert len(plan_half.lines) == 1
        assert abs(plan_half.lines[0].qty_required - 0.15) < 1e-6

        # The two must scale linearly with the forecast.
        assert abs(
            plan_2x.lines[0].qty_required - 4 * plan_half.lines[0].qty_required
        ) < 1e-6
    finally:
        s.close()


# --- Deliverable 1: view modes ---


def test_day_view_backward_compat(client, session_factory):
    pid = _seed_product_with_recipe_and_sales(session_factory)
    r = client.get("/produccion")
    assert r.status_code == 200
    assert "Muffin" in r.text


def test_week_view_renders_seven_cells(client, session_factory):
    _seed_product_with_recipe_and_sales(session_factory)
    monday = date.today()
    while monday.weekday() != 0:
        monday -= timedelta(days=1)
    r = client.get(f"/produccion?view=week&week={monday.isoformat()}")
    assert r.status_code == 200
    assert r.text.count('<th class="num">') >= 7
    assert "Lun" in r.text and "Dom" in r.text
    assert "Semana anterior" in r.text and "Semana siguiente" in r.text


def test_month_view_renders_day_count(client, session_factory):
    _seed_product_with_recipe_and_sales(session_factory)
    import calendar as _cal
    today = date.today()
    r = client.get(f"/produccion?view=month&month={today.strftime('%Y-%m')}")
    assert r.status_code == 200
    # Month view renders a plain table with day-number headers (<th class="num">N</th>)
    ndays = _cal.monthrange(today.year, today.month)[1]
    assert r.text.count('<th class="num">') >= ndays + 1  # +1 for the "Producto" column
    assert "Mes anterior" in r.text and "Mes siguiente" in r.text


def test_view_switcher_present(client, session_factory):
    _seed_product_with_recipe_and_sales(session_factory)
    for view in ("day", "week", "month"):
        r = client.get(f"/produccion?view={view}")
        assert r.status_code == 200
        assert "Día" in r.text and "Semana" in r.text and "Mes" in r.text


# --- Deliverable 4 (Q3): forecast_source labels ---


def test_forecast_source_labels_in_spanish(client, session_factory):
    _seed_product_with_recipe_and_sales(session_factory)
    r = client.get("/produccion")
    assert "Promedio 14 días" in r.text
    assert "rolling_14d_avg" not in r.text
    assert "Cómo se calcula" in r.text


# --- Deliverable 2: manual override ---


def test_override_re_renders_with_manual_qty(client, session_factory):
    pid = _seed_product_with_recipe_and_sales(session_factory)
    r = client.post(
        "/produccion/override",
        data={"for_date": date.today().isoformat(), "product_id": str(pid), "qty": "10"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    r2 = client.get(r.headers["location"])
    assert "10.0" in r2.text or ">10<" in r2.text
    assert "Manual" in r2.text


def test_override_rejects_negative(client, session_factory):
    pid = _seed_product_with_recipe_and_sales(session_factory)
    r = client.post(
        "/produccion/override",
        data={"for_date": date.today().isoformat(), "product_id": str(pid), "qty": "-1"},
    )
    assert r.status_code == 400


def test_override_rejects_unknown_product(client, session_factory):
    r = client.post(
        "/produccion/override",
        data={"for_date": date.today().isoformat(), "product_id": "999999", "qty": "1"},
    )
    assert r.status_code == 404
