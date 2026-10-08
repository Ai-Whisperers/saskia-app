"""tests/test_demo_seed_endpoint.py — phase 2 /demo/seed endpoint tests.

Verify:
- Default state: endpoint disabled (returns 403).
- When AIW_DEMO_SEED_ENABLED=true, POST /demo/seed creates Kyrian
  with a coherent dataset.
- Re-running is idempotent (counts don't double).
- GET /demo/seed/status returns the right enabled flag.
"""

from __future__ import annotations


def test_demo_seed_status_when_disabled(client, monkeypatch):
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "")
    r = client.get("/demo/seed/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "endpoint": "POST /demo/seed"}


def test_demo_seed_status_when_enabled(client, monkeypatch):
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "true")
    r = client.get("/demo/seed/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": True, "endpoint": "POST /demo/seed"}


def test_demo_seed_rejected_when_disabled(client, monkeypatch):
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "")
    r = client.post("/demo/seed")
    # 403 because feature flag is off. The route is mounted (so 404
    # is wrong here); the route should return 403 with a useful detail.
    assert r.status_code == 403, r.text


def test_demo_seed_creates_kyrian(client, monkeypatch):
    """POST /demo/seed with the flag on creates a coherent Kyrian bundle."""
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "true")

    r = client.post("/demo/seed")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["customer_name"] == "kyrian weiss"
    assert body["pedidos_created"] == 6
    assert body["sales_created"] >= 5
    assert body["loyalty_ledger_rows"] >= 7
    assert body["addresses_created"] == 2
    assert body["subscription_created"] is True
    assert body["lifetime_spent_gs"] > 0
    assert body["duration_ms"] > 0


def test_demo_seed_is_idempotent(client, monkeypatch):
    """Calling /demo/seed twice should not duplicate rows."""
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "true")

    r1 = client.post("/demo/seed")
    assert r1.status_code == 200
    first = r1.json()

    r2 = client.post("/demo/seed")
    assert r2.status_code == 200
    second = r2.json()

    assert second["pedidos_created"] == first["pedidos_created"]
    assert second["sales_created"] == first["sales_created"]
    assert second["addresses_created"] == first["addresses_created"]
    assert second["customer_id"] == first["customer_id"]


def test_demo_seed_uses_real_flag_value(client, monkeypatch):
    """AIW_DEMO_SEED_ENABLED=yes (alternate truthy) is also accepted."""
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "yes")
    r = client.post("/demo/seed")
    assert r.status_code == 200, r.text


def test_demo_seed_500_does_not_leak_exception_repr(client, monkeypatch):
    """Regression: /demo/seed used to surface repr(exc) in the 500 detail,
    exposing filesystem paths and stack frames (OWASP ZAP rule 110009,
    "Full Path Disclosure"). Now the 500 detail is a generic message; the
    real exception is logged server-side.
    """
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "true")
    # Monkey-patch seed_kyrian to raise so the except branch fires
    from app.routers import demo as demo_module

    def boom(session):
        raise RuntimeError("/home/secret/path/app/routers/demo.py:42 boom")

    monkeypatch.setattr(demo_module, "seed_kyrian", boom)
    r = client.post("/demo/seed")
    assert r.status_code == 500, f"expected 500 from boom, got {r.status_code}"
    body = r.text
    assert "/home/secret" not in body, f"Path leaked to client! Body: {body[:500]}"
    assert "boom" not in body, f"Exception repr leaked! Body: {body[:500]}"
    # The generic message must be there
    assert "Demo seed failed. See server logs." in body or "Demo seed failed" in body, (
        f"Missing generic 500 message. Body: {body[:500]}"
    )


def test_demo_seed_403_does_not_leak_server_path(client, monkeypatch):
    """ZAP rule 110009: the disabled-flag 403 must not leak /opt/... paths."""
    monkeypatch.setenv("AIW_DEMO_SEED_ENABLED", "")
    r = client.post("/demo/seed")
    assert r.status_code == 403, r.text
    assert "/opt/" not in r.text, f"403 detail leaks server path: {r.text!r}"
