"""tests/test_demo_seed_endpoint.py — phase 2 /demo/seed endpoint tests.

Verify:
- Default state: endpoint disabled (returns 403).
- When AIW_DEMO_SEED_ENABLED=true, POST /demo/seed creates Kyrian
  with a coherent dataset.
- Re-running is idempotent (counts don't double).
- GET /demo/seed/status returns the right enabled flag.
"""

from __future__ import annotations

import pytest


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
