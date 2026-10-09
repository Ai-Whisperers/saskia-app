"""tests/test_eod_completion.py — T5 completion persistence (Phase C).

the operator review: "Al final del día debe registrarse cuánto de la
producción se completó". The forecast half shipped earlier; these tests
cover the persistence half: ProductionCompletion model, POST
/eod/completar upsert, and the Plan vs Hecho rendering on /eod.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.rms.models import Product, ProductionCompletion

_UTC = timezone.utc


@pytest.fixture
def product_id(session_factory):
    """Seed one product and return its id."""
    with session_factory() as s:
        prod = Product(name="Muffin test", sale_price_gs=2500)
        s.add(prod)
        s.commit()
        return prod.id


# --- Model + upsert ---


def test_upsert_creates_then_updates(session_factory, product_id):
    """Re-recording the same product+date updates in place (1 row, latest qty)."""
    from app.rms.eod_completions import upsert_completion

    with session_factory() as s:
        from app.rms.models import Product

        s.execute(select(Product)).scalars().first()

    with session_factory() as s:
        upsert_completion(
            s, product_id=product_id, for_date=datetime.now(_UTC).date(), completed_qty=5.0
        )
        s.commit()
    with session_factory() as s:
        upsert_completion(
            s, product_id=product_id, for_date=datetime.now(_UTC).date(), completed_qty=7.5
        )
        s.commit()

    with session_factory() as s:
        rows = list(s.execute(select(ProductionCompletion)).scalars())
        assert len(rows) == 1
        assert rows[0].completed_qty == 7.5


def test_upsert_rejects_negative(session_factory, product_id):
    from app.rms.eod_completions import upsert_completion

    with session_factory() as s:
        from app.rms.models import Product

        s.execute(select(Product)).scalars().first()

    with session_factory() as s:
        with pytest.raises(ValueError):
            upsert_completion(
                s, product_id=product_id, for_date=datetime.now(_UTC).date(), completed_qty=-1.0
            )


# --- HTTP route ---


def test_post_completar_route_creates_row(client, session_factory, product_id):
    """POST /eod/completar → 303 + row in DB."""
    r = client.post(
        "/eod/completar",
        data={
            "product_id": str(product_id),
            "for_date": datetime.now(_UTC).date().isoformat(),
            "completed_qty": "3.5",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    with session_factory() as s:
        row = s.execute(
            select(ProductionCompletion).where(ProductionCompletion.product_id == product_id)
        ).scalar_one_or_none()
        assert row is not None
        assert row.completed_qty == 3.5


def test_post_completar_rejects_negative_qty(client, product_id):
    r = client.post(
        "/eod/completar",
        data={
            "product_id": str(product_id),
            "for_date": datetime.now(_UTC).date().isoformat(),
            "completed_qty": "-2",
        },
    )
    assert r.status_code == 400


def test_post_completar_rejects_unknown_product(client):
    r = client.post(
        "/eod/completar",
        data={
            "product_id": "999999",
            "for_date": datetime.now(_UTC).date().isoformat(),
            "completed_qty": "1",
        },
    )
    assert r.status_code == 404


def test_eod_view_shows_completion_in_hecho_column(client, session_factory, product_id):
    """GET /eod pre-fills the Hecho input with the recorded value."""
    # Seed sales so the forecast produces a plan row for this product.
    # /eod reads ASUNCION today, so seed the completion for that date —
    # UTC datetime.now(_UTC).date() diverges near midnight and the pre-fill vanishes.
    from app.rms.config import ASUNCION_TZ
    from app.rms.eod_completions import upsert_completion
    from app.rms.models import Sale

    today_asuncion = datetime.now(ASUNCION_TZ).date()
    with session_factory() as s:
        now = datetime.utcnow()
        for i in range(5):
            s.add(
                Sale(
                    product_id=product_id,
                    qty=2.0,
                    sold_at=now - timedelta(days=i),
                    unit_price_gs=2500,
                )
            )
        upsert_completion(s, product_id=product_id, for_date=today_asuncion, completed_qty=4.0)
        s.commit()

    r = client.get("/eod")
    assert r.status_code == 200
    # The pre-filled input for the completion we just wrote
    assert 'value="4.0"' in r.text or 'value="4"' in r.text


# --- Migration ---


def test_migration_v19_idempotent(app_engine):
    """Running migrations twice leaves schema_version at 19 and one table."""
    from sqlalchemy import inspect

    from app.rms.db import init_db, schema_version

    init_db(app_engine)
    init_db(app_engine)  # idempotent second run
    insp = inspect(app_engine)
    tables = insp.get_table_names()
    assert "production_completion" in tables
    with app_engine.connect() as conn:
        assert schema_version(conn) >= 19
