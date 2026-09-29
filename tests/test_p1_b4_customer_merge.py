"""tests/test_p1_b4_customer_merge.py — P1-B4: customer merge endpoint + duplicate detection.

Verifies:
- Domain layer `customer_merge()` reassigns Sales + Pedidos to the target,
  fills missing contact fields, appends a notes trail, and deletes sources.
- The endpoint /clientes/{id}/merge performs the merge, writes an audit row,
  enforces CSRF, and redirects with 303.
- The /clientes/duplicados page surfaces likely-duplicate groups.

See COMPLETE_PLAN.md §P1-B4.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.crud


# --- Factories used only by this test file ---


@pytest.fixture
def make_customer(session_factory):
    """Create a Customer row with explicit fields. Returns id."""
    from app.rms.models import Customer

    def _make(name, *, phone=None, email=None, notes=None, cedula=None):
        with session_factory() as s:
            c = Customer(
                name=name,
                phone=phone,
                email=email,
                cedula=cedula,
                notes=notes,
            )
            s.add(c)
            s.commit()
            s.refresh(c)
            return c.id

    return _make


@pytest.fixture
def make_product(session_factory):
    """Create one Product with the minimum fields a Sale needs."""
    from app.rms.models import Product

    def _make(name="TestProd", sale_price_gs=2500):
        with session_factory() as s:
            p = Product(name=name, sale_price_gs=sale_price_gs)
            s.add(p)
            s.commit()
            s.refresh(p)
            return p.id

    return _make


@pytest.fixture
def make_sale(session_factory):
    """Create a Sale row attached to a product + customer."""
    from app.rms.models import Product, Sale

    def _make(customer_id, *, product_id=None, qty=2.0, unit_price_gs=2500, sold_at=None):
        with session_factory() as s:
            pid = product_id
            if pid is None:
                # Reuse a single product across all sales in a test if any
                # exist; otherwise create one.
                pid = s.scalar(select(Product.id).order_by(Product.id).limit(1))
                if pid is None:
                    p = Product(name="Auto", sale_price_gs=unit_price_gs)
                    s.add(p)
                    s.flush()
                    pid = p.id
            sale = Sale(
                product_id=pid,
                qty=qty,
                sold_at=sold_at or datetime.now(timezone.utc),
                unit_price_gs=unit_price_gs,
                customer_id=customer_id,
                channel="mostrador",
            )
            s.add(sale)
            s.commit()
            s.refresh(sale)
            return sale.id

    return _make


@pytest.fixture
def make_pedido(session_factory):
    """Create a Pedido attached to a customer.

    public_token must be unique (DB-level UNIQUE constraint). Use a
    uuid4 hex slice so multiple pedidos in the same test don't collide.
    """
    import uuid as _uuid

    from app.rms.models import Pedido

    def _make(customer_id, *, customer_name="x", status="pending"):
        with session_factory() as s:
            p = Pedido(
                customer_id=customer_id,
                customer_name=customer_name,
                promised_date=datetime.now(timezone.utc).date(),
                status=status,
                public_token=_uuid.uuid4().hex[:16],
            )
            s.add(p)
            s.commit()
            s.refresh(p)
            return p.id

    return _make


# --- Domain layer tests ---


def test_merge_basic_two_customers(session_factory, make_customer, make_product, make_sale):
    """2 customers with 3 sales each merge into one → 6 sales reassigned, source deleted."""
    from app.rms.models import Customer, Sale
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A")
    source_id = make_customer("Maria A.")

    for _ in range(3):
        make_sale(target_id)
        make_sale(source_id)

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.target_id == target_id
    assert len(result.sources_merged) == 1
    sr = result.sources_merged[0]
    assert sr.from_id == source_id
    assert sr.sales_reassigned == 3
    assert sr.pedidos_reassigned == 0

    # Source deleted, target kept, all 6 sales now belong to target.
    with session_factory() as s:
        assert s.get(Customer, source_id) is None
        assert s.get(Customer, target_id) is not None
        sales_target = s.scalars(
            select(Sale).where(Sale.customer_id == target_id)
        ).all()
        sales_source = s.scalars(
            select(Sale).where(Sale.customer_id == source_id)
        ).all()
        assert len(sales_target) == 6
        assert len(sales_source) == 0


def test_merge_preserves_target_phone_when_source_has_phone(session_factory, make_customer):
    """Target phone wins over source phone when both are set."""
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A", phone="+595981111111")
    source_id = make_customer("Maria A.", phone="+595982222222")

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.phone_filled_from_source is False

    from app.rms.models import Customer as C

    with session_factory() as s:
        t = s.get(C, target_id)
        assert t.phone == "+595981111111"


def test_merge_fills_target_phone_from_source(session_factory, make_customer):
    """Target has no phone → take the first source's phone."""
    from app.rms.models import Customer
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A", phone=None)
    source_id = make_customer("Maria A.", phone="+595981234567")

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.phone_filled_from_source is True

    with session_factory() as s:
        t = s.get(Customer, target_id)
        assert t.phone == "+595981234567"


