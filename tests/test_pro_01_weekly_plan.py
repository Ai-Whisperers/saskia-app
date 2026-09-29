"""Tests for PRO-01: Weekly repeating production plan template + per-date overrides."""
from __future__ import annotations

from datetime import date


def test_weekly_template_repeats_across_weeks(app_engine):
    """PRO-01: A Monday template row applies to every Monday."""
# allow-hardcoded-dates: weekly-plan assertions on a fixed Mon-Sun week
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product
    from app.rms.production import plan_production, upsert_template_row

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod); s.commit()
        pid = prod.id

    # Set Monday (weekday=0) qty to 12
    with sf() as s:
        upsert_template_row(s, weekday=0, product_id=pid, qty=12)
        s.commit()

    # Verify 2026-09-07 (a Monday) reflects the template
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 7))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0].qty_to_produce == 12, f"Expected 12, got {rows[0].qty_to_produce}"
        assert rows[0].forecast_source == "template"

    # Verify 2026-09-14 (next Monday) also reflects the template
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 14))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert len(rows) == 1
        assert rows[0].qty_to_produce == 12

    # Verify 2026-09-08 (Tuesday) does NOT have the Muffin (no template)
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 8))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert len(rows) == 0, "Tuesday should not pick up Monday's template"


def test_override_only_affects_one_date(app_engine):
    """PRO-01: A per-date override does NOT change the template or other dates."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product
    from app.rms.production import plan_production, upsert_override, upsert_template_row

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod); s.commit()
        pid = prod.id

    # Set Monday (every Monday) qty to 12
    with sf() as s:
        upsert_template_row(s, weekday=0, product_id=pid, qty=12)
        s.commit()

    # Override 2026-09-14 (a Monday) to 50
    with sf() as s:
        upsert_override(s, product_id=pid, for_date=date(2026, 9, 14), qty=50)
        s.commit()

    # 2026-09-14 → 50 (override wins)
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 14))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert rows[0].qty_to_produce == 50
        assert rows[0].forecast_source == "override"

    # 2026-09-21 (next Monday) → still 12 (template, not affected)
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 21))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert rows[0].qty_to_produce == 12
        assert rows[0].forecast_source == "template"

    # 2026-09-07 (previous Monday) → still 12 (template, not affected)
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 7))
        rows = [r for r in plan.rows if r.product_name == "Muffin"]
        assert rows[0].qty_to_produce == 12


def test_template_plus_auto_forecast_coexist(app_engine):
    """PRO-01: When the template has product A but not B, A comes from the
    template and B from auto-forecast."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product, Sale
    from app.rms.production import plan_production, upsert_template_row

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod_a = Product(name="Muffin (template)", sale_price_gs=2500)
        prod_b = Product(name="Cookie (forecast)", sale_price_gs=1500)
        s.add(prod_a); s.add(prod_b); s.commit()
        pa_id, pb_id = prod_a.id, prod_b.id

    # Sales for Cookie so it gets auto-forecasted
    with sf() as s:
        for i in range(14):
            s.add(Sale(
                sold_at=datetime.now(timezone.utc) - timedelta(days=i),
                product_id=pb_id,
                qty=10,
                unit_price_gs=1500,
            ))
        s.commit()

    # Template: Monday has only Muffin at qty 12
    with sf() as s:
        upsert_template_row(s, weekday=0, product_id=pa_id, qty=12)
        s.commit()

    # Plan for a Monday (2026-09-14)
    with sf() as s:
        plan = plan_production(s, for_date=date(2026, 9, 14))
        by_name = {r.product_name: r for r in plan.rows}
        # Muffin comes from template
        assert "Muffin (template)" in by_name
        assert by_name["Muffin (template)"].qty_to_produce == 12
        assert by_name["Muffin (template)"].forecast_source == "template"
        # Cookie comes from auto-forecast (no template, has sales)
        assert "Cookie (forecast)" in by_name
        assert by_name["Cookie (forecast)"].forecast_source == "rolling_14d_avg"


