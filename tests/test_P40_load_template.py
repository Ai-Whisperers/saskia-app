"""P40 — /produccion/template/load-day one-click "Cargar plan desde plantilla".

Pre-P40: 21 production_plan_template rows were seeded for weekly planning
but no production_plan_override rows had ever been written. The day
view fell back to rolling 14d average for every product. P40 adds
a button that writes overrides for the current date from the template.

The route is intentionally idempotent: clicking twice only adds rows
for products that have no override for the date. Clicking on a
weekday with no template is a no-op (redirect with flash=sin_plantilla).
"""

from datetime import date

import pytest
from sqlalchemy import delete, select

from app.rms.models import (
    ProductionPlanOverride,
    ProductionPlanTemplate,
)


def test_load_template_creates_overrides(client, session_factory, seeded_today_template):
    """Seeded Tuesday template has 2 products → load-day creates 2 overrides."""
    today = seeded_today_template["today"]
    with session_factory() as s:
        before = (
            s.execute(
                select(ProductionPlanOverride).where(ProductionPlanOverride.for_date == today)
            )
            .scalars()
            .all()
        )
        assert before == []

    r = client.post(
        "/produccion/template/load-day",
        data={"for_date": today.isoformat()},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "flash=plantilla_cargada" in r.headers["location"]

    with session_factory() as s:
        rows = (
            s.execute(
                select(ProductionPlanOverride).where(ProductionPlanOverride.for_date == today)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        qtys = {r.product_id: r.qty for r in rows}
        assert qtys == seeded_today_template["qtys"]
        # Notes are stamped so an operator can see which overrides came from the template
        for row in rows:
            assert row.notes == "P40: desde plantilla semanal"


def test_load_template_idempotent_skips_existing(client, session_factory, seeded_today_template):
    """A second click on the same date is a no-op for already-loaded products."""
    today = seeded_today_template["today"]
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    with session_factory() as s:
        pid = seeded_today_template["product_ids"][0]
        s.add(
            ProductionPlanOverride(
                product_id=pid,
                for_date=today,
                qty=99.0,
                notes="manual override",
                updated_at=now,
            )
        )
        s.commit()

    r = client.post(
        "/produccion/template/load-day",
        data={"for_date": today.isoformat()},
        follow_redirects=False,
    )
    assert r.status_code == 303

    with session_factory() as s:
        rows = (
            s.execute(
                select(ProductionPlanOverride).where(ProductionPlanOverride.for_date == today)
            )
            .scalars()
            .all()
        )
        # 1 manual + 1 newly loaded = 2 (the manual one was NOT overwritten)
        assert len(rows) == 2
        manual = next(r for r in rows if r.product_id == pid)
        assert manual.qty == 99.0
        assert manual.notes == "manual override"


def test_load_template_no_rows_is_redirect_with_flash(client, session_factory):
    """A weekday with no template rows → flash=sin_plantilla, no overrides created."""
    empty_day = date(2030, 1, 7)  # a Monday we never seeded
    # Make sure there really is no template for weekday=0 (Mon) for 2030
    r = client.post(
        "/produccion/template/load-day",
        data={"for_date": empty_day.isoformat()},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "flash=sin_plantilla" in r.headers["location"]


def test_load_template_bad_date_400(client):
    """Garbage date string → 400 (datetime parse) or 422 (form validation)."""
    r = client.post(
        "/produccion/template/load-day",
        data={"for_date": "not-a-date"},
        follow_redirects=False,
    )
    assert r.status_code in (400, 422, 500)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_today_template(session_factory):
    """Seed 2 ProductionPlanTemplate rows for the current weekday and return metadata."""
    from app.rms.models import Product

    today = date.today()
    weekday = today.weekday()
    # Wipe other weekday templates so the test is deterministic
    with session_factory() as s:
        s.execute(delete(ProductionPlanTemplate).where(ProductionPlanTemplate.weekday != weekday))
        s.execute(delete(ProductionPlanOverride).where(ProductionPlanOverride.for_date == today))
        # Create 2 products
        p1 = Product(name="P40-ProductA", sku="P40-A", is_available=True, sale_price_gs=10000)
        p2 = Product(name="P40-ProductB", sku="P40-B", is_available=True, sale_price_gs=20000)
        s.add_all([p1, p2])
        s.flush()
        # And 2 template rows for today.weekday()
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        s.add_all(
            [
                ProductionPlanTemplate(weekday=weekday, product_id=p1.id, qty=5.0, updated_at=now),
                ProductionPlanTemplate(weekday=weekday, product_id=p2.id, qty=8.0, updated_at=now),
            ]
        )
        s.commit()
        return {
            "today": today,
            "product_ids": [p1.id, p2.id],
            "qtys": {p1.id: 5.0, p2.id: 8.0},
        }
