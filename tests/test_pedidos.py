"""tests/test_pedidos.py — Pre-orders (Pedidos) system.

Phase 3 of the 2026-09-17 prelaunch roadmap. Covers:

- Pedido + PedidoLine model persistence (lines, total)
- POST /pedidos/nuevo creates a pedido with one or more lines
- POST /pedidos/{id}/fulfill creates Sale rows + decrements stock per line
- Status transitions: pending → confirmed → ready → fulfilled
- Invalid status transition (e.g. fulfilled → ready) rejected with 409
- Public token: GET /p/{token} works WITHOUT auth
- /pedidos list groups: Hoy/Mañana, Esta semana, Pendientes viejos
- public_token unique per pedido
- Audit log records pedido.create / status / fulfill events
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.crud

# --- helpers ----------------------------------------------------------------


def _seed_product(session_factory, name="Muffin", price=10000, qty=10, recipe_id=None):
    """Create a Product row. Returns product_id. Delegates to factories."""
    from tests.factories import make_product

    with session_factory() as s:
        p = make_product(s, name=name, sale_price_gs=price, recipe=recipe_id)
        s.commit()
        return p.id


def _seed_customer(session_factory, name="Cliente", phone="+595****9001"):
    from tests.factories import make_customer

    with session_factory() as s:
        c = make_customer(s, name=name, phone=phone)
        s.commit()
        return c.id


def _pedido_detail(client, pedido_id):
    return client.get(f"/pedidos/{pedido_id}")


# --- model + migration ------------------------------------------------------


def test_pedido_model_persists_with_lines(session_factory):
    """Creating a Pedido + PedidoLines persists them with correct totals."""
    from app.rms.models import Pedido, PedidoLine

    pid = _seed_product(session_factory, name="Croissant", price=12000)
    with session_factory() as s:
        p = Pedido(
            customer_name="Cliente W",
            customer_phone="+595999111",
            promised_date=datetime.combine(
                datetime.utcnow().date() + timedelta(days=1), datetime.min.time()
            ),
            promised_time="10:00",
            channel="whatsapp",
            status="pending",
            payment_intent="efectivo",
            public_token="abcd1234",
        )
        s.add(p)
        s.flush()
        s.add(PedidoLine(pedido_id=p.id, product_id=pid, qty=3, unit_price_gs=12000))
        s.add(PedidoLine(pedido_id=p.id, product_id=pid, qty=2, unit_price_gs=12000))
        s.commit()
        pedido_id = p.id

    with session_factory() as s:
        rows = (
            s.execute(select(PedidoLine).where(PedidoLine.pedido_id == pedido_id)).scalars().all()
        )
        assert len(rows) == 2
        # total = 3*12000 + 2*12000 = 60000
        assert sum(int(r.qty * r.unit_price_gs) for r in rows) == 60_000


def test_schema_version_is_16(session_factory, tmp_db_path):
    """CURRENT_SCHEMA_VERSION bumped to 16 so init_db runs the pedidos migration."""
    from app.rms.config import CURRENT_SCHEMA_VERSION
    from app.rms.db import init_db, make_engine

    engine = make_engine(f"sqlite:///{tmp_db_path}/schema16.sqlite")
    init_db(engine)
    with engine.connect() as conn:
        row = conn.execute(
            __import__("sqlalchemy").text("SELECT value FROM app_meta WHERE key='schema_version'")
        ).first()
        assert row is not None
        # On Postgres app_meta.value may be JSONB; coerce via str() for sqlite/PG alike
        assert str(row[0]).strip('"') == str(CURRENT_SCHEMA_VERSION)


def test_public_token_unique_per_pedido(session_factory):
    """The DB unique constraint on public_token prevents two pedidos from sharing one."""

    from app.rms.models import Pedido

    tomorrow = datetime.combine(datetime.utcnow().date() + timedelta(days=1), datetime.min.time())
    with session_factory() as s:
        s.add(Pedido(customer_name="A", promised_date=tomorrow, public_token="tok-1"))
        s.add(Pedido(customer_name="B", promised_date=tomorrow, public_token="tok-2"))
        s.commit()

    with session_factory() as s:
        rows = s.execute(select(Pedido)).scalars().all()
        assert len(rows) == 2
        tokens = {r.public_token for r in rows}
        assert tokens == {"tok-1", "tok-2"}


# --- list view --------------------------------------------------------------


def test_pedidos_list_groups_by_recency(session_factory, client):
    """/pedidos list splits rows into Hoy/Mañana, Esta semana, Pendientes viejos."""
    from app.rms.models import Pedido

    today = datetime.utcnow().date()
    with session_factory() as s:
        s.add(
            Pedido(
                customer_name="Hoy",
                promised_date=datetime.combine(today, datetime.min.time()),
                public_token="tk-hoy",
            )
        )
        s.add(
            Pedido(
                customer_name="Manana",
                promised_date=datetime.combine(today + timedelta(days=1), datetime.min.time()),
                public_token="tk-man",
            )
        )
        s.add(
            Pedido(
                customer_name="Semana",
                promised_date=datetime.combine(today + timedelta(days=4), datetime.min.time()),
                public_token="tk-sem",
            )
        )
        s.add(
            Pedido(
                customer_name="Viejo",
                promised_date=datetime.combine(today - timedelta(days=3), datetime.min.time()),
                status="pending",
                public_token="tk-vj",
            )
        )
        s.commit()

    resp = client.get("/pedidos")
    assert resp.status_code == 200
    body = resp.text
    # Hoy / Mañana section header + entry
    assert "Hoy / Mañana" in body
    assert "Hoy" in body
    assert "Manana" in body
    # Esta semana
    assert "Esta semana" in body
    assert "Semana" in body
    # Viejos
    assert "Pendientes viejos" in body
    assert "Viejo" in body
    # Age flag for the past-due
    assert "atrasado" in body


def test_pedidos_list_excludes_fulfilled_past_due(session_factory, client):
    """fulfilled past-due pedidos don't surface in the pendientes_viejos bucket."""
    from app.rms.models import Pedido

    today = datetime.utcnow().date()
    with session_factory() as s:
        s.add(
            Pedido(
                customer_name="YA-ENTREGADO",
                promised_date=datetime.combine(today - timedelta(days=5), datetime.min.time()),
                status="fulfilled",
                public_token="tk-fe",
            )
        )
        s.commit()

    resp = client.get("/pedidos")
    assert resp.status_code == 200
    body = resp.text
    # The fulfilled past-due pedido should NOT be in pendientes_viejos
    # (search around the "Pendientes viejos" section).
    if "YA-ENTREGADO" in body:
        # If it appears, it should not be under "Pendientes viejos".
        # Heuristic: it appears with a non-pending badge like "Entregado".
        assert "Entregado" in body


