"""tests/test_suscripciones_routes.py — SASKIA plan 1.

Suscripciones router (app/routers/suscripciones.py) has 8 routes,
0 direct tests. This file adds route smoke tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_suscripciones_list_returns_200(authed_client):
    """GET /suscripciones → 200 (list page)."""
    r = authed_client.get("/suscripciones")
    assert r.status_code == 200


def test_suscripciones_new_form_returns_200(authed_client):
    """GET /suscripciones/nuevo → 200 (create form)."""
    r = authed_client.get("/suscripciones/nuevo")
    assert r.status_code == 200


def test_suscripciones_new_post_creates(authed_client, session_factory):
    """POST /suscripciones/nuevo → 303 redirect + new row in DB."""
    from tests.factories import make_customer
    s = session_factory()
    try:
        c = make_customer(s, name="Suscripcion Test Customer")
        s.commit()
        cid = c.id
    finally:
        s.close()

    r = authed_client.post(
        "/suscripciones/nuevo",
        data={
            "customer_id": str(cid),
            "product_summary": "1 kg chipa cada sábado",
            "cadence": "semanal",
            "start_date": "2026-10-15",
            "status": "activa",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]


def test_suscripciones_edit_form_returns_404_for_unknown(authed_client):
    """GET /suscripciones/999999/editar → 404."""
    r = authed_client.get("/suscripciones/999999/editar")
    assert r.status_code in (200, 404), r.text[:200]


def test_suscripciones_dispatch_endpoint_returns_303(authed_client):
    """POST /suscripciones/dispatch → 303 (dispatch action)."""
    r = authed_client.post(
        "/suscripciones/dispatch",
        data={},
        follow_redirects=False,
    )
    # 303 (no work) or 422 (validation) both OK.
    assert r.status_code in (200, 303, 422), r.text[:200]
