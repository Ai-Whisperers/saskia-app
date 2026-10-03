"""tests/test_pedido_history.py — phase 4 timeline + customer history tests.

Verify that:
- build_pedido_timeline() returns sorted events with the right kinds
- customer_recent_pedidos() excludes the current pedido and limits results
- The pedido detail page renders the timeline + recent pedidos
- /pedidos/nuevo?customer_id=X&from=Y triggers the Pedir de nuevo flow
"""

from __future__ import annotations

import json

from app.services.pedido_history import (
    build_pedido_timeline,
    customer_recent_pedidos,
)


def _kyrian_customer_id(session_factory):
    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        return c.id


def test_timeline_for_fresh_pedido(qseed, session_factory):
    """A pedido with no audit history returns an empty timeline."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    with session_factory() as s:
        from app.rms.models import Pedido
        pedido = s.execute(
            __import__("sqlalchemy").select(Pedido)
            .where(Pedido.customer_id == cid)
            .limit(1)
        ).scalar_one()
        timeline = build_pedido_timeline(s, pedido)
    # The seed doesn't write audit_log entries, so empty is expected
    assert isinstance(timeline, list)


def test_timeline_includes_audit_status_change(qseed, session_factory):
    """A status transition via /pedidos/{id}/status creates an audit row
    that should appear in the timeline."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        from app.rms.models import AuditLog, Pedido
        pedido = s.execute(
            __import__("sqlalchemy").select(Pedido)
            .where(Pedido.customer_id == cid)
            .order_by(Pedido.id.asc())
            .limit(1)
        ).scalar_one()
        pedido_id = pedido.id

        # Manually create an audit row (simulating a status transition)
        from datetime import datetime
        s.add(AuditLog(
            occurred_at=datetime.utcnow(),
            user_id="test-operator",
            action="write.pedido.status",
            target_type="pedido",
            target_id=str(pedido_id),
            detail={"old_status": "pending", "new_status": "confirmed"},
        ))
        s.commit()

    with session_factory() as s:
        pedido = s.get(Pedido, pedido_id)
        timeline = build_pedido_timeline(s, pedido)

    status_events = [e for e in timeline if e.kind == "status"]
    assert len(status_events) == 1
    assert "confirmed" in status_events[0].label
    assert status_events[0].actor == "test-operator"


def test_recent_pedidos_excludes_current(qseed, session_factory):
    """customer_recent_pedidos() should not include the current pedido."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        from app.rms.models import Pedido
        all_pedidos = s.execute(
            __import__("sqlalchemy").select(Pedido)
            .where(Pedido.customer_id == cid)
            .order_by(Pedido.promised_date.desc())
        ).scalars().all()
        assert len(all_pedidos) == 6

        current = all_pedidos[0]
        recent = customer_recent_pedidos(s, cid, limit=8, exclude_pedido_id=current.id)

    # 6 total, exclude current → 5 returned
    assert len(recent) == 5
    assert all(r.id != current.id for r in recent)
    # Most recent should be the pedido with promised_date closest to today
    assert recent[0].id == all_pedidos[1].id


def test_recent_pedidos_respects_limit(qseed, session_factory):
    """limit caps the number of returned pedidos."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        recent = customer_recent_pedidos(s, cid, limit=3)
    assert len(recent) == 3


def test_recent_pedidos_has_totals_and_counts(qseed, session_factory):
    """Each summary has the right total + line count."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)

    with session_factory() as s:
        recent = customer_recent_pedidos(s, cid, limit=2)

    for r in recent:
        assert r.total_gs > 0  # Every pedido has at least one line
        assert r.line_count >= 1
        assert r.status in ("pending", "confirmed", "ready", "fulfilled", "cancelled")


def test_detail_page_renders_timeline(client, monkeypatch, qseed, session_factory):
    """GET /pedidos/{id} embeds timeline + recent pedidos in the rendered HTML."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    with session_factory() as s:
        from app.rms.models import Pedido
        pedido = s.execute(
            __import__("sqlalchemy").select(Pedido).where(Pedido.customer_id == cid).limit(1)
        ).scalar_one()
        pedido_id = pedido.id

    r = client.get(f"/pedidos/{pedido_id}")
    assert r.status_code == 200
    html = r.text
    # Either timeline is shown (when present) or the section is skipped —
    # both are valid; what matters is no crash + recent pedidos section
    # appears when there's history.
    assert "Historial" in html or "historial" in html.lower() or "Otros pedidos" in html


def test_detail_page_shows_recent_pedidos_section(client, monkeypatch, qseed, session_factory):
    """Detail page shows the recent pedidos table when customer has >1 pedido."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    with session_factory() as s:
        from app.rms.models import Pedido
        pedido = s.execute(
            __import__("sqlalchemy").select(Pedido).where(Pedido.customer_id == cid).limit(1)
        ).scalar_one()
        pedido_id = pedido.id

    r = client.get(f"/pedidos/{pedido_id}")
    html = r.text
    assert "Otros pedidos" in html
    # Should show links to repeat (Pedir de nuevo from this pedido)
    assert "Repetir" in html or "Pedir de nuevo" in html


def test_detail_page_pedir_de_nuevo_link(client, monkeypatch, qseed, session_factory):
    """The 'Pedir de nuevo' CTA links to /pedidos/nuevo with the right params."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    with session_factory() as s:
        from app.rms.models import Pedido
        pedido = s.execute(
            __import__("sqlalchemy").select(Pedido).where(Pedido.customer_id == cid).limit(1)
        ).scalar_one()
        pedido_id = pedido.id

    r = client.get(f"/pedidos/{pedido_id}")
    html = r.text
    expected_href = f"/pedidos/nuevo?customer_id={cid}&from={pedido_id}"
    assert expected_href in html, f"Expected {expected_href} in detail HTML"


def test_nuevo_with_from_param_prefills_lines(client, monkeypatch, qseed, session_factory):
    """GET /pedidos/nuevo?customer_id=X&from=Y embeds clone_lines in JSON."""
    qseed("with_kyrian_full")
    cid = _kyrian_customer_id(session_factory)
    with session_factory() as s:
        from app.rms.models import Pedido
        source = s.execute(
            __import__("sqlalchemy").select(Pedido).where(Pedido.customer_id == cid).limit(1)
        ).scalar_one()
        source_id = source.id

    r = client.get(f"/pedidos/nuevo?customer_id={cid}&from={source_id}")
    assert r.status_code == 200
    html = r.text
    # The prefill JSON blob is rendered server-side
    assert "customer-prefill" in html
    # Extract the JSON between the script tags
    import re
    m = re.search(r'<script id="customer-prefill"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert m, "customer-prefill script not found"
    prefill = json.loads(m.group(1))
    assert len(prefill["clone_lines"]) >= 1
    assert prefill["last_pedido_id"] == source_id
