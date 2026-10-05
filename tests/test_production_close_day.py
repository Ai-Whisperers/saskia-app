"""tests/test_production_close_day.py — PRODUCCION-V2 Fase 2.

Tests for the close-day endpoint and the helper in app/rms/eod_completions.py.

Covers:
- close_day_for_product helper: status transitions, notes, idempotency, errors
- /produccion/close-day endpoint: form parse, rate limit, audit, redirect
- /produccion/close-day/reopen endpoint: reverts to open
- /produccion day view enrichment: closure fields in plan_rows_view
- day-level counts: open/done/cancelled/total match plan_rows_view
"""

from __future__ import annotations

from datetime import date

import pytest

from app.rms.eod_completions import close_day_for_product
from app.rms.models import ProductionCompletion


# ---------------------------------------------------------------------------
# Helper: close_day_for_product
# ---------------------------------------------------------------------------


def test_close_day_creates_completion_row_with_zero_qty(session_factory):
    """Closing a product with no prior completion creates a row with qty=0."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        s.commit()  # persist the product so the next session can find it

    with session_factory() as s:
        row = close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes=None
        )
        s.commit()
        assert row.status == "done"
        assert row.completed_qty == 0.0
        assert row.closure_notes is None
        assert row.for_date == target


def test_close_day_updates_existing_completion_status(session_factory):
    """Closing a product that already has a completion row only flips status."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=24.0)
        s.commit()

    with session_factory() as s:
        row = close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes="ok"
        )
        s.commit()
        # qty is NOT changed by closing — that was the cook's "real" bake count.
        assert row.completed_qty == 24.0
        assert row.status == "done"
        assert row.closure_notes == "ok"


def test_close_day_blank_notes_in_helper_overwrites(session_factory):
    """The helper does what the caller asks; only the router normalizes ''→None.

    This documents the contract: the helper is a low-level utility, the
    router layer (produccion_close_day) is responsible for normalizing
    blank form input to None before calling the helper. So passing
    closure_notes='' directly to the helper does overwrite the prior
    value — that's by design, and downstream code (router) prevents it.
    """
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=10.0)
        s.commit()

    with session_factory() as s:
        close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes="feriado"
        )
        s.commit()

    with session_factory() as s:
        # Reopen then re-close with explicit empty string — at the
        # helper level, this DOES overwrite the prior notes. (The
        # router would have converted '' to None before this call.)
        close_day_for_product(s, product_id=pid, for_date=target, status="open")
        s.commit()
    with session_factory() as s:
        row = close_day_for_product(
            s,
            product_id=pid,
            for_date=target,
            status="done",
            closure_notes="",  # blank string
        )
        s.commit()
        assert row.closure_notes == "", (
            "helper with empty string DOES overwrite (router normalizes ''→None)"
        )


def test_close_day_none_notes_preserves_existing(session_factory):
    """The router passes None for blank — the helper must NOT overwrite."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=10.0)
        s.commit()
    with session_factory() as s:
        close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes="feriado"
        )
        s.commit()
    with session_factory() as s:
        # Reopen with no notes — should preserve "feriado".
        close_day_for_product(s, product_id=pid, for_date=target, status="open")
        s.commit()
    with session_factory() as s:
        row = close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes=None
        )
        s.commit()
        assert row.closure_notes == "feriado"


def test_close_day_rejects_invalid_status(session_factory):
    """Status must be open|done|cancelled."""
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        s.commit()

    with session_factory() as s:
        with pytest.raises(ValueError, match="status must be"):
            close_day_for_product(
                s, product_id=pid, for_date=target, status="banana"
            )


def test_close_day_raises_keyerror_for_unknown_product(session_factory):
    """Product that doesn't exist → KeyError."""
    with session_factory() as s:
        with pytest.raises(KeyError, match="Product 99999 not found"):
            close_day_for_product(
                s, product_id=99999, for_date=date(2026, 10, 5), status="done"
            )


def test_close_day_truncates_long_notes_to_500_chars_in_router(client, session_factory):
    """Router truncates >500-char notes; helper itself stores full string."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Croissant")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=8.0)
        s.commit()
    long = "x" * 800
    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
            "status": "done",
            "closure_notes": long,
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text
    with session_factory() as s:
        row = (
            s.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == target,
            )
            .one()
        )
        assert row.closure_notes is not None
        assert len(row.closure_notes) == 500, "router must truncate to 500 chars"


# ---------------------------------------------------------------------------
# Endpoint: /produccion/close-day
# ---------------------------------------------------------------------------


def test_close_day_endpoint_flips_status_to_done(client, session_factory):
    """POST /produccion/close-day with status=done flips the row's status."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=12.0)
        s.commit()

    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
            "status": "done",
            "closure_notes": "Listo",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text

    with session_factory() as s:
        row = (
            s.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == target,
            )
            .one()
        )
        assert row.status == "done"
        assert row.closure_notes == "Listo"


