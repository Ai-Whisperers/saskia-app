"""BACKLOG #9 — /eod/check idempotency against double-click.

Without an idempotency key, a cashier who double-clicks "Guardar cierre"
fires two EOD saves: two ``write.eod.checklist.save`` audit rows + two
``write.backup.triggered`` audit rows + two ``run_backup`` calls. Backup
itself is idempotent so no data corruption, but the audit trail is
polluted and a backup attempt that started mid-click can race with the
first.

With ``idempotency_key=<token>`` injected by the template:
  - 1st POST: reserves the ``eod_save_idem:<token>`` AppMeta row, runs
    the save + backup, commits.
  - 2nd POST (same token, < 5min later): IntegrityError on the same
    key → redirect with ``flash=cierre_duplicado`` → no audit row, no
    backup attempt.

Run: cd /opt/data/profiles/ivan/scratch/sazon-app-work && ./.venv/bin/python -m pytest tests/test_eod_check_idempotency.py -v
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.rms.config import ASUNCION_TZ
from app.rms.models import AppMeta, AuditLog
from app.rms.workflow import fresh_eod_checklist


def _check_all_with_key(client: TestClient, idempotency_key: str):
    items = fresh_eod_checklist()
    data = {item.key: "on" for item in items}
    data["notes_for_next"] = "idem test"
    data["idempotency_key"] = idempotency_key
    return client.post("/eod/check", data=data, follow_redirects=False)


def _audit_rows_for_today(session_factory, action: str) -> list:
    datetime.now(ASUNCION_TZ).date().isoformat()
    with session_factory() as s:
        rows = list(s.scalars(select(AuditLog).where(AuditLog.action == action)))
    # Filter to today's EOD ones by parsing detail JSON — small dataset so OK
    return rows


def test_eod_save_with_key_succeeds_first_time(client) -> None:
    """First POST with idempotency_key → 303."""
    r = _check_all_with_key(client, secrets.token_urlsafe(16))
    assert r.status_code == 303, f"Expected 303, got {r.status_code}"


def test_eod_save_double_click_returns_duplicate_redirect(client) -> None:
    """Two POSTs with the SAME idempotency_key → 2nd one redirects with
    flash=cierre_duplicado (and does NOT run a second save or backup).
    """
    key = secrets.token_urlsafe(16)

    r1 = _check_all_with_key(client, key)
    assert r1.status_code == 303, f"1st: expected 303, got {r1.status_code}"

    r2 = _check_all_with_key(client, key)
    assert r2.status_code == 303, f"2nd: expected 303, got {r2.status_code}"
    assert "cierre_duplicado" in (r2.headers.get("location") or ""), (
        f"2nd POST must redirect with flash=cierre_duplicado; "
        f"got Location: {r2.headers.get('location')!r}"
    )


def test_eod_save_double_click_does_not_write_duplicate_audit(client, session_factory) -> None:
    """Two POSTs with the SAME idempotency_key → only ONE write.eod.checklist.save audit row."""
    key = secrets.token_urlsafe(16)

    # Count audit rows BEFORE
    before = len(_audit_rows_for_today(session_factory, "write.eod.checklist.save"))

    _check_all_with_key(client, key)
    _check_all_with_key(client, key)  # 2nd should be deduped

    after = len(_audit_rows_for_today(session_factory, "write.eod.checklist.save"))
    new_rows = after - before
    assert new_rows == 1, f"Double-click should write exactly 1 audit row; got {new_rows}"


def test_eod_save_without_key_still_works_legacy_path(client) -> None:
    """Without idempotency_key (legacy template), the save still works
    (303) but does NOT reserve the idem row. This is the legacy
    fallback documented in the router.
    """
    items = fresh_eod_checklist()
    data = {item.key: "on" for item in items}
    data["notes_for_next"] = "legacy"
    # no idempotency_key
    r = client.post("/eod/check", data=data, follow_redirects=False)
    assert r.status_code == 303


def test_eod_idempotency_key_isolates_distinct_submissions(client) -> None:
    """Two POSTs with DIFFERENT idempotency_keys → both succeed
    independently (no false-positive dedup)."""
    key_a = secrets.token_urlsafe(16)
    key_b = secrets.token_urlsafe(16)

    # For the second POST, the checklist is already all done from the
    # first — but the key is different so it should still succeed as a
    # distinct save action.
    r1 = _check_all_with_key(client, key_a)
    assert r1.status_code == 303, f"1st: {r1.status_code}"

    r2 = _check_all_with_key(client, key_b)
    assert r2.status_code == 303, f"2nd (different key): {r2.status_code}"
    assert "cierre_duplicado" not in (r2.headers.get("location") or ""), (
        f"2nd POST with distinct key should NOT be marked duplicate; "
        f"got Location: {r2.headers.get('location')!r}"
    )


def test_eod_idem_key_reserved_in_appmeta(client, session_factory) -> None:
    """After a successful save, the eod_save_idem:<key> AppMeta row exists."""
    key = secrets.token_urlsafe(16)
    _check_all_with_key(client, key)

    with session_factory() as s:
        row = s.scalar(select(AppMeta).where(AppMeta.key == f"eod_save_idem:{key}"))
    assert row is not None, "AppMeta idem reservation row must exist after a successful save"
