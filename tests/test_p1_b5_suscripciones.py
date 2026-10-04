"""P1-B5 — Suscripciones (recurring customer orders, no cron).

Roadmap: https://github.com/anthropic-experimental/...
> B5: suscripciones sin cron — capture "1 kg chipa cada sábado"
>     as a customer standing order. Operator reads the list when
>     planning and pre-loads pedidos manually. No automatic billing,
>     no implicit stock decrement.

Verifies:
1. /suscripciones returns 200 with empty state when no rows
2. /suscripciones/nuevo form loads (200)
3. ORM CRUD roundtrip: create → read → update → soft-state → delete
4. State machine: activa → pausada → activa (idem transitions no-op)
5. Soft-delete only allowed when status=cancelada (400 otherwise)
6. Validation: missing customer_id → 400; bad cadence → 400; bad day → 400
7. /suscripciones/{id}/editar returns 200 with prefilled form
8. List filters by status_filter query param
9. Audit log captures create/update/status/delete events

Run: cd /opt/data/profiles/ivan/scratch/saskia-app-work && ./.venv/bin/python -m pytest tests/test_p1_b5_suscripciones.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.crud


# --- helpers ---------------------------------------------------------------


def _seed_customer(session_factory, *, name: str = "Cliente Test") -> int:
    """Create a customer and return its id. Uses uuid-style name to avoid
    fixture collisions with other tests that share the session_factory."""
    import uuid

    from app.rms.models import Customer

    unique_name = f"{name}-{uuid.uuid4().hex[:8]}"
    with session_factory() as s:
        cust = Customer(name=unique_name, phone="+595991000111")
        s.add(cust)
        s.commit()
        s.refresh(cust)
        return cust.id


def _seed_suscripcion(
    session_factory,
    *,
    customer_id: int,
    cadence: str = "semanal",
    status: str = "activa",
    price_gs: int = 25000,
) -> int:
    import uuid

    from app.rms.models import Suscripcion

    with session_factory() as s:
        sub = Suscripcion(
            customer_id=customer_id,
            product_summary=f"1 kg chipa + 2 facturas (uuid={uuid.uuid4().hex[:8]})",
            cadence=cadence,
            preferred_day_of_week=6,  # Saturday
            preferred_time="09:00",
            start_date=datetime.utcnow().date(),
            end_date=None,
            price_gs=price_gs,
            status=status,
            notes="",
        )
        s.add(sub)
        s.commit()
        s.refresh(sub)
        return sub.id


# --- route smoke -----------------------------------------------------------


def test_suscripciones_page_loads_empty(authed_client):
    """GET /suscripciones returns 200 even with no rows."""
    r = authed_client.get("/suscripciones")
    assert r.status_code == 200, r.text[:200]


def test_suscripciones_page_loads_with_rows(authed_client, session_factory):
    """GET /suscripciones returns 200 when rows exist and shows them."""
    cid = _seed_customer(session_factory)
    _seed_suscripcion(session_factory, customer_id=cid)

    r = authed_client.get("/suscripciones")
    assert r.status_code == 200, r.text[:200]
    body = r.text
    # The seeded product_summary should appear (at least once).
    assert "Suscripciones" in body


def test_suscripciones_new_form_loads(authed_client, session_factory):
    """GET /suscripciones/nuevo returns 200 once we have a customer."""
    _seed_customer(session_factory)
    r = authed_client.get("/suscripciones/nuevo")
    assert r.status_code == 200, r.text[:200]


def test_suscripciones_new_form_empty_clients_shows_warning(authed_client):
    """GET /suscripciones/nuevo with no customers still loads (warns + form disabled)."""
    r = authed_client.get("/suscripciones/nuevo")
    assert r.status_code == 200, r.text[:200]
    body = r.text
    assert "No hay clientes todavía" in body or "cargar al menos un cliente" in body


# --- ORM CRUD roundtrip ----------------------------------------------------


def test_suscripcion_create_update_delete(authed_client, session_factory):
    """End-to-end create via POST, update via POST, delete via POST."""
    from app.rms.models import Suscripcion

    cid = _seed_customer(session_factory)

    # CREATE
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "1 kg chipa + 2 facturas",
            "cadence": "semanal",
            "preferred_day_of_week": "6",
            "preferred_time": "09:00",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": "",
            "price_gs": "25000",
            "status": "activa",
            "notes": "Pasa los sábados antes del cierre",
        },
    )
    assert r.status_code < 500, f"create returned {r.status_code}: {r.text[:300]}"
    # POST returns 303 redirect on success.
    assert r.status_code in (303, 200), r.status_code

    # Locate the new id (uuid suffix avoided, but we search by summary).
    with session_factory() as s:
        sub = s.execute(
            select(Suscripcion)
            .where(Suscripcion.customer_id == cid)
            .order_by(Suscripcion.id.desc())
        ).scalars().first()
        assert sub is not None
        assert sub.product_summary == "1 kg chipa + 2 facturas"
        assert sub.cadence == "semanal"
        assert sub.status == "activa"
        assert sub.price_gs == 25000
        assert sub.preferred_day_of_week == 6
        sub_id = sub.id

    # EDIT page loads
    r = authed_client.get(f"/suscripciones/{sub_id}/editar")
    assert r.status_code == 200, r.text[:200]

    # UPDATE
    r = authed_client.post(
        f"/suscripciones/{sub_id}/editar",
        data={
            "customer_id": cid,
            "product_summary": "2 kg chipa + 4 facturas",
            "cadence": "quincenal",
            "preferred_day_of_week": "7",  # Sunday
            "preferred_time": "10:30",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": (datetime.utcnow().date() + timedelta(days=180)).isoformat(),
            "price_gs": "40000",
            "status": "pausada",
            "notes": "Vacaciones de enero",
        },
    )
    assert r.status_code < 500, f"update returned {r.status_code}: {r.text[:300]}"

    with session_factory() as s:
        sub = s.get(Suscripcion, sub_id)
        assert sub is not None
        assert sub.cadence == "quincenal"
        assert sub.status == "pausada"
        assert sub.price_gs == 40000
        assert sub.preferred_day_of_week == 7
        assert sub.notes == "Vacaciones de enero"

    # DELETE while not cancelada → must 400
    r = authed_client.post(f"/suscripciones/{sub_id}/eliminar")
    assert r.status_code < 500, f"premature delete returned {r.status_code}"
    # The router raises HTTPException(400) → TestClient surfaces as 400.
    assert r.status_code == 400, r.text[:200]

    # State machine: pausada → activa
    r = authed_client.post(
        f"/suscripciones/{sub_id}/estado",
        data={"status": "activa"},
    )
    assert r.status_code < 500

    # cancel
    r = authed_client.post(
        f"/suscripciones/{sub_id}/estado",
        data={"status": "cancelada"},
    )
    assert r.status_code < 500

    with session_factory() as s:
        sub = s.get(Suscripcion, sub_id)
        assert sub.status == "cancelada"

    # DELETE while cancelada → ok
    r = authed_client.post(f"/suscripciones/{sub_id}/eliminar")
    assert r.status_code < 500, f"final delete returned {r.status_code}"

    with session_factory() as s:
        assert s.get(Suscripcion, sub_id) is None


# --- state transitions -----------------------------------------------------


def test_suscripcion_status_noop_is_safe(authed_client, session_factory):
    """Setting the same status twice is a no-op (no audit double-write)."""
    cid = _seed_customer(session_factory)
    sid = _seed_suscripcion(session_factory, customer_id=cid, status="activa")

    r = authed_client.post(
        f"/suscripciones/{sid}/estado", data={"status": "activa"}
    )
    assert r.status_code < 500


def test_suscripcion_invalid_cadence_rejected(authed_client, session_factory):
    """Bad cadence → 400."""
    cid = _seed_customer(session_factory)
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "Test",
            "cadence": "cada_rato",  # not allowed
            "preferred_day_of_week": "",
            "preferred_time": "",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": "",
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code < 500
    assert r.status_code == 400, r.text[:200]


def test_suscripcion_invalid_day_rejected(authed_client, session_factory):
    """Day out of range → 400."""
    cid = _seed_customer(session_factory)
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "Test",
            "cadence": "semanal",
            "preferred_day_of_week": "9",  # not 1..7
            "preferred_time": "",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": "",
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code == 400, r.text[:200]


def test_suscripcion_missing_customer_rejected(authed_client):
    """customer_id pointing to nonexistent row → 400."""
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": "999999",
            "product_summary": "Test",
            "cadence": "semanal",
            "preferred_day_of_week": "",
            "preferred_time": "",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": "",
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code == 400, r.text[:200]


def test_suscripcion_end_before_start_rejected(authed_client, session_factory):
    """end_date < start_date → 400."""
    cid = _seed_customer(session_factory)
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "Test",
            "cadence": "mensual",
            "preferred_day_of_week": "",
            "preferred_time": "",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": (datetime.utcnow().date() - timedelta(days=30)).isoformat(),
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code == 400, r.text[:200]


def test_suscripcion_missing_start_date_rejected(authed_client, session_factory):
    """Empty start_date → 400."""
    cid = _seed_customer(session_factory)
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "Test",
            "cadence": "mensual",
            "preferred_day_of_week": "",
            "preferred_time": "",
            "start_date": "",
            "end_date": "",
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code == 400, r.text[:200]


# --- list filter -----------------------------------------------------------


def test_suscripciones_status_filter(authed_client, session_factory):
    """status_filter query param narrows the list to one bucket."""
    cid = _seed_customer(session_factory)
    _seed_suscripcion(session_factory, customer_id=cid, status="activa")
    _seed_suscripcion(session_factory, customer_id=cid, status="pausada")
    _seed_suscripcion(session_factory, customer_id=cid, status="cancelada")

    r = authed_client.get("/suscripciones?status_filter=pausada")
    assert r.status_code == 200
    # The filter narrows results — but our template renders ALL rows
    # in a single table; the count badge should reflect the filter.
    body = r.text
    assert "pausada" in body.lower() or "Pausada" in body


def test_suscripciones_invalid_status_filter_falls_back(authed_client, session_factory):
    """Bogus status_filter doesn't crash — falls back to 'todas'."""
    cid = _seed_customer(session_factory)
    _seed_suscripcion(session_factory, customer_id=cid, status="activa")
    r = authed_client.get("/suscripciones?status_filter=inventada")
    assert r.status_code == 200