def test_close_day_endpoint_blank_notes_become_null(client, session_factory):
    """Empty closure_notes form field is stored as NULL."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=12.0)
        s.commit()

    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
            "status": "done",
            "closure_notes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text

    with session_factory() as s:
        row = (
            s.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == target,
            )
            .one()
        )
        assert row.status == "done"
        assert row.closure_notes is None


def test_close_day_endpoint_404_for_unknown_product(client, session_factory):
    """POST /produccion/close-day with a bogus product_id → 404."""
    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": "2026-10-05",
            "product_id": "999999",
            "status": "done",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 404, resp.text
    # The global error handler renders a JSON 404. The detail text
    # may not surface "Producto no encontrado" verbatim, but the
    # status code and the not_found path are the contract.
    assert "/produccion/close-day" in resp.text


def test_close_day_endpoint_invalid_status_returns_400(client):
    """Pattern-mismatch in the form field → 400 (project's standard)."""
    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": "2026-10-05",
            "product_id": "1",
            "status": "banana",  # not in (done|cancelled)
        },
        follow_redirects=False,
    )
    # The project uses a custom validation handler that returns 400,
    # not FastAPI's default 422. We accept either as a contract.
    assert resp.status_code in (400, 422), resp.text
    assert "status" in resp.text.lower()


def test_close_day_endpoint_preserves_ui_v2_on_redirect(client, session_factory):
    """When ?ui=v2 is on the request, the redirect Location must include it."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=5.0)
        s.commit()

    resp = client.post(
        "/produccion/close-day?ui=v2",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
            "status": "done",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text
    location = resp.headers.get("location", "")
    assert "ui=v2" in location, f"redirect should preserve ui=v2; got {location!r}"


def test_close_day_endpoint_writes_audit_row(client, session_factory):
    """Close action must be recorded in production_plan_audit (Fase 1 plumbing)."""
    from sqlalchemy import text

    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=5.0)
        s.commit()

    resp = client.post(
        "/produccion/close-day",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
            "status": "cancelled",
            "closure_notes": "no se vendió",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text
    with session_factory() as s:
        rows = s.execute(
            text(
                "SELECT change_source, notes FROM production_plan_audit "
                "WHERE product_id = :pid AND for_date = :fd "
                "AND change_source LIKE 'close_day_%'"
            ),
            {"pid": pid, "fd": target},
        ).all()
        assert len(rows) >= 1, "close must write a production_plan_audit row"
        assert any(r[0] == "close_day_cancelled" for r in rows)
        assert any(r[1] == "no se vendió" for r in rows)


def test_reopen_endpoint_flips_status_to_open(client, session_factory):
    """POST /produccion/close-day/reopen reverts a closed row to open."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=10.0)
        s.commit()
    with session_factory() as s:
        close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes="ok"
        )
        s.commit()

    resp = client.post(
        "/produccion/close-day/reopen",
        data={
            "for_date": target.isoformat(),
            "product_id": str(pid),
        },
        follow_redirects=False,
    )
    assert resp.status_code in (303, 302), resp.text

    with session_factory() as s:
        row = (
            s.query(ProductionCompletion)
            .filter(
                ProductionCompletion.product_id == pid,
                ProductionCompletion.for_date == target,
            )
            .one()
        )
        assert row.status == "open"


# ---------------------------------------------------------------------------
# Day view enrichment: closure fields + counts
# ---------------------------------------------------------------------------


