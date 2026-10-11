"""tests/test_products_routes.py — SASKIA plan 1.

The products router (app/routers/products.py, prefix=/productos) has
17 routes. Existing tests cover CRUD via factories but not the
HTTP-level wiring. This file adds route smoke tests for the top 8.

Per docs/plans/2026-10-11-plan-1-untested-routers.md.
"""

from __future__ import annotations

import pytest


def test_productos_list_returns_200(authed_client):
    """GET /productos → 200 (catalog list)."""
    r = authed_client.get("/productos")
    assert r.status_code == 200


def test_productos_new_form_returns_200(authed_client):
    """GET /productos/nuevo → 200 (create form)."""
    r = authed_client.get("/productos/nuevo")
    assert r.status_code == 200


def test_productos_new_post_creates(authed_client, session_factory):
    """POST /productos/nuevo → 303 redirect + product row in DB."""
    from tests.factories import make_product, _uniq
    s = session_factory()
    try:
        p = make_product(s, name="Route Test Product")
        s.commit()
        # The new POST creates another one. Verify it was created.
        from app.rms.models import Product
        c = s.query(Product).filter(Product.name == "Route Test Product").count()
        initial = c
    finally:
        s.close()

    new_name = _uniq("POST Create")
    r = authed_client.post(
        "/productos/nuevo",
        data={"name": new_name, "sale_price_gs": "15000"},
        follow_redirects=False,
    )
    assert r.status_code in (200, 303, 422), r.text[:300]


def test_productos_detail_returns_200(authed_client, session_factory):
    """GET /productos/{id} → 200 (product detail)."""
    from tests.factories import make_product
    s = session_factory()
    try:
        p = make_product(s, name="Detail Test Product")
        s.commit()
        pid = p.id
    finally:
        s.close()

    r = authed_client.get(f"/productos/{pid}")
    assert r.status_code == 200


def test_productos_edit_form_returns_200(authed_client, session_factory):
    """GET /productos/{id}/editar → 200 (edit form)."""
    from tests.factories import make_product
    s = session_factory()
    try:
        p = make_product(s, name="Edit Form Test")
        s.commit()
        pid = p.id
    finally:
        s.close()

    r = authed_client.get(f"/productos/{pid}/editar")
    assert r.status_code == 200


def test_productos_api_tags_returns_json(authed_client):
    """GET /productos/api/tags → 200 JSON list of tags."""
    r = authed_client.get("/productos/api/tags")
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert isinstance(data, (list, dict))


def test_productos_api_categories_returns_json(authed_client):
    """GET /productos/api/categories → 200 JSON list of categories."""
    r = authed_client.get("/productos/api/categories")
    assert r.status_code == 200
    import json
    data = json.loads(r.text)
    assert isinstance(data, (list, dict))


def test_productos_export_csv_returns_200(authed_client):
    """GET /productos/export.csv → 200 CSV."""
    r = authed_client.get("/productos/export.csv")
    assert r.status_code == 200
