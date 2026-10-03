"""Tests for /healthz/depth — BACKLOG #40 (Tier 7).

The endpoint probes:
  - disk_free_bytes: free space in DATA_DIR
  - r2_reachable: HEAD on R2_BUCKET_URL (env-gated)
  - Supabase env-var presence (no network probe)

Each test runs in-process via FastAPI TestClient with a SessionLocal
backed by in-memory SQLite so the lifespan completes successfully and
`/healthz/depth` returns 200 (not 503 warming_up).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.rms.main import app


@pytest.fixture
def client():
    # TestClient as a context manager runs lifespan, which calls init_db.
    with TestClient(app) as c:
        yield c


def test_healthz_depth_ok_shape(client: TestClient) -> None:
    """Endpoint returns 200 with disk + r2 + supabase_env keys."""
    r = client.get("/healthz/depth")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "free_bytes" in body["disk"]
    assert "total_bytes" in body["disk"]
    assert body["disk"]["ok"] is True
    assert body["disk"]["free_bytes"] > 0
    assert "path" in body["disk"]
    # R2 not set in test env — should report ok=None
    assert body["r2"]["configured"] is False or "ok" in body["r2"]


def test_healthz_depth_includes_supabase_env(client: TestClient) -> None:
    """Supabase env vars reported as booleans (not values)."""
    body = client.get("/healthz/depth").json()
    assert "url_set" in body["supabase_env"]
    assert "publishable_set" in body["supabase_env"]
    assert "secret_set" in body["supabase_env"]
    # All booleans, never strings
    for v in body["supabase_env"].values():
        assert isinstance(v, bool)


def test_healthz_depth_disk_path_matches_config(client: TestClient) -> None:
    """Disk path matches DATA_DIR from app config."""
    from app.rms.config import DATA_DIR

    body = client.get("/healthz/depth").json()
    assert body["disk"]["path"] == str(DATA_DIR)


def test_healthz_depth_r2_unconfigured_ok_none(client: TestClient, monkeypatch) -> None:
    """When R2_BUCKET_URL is unset, ok=None (not False)."""
    monkeypatch.delenv("R2_BUCKET_URL", raising=False)
    body = client.get("/healthz/depth").json()
    assert body["r2"]["configured"] is False
    assert body["r2"]["ok"] is None


def test_healthz_depth_r2_unreachable_reports_error(client: TestClient, monkeypatch) -> None:
    """When R2 URL is set but the host is unreachable, the probe reports
    the failure without wedging the endpoint."""
    # 127.0.0.1:1 is reserved/unused; urllib will fail fast.
    monkeypatch.setenv("R2_BUCKET_URL", "http://127.0.0.1:1/x")
    body = client.get("/healthz/depth").json()
    assert body["r2"]["configured"] is True
    assert body["r2"]["ok"] is False
    # Endpoint still returns 200 — operators see the diagnostic.
    assert "error" in body["r2"]
    # Overall status flips to degraded.
    assert body["status"] == "degraded"


def test_healthz_depth_r2_reachable_ok(client: TestClient, monkeypatch) -> None:
    """When R2 URL is set and a local server returns 200, ok=True."""
    import http.server
    import socketserver
    import threading

    class _OK(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            self.send_response(200)
            self.end_headers()

        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args, **kwargs) -> None:
            pass

    # ThreadingTCPServer so serve_forever runs in its own thread without
    # blocking the test thread.
    class _Threaded(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = _Threaded(("127.0.0.1", 0), _OK)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        monkeypatch.setenv("R2_BUCKET_URL", f"http://127.0.0.1:{port}/")
        body = client.get("/healthz/depth").json()
    finally:
        srv.shutdown()
        srv.server_close()

    assert body["r2"]["configured"] is True
    assert body["r2"]["ok"] is True
    assert body["r2"]["status"] == 200
    assert body["status"] == "ok"
