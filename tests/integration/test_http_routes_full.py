"""tests/integration/test_http_routes_full.py — Full HTTP route integration tests.

Uses authed_client from conftest.py (auth disabled). For tests that need
auth enabled, use the `client` fixture from conftest instead.
"""
import pytest

from tests._lib.auth import assert_safe_response
from tests._lib.http import (
    SAFE_CODES,
    LOGIN_POST_CODES,
    LOGIN_CODES,
    AUTH_METHOD_CODES,
)


pytestmark = [pytest.mark.integration, pytest.mark.smoke]


def test_root_returns_something(authed_client):
    r = authed_client.get("/", follow_redirects=False)
    assert r.status_code in SAFE_CODES


def test_login_page_renders(authed_client):
    r = authed_client.get("/login", follow_redirects=False)
    assert r.status_code in SAFE_CODES


def test_login_post_invalid(authed_client):
    r = authed_client.post("/login", data={"username": "x", "password": "y"}, follow_redirects=False)
    assert r.status_code in LOGIN_POST_CODES


def test_static_assets_path(authed_client):
    r = authed_client.get("/static/", follow_redirects=False)
    assert r.status_code in SAFE_CODES


def test_404_returns_html(authed_client):
    r = authed_client.get("/__not_found_path_xyz__", follow_redirects=False)
    assert r.status_code in SAFE_CODES
    assert_safe_response(r)


def test_logout_endpoint(authed_client):
    r = authed_client.post("/logout", follow_redirects=False)
    assert r.status_code in LOGIN_CODES


def test_admin_path_doesnt_crash(authed_client):
    r = authed_client.get("/admin", follow_redirects=False)
    assert r.status_code in AUTH_METHOD_CODES


def test_settings_path(authed_client):
    r = authed_client.get("/settings", follow_redirects=False)
    assert r.status_code in AUTH_METHOD_CODES


def test_dashboard_path(authed_client):
    r = authed_client.get("/dashboard", follow_redirects=False)
    assert r.status_code in AUTH_METHOD_CODES


def test_inventory_path(authed_client):
    r = authed_client.get("/inventario", follow_redirects=False)
    assert r.status_code in AUTH_METHOD_CODES
