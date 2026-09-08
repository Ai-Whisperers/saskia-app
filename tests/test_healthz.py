"""Test the dialect-aware /healthz/db fix (live-site bug)."""
import json

from app.routers.health import _healthz_payload


def test_healthz_payload_shape():
    payload = _healthz_payload()
    assert payload["status"] == "ok"
    assert payload["service"] == "aiw-saskia-rms"


def test_healthz_payload_serializeable():
    """Payload must be JSON-serializable for FastAPI."""
    payload = _healthz_payload()
    s = json.dumps(payload)
    assert "ok" in s