def test_day_view_does_not_500_with_closed_rows(client, session_factory):
    """Smoke: /produccion?for_date=... must render with closed rows present."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=8.0)
        s.commit()
    with session_factory() as s:
        close_day_for_product(
            s, product_id=pid, for_date=target, status="done", closure_notes="fin"
        )
        s.commit()

    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200, resp.text


def test_day_view_does_not_500_with_no_completions(client, session_factory):
    """Fresh day with no completions: closure counts should all be 0, status 200."""
    from tests.factories import make_product

    with session_factory() as s:
        make_product(s, name="Croissant")
        s.commit()
    target = date(2030, 1, 1)
    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# UI: v2 toggle + closure summary + per-row closure cell
# ---------------------------------------------------------------------------


def test_day_view_v2_renders_demanda_column(client, session_factory):
    """v2 (now the default) must include the DEMANDA column header +
    'Demanda' label in rows. Cutover 2026-10-05 removed v1; the
    no-query-param request is now identical to ?ui=v2.
    """
    from datetime import date as _date

    from app.rms.models import ProductionPlanTemplate
    from tests.factories import make_product

    with session_factory() as s:
        prod = make_product(s, name="Chipitas")
        s.commit()
        target = _date(2030, 1, 1)
        from datetime import datetime as _dt, timezone as _tz
        s.add(
            ProductionPlanTemplate(
                weekday=target.weekday(),
                product_id=prod.id,
                qty=10.0,
                updated_at=_dt.now(_tz.utc),
            )
        )
        s.commit()
    # Default (no ?ui param) — must be v2.
    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "Demanda" in body, (
        f"v2 grilla should show 'Demanda' header; body length={len(body)}; "
        f"production-row count={body.count('production-row')}"
    )
    # Check the decomp label is present in the page (header subtitle)
    assert "forecast + pedidos" in body, "v2 should show demand decomposition"
    # Explicit ?ui=v2 still works (idempotent with default).
    resp_v2 = client.get(f"/produccion?for_date={target.isoformat()}&ui=v2")
    assert resp_v2.status_code == 200, resp_v2.text
    assert "Demanda" in resp_v2.text
    # ?ui=v1 is rejected (cutover removed it).
    resp_v1 = client.get(f"/produccion?for_date={target.isoformat()}&ui=v1")
    # App's RequestValidationError handler returns 400 (not FastAPI's
    # default 422) for human-friendly Spanish error messages. Either is
    # a valid "rejected" status; we just need non-200.
    assert resp_v1.status_code in (400, 422), (
        f"?ui=v1 should now return 400 or 422 (cutover 2026-10-05), got {resp_v1.status_code}"
    )


def test_day_view_v2_renders_ui_badge(client, session_factory):
    """After the cutover, the v1/v2 toggle is replaced by a static
    'v2 ✨' badge in the header — no more v1 link to click."""
    from tests.factories import make_product

    with session_factory() as s:
        make_product(s, name="X")
        s.commit()
    target = date(2030, 1, 1)
    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    # The v2 badge is always visible (the only UI version now).
    assert "v2 ✨" in body, "v2 label should be visible in the header badge"
    # The old v1 link should be gone.
    assert 'href="/produccion?view' not in body or 'ui=v1' not in body, (
        "v1 link should be removed from the header after cutover"
    )


def test_day_view_closure_summary_zero_state(client, session_factory):
    """Empty day: counts are 0/0/0/0, the 'cerradas' badge is visible."""
    from tests.factories import make_product

    with session_factory() as s:
        make_product(s, name="X")
        s.commit()
    target = date(2030, 1, 1)
    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200, resp.text
    body = resp.text
    # Save the body for debugging if this fails again.
    import os
    debug_path = os.environ.get("SASKIA_DEBUG_PAGE")
    if debug_path:
        with open(debug_path, "w") as f:
            f.write(body)
    # Debug: confirm we're getting the day view, not the login page.
    assert "Ejecución del turno" in body, (
        f"day view should be rendered; body length={len(body)}; "
        f"first 200 chars: {body[:200]!r}"
    )
    assert "0 cerradas" in body, "day-level 'cerradas' badge should be visible"
    assert "0 pendientes" in body, "day-level 'pendientes' badge should be visible"
    assert "del día" in body, "'del día' suffix should be visible"


def test_day_view_closure_summary_reflects_real_closure(client, session_factory):
    """After closing 1 of 2 rows, day_done_count must be 1."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        p1 = make_product(s, name="A")
        p2 = make_product(s, name="B")
        s.commit()
        ids = [p1.id, p2.id]
        target = date(2026, 10, 5)
        for pid in ids:
            make_completion(
                s, product=s.get(type(p1), pid), for_date=target, completed_qty=2.0
            )
        s.commit()
    # Close one of them
    with session_factory() as s:
        close_day_for_product(s, product_id=ids[0], for_date=target, status="done")
        s.commit()

    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "1 cerradas" in body, (
        f"after closing 1 row, badge should read '1 cerradas'; body contains it: {('1 cerradas' in body)}"
    )


def test_day_view_closure_cell_renders_button_per_row(client, session_factory):
    """Each row must have a .closure-btn (Cerrar turno or Reabrir)."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="X")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=2.0)
        s.commit()

    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "Cerrar turno" in body, "open row should show 'Cerrar turno' button"
    assert "closure-btn" in body, "per-row closure cell should be present"
    assert "data-action=\"close-day\"" in body, "button must declare its action"
    assert f"data-product-id=\"{pid}\"" in body, "button must carry the product id"


def test_day_view_closure_cell_renders_reopen_for_done_row(client, session_factory):
    """A row with status='done' must show the 'Reabrir' button."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="X")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=2.0)
        s.commit()
    with session_factory() as s:
        close_day_for_product(s, product_id=pid, for_date=target, status="done")
        s.commit()

    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "Reabrir" in body, "closed row should show 'Reabrir' button"
    assert "Cerrado" in body, "closed row should show the 'Cerrado' pill"
    assert "data-action=\"reopen-day\"" in body, "reopen button must declare its action"


def test_day_view_closure_cell_renders_cancelled_pill(client, session_factory):
    """A row with status='cancelled' must show 'No horneado' pill + Reabrir button."""
    from tests.factories import make_completion, make_product

    with session_factory() as s:
        prod = make_product(s, name="X")
        pid = prod.id
        target = date(2026, 10, 5)
        make_completion(s, product=prod, for_date=target, completed_qty=0.0)
        s.commit()
    with session_factory() as s:
        close_day_for_product(
            s, product_id=pid, for_date=target, status="cancelled", closure_notes="feriado"
        )
        s.commit()

    resp = client.get(f"/produccion?for_date={target.isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "No horneado" in body, "cancelled row should show 'No horneado' pill"
    assert "feriado" in body, "cancelled row's closure_notes should be in the title attr"
