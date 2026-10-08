"""tests/test_SASKIA-MIG-2_cash_session_gate.py — SASKIA-MIG-2.

Pre-shift session gate (FloCafe ShiftOpenModal + URY posOpening pattern):

  - /ventas renders a soft banner with "Abrir caja" button when no
    open cash session exists.
  - POST /ventas/nueva and POST /ventas/nueva/multi return 422 when
    the resolved payment method is "efectivo" AND no open cash session
    exists.
  - Non-cash methods (QR, transferencia, fiado) pass through even
    without an open session.
  - After opening the caja, sales in efectivo work normally.
  - The sidebar exposes /caja as a link in the "Operación" group.

Cross-session pattern: /caja was already implemented (WP-1.3, migration
106, app/routers/caja.py) and tests/test_cash_sessions.py already locks
the open/close/expected-amount arithmetic. This module only locks the
NEW UX surface: the banner on /ventas, the hard gate on POST, and the
sidebar entry — the things that make the gate user-visible.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

# ── helpers ────────────────────────────────────────────────────────


def _svc_session(session_factory):
    return sessionmaker(bind=session_factory.kw["bind"])()


def _make_product(session_factory, name: str = "Mig2Prod", price: int = 5000):
    from tests.factories import make_product

    s = _svc_session(session_factory)
    try:
        p = make_product(s, name=name, sale_price_gs=price)
        s.commit()
        return p.id
    finally:
        s.close()


# ── 1. Sidebar exposes /caja under Operación ──────────────────────


def test_nav_groups_contains_caja_under_operacion():
    """The cashier's daily flow has a /caja link in the same group as
    Ventas. /caja was orphaned before SASKIA-MIG-2 — there was no
    sidebar entry and the only way to open a caja was to type the URL
    by hand, which is the kind of friction we are removing."""
    from app.rms.nav import NAV_GROUPS

    operacion = next((g for g in NAV_GROUPS if g[0] == "Operación"), None)
    assert operacion is not None, "Operación group missing from NAV_GROUPS"
    routes = [item["route"] for item in operacion[1]]
    assert "/caja" in routes, f"/caja not in Operación sidebar; got {routes}"


def test_caja_link_uses_icon_cash():
    """The /caja nav entry uses the icon-cash symbol. Locks the
    'icon is in the right shape' invariant so a future template
    refactor can't silently break the icon."""
    from app.rms.nav import NAV_GROUPS

    operacion = next(g for g in NAV_GROUPS if g[0] == "Operación")
    caja = next((i for i in operacion[1] if i["route"] == "/caja"), None)
    assert caja is not None
    assert caja["icon"] == "icon-cash"
    assert caja["label"] == "Caja"


# ── 2. /ventas GET surfaces the soft banner ──────────────────────


def test_ventas_renders_banner_when_no_open_session(authed_client):
    """When no cash session is open, /ventas must show the soft
    banner with the 'Abrir caja' CTA. The banner is data-testid'd
    so the regression test is anchored to the specific affordance
    rather than to free-text Spanish (which can change for tone)."""
    r = authed_client.get("/ventas", follow_redirects=False)
    assert r.status_code == 200
    assert b'data-testid="caja-banner-soft"' in r.content
    assert b"Caja cerrada" in r.content
    assert b"Abrir caja" in r.content
    # The banner links to /caja
    assert b'href="/caja"' in r.content


def test_ventas_no_banner_when_session_is_open(authed_client, session_factory):
    """When a cash session IS open, the banner must NOT appear.
    The cashier can register ventas without further interruption."""
    from app.rms import cash

    s = _svc_session(session_factory)
    try:
        cash.open_session(s, opening_gs=0, opened_by="test")
        s.commit()
    finally:
        s.close()

    r = authed_client.get("/ventas", follow_redirects=False)
    assert r.status_code == 200
    assert b'data-testid="caja-banner-soft"' not in r.content
    assert b"Caja cerrada" not in r.content


# ── 3. Hard gate on POST /ventas/nueva (cash only) ──────────────


