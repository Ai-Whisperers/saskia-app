"""tests/test_healthz.py — /healthz and /healthz/db endpoints.

Per dev plan Batch 3. Targets ~6 tests.

Covers:
- /healthz returns 200, status=ok
- /healthz/db returns 200, db=ok, journal_mode=wal
- /healthz/db handles unreachable DB → 503 (mocked)
- Both endpoints are JSON
- /healthz body shape
- /healthz/db body shape (journal_mode field)
"""

from __future__ import annotations


def test_healthz_returns_200(client):
    r = client.get("/healthz")
    assert r.status_code == 200


def test_healthz_body(client):
    r = client.get("/healthz")
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "aiw-saskia-rms"


def test_healthz_content_type_json(client):
    r = client.get("/healthz")
    assert r.headers["content-type"].startswith("application/json")


def test_healthz_db_returns_200(client):
    r = client.get("/healthz/db")
    assert r.status_code == 200


def test_healthz_db_reports_wal(client):
    r = client.get("/healthz/db")
    body = r.json()
    assert body["db"] == "ok"
    assert body["journal_mode"] == "wal"


def test_healthz_db_unreachable_returns_503(client, monkeypatch):
    """Mock engine.connect to raise → endpoint returns 503."""

    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("simulated DB outage")

    monkeypatch.setattr("app.rms.main.app.state.__class__", type("S", (), {}))  # no-op safety
    # Patch the request.app.state.engine on the test's app instance
    from app.rms import main as main_module

    original = getattr(main_module.app.state, "engine", None)
    main_module.app.state.engine = _BrokenEngine()
    try:
        r = client.get("/healthz/db")
        assert r.status_code == 503
        body = r.json()
        assert body["db"] == "error"
        assert "simulated DB outage" in body["detail"]
    finally:
        if original is not None:
            main_module.app.state.engine = original
