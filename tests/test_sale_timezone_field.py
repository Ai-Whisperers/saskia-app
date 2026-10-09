"""tests/test_sale_timezone_field.py — Sale.tz column for per-sale timezone tracking."""

from __future__ import annotations


def test_sale_model_has_tz_column():
    """The Sale model has a tz column (string, defaulting to America/Asuncion)."""
    from app.rms.models import Sale

    assert hasattr(Sale, "tz"), "Sale model missing `tz` field"
    # Default value
    col = Sale.__table__.columns.get("tz")
    assert col is not None
    # Default to Paraguay time since single-tenant Asunción bakery.
    # (Will be enforced in DB by migration 012 default.)


def test_sale_create_with_explicit_tz_persists(session_factory):
    """A sale created with tz='America/New_York' persists the value."""
    from datetime import datetime, timezone

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="TzProd", sale_price_gs=10000)
        s.add(p)
        s.flush()
        sale = Sale(
            product_id=p.id,
            qty=1.0,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
            tz="America/New_York",
        )
        s.add(sale)
        s.commit()
        sale_id = sale.id

    with session_factory() as s:
        from sqlalchemy import select

        loaded = s.execute(select(Sale).where(Sale.id == sale_id)).scalar_one()
        assert loaded.tz == "America/New_York"


def test_sale_default_tz_is_paraguay(session_factory):
    """When tz is not provided, default to America/Asuncion."""
    from datetime import datetime, timezone

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="TzDefault", sale_price_gs=10000)
        s.add(p)
        s.flush()
        sale = Sale(
            product_id=p.id,
            qty=1.0,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
            # tz not provided
        )
        s.add(sale)
        s.commit()
        sale_id = sale.id

    with session_factory() as s:
        from sqlalchemy import select

        loaded = s.execute(select(Sale).where(Sale.id == sale_id)).scalar_one()
        assert loaded.tz == "America/Asuncion"


def test_groupby_tz_works(session_factory):
    """Aggregation: sum of sales grouped by tz works."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="TzGroup", sale_price_gs=10000)
        s.add(p)
        s.flush()
        now = datetime.now(timezone.utc)
        for tz, qty in [
            ("America/Asuncion", 3.0),
            ("America/New_York", 2.0),
            ("America/Asuncion", 1.0),
        ]:
            s.add(
                Sale(
                    product_id=p.id,
                    qty=qty,
                    unit_price_gs=10000,
                    sold_at=now,
                    tz=tz,
                )
            )
        s.commit()

    with session_factory() as s:
        result = s.execute(
            select(Sale.tz, func.sum(Sale.qty).label("total_qty"))
            .group_by(Sale.tz)
            .order_by(Sale.tz)
        ).all()
        by_tz = {row.tz: row.total_qty for row in result}
        assert by_tz.get("America/Asuncion") == 4.0
        assert by_tz.get("America/New_York") == 2.0