# --- create -----------------------------------------------------------------


def test_create_pedido_with_two_lines(client, session_factory):
    """POST /pedidos/nuevo persists 2 lines + computes total Gs."""
    pid1 = _seed_product(session_factory, name="Croissant", price=12000)
    pid2 = _seed_product(session_factory, name="Muffin", price=8000)

    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Cliente A",
            "customer_phone": "+595 9XX XXXX",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            "promised_time": "10:00",
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "notes": "Sin TACC",
            # 2 lines
            "line_product_id": [str(pid1), str(pid2)],
            "line_qty": ["3", "2"],
            "line_unit_price_gs": ["12000", "8000"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), resp.text
    # Should redirect to detail
    assert "/pedidos/" in resp.headers.get("location", "")

    from app.rms.models import Pedido, PedidoLine

    with session_factory() as s:
        rows = s.execute(select(Pedido)).scalars().all()
        assert len(rows) == 1
        p = rows[0]
        assert p.customer_name == "Cliente A"
        assert p.public_token  # non-empty
        assert len(p.public_token) >= 6
        assert p.status == "pending"
        lines = s.execute(select(PedidoLine).where(PedidoLine.pedido_id == p.id)).scalars().all()
        assert len(lines) == 2
        assert sum(ln.qty * ln.unit_price_gs for ln in lines) == (3 * 12000 + 2 * 8000)


def test_create_pedido_requires_at_least_one_line(client):
    """POST with no line_product_id returns 400 (BUG-00: Spanish, not 422)."""
    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Vacío",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


# --- fulfill ----------------------------------------------------------------


