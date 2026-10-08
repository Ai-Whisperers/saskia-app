"""tests/test_held_sales_routes.py — integration tests for /ventas/hold*.

Tests the HTTP layer against an in-process FastAPI app with the sales
router mounted, using the project's cookie-based login bypass.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_sales_router(app_engine):
    """Build a minimal FastAPI app with the sales router mounted.

    Uses the project-wide ``app_engine`` fixture (from tests/conftest.py)
    so we don't fight the ``AIW_RMS_DB_PATH`` autouse fixture.

    Auth is bypassed via SASKIA_TEST_AUTH_DISABLED env (set in
    tests/conftest.py).
    """
    from app.routers.sales import router

    app = FastAPI()
    from app.rms.db import make_session_factory

    app.state.session_factory = make_session_factory(app_engine)
    from starlette.middleware.sessions import SessionMiddleware

    from app.auth import SESSION_SECRET

    app.add_middleware(
        SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="saskia_session"
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app_with_sales_router):
    return TestClient(app_with_sales_router, raise_server_exceptions=True)


def test_hold_empty_cart_returns_400(client):
    """POST /ventas/hold with no items must be rejected by the service."""
    r = client.post("/ventas/hold", json={"cart": {}, "label": ""})
    # Service raises ValueError → 400
    assert r.status_code == 400


def test_hold_creates_row_and_returns_id(client):
    cart = {"items": [{"product_id": 1, "qty": 2.0, "unit_price_gs": 5000}]}
    r = client.post("/ventas/hold", json={"cart": cart, "label": "Cliente Juan"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] >= 1
    assert data["label"] == "Cliente Juan"
    assert data["item_count"] == 1


def test_list_json_returns_active(client):
    client.post(
        "/ventas/hold", json={"cart": {"items": [{"product_id": 1, "qty": 1}]}, "label": "a"}
    )
    client.post(
        "/ventas/hold", json={"cart": {"items": [{"product_id": 2, "qty": 2}]}, "label": "b"}
    )
    r = client.get("/ventas/held/list.json")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    labels = sorted(it["label"] for it in data["held"])
    assert labels == ["a", "b"]


def test_resume_returns_cart_payload_and_excludes_from_list(client):
    cart = {"items": [{"product_id": 42, "qty": 3.0, "unit_price_gs": 1500}]}
    hold_r = client.post("/ventas/hold", json={"cart": cart, "label": "to resume"})
    held_id = hold_r.json()["id"]

    r = client.post(f"/ventas/held/{held_id}/resume")
    assert r.status_code == 200
    data = r.json()
    assert data["cart"]["items"][0]["product_id"] == 42
    assert data["cart"]["items"][0]["qty"] == 3.0

    # Now it should no longer be in the active list.
    list_r = client.get("/ventas/held/list.json")
    assert all(it["id"] != held_id for it in list_r.json()["held"])


def test_resume_missing_returns_404(client):
    r = client.post("/ventas/held/99999/resume")
    assert r.status_code == 404


def test_discard_marks_and_returns_ok(client):
    hold_r = client.post(
        "/ventas/hold", json={"cart": {"items": [{"product_id": 1, "qty": 1}]}, "label": "x"}
    )
    held_id = hold_r.json()["id"]
    r = client.post(f"/ventas/held/{held_id}/discard")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_discard_missing_returns_404(client):
    r = client.post("/ventas/held/99999/discard")
    assert r.status_code == 404


def test_label_truncated_to_120_chars(client):
    long_label = "x" * 200
    r = client.post(
        "/ventas/hold", json={"cart": {"items": [{"product_id": 1, "qty": 1}]}, "label": long_label}
    )
    assert r.status_code == 200
    assert len(r.json()["label"]) == 120


def test_unicode_label_and_item_survives_round_trip(client):
    """Unicode characters in label and cart survive JSON serialization."""
    label = "Cliente Juan — 漢字 + ñoño"
    cart = {"items": [{"product_id": 1, "qty": 1, "note": "Exquisito ☕"}]}
    hold_r = client.post("/ventas/hold", json={"cart": cart, "label": label})
    held_id = hold_r.json()["id"]
    resume_r = client.post(f"/ventas/held/{held_id}/resume")
    assert resume_r.status_code == 200
    data = resume_r.json()
    assert data["cart"]["items"][0]["note"] == "Exquisito ☕"


def test_blank_label_normalized(client):
    r = client.post(
        "/ventas/hold", json={"cart": {"items": [{"product_id": 1, "qty": 1}]}, "label": ""}
    )
    assert r.status_code == 200
    assert r.json()["label"] == "sin etiqueta"
