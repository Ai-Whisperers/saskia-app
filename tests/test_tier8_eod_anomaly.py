"""Tier 8.3 (2026-10-01) — EOD anomaly detection.

Tests for ``app.services.eod_anomaly.detect_anomalies``:
- Empty day → no anomalies
- Single voided sale → no anomaly (below 3-sale threshold)
- High voided rate → voided_rate anomaly
- Factura without number → uninvoiced_factura anomaly
- Negative grand total → critical anomaly
- Many sales all-card → cash_zero_with_active_sales info

We insert sales via raw SQL to avoid the Product / SaleStockMove
relationship plumbing (those classes have deprecated stub mappers
that block SQLAlchemy from resolving the relationship when the
class is queried in isolation).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import text

from app.rms.config import ASUNCION_TZ
from app.services.eod_anomaly import detect_anomalies


def _insert_sale(
    session,
    *,
    product_id: int,
    sold_at: datetime,
    unit_price_gs: int = 10_000,
    qty: float = 1.0,
    discount_gs: int = 0,
    voided_at: datetime | None = None,
    payment_method: str | None = "efectivo",
    invoice_type: str = "boleta_resimple",
    invoice_number: int | None = 1,
) -> int:
    """Bypass SQLAlchemy ORM with a raw INSERT. Returns sale.id.

    Avoids the SaleStockMove stub relationship issue that breaks
    mapper configuration in test scope.
    """
    result = session.execute(
        text(
            """
            INSERT INTO sale (
                product_id, qty, unit_price_gs, discount_gs,
                sold_at, voided_at, payment_method,
                invoice_type, invoice_number, tz, channel
            ) VALUES (
                :product_id, :qty, :unit_price_gs, :discount_gs,
                :sold_at, :voided_at, :payment_method,
                :invoice_type, :invoice_number, 'America/Asuncion', 'mostrador'
            )
            """
        ),
        {
            "product_id": product_id,
            "qty": qty,
            "unit_price_gs": unit_price_gs,
            "discount_gs": discount_gs,
            "sold_at": sold_at,
            "voided_at": voided_at,
            "payment_method": payment_method,
            "invoice_type": invoice_type,
            "invoice_number": invoice_number,
        },
    )
    return result.lastrowid


@pytest.fixture
def product_id(session_factory) -> int:
    """Create a real Product row using qseed so the mapper is fully
    configured by the time we INSERT sales.

    The Product ORM class is fragile in test scope (the SaleStockMove
    relationship stub breaks the mapper if Product is the first
    model touched). qseed runs the demo reset which configures all
    mappers as a side effect.
    """
    from tests._fixtures_quick_seed import quick_seed

    data = quick_seed(session_factory, "basic")
    return int(data["product"].id)


def test_detect_no_sales_returns_empty(session_factory) -> None:
    with session_factory() as s:
        assert detect_anomalies(s, day=date(2026, 9, 1)) == []


def test_detect_few_sales_below_voided_threshold(session_factory, product_id) -> None:
    """Two sales with one voided = 50% rate, but below 3-sale cutoff
    so we don't fire."""
    with session_factory() as session:
        base = datetime(2026, 9, 1, 12, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        _insert_sale(session, product_id=product_id, sold_at=base)
        _insert_sale(
            session,
            product_id=product_id,
            sold_at=base.replace(hour=13),
            voided_at=base.replace(hour=14),
        )
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 1))
    assert not any(a.key == "eod.voided_rate" for a in anomalies)


def test_detect_high_voided_rate(session_factory, product_id) -> None:
    """4 sales, 1 voided = 25% rate, fires the warn."""
    with session_factory() as session:
        base = datetime(2026, 9, 2, 10, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        for i in range(3):
            _insert_sale(session, product_id=product_id, sold_at=base.replace(hour=10 + i))
        _insert_sale(
            session,
            product_id=product_id,
            sold_at=base.replace(hour=14),
            voided_at=base,
        )
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 2))
    voided = [a for a in anomalies if a.key == "eod.voided_rate"]
    assert len(voided) == 1
    assert voided[0].severity == "warn"
    assert "25%" in voided[0].body


def test_detect_uninvoiced_factura(session_factory, product_id) -> None:
    with session_factory() as session:
        base = datetime(2026, 9, 3, 10, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        _insert_sale(
            session,
            product_id=product_id,
            sold_at=base,
            invoice_type="factura",
            invoice_number=None,  # the bug
        )
        _insert_sale(session, product_id=product_id, sold_at=base.replace(hour=11))
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 3))
    bad = [a for a in anomalies if a.key == "eod.uninvoiced_factura"]
    assert len(bad) == 1
    assert bad[0].severity == "error"


def test_detect_negative_grand_total(session_factory, product_id) -> None:
    """A negative total (shouldn't happen but the detector catches it)."""
    with session_factory() as session:
        base = datetime(2026, 9, 4, 10, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        _insert_sale(
            session,
            product_id=product_id,
            sold_at=base,
            unit_price_gs=10_000,
            discount_gs=20_000,
        )
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 4))
    neg = [a for a in anomalies if a.key == "eod.negative_grand_total"]
    assert len(neg) == 1
    assert neg[0].severity == "critical"


def test_detect_all_card_with_active_sales_fires_info(session_factory, product_id) -> None:
    """5+ active sales, all card (no cash) = info alert."""
    with session_factory() as session:
        base = datetime(2026, 9, 5, 10, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        for i in range(6):
            _insert_sale(
                session,
                product_id=product_id,
                sold_at=base.replace(hour=10 + i),
                payment_method="tarjeta",
            )
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 5))
    info = [a for a in anomalies if a.key == "eod.cash_zero_with_active_sales"]
    assert len(info) == 1
    assert info[0].severity == "info"


def test_detect_day_with_mixed_sales_no_anomaly(session_factory, product_id) -> None:
    """A boring normal day = empty list."""
    with session_factory() as session:
        base = datetime(2026, 9, 6, 10, 0, tzinfo=ASUNCION_TZ).replace(tzinfo=None)
        for i in range(10):
            _insert_sale(
                session,
                product_id=product_id,
                sold_at=base.replace(hour=10 + (i % 6)),
                payment_method="efectivo" if i % 2 == 0 else "tarjeta",
            )
        session.commit()
        anomalies = detect_anomalies(session, day=date(2026, 9, 6))
    assert anomalies == []