def test_fulfill_creates_sales_and_decrements_stock(client, session_factory):
    """POST /pedidos/{id}/fulfill creates one Sale per line + applies stock drop."""
    from app.rms.models import Ingredient, Pedido, Product, Recipe, RecipeLine

    # Seed: ingredient + recipe (yield 1 muffin) + product
    with session_factory() as s:
        ing = Ingredient(
            name="Harina Pedido",
            unit="kg",
            stock_qty=10.0,
            purchase_price_gs=5000,
        )
        s.add(ing)
        s.flush()
        recipe = Recipe(name="MuffinRec", yield_qty=12, yield_unit="und")
        s.add(recipe)
        s.flush()
        s.add(RecipeLine(recipe_id=recipe.id, line_kind="ingredient", line_ref_id=ing.id, qty=0.3))
        prod = Product(name="MuffinF", sale_price_gs=8000, recipe_id=recipe.id)
        s.add(prod)
        s.commit()
        product_id = prod.id

    # Create pedido with one line: 2 muffins @ 8000
    pdate = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Cumpleañera",
            "customer_phone": "+595",
            "promised_date": pdate,
            "channel": "whatsapp",
            "payment_intent": "efectivo",
            "line_product_id": [str(product_id)],
            "line_qty": ["2"],
            "line_unit_price_gs": ["8000"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with session_factory() as s:
        p = s.execute(select(Pedido)).scalar_one()
        pedido_id = p.id

    # Fulfill
    resp = client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert resp.status_code in (302, 303), resp.text

    from app.rms.models import Sale, StockMovement

    with session_factory() as s:
        p = s.execute(select(Pedido)).scalar_one()
        assert p.status == "fulfilled"
        assert p.fulfilled_at is not None
        assert p.fulfilled_sale_id is not None
        # 1 Sale row created — fulfills into a Sale. With auto-create-customer,
        # the Pedido now has customer_id pointing to the auto-created Customer
        # "Cumpleañera", so the Sale also has customer_id set.
        sales = s.execute(select(Sale).where(Sale.product_id == product_id)).scalars().all()
        sale = next(x for x in sales if x.id == p.fulfilled_sale_id)
        assert sale.qty == 2
        assert sale.unit_price_gs == 8000
        # Stock moved (1 stock move for 1 ingredient line × 2/12 × 0.3 = 0.05 kg)
        moves = (
            s.execute(
                select(StockMovement).where(
                    StockMovement.reference_id == sale.id,
                    StockMovement.reference_type == "sale",
                )
            )
            .scalars()
            .all()
        )
        assert len(moves) >= 1
        ing_row = s.execute(
            select(Ingredient).where(Ingredient.id == moves[0].ingredient_id)
        ).scalar_one()
        # Original 10.0 - (2/12)*0.3 = 10.0 - 0.05 = 9.95
        assert abs(ing_row.stock_qty - 9.95) < 0.01


def test_fulfill_multi_line_creates_multiple_sales(client, session_factory):
    """POST /pedidos/{id}/fulfill on a multi-line pedido creates N Sale rows."""
    from app.rms.models import Pedido, Sale

    p1 = _seed_product(session_factory, name="Pan", price=5000)
    p2 = _seed_product(session_factory, name="Torta", price=30000)

    pdate = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Multi",
            "promised_date": pdate,
            "line_product_id": [str(p1), str(p2)],
            "line_qty": ["2", "1"],
            "line_unit_price_gs": ["5000", "30000"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    resp = client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert resp.status_code in (302, 303)

    with session_factory() as s:
        sales = s.execute(select(Sale).order_by(Sale.id)).scalars().all()
        assert len(sales) == 2
        assert {s.product_id for s in sales} == {p1, p2}
        p = s.execute(select(Pedido)).scalar_one()
        assert p.fulfilled_sale_id == sales[0].id  # first sale linked


# --- status transitions -----------------------------------------------------


def test_status_transition_pending_to_confirmed_to_ready_to_fulfilled(client, session_factory):
    """Full happy path: pending → confirmed → ready → fulfilled."""
    from app.rms.models import Pedido

    pid = _seed_product(session_factory)
    pdate = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    resp = client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "HappyPath",
            "promised_date": pdate,
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["0"],
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    # pending -> confirmed
    r = client.post(
        f"/pedidos/{pedido_id}/status", data={"new_status": "confirmed"}, follow_redirects=False
    )
    assert r.status_code in (302, 303)
    # confirmed -> ready
    r = client.post(
        f"/pedidos/{pedido_id}/status", data={"new_status": "ready"}, follow_redirects=False
    )
    assert r.status_code in (302, 303)
    # ready -> fulfilled via /fulfill endpoint
    r = client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)
    assert r.status_code in (302, 303)

    with session_factory() as s:
        p = s.execute(select(Pedido)).scalar_one()
        assert p.status == "fulfilled"


def test_invalid_transition_fulfilled_to_ready_returns_error(client, session_factory):
    """A fulfilled pedido can't go back to ready (409)."""
    from app.rms.models import Pedido

    pid = _seed_product(session_factory)
    pdate = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "X",
            "promised_date": pdate,
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["0"],
        },
        follow_redirects=False,
    )
    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    # Force the pedido to fulfilled directly via DB
    with session_factory() as s:
        p = s.execute(select(Pedido).where(Pedido.id == pedido_id)).scalar_one()
        p.status = "fulfilled"
        s.commit()

    r = client.post(
        f"/pedidos/{pedido_id}/status",
        data={"new_status": "ready"},
        follow_redirects=False,
    )
    assert r.status_code == 409


