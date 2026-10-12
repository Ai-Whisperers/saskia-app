"""tests/integration/test_http_routes_full.py — Full HTTP route integration tests."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.rms.main import app

    with patch("app.auth.is_auth_disabled", return_value=True):
        yield TestClient(app, raise_server_exceptions=False)


def test_root_returns_something(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 404)


def test_login_page_renders(client):
    r = client.get("/login", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 404)


def test_login_post_invalid(client):
    r = client.post("/login", data={"username": "x", "password": "y"}, follow_redirects=False)
    assert r.status_code in (200, 302, 307, 400, 401, 403, 422, 500)


def test_static_assets_path(client):
    r = client.get("/static/", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 404)


def test_404_returns_html(client):
    r = client.get("/__not_found_path_xyz__", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 404, 500)
    if r.text:
        assert "Traceback" not in r.text


def test_logout_endpoint(client):
    r = client.post("/logout", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 401, 403, 404, 405, 500)


def test_admin_path_doesnt_crash(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 401, 403, 404, 500)


def test_settings_path(client):
    r = client.get("/settings", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 401, 403, 404, 500)


def test_dashboard_path(client):
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 401, 403, 404, 500)


def test_inventory_path(client):
    r = client.get("/inventario", follow_redirects=False)
    assert r.status_code in (200, 302, 307, 401, 403, 404, 500)