def test_override_endpoint_persists_to_db(client, app_engine):
    """PRO-01: POST /produccion/override saves to production_plan_override."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product, ProductionPlanOverride

    # First create a product via the public API
    client.post("/productos/nuevo", data={
        "name": "Muffin override test",
        "sale_price_gs": "2500",
    }, follow_redirects=False)

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = s.query(Product).filter_by(name="Muffin override test").first()
        pid = prod.id

    # POST the override
    r = client.post("/produccion/override", data={
        "for_date": "2026-09-21",
        "product_id": str(pid),
        "qty": "10",
    }, follow_redirects=False)
    assert r.status_code == 303, f"Override POST failed: {r.status_code} {r.text}"

    # Verify DB has the row
    with sf() as s:
        ov = s.query(ProductionPlanOverride).filter(
            ProductionPlanOverride.product_id == pid,
            ProductionPlanOverride.for_date == date(2026, 9, 21),
        ).one_or_none()
        assert ov is not None, "Override should be persisted to DB"
        assert ov.qty == 10


def test_override_endpoint_qty_zero_deletes_row(client, app_engine):
    """PRO-01: POST /produccion/override with qty=0 deletes the override."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product, ProductionPlanOverride

    client.post("/productos/nuevo", data={
        "name": "Muffin zero test",
        "sale_price_gs": "2500",
    }, follow_redirects=False)

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = s.query(Product).filter_by(name="Muffin zero test").first()
        pid = prod.id

    # Create an override
    client.post("/produccion/override", data={
        "for_date": "2026-09-21",
        "product_id": str(pid),
        "qty": "10",
    }, follow_redirects=False)

    # Set it to 0 (deletes)
    r = client.post("/produccion/override", data={
        "for_date": "2026-09-21",
        "product_id": str(pid),
        "qty": "0",
    }, follow_redirects=False)
    assert r.status_code == 303

    with sf() as s:
        ov = s.query(ProductionPlanOverride).filter(
            ProductionPlanOverride.product_id == pid,
        ).one_or_none()
        assert ov is None, "qty=0 should remove the override"


def test_template_endpoint_persists_to_db(client, app_engine):
    """PRO-01: POST /produccion/template saves to production_plan_template."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product, ProductionPlanTemplate

    client.post("/productos/nuevo", data={
        "name": "Muffin template test",
        "sale_price_gs": "2500",
    }, follow_redirects=False)

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = s.query(Product).filter_by(name="Muffin template test").first()
        pid = prod.id

    # POST the template row
    r = client.post("/produccion/template", data={
        "weekday": "0",  # Monday
        "product_id": str(pid),
        "qty": "24",
        "notes": "Lunes de muffins",
    }, follow_redirects=False)
    assert r.status_code == 303

    with sf() as s:
        tpl = s.query(ProductionPlanTemplate).filter(
            ProductionPlanTemplate.weekday == 0,
            ProductionPlanTemplate.product_id == pid,
        ).one_or_none()
        assert tpl is not None
        assert tpl.qty == 24
        assert tpl.notes == "Lunes de muffins"


def test_template_endpoint_invalid_weekday_returns_400(client):
    """PRO-01: weekday outside 0..6 returns 400."""
    r = client.post("/produccion/template", data={
        "weekday": "9",  # invalid
        "product_id": "1",
        "qty": "5",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "weekday" in r.text.lower()


def test_get_weekly_template_returns_empty_for_unset_days(app_engine):
    """PRO-01: get_weekly_template returns empty dict for weekdays with no rows."""
    from sqlalchemy.orm import sessionmaker

    from app.rms.models import Product
    from app.rms.production import get_weekly_template, upsert_template_row

    sf = sessionmaker(bind=app_engine)
    with sf() as s:
        prod = Product(name="Muffin", sale_price_gs=2500)
        s.add(prod); s.commit()
        pid = prod.id

    # Only set Monday
    with sf() as s:
        upsert_template_row(s, weekday=0, product_id=pid, qty=10)
        s.commit()

    with sf() as s:
        template = get_weekly_template(s)
        assert template[0] == {pid: 10.0}
        assert template[1] == {}  # Tuesday
        assert template[6] == {}  # Sunday
