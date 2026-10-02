"""Tests for BACKLOG #39: /healthz/backup status + /admin/backup trigger.

The original behavior: `run_backup` is called only on app startup
(lifespan). If the app stays up for weeks, no backup ever runs. This
is BACKLOG #39's "Render backup runs on app-startup, not on cron"
complaint.

Fix: expose the backup state via /healthz/backup (visible to
UptimeRobot) and add /admin/backup as an operator escape hatch
(matches the /admin/migrate pattern). The lifespan call remains as a
first-line guarantee on deploy.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from app.rms.config import ASUNCION_TZ


def test_healthz_backup_reports_last_backup_at(client):
    """E4.S2 (BACKLOG #39): /healthz/backup shows when last backup ran.

    Locks the contract so UptimeRobot / dashboards can surface a stale
    backup warning before operators notice.
    """
    resp = client.get("/healthz/backup")
    assert resp.status_code == 200
    body = resp.json()
    assert "last_backup_at" in body
    # Either we have a backup (ISO string) or no backup yet (None).
    if body["last_backup_at"] is not None:
        # ISO format parseable
        datetime.fromisoformat(body["last_backup_at"])
    assert "age_hours" in body
    assert "stale" in body
    assert body["stale"] in (True, False)
    assert "threshold_hours" in body
    # Default 24h threshold.
    assert body["threshold_hours"] == 24


def test_healthz_backup_returns_503_when_stale(client, monkeypatch):
    """If last backup is older than threshold, status = stale + 503.

    UptimeRobot treats 503 as "down" — operators get paged on stale
    backups the same way they would for any outage.
    """
    # Force stale: pretend the last backup was 30 hours ago
    stale_time = (datetime.now() - timedelta(hours=30)).isoformat()
    with patch("app.routers.health._get_last_backup_at", return_value=stale_time):
        resp = client.get("/healthz/backup")
    assert resp.status_code == 503
    body = resp.json()
    assert body["stale"] is True
    assert body["age_hours"] >= 30


def test_healthz_backup_no_backup_yet_returns_stale(client):
    """If we've never run a backup, the endpoint reports stale=True."""
    with patch("app.routers.health._get_last_backup_at", return_value=None):
        resp = client.get("/healthz/backup")
    assert resp.status_code == 503
    body = resp.json()
    assert body["stale"] is True
    assert body["last_backup_at"] is None


def test_admin_backup_requires_auth(client, monkeypatch):
    """/admin/backup must reject unauthenticated requests.

    The SASKIA_TEST_AUTH_DISABLED env var normally bypasses auth for
    tests; we clear it here so the production auth path runs.
    """
    monkeypatch.delenv("SASKIA_TEST_AUTH_DISABLED", raising=False)
    resp = client.post("/admin/backup")
    # The auth gate returns 401 for unauthenticated requests.
    assert resp.status_code == 401


def test_admin_backup_triggers_run_backup(client):
    """Authenticated POST /admin/backup calls run_backup synchronously.

    Mock run_backup so we don't depend on R2 / DB state.
    """
    from app.routers import health as health_module
    from app.services.backup_scheduler import BackupResult

    fake = BackupResult(
        local_path=Path("/tmp/backups/rms-backup-20261002-024000.xlsx"),
        local_pruned=0,
        r2_uploaded=False,
        r2_key=None,
        skipped=False,
        reason="Backup completed",
    )
    with patch.object(
        health_module,
        "_run_backup_admin",
        return_value=fake,
    ):
        resp = client.post("/admin/backup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "backup_complete"
    assert body["local_path"] == str(fake.local_path)


def test_admin_backup_handles_run_backup_failure(client):
    """If run_backup raises, /admin/backup returns 500 with detail.

    Operators see the failure cause (R2 outage, DB lock, etc.) instead
    of a silent hang.
    """
    from app.routers import health as health_module

    with patch.object(
        health_module,
        "_run_backup_admin",
        side_effect=RuntimeError("R2 bucket missing"),
    ):
        resp = client.post("/admin/backup")
    assert resp.status_code == 500
    body = resp.json()
    assert "R2 bucket missing" in body.get("detail", "")


def test_healthz_backup_helper_reads_app_meta(client):
    """_get_last_backup_at helper reads the app_meta DB row.

    Verifies the integration between /healthz/backup and the actual
    app_meta.last_backup_at key written by run_backup.
    """
    from app.rms.models import AppMeta

    # Backup state may already exist from the lifespan backup — update
    # rather than insert so we don't violate the UNIQUE constraint.
    fresh = (datetime.now(ASUNCION_TZ) - timedelta(hours=1)).isoformat()
    with client.app.state.session_factory() as s:
        existing = s.query(AppMeta).filter_by(key="last_backup_at").first()
        if existing is None:
            s.add(
                AppMeta(
                    key="last_backup_at",
                    value=fresh,
                    updated_at=datetime.now(ASUNCION_TZ).isoformat(),
                )
            )
        else:
            existing.value = fresh
            existing.updated_at = datetime.now(ASUNCION_TZ).isoformat()
        s.commit()

    resp = client.get("/healthz/backup")
    body = resp.json()
    assert body["last_backup_at"] is not None
    assert body["age_hours"] < 2  # ~1h ago
    assert body["stale"] is False