def test_post_ventas_nueva_efectivo_blocked_without_session(authed_client, session_factory):
    """POST /ventas/nueva with payment_method=efectivo AND no open
    cash session must return 422. This is the hard safety net below
    the soft banner — a cashier who skips the banner still cannot
    create an orphan cash sale that would not be reconciled at
    cierre-Z."""
    pid = _make_product(session_factory)
    r = authed_client.post(
        "/ventas/nueva",
        data={"product_id": pid, "qty": 1, "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 422, r.text[:300]
    # The 422 body must contain the user-facing Spanish message so
    # the operator knows exactly what to do.
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    detail = body.get("detail", "")
    assert "caja" in detail.lower() or "efectivo" in detail.lower(), (
        f"422 detail should mention caja/efectivo, got: {detail!r}"
    )


def test_post_ventas_nueva_qr_allowed_without_session(authed_client, session_factory):
    """POST /ventas/nueva with a non-efectivo method (QR) must
    SUCCEED even without an open cash session. The cash drawer
    never opens for QR sales, so the cierre-Z arithmetic would
    not be affected by the absence of an open session."""
    pid = _make_product(session_factory, name="Mig2QrProd")
    r = authed_client.post(
        "/ventas/nueva",
        data={"product_id": pid, "qty": 1, "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]
    # 303 is the standard sale-create redirect to the recibo; both are fine.


def test_post_ventas_nueva_efectivo_allowed_with_session(authed_client, session_factory):
    """Once a cash session is open, POST /ventas/nueva with efectivo
    must succeed (the gate is no longer armed)."""
    from app.rms import cash

    s = _svc_session(session_factory)
    try:
        cash.open_session(s, opening_gs=0, opened_by="test")
        s.commit()
    finally:
        s.close()

    pid = _make_product(session_factory, name="Mig2OkProd")
    r = authed_client.post(
        "/ventas/nueva",
        data={"product_id": pid, "qty": 1, "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]


# ── 4. Hard gate on POST /ventas/nueva/multi (cash only) ────────


def test_post_ventas_nueva_multi_efectivo_blocked_without_session(authed_client, session_factory):
    """Same gate applies to the multi-item path that the POS UI
    actually uses. /ventas/nueva is the form-style endpoint (single
    product), /ventas/nueva/multi is the JSON endpoint the JS cart
    serialises to — both must block cash sales without a session."""
    pid = _make_product(session_factory, name="Mig2MultiProd")
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 422, r.text[:300]


def test_post_ventas_nueva_multi_default_efectivo_blocked(authed_client, session_factory):
    """If the client omits payment_method, the server resolves to
    the default (efectivo per Phase 4 catalogs) and the gate must
    still fire. This is the realistic scenario: a quick-sale UI
    just hits POST without a payment_method field."""
    pid = _make_product(session_factory, name="Mig2DefaultProd")
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": pid, "qty": 1}]},
        follow_redirects=False,
    )
    assert r.status_code == 422, r.text[:300]


def test_post_ventas_nueva_multi_transferencia_allowed_without_session(
    authed_client, session_factory
):
    """Non-cash methods (transferencia) on the multi endpoint also
    pass through the gate when no session is open. Mirrors the
    /ventas/nueva QR test above for the multi-item path."""
    pid = _make_product(session_factory, name="Mig2TransfProd")
    r = authed_client.post(
        "/ventas/nueva/multi",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "transferencia"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]


# ── 5. Other /ventas/* routes are unaffected ─────────────────────


@pytest.mark.parametrize("path", ["/ventas/historial", "/ventas/qa", "/ventas/express"])
def test_ventas_subroutes_have_no_banner(authed_client, path):
    """The banner lives ONLY on /ventas (the POS landing). Sub-routes
    like /ventas/historial, /ventas/qa, /ventas/express are not the
    cashier surface and must not show the caja-closed banner."""
    r = authed_client.get(path, follow_redirects=False)
    assert r.status_code == 200, r.text[:300]
    assert b'data-testid="caja-banner-soft"' not in r.content


# ── 6. SASKIA-MIG-5: ?bypass=true emergency escape hatch ────────


def test_bypass_query_param_skips_caja_gate(authed_client, session_factory):
    """SASKIA-MIG-5: ?bypass=true on /ventas/nueva/multi skips the
    cash-session gate. This is the emergency escape hatch for
    power-outage / system-bug situations where opening a caja is not
    possible. The bypass is recorded in the audit log so a manager
    can review later.

    Use case: the operator's terminal lost connectivity, they still
    need to ring up a customer in cash, and they can't open the caja
    page. They hit ?bypass=true to record the sale, then reconcile
    the difference at EOD."""
    pid = _make_product(session_factory, name="Mig2BypassProd")
    # No caja opened — gate would normally fire.
    r = authed_client.post(
        "/ventas/nueva/multi?bypass=true",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]


def test_bypass_uppercase_works(authed_client, session_factory):
    """?bypass=TRUE (uppercase) must also work — the gate lower-cases
    the param so the cashier doesn't need to remember exact casing
    under stress."""
    pid = _make_product(session_factory, name="Mig2BypassUpper")
    r = authed_client.post(
        "/ventas/nueva/multi?bypass=TRUE",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]


def test_bypass_writes_audit_row(authed_client, session_factory):
    """Bypassing the gate must leave an audit trail. The
    sale_cash_session_bypass action with target_type=sale is the
    marker a manager queries at EOD."""
    from app.rms.models_legacy import AuditLog

    pid = _make_product(session_factory, name="Mig2BypassAudit")
    r = authed_client.post(
        "/ventas/nueva/multi?bypass=true",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]

    s = _svc_session(session_factory)
    try:
        bypass_rows = s.query(AuditLog).filter(AuditLog.action == "sale_cash_session_bypass").all()
        assert len(bypass_rows) >= 1, "No sale_cash_session_bypass audit row was written"
        assert bypass_rows[-1].detail.get("reason") == "operator-bypass"
    finally:
        s.close()


def test_bypass_does_not_apply_to_non_cash(authed_client, session_factory):
    """Bypass is a no-op for non-cash sales — the gate never fires
    for QR/transferencia/fiado so there's nothing to bypass. This
    test pins that behavior so a future refactor doesn't accidentally
    introduce an unrelated effect."""
    pid = _make_product(session_factory, name="Mig2BypassQr")
    # QR sale with no caja + bypass param
    r = authed_client.post(
        "/ventas/nueva/multi?bypass=true",
        json={"items": [{"product_id": pid, "qty": 1}], "payment_method": "qr"},
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), r.text[:300]