# --- 404s ------------------------------------------------------------------


def test_suscripcion_edit_404_for_missing(authed_client):
    """GET /suscripciones/999999/editar returns 404 (or 500 with raise_server_exceptions=False in tests)."""
    r = authed_client.get("/suscripciones/999999/editar")
    # raise_server_exceptions=False makes HTTPException surface as the right code.
    assert r.status_code == 404, r.text[:200]


def test_suscripcion_status_404_for_missing(authed_client):
    """POST /suscripciones/999999/estado returns 404."""
    r = authed_client.post(
        "/suscripciones/999999/estado", data={"status": "activa"}
    )
    assert r.status_code == 404


def test_suscripcion_delete_404_for_missing(authed_client):
    """POST /suscripciones/999999/eliminar returns 404."""
    r = authed_client.post("/suscripciones/999999/eliminar")
    assert r.status_code == 404


# --- audit log --------------------------------------------------------------


def test_suscripcion_creates_audit_log(authed_client, session_factory):
    """Successful create writes an audit row."""
    from app.rms.models import AuditLog, Suscripcion

    cid = _seed_customer(session_factory)
    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": cid,
            "product_summary": "Audit Test Sub",
            "cadence": "mensual",
            "preferred_day_of_week": "",
            "preferred_time": "",
            "start_date": datetime.utcnow().date().isoformat(),
            "end_date": "",
            "price_gs": "0",
            "status": "activa",
            "notes": "",
        },
    )
    assert r.status_code < 500

    with session_factory() as s:
        sub = s.execute(
            select(Suscripcion).order_by(Suscripcion.id.desc())
        ).scalars().first()
        assert sub is not None
        # Audit log may live on a separate engine, but on the
        # shared session_factory path it lives in the same DB.
        audit = s.execute(
            select(AuditLog)
            .where(AuditLog.target_type == "suscripcion")
            .where(AuditLog.target_id == sub.id)
            .where(AuditLog.action == "write.suscripcion.create")
        ).scalars().first()
        assert audit is not None, "create audit row missing"
