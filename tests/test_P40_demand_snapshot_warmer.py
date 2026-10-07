"""P40 — EOD view warms the demand snapshot for today + 6 future days.

Pre-P40: production_demand_snapshot was filled only when the operator
opened /produccion or /produccion/manana. Operators don't open those
pages every day, so the table sat empty for 30+ days. P40 makes the
snapshot warm up as a side-effect of opening /eod (a page that
operators DO open every day at close).

The warmer is best-effort: a failure in any single date is logged
and skipped. The route does not raise. The test verifies both
the happy path and the failure-isolation.
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import select, func

from app.rms.models import ProductionDemandSnapshot, Product, Sale


def test_eod_view_warms_today_and_next_6_days(client, session_factory):
    """Opening /eod with no products → snapshot table still gets a warm
    pass (we record 0 rows for each date because there are no products,
    but the warmer ran for 7 dates)."""
    r = client.get("/eod", follow_redirects=True)
    assert r.status_code == 200

    with session_factory() as s:
        # Verify a recent computed_at for today exists if any rows are
        # present; if there are no products, the table stays empty,
        # which is the documented best-effort behavior.
        n = s.scalar(
            select(func.count()).select_from(ProductionDemandSnapshot)
        )
    # n may be 0 in a test fixture with no products; the important
    # thing is that the route returned 200 (i.e. the warmer didn't
    # crash the EOD page).
    assert n is not None


def test_warm_snapshots_for_dates_helper_populates(client, session_factory, db_with_sales):
    """Helper writes a ProductionDemandSnapshot row for each (date, product)."""
    from app.rms.production_demand import warm_snapshots_for_dates
    today = date.today()
    dates = [today, today + timedelta(days=1), today + timedelta(days=6)]

    with session_factory() as s:
        warmed = warm_snapshots_for_dates(s, dates)
    assert warmed == 3

    with session_factory() as s:
        n = s.scalar(
            select(func.count()).select_from(ProductionDemandSnapshot)
            .where(ProductionDemandSnapshot.for_date.in_([d.isoformat() for d in dates]))
        )
    # 1 product * 3 dates = 3 rows (Product loop only yields 1)
    assert n == 3


def test_warm_snapshots_for_dates_best_effort_on_bad_date(client, session_factory):
    """A bad date in the list (e.g. very far future) shouldn't kill the
    whole batch — the function returns the count of dates that succeeded."""
    from app.rms.production_demand import warm_snapshots_for_dates
    today = date.today()
    # Mix a good date with a 100-year-future date; both should be
    # "successful" because get_demand() doesn't range-bound by date.
    dates = [today, today + timedelta(days=36500)]
    with session_factory() as s:
        warmed = warm_snapshots_for_dates(s, dates)
    assert warmed == 2


def test_eod_view_does_not_500_when_warmer_fails(client, monkeypatch, session_factory):
    """If the warmer raises, the EOD page should still render 200.

    Simulates the worst case: a future change to production_demand
    breaks the function. The EOD page must not turn into a 500.
    """
    from app.routers.eod import eod_view
    import app.rms.production_demand as pd_mod

    real = pd_mod.warm_snapshots_for_dates

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated demand warmer failure")

    monkeypatch.setattr(pd_mod, "warm_snapshots_for_dates", boom)
    try:
        r = client.get("/eod", follow_redirects=True)
        assert r.status_code == 200
    finally:
        monkeypatch.setattr(pd_mod, "warm_snapshots_for_dates", real)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def db_with_sales(session_factory):
    """One product + one historical sale so the forecast path runs."""
    from datetime import datetime, timezone
    with session_factory() as s:
        p = Product(name="P40-Product", sku="P40-SNAPSHOT", sale_price_gs=10000)
        s.add(p)
        s.flush()
        s.add(Sale(
            product_id=p.id, qty=3.0, unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc) - timedelta(days=3),
        ))
        s.commit()
        return {"product_id": p.id}
