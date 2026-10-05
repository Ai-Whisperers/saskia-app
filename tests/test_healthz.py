"""Test the dialect-aware /healthz/db fix (live-site bug)."""

import json

from app.routers.health import _healthz_payload


def test_healthz_payload_shape():
    payload = _healthz_payload()
    assert payload["status"] == "ok"
    assert payload["service"] == "sazon-rms"


def test_healthz_payload_serializeable():
    """Payload must be JSON-serializable for FastAPI."""
    payload = _healthz_payload()
    s = json.dumps(payload)
    assert "ok" in s


def test_healthz_db_returns_schema_version_and_drift(client):
    """E3.S4: /healthz/db reports schema_version + migrations_pending + last_audit_at.

    Locks the contract documented in
    docs/operations/uptime-monitoring.md — UptimeRobot and operator dashboards
    depend on these fields to detect DB drift and write silence.
    """
    resp = client.get("/healthz/db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db"] == "ok"
    assert "schema_version" in body
    assert "code_schema_version" in body
    assert "migrations_pending" in body
    assert "last_audit_at" in body
    # Schema should be in sync (init_db() runs at lifespan startup).
    assert body["schema_version"] == body["code_schema_version"]
    assert body["migrations_pending"] == 0
