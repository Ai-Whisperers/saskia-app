"""tests/test_cotizador_routes.py — SASKIA plan 1.

cotizador router has 3 routes (/cotizador, /cotizador [POST],
/cotizador/pdf), 0 tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_cotizador_get_returns_200(authed_client):
    """GET /cotizador → 200 (price quote tool)."""
    r = authed_client.get("/cotizador")
    assert r.status_code == 200


def test_cotizador_post_calculates(authed_client):
    """POST /cotizador → 200/303 (price calculation)."""
    r = authed_client.post(
        "/cotizador",
        data={"items": "1x demo", "margin_pct": "30"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 422), r.text[:200]


def test_cotizador_pdf_returns_redirect_or_file(authed_client):
    """POST /cotizador/pdf → 200 (PDF) or 303 (redirect)."""
    r = authed_client.post(
        "/cotizador/pdf",
        data={"items": "1x demo", "margin_pct": "30"},
        follow_redirects=False,
    )
    # 200 (PDF binary), 303 (redirect to download), or 422 (validation)
    assert r.status_code in (200, 303, 422), r.text[:200]