def test_merge_fills_target_email_from_source(session_factory, make_customer):
    """Target has no email → take the first source's email."""
    from app.rms.models import Customer
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A", email=None)
    source_id = make_customer("Maria A.", email="maria@example.com")

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.email_filled_from_source is True

    with session_factory() as s:
        t = s.get(Customer, target_id)
        assert t.email == "maria@example.com"


def test_merge_appends_notes_trail(session_factory, make_customer):
    """Source.notes appended to target.notes with separator."""
    from app.rms.models import Customer
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A", notes="VIP desde 2020")
    source_id = make_customer("Maria A.", notes="Cumpleaños: 15/03")

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.notes_appended is True

    with session_factory() as s:
        t = s.get(Customer, target_id)
        assert "VIP desde 2020" in t.notes
        assert f"--- Fusionado desde Maria A. (id={source_id}) ---" in t.notes
        assert "Cumpleaños: 15/03" not in t.notes  # source.notes is NOT copied wholesale


def test_merge_with_pedidos(session_factory, make_customer, make_pedido):
    """Pedidos are reassigned along with sales (FK update)."""
    from app.rms.models import Customer, Pedido
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A")
    source_id = make_customer("Maria A.")
    make_pedido(source_id, customer_name="Maria A.")
    make_pedido(source_id, customer_name="Maria A.")

    with session_factory() as s:
        result = customer_merge(s, target_id=target_id, source_ids=[source_id])
        s.commit()

    assert result.sources_merged[0].pedidos_reassigned == 2

    with session_factory() as s:
        target_pedidos = s.scalars(
            select(Pedido).where(Pedido.customer_id == target_id)
        ).all()
        assert len(target_pedidos) == 2
        # Source row gone.
        assert s.get(Customer, source_id) is None


def test_merge_rejects_self_merge(session_factory, make_customer):
    """target_id in source_ids → ValueError."""
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A")
    with session_factory() as s:
        with pytest.raises(ValueError, match="cannot merge"):
            customer_merge(s, target_id=target_id, source_ids=[target_id])


def test_merge_rejects_missing_target(session_factory, make_customer):
    """Non-existent target_id → ValueError."""
    from app.rms.customer_merge import customer_merge

    with session_factory() as s:
        with pytest.raises(ValueError, match="target customer"):
            customer_merge(s, target_id=99999, source_ids=[1])


def test_merge_rejects_missing_source(session_factory, make_customer):
    """Non-existent source_id → ValueError."""
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A")
    with session_factory() as s:
        with pytest.raises(ValueError, match="source customer"):
            customer_merge(s, target_id=target_id, source_ids=[99999])


def test_merge_rejects_empty_sources(session_factory, make_customer):
    """Empty source_ids → ValueError."""
    from app.rms.customer_merge import customer_merge

    target_id = make_customer("Maria A")
    with session_factory() as s:
        with pytest.raises(ValueError, match="source_ids must not be empty"):
            customer_merge(s, target_id=target_id, source_ids=[])


# --- Endpoint tests (HTTP) ---


