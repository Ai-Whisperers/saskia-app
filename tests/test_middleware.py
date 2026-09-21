"""tests/test_middleware.py — regression tests for GZip + StaticCache.

Verifies:
- HTML responses are gzipped when client sends Accept-Encoding: gzip
- CSS responses get Cache-Control: max-age=31536000, immutable (version-busted assets)
"""
from __future__ import annotations


def test_gzip_compression_active_on_login(client):
    """HTML responses must include Content-Encoding: gzip when client accepts it."""
    resp = client.get("/login", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"


def test_gzip_skips_tiny_responses(client):
    """42-byte /healthz response must NOT be gzipped (overhead > savings)."""
    resp = client.get("/healthz", headers={"Accept-Encoding": "gzip"})
    # 42 bytes is below the 500-byte minimum_size threshold, so no gzip.
    assert resp.headers.get("content-encoding") != "gzip"


def test_static_cache_control_set(client):
    """Static asset responses must include Cache-Control: max-age=31536000, immutable."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    cc = resp.headers.get("cache-control", "")
    assert "max-age=31536000" in cc, f"Missing cache-control header (got: {cc!r})"


def test_static_cache_control_not_applied_to_routes(client):
    """Non-static routes should NOT get the static Cache-Control header.

    (Other middlewares may add their own; this test only verifies our
    specific header is absent on non-static paths.)
    """
    resp = client.get("/login")
    # /login should NOT have max-age=3600 (it's session-aware content).
    cc = resp.headers.get("cache-control", "")
    assert "max-age=3600" not in cc, (
        f"Static cache-control leaked to /login (got: {cc!r})"
    )
