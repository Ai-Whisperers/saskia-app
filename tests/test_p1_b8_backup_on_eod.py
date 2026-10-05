"""P1-B8 — backup fires automatically when EOD checklist completes.

The roadmap (sazon-only-roadmap.md) requires:
> Backup local AES-256 + cron diario (no al startup)

We don't have a system cron in the container, so we hook the backup
trigger into the EOD checklist save endpoint. When ALL items in the
checklist are checked off for a day, run_backup is invoked.

This module verifies:
1. When all EOD items are checked, the EOD save succeeds (303)
2. When only SOME items are checked, the day is NOT marked closed
3. Backup failure (R2 unreachable) does NOT block the EOD save
4. When a backup runs (last_backup_at cleared), the audit row contains the trigger tag

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_p1_b8_backup_on_eod.py -v
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.rms.eod_closed import eod_is_day_closed
from app.rms.models import AppMeta, AuditLog
from app.rms.workflow import fresh_eod_checklist


def _today_local() -> str:
    from app.rms.config import ASUNCION_TZ

    return datetime.now(ASUNCION_TZ).date().isoformat()


def _check_all_today(client) -> None:
    """POST /eod/check with all checklist items checked off for today."""
    items = fresh_eod_checklist()
    data = {item.key: "on" for item in items}
    data["notes_for_next"] = "test"
    r = client.post("/eod/check", data=data, follow_redirects=False)
    assert r.status_code == 303, f"Expected 303, got {r.status_code}: {r.text[:200]}"


def _check_only_first_today(client) -> None:
    """POST /eod/check with only the first item checked off."""
    items = fresh_eod_checklist()
    data = {items[0].key: "on"}
    r = client.post("/eod/check", data=data, follow_redirects=False)
    assert r.status_code == 303


def test_eod_save_succeeds_when_all_items_checked(client) -> None:
    """All 9 EOD items checked off → EOD save succeeds (303)."""
    _check_all_today(client)


def test_day_not_closed_when_only_some_items_checked(client, session_factory) -> None:
    """Only some items checked → day NOT marked closed."""
    _check_only_first_today(client)
    from app.rms.config import ASUNCION_TZ

    today = datetime.now(ASUNCION_TZ).date()
    with session_factory() as s:
        assert eod_is_day_closed(s, today) is False


def test_eod_save_succeeds_when_backup_throws(client, session_factory, monkeypatch) -> None:
    """If backup raises (e.g., R2 unreachable), the EOD save still succeeds.

    We patch run_backup in the eod module to raise; the /eod/check endpoint
    must still return 303 and the checklist must still be persisted.
    """
    import app.routers.eod as eod_module

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated R2 outage")

    monkeypatch.setattr(eod_module, "run_backup", _raise, raising=False)

    items = fresh_eod_checklist()
    checkable_items = [item for item in items if item.key != "notes_for_tomorrow"]
    data = {item.key: "on" for item in items}
    data["notes_for_next"] = "with backup failure"
    r = client.post("/eod/check", data=data, follow_redirects=False)
    assert r.status_code == 303, (
        f"EOD save must succeed even when backup fails: {r.status_code} {r.text[:200]}"
    )

    # Verify the checklist WAS persisted (the operator can save their day)
    today = _today_local()
    with session_factory() as s:
        saved_keys = list(
            s.scalars(select(AppMeta).where(AppMeta.key.like(f"eod_check_{today}_%")))
        )
    assert len(saved_keys) == len(checkable_items), (
        f"All {len(checkable_items)} checkable items must be persisted, got {len(saved_keys)}"
    )


def test_backup_audit_row_contains_trigger_tag(client, session_factory) -> None:
    """When a backup runs (not skipped), the audit row detail contains 'eod_checklist_complete'."""
    # Force a backup by clearing last_backup_at metadata
    with session_factory() as s:
        row = s.scalar(select(AppMeta).where(AppMeta.key == "last_backup_at"))
        if row:
            s.delete(row)
        s.commit()

    _check_all_today(client)

    # The backup should have fired (we cleared last_backup_at). Look for the audit row.
    with session_factory() as s:
        rows = list(
            s.scalars(
                select(AuditLog)
                .where(AuditLog.action == "write.backup.triggered")
                .where(AuditLog.target_type == "backup")
            )
        )
    assert len(rows) >= 1, (
        "Expected at least one backup audit row after EOD close + cleared last_backup_at"
    )
    # Check that at least one row has the trigger tag
    found = any(
        r.detail
        and "eod_checklist_complete" in (r.detail if isinstance(r.detail, str) else str(r.detail))
        for r in rows
    )
    assert found, (
        f"Expected eod_checklist_complete trigger in at least one backup audit row, got details: {[r.detail for r in rows]}"
    )
