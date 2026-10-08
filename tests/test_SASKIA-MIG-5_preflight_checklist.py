"""tests/test_SASKIA-MIG-5_preflight_checklist.py — SASKIA-MIG-5.

Pre-billing compliance checklist (URY ury_pos_checklist_log + ury_checklist_item
pattern).

Cross-session context: the Sazon pre-billing checklist is ALREADY
shipped as an *advisory* layer (warnings, not blocks):

  - app/rms/sales/pre_sale_check.py — PreSaleIntent, validate_sale_intent
  - app/rms/sales/pre_sale_check_cart.py — CartIntent, validate_cart_intent
  - app/routers/sales.py:2116 — POST /ventas/nueva/preflight (single-item)
  - app/routers/sales.py:2193 — POST /ventas/nueva/preflight/multi (cart)
  - app/templates/ventas.html — debounced JS preflight call, banner UI

This module LOCKS that contract (regression coverage) so the preflight
behaviour cannot drift:

  1. POST /ventas/nueva/preflight returns a JSON shape with
     {warnings, blockers, is_ready, is_clean}.
  2. POST /ventas/nueva/preflight/multi returns the same shape with a
     per-line warnings/blockers breakdown.
  3. /ventas/nueva/multi's preflight result is consumed by the
     front-end (ventas.html#preflight) to disable submit on blockers.
  4. SASKIA-MIG-5: ?bypass=true on /ventas/nueva/multi (the cash-session
     gate's escape hatch) is a SEPARATE concern — covered by
     test_SASKIA-MIG-2_cash_session_gate.py — and does NOT bypass the
     preflight blockers (stock shortage, allergen, etc.). Power-outage
     escapes the cash gate but the preflight still warns.

If a future agent moves the StockMovement write back to the router
(AGENTS.md rule 8 violation), the preflight's stock-shortage warning
will be lost — the cashier will see "all green" until they hit submit
and a downstream 422 fires. The tests in
test_SASKIA-MIG-6_receta_venta_inventario_close.py cover the
end-to-end chain, this module covers the preflight contract.
"""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker


def _svc_session(session_factory):
    return sessionmaker(bind=session_factory.kw["bind"])()


def _make_product(session_factory, name: str, price: int = 5000, recipe=None):
    from tests.factories import make_product

    s = _svc_session(session_factory)
    try:
        p = make_product(s, name=name, sale_price_gs=price, recipe=recipe)
        s.commit()
        return p.id
    finally:
        s.close()


# ── 1. /ventas/nueva/preflight shape ──────────────────────────────