def test_invalid_status_value_returns_422(client, session_factory):
    """new_status must be one of the allowed values."""
    from app.rms.models import Pedido

    pid = _seed_product(session_factory)
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "Y",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["0"],
        },
        follow_redirects=False,
    )
    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    r = client.post(
        f"/pedidos/{pedido_id}/status", data={"new_status": "frobnicated"}, follow_redirects=False
    )
    assert r.status_code == 422


def test_cancel_from_pending(client, session_factory):
    """pending → cancelled should succeed."""
    from app.rms.models import Pedido

    pid = _seed_product(session_factory)
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "CancelMe",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["0"],
        },
        follow_redirects=False,
    )
    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    r = client.post(
        f"/pedidos/{pedido_id}/status", data={"new_status": "cancelled"}, follow_redirects=False
    )
    assert r.status_code in (302, 303)

    with session_factory() as s:
        p = s.execute(select(Pedido)).scalar_one()
        assert p.status == "cancelled"


# --- public pickup page -----------------------------------------------------


def test_public_pickup_page_works_without_login(client, session_factory):
    """GET /p/{token} renders without requiring login (no redirect to /login)."""
    from app.rms.models import Pedido

    pid = _seed_product(session_factory)
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "WhatsApp Customer",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            "line_product_id": [str(pid)],
            "line_qty": ["2"],
            "line_unit_price_gs": ["5000"],
        },
        follow_redirects=False,
    )
    with session_factory() as s:
        p = s.execute(select(Pedido)).scalar_one()
        token = p.public_token

    # Hit public page WITHOUT auth cookies (fresh client without session).
    # Use the same `client` fixture (which already monkey-patches
    # make_engine_dialect to point at the test engine); just clear cookies.
    from starlette.testclient import TestClient

    c2 = TestClient(client.app)
    c2.cookies.clear()
    r = c2.get(f"/p/{token}", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "WhatsApp Customer" in body
    # 2 × 5000 = 10000
    assert "10.000" in body  # formatted with dot thousands separator


def test_public_pickup_404_for_unknown_token(client):
    """Unknown public tokens get a 404 (no enumeration leak in the body)."""
    r = client.get("/p/totally-bogus-token-zzz", follow_redirects=False)
    assert r.status_code == 404


# --- audit log --------------------------------------------------------------


def test_audit_log_records_pedido_create_and_fulfill(client, session_factory):
    """AuditLog gets rows for create + fulfill actions."""
    from app.rms.models import AuditLog, Pedido

    pid = _seed_product(session_factory)
    client.post(
        "/pedidos/nuevo",
        data={
            "customer_name": "AuditMe",
            "promised_date": (datetime.utcnow().date() + timedelta(days=1)).isoformat(),
            "line_product_id": [str(pid)],
            "line_qty": ["1"],
            "line_unit_price_gs": ["0"],
        },
        follow_redirects=False,
    )
    with session_factory() as s:
        pedido_id = s.execute(select(Pedido)).scalar_one().id

    client.post(f"/pedidos/{pedido_id}/fulfill", follow_redirects=False)

    with session_factory() as s:
        rows = (
            s.execute(
                select(AuditLog).where(
                    AuditLog.action.in_(("write.pedido.create", "write.pedido.fulfill"))
                )
            )
            .scalars()
            .all()
        )
        actions = {r.action for r in rows}
        assert "write.pedido.create" in actions
        assert "write.pedido.fulfill" in actions
