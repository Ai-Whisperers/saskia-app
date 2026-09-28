"""tests/test_sale_channel.py — sale.channel column + form + validation.

Verifies migration 015 lands 'channel' on Sale, the form defaults to
'mostrador', and the POST handler accepts the 5 allowed values and
rejects unknowns.
"""
from __future__ import annotations

from datetime import datetime, timezone


def test_migration_015_runs_and_adds_channel_column(app_engine):
    """init_db() applies migration 015 and the column is usable."""
    from sqlalchemy import inspect

    insp = inspect(app_engine)
    cols = {c["name"] for c in insp.get_columns("sale")}
    assert "channel" in cols, f"migration 015 didn't add sale.channel; cols={cols}"


def test_schema_version_is_at_least_15(app_engine):
    """init_db() bumps schema_version to at least 15 (latest: 18, after
    v17 recipe_line.line_unit and v18 ingredient_price_event)."""
    from app.rms.db import schema_version

    with app_engine.connect() as conn:
        actual = schema_version(conn)
    assert actual >= 15, f"schema_version drifted below baseline: {actual}"


def test_default_channel_is_mostrador(session_factory):
    """A Sale constructed with no explicit channel defaults to 'mostrador'."""
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Default Channel Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        s.add(Sale(
            product_id=p.id,
            qty=1,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
        ))
        s.commit()

    with session_factory() as s:
        sale = s.query(Sale).order_by(Sale.id.desc()).first()
        assert sale.channel == "mostrador"


def test_apply_sale_accepts_custom_channel(session_factory):
    """apply_sale with channel=whatsapp persists it."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Whatsapp Sale Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        apply_sale(
            s,
            product_id=p.id,
            qty=1,
            sold_at=datetime.now(timezone.utc),
            channel="whatsapp",
        )
        s.commit()

    with session_factory() as s:
        sale = s.query(Sale).order_by(Sale.id.desc()).first()
        assert sale.channel == "whatsapp"


def test_all_five_channels_accepted_by_apply_sale(session_factory):
    """Each of the 5 allowed channels is round-trippable via apply_sale."""
    from app.rms.costing import apply_sale
    from app.rms.models import Product, Sale
    from app.rms.schemas import ALLOWED_CHANNELS

    expected = {"mostrador", "mostrador-encargo", "whatsapp", "pedidosya", "monchis"}
    assert set(ALLOWED_CHANNELS) == expected

    with session_factory() as s:
        p = Product(name="All Channels Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        for ch in expected:
            apply_sale(
                s,
                product_id=p.id,
                qty=1,
                sold_at=datetime.now(timezone.utc),
                channel=ch,
            )
        s.commit()

    with session_factory() as s:
        channels = sorted(sale.channel for sale in s.query(Sale).all())
    assert channels == sorted(expected)


def test_post_sale_rejects_unknown_channel_at_route(client, session_factory):
    """POST /ventas/nueva with channel='bitcoin' returns 400."""
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="Route Reject Channel", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        pid = p.id

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(pid), "qty": "1", "channel": "bitcoin"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Canal" in resp.text or "canal" in resp.text.lower()


def test_post_sale_accepts_all_five_channels(client, session_factory):
    """POST /ventas/nueva with each of the 5 channels persists it."""
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="All Channels Route Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        pid = p.id

    expected = ["mostrador", "mostrador-encargo", "whatsapp", "pedidosya", "monchis"]
    for ch in expected:
        resp = client.post(
            "/ventas/nueva",
            data={"product_id": str(pid), "qty": "1", "channel": ch},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 303), f"{ch!r} got {resp.status_code}"

    with session_factory() as s:
        channels = sorted(sale.channel for sale in s.query(Sale).all())
    assert channels == sorted(expected)


def test_post_sale_defaults_channel_to_mostrador(client, session_factory):
    """POST without channel field defaults to 'mostrador'."""
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="Default Channel Route Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        pid = p.id

    resp = client.post(
        "/ventas/nueva",
        data={"product_id": str(pid), "qty": "1"},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 303)

    with session_factory() as s:
        sale = s.query(Sale).order_by(Sale.id.desc()).first()
        assert sale.channel == "mostrador"


def test_ventas_page_renders_channel_select(client):
    """The /ventas form must include a combo for channel with the 5 options."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert "channel" in body  # Look for the combo
    for ch in ("mostrador", "mostrador-encargo", "whatsapp", "pedidosya", "monchis"):
        # The saskia-combo serialises each option as {value, label}
        assert f'"value": "{ch}"' in body or f"'{ch}'" in body, f"missing channel option for {ch}"


def test_ventas_page_default_channel_is_mostrador(client):
    """The default selected channel is 'mostrador'."""
    resp = client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    # Look for the channel combo and check default empty value
    assert "channel" in body
    assert 'value=""' in body  # Hidden input for channel should be empty by default


def test_csv_export_includes_channel_column(client, session_factory):
    """/ventas/export.csv writes the channel column for each sale."""
    from app.rms.models import Product, Sale

    with session_factory() as s:
        p = Product(name="CSV Channel Test", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.flush()
        s.add(Sale(
            product_id=p.id,
            qty=1,
            unit_price_gs=10000,
            sold_at=datetime.now(timezone.utc),
            channel="whatsapp",
        ))
        s.commit()

    resp = client.get("/ventas/export.csv")
    assert resp.status_code == 200
    body = resp.text
    assert "canal" in body
    assert "whatsapp" in body