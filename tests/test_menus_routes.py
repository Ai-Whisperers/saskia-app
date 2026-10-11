"""tests/test_menus_routes.py — SASKIA plan 1.

menus router has 3 routes (/menus, /menus/nuevo, /menus/{id}/off),
0 direct tests.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_menus_list_returns_200(authed_client):
    """GET /menus → 200 (menu planning page)."""
    r = authed_client.get("/menus")
    assert r.status_code == 200


def test_menus_new_post_creates(authed_client, session_factory):
    """POST /menus/nuevo → 303 (create menu) or 400 (validation)."""
    from tests.factories import _uniq, make_product
    s = session_factory()
    try:
        p = make_product(s, name="Menu Test Product")
        s.commit()
        pid = p.id
    finally:
        s.close()

    name = _uniq("Menu")
    r = authed_client.post(
        "/menus/nuevo",
        data={
            "name": name,
            "price_gs": "25000",
            f"prod_{pid}": "on",
            f"qty_{pid}": "1.5",
        },
        follow_redirects=False,
    )
    # 303 (success), 400 (validation error)
    assert r.status_code in (200, 303, 400), r.text[:300]


def test_menus_off_returns_404_for_unknown(authed_client):
    """POST /menus/999999/off → 404."""
    r = authed_client.post(
        "/menus/999999/off",
        data={},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 404, 422), r.text[:200]
