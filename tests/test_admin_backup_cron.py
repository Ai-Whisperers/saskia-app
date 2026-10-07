"""tests/test_admin_backup_cron.py — B.8: scheduled backup via cron endpoint.

The lifespan hook in app/rms/main.py runs `run_backup()` on app
startup, which works for short deploys but means a 30-day-uptime
container only backs up once (on day 1). BACKLOG #39 calls this out:
"Render backup runs on app-startup, not on cron".

Fix: a new `POST /admin/backup/cron` endpoint that authenticates with
a shared secret (env var SASKIA_CRON_BACKUP_TOKEN) and runs
`_run_backup_admin()` synchronously. The endpoint is meant to be hit
by a host-level cron job (`0 3 * * *  curl -X POST -H
"X-Cron-Token: $SASKIA_CRON_BACKUP_TOKEN" https://.../admin/backup/cron`).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.backup_scheduler import BackupResult


def _fake_result() -> BackupResult:
    return BackupResult(
        local_path=Path("/tmp/backups/rms-backup-20261007-030000.xlsx"),
        local_pruned=0,
        r2_uploaded=False,
        r2_key=None,
        skipped=False,
        reason="Backup completed",
    )


def test_cron_backup_rejects_missing_token(client, monkeypatch):
    """Without the X-Cron-Token header, the endpoint must 401.

    Otherwise anyone with network access to the admin port could
    trigger expensive backups (and R2 uploads) at will. We set the
    env var first so this test exercises the "header missing" path
    (not the "env not configured" path, which is 503 in test_503_*).
    """
    monkeypatch.setenv("SASKIA_CRON_BACKUP_TOKEN", "test-cron-secret-12345")
    resp = client.post("/admin/backup/cron")
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"] == "missing_cron_token"


def test_cron_backup_rejects_wrong_token(client, monkeypatch):
    """A wrong X-Cron-Token must 401 with a generic 'invalid' error
    (don't leak whether the token was 'almost right' or 'completely
    wrong' to the response — that's a token-guessing oracle)."""
    monkeypatch.setenv("SASKIA_CRON_BACKUP_TOKEN", "test-cron-secret-12345")
    resp = client.post(
        "/admin/backup/cron",
        headers={"X-Cron-Token": "definitely-not-the-real-token"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "invalid_cron_token"


def test_cron_backup_503_when_token_unconfigured(client, monkeypatch):
    """If the operator forgot to set SASKIA_CRON_BACKUP_TOKEN in
    env, the endpoint must fail closed (503) so a misconfigured
    deploy doesn't silently accept empty tokens."""
    monkeypatch.delenv("SASKIA_CRON_BACKUP_TOKEN", raising=False)
    resp = client.post(
        "/admin/backup/cron",
        headers={"X-Cron-Token": "anything"},
    )
    assert resp.status_code == 503
    body = resp.json()
    assert "error" in body
    # The hint should name the env var so an operator running into this
    # 503 in logs can search for the var name and find the docs.
    assert "SASKIA_CRON_BACKUP_TOKEN" in body.get("hint", "")


def test_cron_backup_runs_with_correct_token(client, monkeypatch):
    """Happy path: right token + real run_backup → 200 with result."""
    monkeypatch.setenv("SASKIA_CRON_BACKUP_TOKEN", "test-cron-secret-12345")
    from app.routers import health as health_module

    with patch.object(
        health_module,
        "_run_backup_admin",
        return_value=_fake_result(),
    ) as mock_run:
        resp = client.post(
            "/admin/backup/cron",
            headers={"X-Cron-Token": "test-cron-secret-12345"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "backup_complete"
    assert body["skipped"] is False
    assert body["local_path"] == str(_fake_result().local_path)
    assert mock_run.called


def test_cron_backup_returns_500_on_run_backup_failure(client, monkeypatch):
    """If _run_backup_admin raises (R2 down, disk full), the cron
    endpoint must return 500 so the cron wrapper script can detect
    the failure and exit non-zero. Silent 200s here would mean a
    failed backup looks like a successful one in /var/log/sazon-cron.log."""
    monkeypatch.setenv("SASKIA_CRON_BACKUP_TOKEN", "test-cron-secret-12345")
    from app.routers import health as health_module

    with patch.object(
        health_module,
        "_run_backup_admin",
        side_effect=RuntimeError("R2 outage: bucket unreachable"),
    ):
        resp = client.post(
            "/admin/backup/cron",
            headers={"X-Cron-Token": "test-cron-secret-12345"},
        )
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "backup_failed"
    assert "R2 outage" in body["detail"]


def test_cron_backup_skipped_response_includes_skip_reason(client, monkeypatch):
    """When run_backup returns skipped=True (last backup was recent),
    the response should still be 200 — skipping is a successful no-op,
    not a failure. The cron wrapper should not retry on a skipped
    response."""
    monkeypatch.setenv("SASKIA_CRON_BACKUP_TOKEN", "test-cron-secret-12345")
    from app.routers import health as health_module

    skipped = BackupResult(
        local_path=None,
        local_pruned=0,
        r2_uploaded=False,
        r2_key=None,
        skipped=True,
        reason="Last backup at 2026-10-07T02:55:00 is within 24h threshold",
    )
    with patch.object(
        health_module,
        "_run_backup_admin",
        return_value=skipped,
    ):
        resp = client.post(
            "/admin/backup/cron",
            headers={"X-Cron-Token": "test-cron-secret-12345"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] is True
    assert "threshold" in body["reason"]
