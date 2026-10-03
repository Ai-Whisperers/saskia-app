"""tests/test_healthz_db_documented.py — E4.S4 runbook + endpoint contract.

The /healthz/db endpoint ships with an operator runbook. These tests
guard the runbook + endpoint contract together:

1. The endpoint returns 200 in a healthy test DB.
2. The runbook exists at docs/operations/healthz-db-runbook.md.
3. The runbook mentions the actual JSON fields the endpoint returns.
4. The runbook mentions UptimeRobot with a 5-minute interval.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = REPO_ROOT / "docs" / "operations" / "healthz-db-runbook.md"


def test_healthz_db_returns_200_in_healthy_state(authed_client):
    r = authed_client.get("/healthz/db")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["db"] == "ok"


def test_healthz_db_documents_schema_version_field(authed_client):
    """The runbook must list `schema_version` because operators grep it."""
    r = authed_client.get("/healthz/db")
    assert r.status_code == 200
    body = r.json()
    # Document the keys actually returned
    documented_keys = ["db", "schema_version", "migrations_pending"]
    for k in documented_keys:
        assert k in body, f"healthz/db missing expected key: {k}"
    # Runbook must reference each key
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    for k in documented_keys:
        assert k in text, f"runbook missing key reference: {k}"


def test_healthz_db_documents_uptime_robot_5min():
    """Runbook should recommend 5-min UptimeRobot interval (matches prod config)."""
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "UptimeRobot" in text
    assert "5 minute" in text


def test_healthz_db_runbook_exists_and_nonempty():
    assert RUNBOOK_PATH.exists(), "runbook missing at expected path"
    text = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert len(text) > 500, "runbook is suspiciously short"


def test_healthz_db_documents_journal_mode_field(authed_client):
    """When running SQLite, journal_mode is in the payload."""
    r = authed_client.get("/healthz/db")
    assert r.status_code == 200
    body = r.json()
    if "journal_mode" in body:
        # Then the runbook must mention it
        text = RUNBOOK_PATH.read_text(encoding="utf-8")
        assert "journal_mode" in text