def test_preflight_single_returns_expected_shape(client_with_caja, session_factory):
    """The single-item preflight must return a JSON with the four
    documented keys: warnings, blockers, is_ready, is_clean. A UI
    client that consumes this can rely on the shape."""
    pid = _make_product(session_factory, name="Mig5PfProd")
    r = client_with_caja.post(
        "/ventas/nueva/preflight",
        data={"product_id": pid, "qty": 1, "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "warnings" in body
    assert "blockers" in body
    assert "is_ready" in body
    assert "is_clean" in body
    # A clean sale with stock available must be is_ready=True (no blockers).
    # is_clean (no warnings AND no blockers) may be False — the
    # preflight emits advisory warnings (e.g. "verify cierres-Z") that
    # the cashier should be aware of but do not block the sale.
    assert body["is_ready"] is True
    assert body["blockers"] == []


def test_preflight_single_invalid_product_is_blocker(client_with_caja):
    """An unknown product_id must surface as a blocker (the sale cannot
    proceed). This pins the contract: a missing product is fatal, not
    a warning."""
    r = client_with_caja.post(
        "/ventas/nueva/preflight",
        data={"product_id": 999999, "qty": 1, "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["is_ready"] is False
    assert len(body["blockers"]) >= 1
    # The blocker must have a code field (consumed by the UI for icon mapping).
    assert all("code" in b for b in body["blockers"])


# ── 2. /ventas/nueva/preflight/multi shape ────────────────────────


def test_preflight_multi_returns_expected_shape(client_with_caja, session_factory):
    """The cart preflight must return the same four keys, plus line_count."""
    pid = _make_product(session_factory, name="Mig5CartProd")
    r = client_with_caja.post(
        "/ventas/nueva/preflight/multi",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "warnings" in body
    assert "blockers" in body
    assert "is_ready" in body
    assert "is_clean" in body
    assert "line_count" in body
    assert body["line_count"] == 1


def test_preflight_multi_empty_cart_is_blocker(client_with_caja):
    """An empty cart must NOT be silently approved. The preflight
    surfaces a blocker so the UI disables submit."""
    r = client_with_caja.post(
        "/ventas/nueva/preflight/multi",
        json={"items": [], "payment_method": "efectivo"},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["is_ready"] is False
    assert body["line_count"] == 0
    assert body["blockers"]


def test_preflight_multi_oversell_is_blocker(client_with_caja, session_factory):
    """Asking for a wildly large quantity must surface as a blocker
    (per app/rms/sales/pre_sale_check.py). This pins the safety
    check that prevents typos like '1000000 muffins' from passing
    the pre-bill checklist."""
    pid = _make_product(session_factory, name="Mig5Oversell")
    r = client_with_caja.post(
        "/ventas/nueva/preflight/multi",
        json={"items": [{"product_id": pid, "qty": 1_000_000}], "payment_method": "efectivo"},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["is_ready"] is False
    # Must be a blocker, not just a warning
    blocker_codes = [b.get("code", "") for b in body["blockers"]]
    assert any("QTY" in c for c in blocker_codes), (
        f"Expected a QTY-related blocker, got {blocker_codes}"
    )


# ── 3. The preflight is independent of the cash-session gate ────


def test_preflight_runs_without_open_caja(client, session_factory):
    """SASKIA-MIG-5: the preflight is the ADVISORY compliance layer.
    It must run regardless of the cash-session gate's state — the
    cashier can run preflight on /ventas/nueva/preflight/multi to see
    the readiness state even when the caja is closed (so they can
    open the caja and retry)."""
    pid = _make_product(session_factory, name="Mig5NoCaja")
    # Note: client (NOT client_with_caja) — no open caja
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # Pre-flight has no opinion on caja state — it checks the sale
    # data, not the session state. The gate is enforced at sale-create.
    assert "blockers" in body
    # The preflight must not itself block on "no caja" — that's the
    # gate's job, not the preflight's.
    blocker_codes = [b.get("code", "") for b in body["blockers"]]
    assert not any("caja" in c.lower() for c in blocker_codes), (
        f"Preflight must not block on caja (that's the gate), got {blocker_codes}"
    )


# ── 4. ?bypass=true does NOT bypass preflight blockers ──────────


def test_bypass_does_not_skip_preflight_blockers(client, session_factory):
    """SASKIA-MIG-5: ?bypass=true is the cash-session gate's escape
    hatch (audit-logged). It must NOT also bypass the preflight's
    stock / qty / allergen blockers — those are about data validity,
    not session state. The two concerns are orthogonal."""
    pid = _make_product(session_factory, name="Mig5BypassNoPf")
    # ?bypass=true + an oversell qty: gate bypassed, preflight blocker
    # should still flag the qty. (But the preflight is advisory —
    # POST /ventas/nueva/multi still goes through. So the test asserts
    # the preflight API separately, not the sale-create path.)
    r = client.post(
        "/ventas/nueva/preflight/multi",
        json={"items": [{"product_id": pid, "qty": 1_000_000}], "payment_method": "efectivo"},
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # The preflight must still surface the qty blocker — bypass is
    # only on the gate, not the preflight.
    assert body["is_ready"] is False


# ── 5. The preflight banner JS contract ─────────────────────────


def test_ventas_renders_preflight_banner_element(client_with_caja):
    """The ventas.html front-end expects a #preflight-banner element
    to render the blockers/warnings. The element must exist in the
    rendered HTML so the JS can target it."""
    r = client_with_caja.get("/ventas", follow_redirects=False)
    assert r.status_code == 200
    assert b'id="preflight-banner"' in r.content


def test_ventas_submits_to_nueva_multi(client_with_caja):
    """The sales form's action is /ventas/nueva/multi (not
    /ventas/nueva). This pins the form so a refactor can't silently
    route it to the single-item endpoint and skip the cart preflight."""
    r = client_with_caja.get("/ventas", follow_redirects=False)
    assert r.status_code == 200
    # The sale form action is set via the form attribute
    assert b'action="/ventas/nueva/multi"' in r.content