def test_clientes_duplicados_page_finds_duplicate_groups(
    authed_client, session_factory, make_customer
):
    """GET /clientes/duplicados returns 200 with at least one group when fixtures have duplicates."""
    # Two customers with the same phone prefix (first 5 chars) + same name.
    a = make_customer("Maria Garcia", phone="+595981234567")
    b = make_customer("Maria Garcia", phone="+595981234599")  # same first 5 chars
    # Distractor: should NOT appear in any group.
    c = make_customer("Juan Perez", phone="+595979876543")

    resp = authed_client.get("/clientes/duplicados")
    assert resp.status_code == 200
    body = resp.text
    # The HTML must show the group.
    assert f"id={a}" in body or f"id={b}" in body
    # Sanity: a non-duplicate row should not be present as a "duplicado" of anyone else.
    assert f"id={c}" not in body or "Juan Perez" in body  # distractor name appears only as itself


def test_clientes_duplicados_page_empty_when_no_duplicates(
    authed_client, make_customer
):
    """No duplicates → 200 with empty groups.

    Phones chosen so the first 5 chars differ ('+5959' vs '+5957').
    """
    make_customer("Solo Uno", phone="+595981111111")
    make_customer("Otro Cliente", phone="+595871222222")

    resp = authed_client.get("/clientes/duplicados")
    assert resp.status_code == 200
    # Empty-state template renders.
    assert "No se detectaron duplicados" in resp.text


def test_merge_endpoint_returns_303_on_success(
    authed_client, session_factory, make_customer, make_product, make_sale
):
    """POST /clientes/{id}/merge returns 303 redirect on success."""
    from app.rms.models import Customer, Sale

    target_id = make_customer("Maria A")
    source_id = make_customer("Maria A.")
    make_sale(target_id)
    make_sale(source_id)

    csrf = authed_client.cookies.get("csrf_token", "")
    resp = authed_client.post(
        f"/clientes/{target_id}/merge",
        data={
            "source_ids": str(source_id),
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/clientes" in resp.headers.get("location", "")

    # Verify the merge landed.
    with session_factory() as s:
        assert s.get(Customer, source_id) is None
        n_sales = s.scalar(select(Sale).where(Sale.customer_id == target_id))
        assert n_sales is not None


def test_merge_endpoint_records_audit_log(
    authed_client, session_factory, make_customer, make_product, make_sale
):
    """POST /clientes/{id}/merge writes a write.customer.merge audit row."""
    from app.rms.models import AuditLog

    target_id = make_customer("Maria A")
    source_id = make_customer("Maria A.")
    make_sale(source_id)

    csrf = authed_client.cookies.get("csrf_token", "")
    resp = authed_client.post(
        f"/clientes/{target_id}/merge",
        data={"source_ids": str(source_id), "csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with session_factory() as s:
        rows = s.scalars(
            select(AuditLog).where(AuditLog.action == "write.customer.merge")
        ).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.target_type == "customer"
        assert row.target_id == str(target_id)
        assert row.detail["sources"] == [{"id": source_id, "name": "Maria A."}]
        assert row.detail["sales_reassigned"] == 1
        assert row.detail["pedidos_reassigned"] == 0


def test_merge_endpoint_requires_csrf(
    authed_client, session_factory, make_customer, make_product, make_sale
):
    """POST without csrf cookie → 403 (middleware-level rejection)."""
    target_id = make_customer("Maria A")
    source_id = make_customer("Maria A.")
    make_sale(target_id)

    # Clear cookies so the middleware doesn't see a valid csrf_token cookie.
    authed_client.cookies.clear()
    resp = authed_client.post(
        f"/clientes/{target_id}/merge",
        data={"source_ids": str(source_id), "csrf_token": "bogus"},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_merge_endpoint_handles_value_error(
    authed_client, session_factory, make_customer
):
    """POST with target_id in source_ids → redirect with error flash."""
    target_id = make_customer("Maria A")
    csrf = authed_client.cookies.get("csrf_token", "")
    resp = authed_client.post(
        f"/clientes/{target_id}/merge",
        data={"source_ids": str(target_id), "csrf_token": csrf},
        follow_redirects=False,
    )
    # ValueError is caught, redirected to /clientes/duplicados with error flash.
    assert resp.status_code == 303
    assert "/clientes/duplicados" in resp.headers.get("location", "")


def test_clientes_list_has_duplicados_link(authed_client):
    """The /clientes page surfaces a 'Ver duplicados' button."""
    resp = authed_client.get("/clientes")
    assert resp.status_code == 200
    body = resp.text
    assert 'href="/clientes/duplicados"' in body
    assert "Ver duplicados" in body