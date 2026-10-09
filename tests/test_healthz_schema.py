"""tests/test_healthz_schema.py — /healthz/schema endpoint."""

from app.rms.db import CURRENT_SCHEMA_VERSION


def test_healthz_schema_returns_versions(client):
    """Returns code_version + db_version + drift fields."""
    resp = client.get("/healthz/schema")
    assert resp.status_code == 200
    body = resp.json()
    for k in ("code_version", "db_version", "drift"):
        assert k in body


def test_healthz_schema_in_sync_returns_drift_zero(client):
    """When DB matches code, drift must be 0."""
    resp = client.get("/healthz/schema")
    assert resp.status_code == 200
    assert resp.json()["drift"] == 0
    assert resp.json()["code_version"] == resp.json()["db_version"]


def test_healthz_schema_out_of_sync_returns_500(client, session_factory):
    """When DB is behind, /healthz/schema returns 500 with hint."""
    from app.rms.db import app_meta_write

    with session_factory() as s:
        app_meta_write(s.connection(), "schema_version", str(CURRENT_SCHEMA_VERSION - 1))
        s.commit()
    resp = client.get("/healthz/schema")
    assert resp.status_code == 500
    body = resp.json()
    assert body["drift"] > 0
    assert "migrate" in body["hint"].lower() or "deploy" in body["hint"].lower()
