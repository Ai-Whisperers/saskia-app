"""Tests for /healthz/summary — operator one-pager.

BACKLOG (operator UX): the operator has to open /healthz, /healthz/db,
/healthz/errors, /healthz/backup, /healthz/deps, /healthz/schema to
diagnose a failure. This page aggregates all of them into one screen
with status pills + drill-down links.

Covers:
- Page returns 200 in all states (warming-up, all-ok, mixed)
- Each check's status pill matches its helper's ok flag
- Drill-down links are present per check
- All-red edge: page still renders, no exception
- Top banner switches between alert--success / warn / danger
- _summary_payload() aggregator: ready=False short-circuits to all_ok=False
- Each sub-check helper is patchable (mock_in_path to set fake values)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from app.rms.config import ASUNCION_TZ

# --- top-level endpoint ---


def test_healthz_summary_renders(client):
    """Page renders with 200 in default state."""
    resp = client.get("/healthz/summary")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    # Each card section is in the body (Spanish headings, not changed).
    for heading in [
        "Base de datos",
        "Errores 500",
        "Backup",
        "Dependencias externas",
        "Disco",
        "Atajos del operador",
    ]:
        assert heading in body, f"missing section: {heading}"


def test_healthz_summary_links_to_drill_downs(client):
    """Every card has a /healthz/<sub> drill-down link."""
    resp = client.get("/healthz/summary")
    body = resp.text
    for href in [
        "/healthz/db",
        "/healthz/errors",
        "/healthz/backup",
        "/healthz/deps",
        "/healthz/schema",
    ]:
        assert href in body, f"missing drill-down link: {href}"


def test_healthz_summary_includes_auditoria_filter_link(client):
    """When /healthz/errors has >0 last_1h, the auditoria filter link shows."""
    fake_errors = {"ok": True, "last_1h": 3, "last_24h": 12}
    with patch(
        "app.routers.health._summary_check_errors",
        return_value=fake_errors,
    ):
        resp = client.get("/healthz/summary")
    assert "/auditoria?action_filter=http.500" in resp.text


def test_healthz_summary_omits_auditoria_link_when_zero_errors(client):
    """When errors_last_1h == 0, no auditoria-filter CTA."""
    fake_errors = {"ok": True, "last_1h": 0, "last_24h": 0}
    with patch(
        "app.routers.health._summary_check_errors",
        return_value=fake_errors,
    ):
        resp = client.get("/healthz/summary")
    assert "/auditoria?action_filter=http.500" not in resp.text


def test_healthz_summary_admin_backup_cta_when_stale(client):
    """When backup is stale, /admin/backup CTA appears."""
    fake_backup = {
        "ok": False,
        "last_backup_at": "2026-01-01T00:00:00",
        "age_hours": 48.0,
        "threshold_hours": 24,
    }
    with patch(
        "app.routers.health._summary_check_backup",
        return_value=fake_backup,
    ):
        resp = client.get("/healthz/summary")
    assert "/admin/backup" in resp.text


# --- _summary_payload aggregator ---


def test_summary_payload_short_circuits_when_not_ready(client):
    """ready=False on app.state → all_ok=False, checks empty."""
    with patch.object(
        client.app.state, "ready", False, create=False
    ):
        resp = client.get("/healthz/summary")
    assert resp.status_code == 200
    # Banner says "todavía está arrancando"
    assert "todavía está arrancando" in resp.text or \
        "todav" in resp.text


def test_summary_payload_all_ok_true_when_every_check_passes(client):
    """When every sub-check is ok=True, all_ok=True → green banner."""
    ok_check = {"ok": True}
    with patch(
        "app.routers.health._summary_check_db", return_value=ok_check
    ), patch(
        "app.routers.health._summary_check_errors", return_value=ok_check
    ), patch(
        "app.routers.health._summary_check_backup", return_value=ok_check
    ), patch(
        "app.routers.health._summary_check_deps", return_value=ok_check
    ), patch(
        "app.routers.health._summary_check_disk", return_value=ok_check
    ):
        resp = client.get("/healthz/summary")
    assert "Todo en verde" in resp.text


def test_summary_payload_all_ok_false_when_one_check_fails(client):
    """One check ok=False → yellow banner."""
    ok = {"ok": True}
    bad = {"ok": False, "detail": "simulated failure"}
    with patch(
        "app.routers.health._summary_check_db", return_value=ok
    ), patch(
        "app.routers.health._summary_check_errors", return_value=ok
    ), patch(
        "app.routers.health._summary_check_backup", return_value=bad
    ), patch(
        "app.routers.health._summary_check_deps", return_value=ok
    ), patch(
        "app.routers.health._summary_check_disk", return_value=ok
    ):
        resp = client.get("/healthz/summary")
    assert "amarillo o rojo" in resp.text


def test_summary_payload_all_red_still_renders(client):
    """Every check ok=False → page still returns 200 (no exception)."""
    bad = {"ok": False, "detail": "all red"}
    with patch(
        "app.routers.health._summary_check_db", return_value=bad
    ), patch(
        "app.routers.health._summary_check_errors", return_value=bad
    ), patch(
        "app.routers.health._summary_check_backup", return_value=bad
    ), patch(
        "app.routers.health._summary_check_deps", return_value=bad
    ), patch(
        "app.routers.health._summary_check_disk", return_value=bad
    ):
        resp = client.get("/healthz/summary")
    assert resp.status_code == 200
    assert "amarillo o rojo" in resp.text


# --- per-check helper unit tests ---


def test_summary_check_backup_marks_stale_for_old_timestamp():
    """_summary_check_backup correctly maps age > 24h → ok=False."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    now_iso = datetime.now(ASUNCION_TZ).isoformat()
    old_iso = (datetime.now(ASUNCION_TZ) - timedelta(hours=48)).isoformat()
    with patch.object(hb, "_get_last_backup_at", return_value=old_iso):
        result = hb._summary_check_backup(fake_req)
    assert result["ok"] is False
    assert result["age_hours"] > 24


def test_summary_check_backup_marks_fresh_for_new_timestamp():
    """_summary_check_backup ok=True when age < 24h."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    fresh_iso = datetime.now(ASUNCION_TZ).isoformat()
    with patch.object(hb, "_get_last_backup_at", return_value=fresh_iso):
        result = hb._summary_check_backup(fake_req)
    assert result["ok"] is True
    assert result["age_hours"] < 1


def test_summary_check_backup_reports_never_when_missing():
    """When _get_last_backup_at returns None, ok=False with reason='never'."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    with patch.object(hb, "_get_last_backup_at", return_value=None):
        result = hb._summary_check_backup(fake_req)
    assert result["ok"] is False
    assert result["reason"] == "never"


def test_summary_check_backup_handles_unparseable():
    """Unparseable stored date → ok=False, reason='unparseable'."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    with patch.object(hb, "_get_last_backup_at", return_value="not-a-date"):
        result = hb._summary_check_backup(fake_req)
    assert result["ok"] is False
    assert result["reason"] == "unparseable"


def test_summary_check_disk_marks_danger_above_90pct():
    """Disk > 90% → ok=False."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    # Patchable via _disk_usage.
    with patch.object(hb, "_disk_usage") as fake_du:
        fake_du.return_value = _FakeDiskUsage(
            total=100, used=95, free=5
        )
        result = hb._summary_check_disk(fake_req)
    assert result["ok"] is False
    assert result["used_pct"] == 95.0


def test_summary_check_disk_marks_ok_below_90pct():
    """Disk < 90% → ok=True."""
    from app.routers import health as hb
    fake_req = _MockRequest()
    with patch.object(hb, "_disk_usage") as fake_du:
        fake_du.return_value = _FakeDiskUsage(
            total=100, used=50, free=50
        )
        result = hb._summary_check_disk(fake_req)
    assert result["ok"] is True
    assert result["used_pct"] == 50.0


def test_summary_check_deps_skips_when_no_env(client):
    """When SUPABASE_URL and R2_BUCKET are unset, deps returns 'skipped'."""
    import os
    saved = {}
    for k in ("SUPABASE_URL", "R2_BUCKET"):
        if k in os.environ:
            saved[k] = os.environ.pop(k)
    try:
        from app.routers import health as hb
        result = hb._summary_check_deps(_MockRequest())
    finally:
        for k, v in saved.items():
            os.environ[k] = v
    assert result["supabase"]["ok"] == "skipped"
    assert result["r2"] == "skipped"
    assert result["ok"] is True


def test_summary_check_deps_supabase_dns_error_visible(client, monkeypatch):
    """When supabase probe returns DNSError, summary includes error_class.

    Locks the new diagnostic shape so operators see "DNSError: Name or
    service not known" instead of a generic "caído".
    """
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    from app.routers import health as hb
    monkeypatch.setattr(
        hb, "_check_supabase_reachable",
        lambda url, timeout=2.0: {
            "ok": False,
            "http_status": None,
            "error_class": "DNSError",
            "latency_ms": 23,
            "reason": "Name or service not known",
        },
    )
    result = hb._summary_check_deps(_MockRequest())
    assert result["ok"] is False
    assert result["supabase"]["error_class"] == "DNSError"
    assert "Name or service not known" in result["supabase"]["reason"]


def test_healthz_summary_renders_supabase_error_class(client, monkeypatch):
    """When supabase probe fails with DNSError, the template shows it.

    Operator UX win: before, /healthz/summary said "caído". Now it says
    "caído DNSError: Name or service not known" — which immediately
    tells the operator to check DNS, not the supabase project.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    from app.routers import health as hb
    monkeypatch.setattr(
        hb, "_check_supabase_reachable",
        lambda url, timeout=2.0: {
            "ok": False,
            "http_status": None,
            "error_class": "DNSError",
            "latency_ms": 23,
            "reason": "Name or service not known",
        },
    )
    resp = client.get("/healthz/summary")
    body = resp.text
    assert "DNSError" in body, f"DNSError not surfaced in {body[:500]}"
    assert "Name or service not known" in body


def test_summary_payload_keys(client):
    """_summary_payload returns {ready, all_ok, checks: {db, errors, backup, deps, disk}}."""
    from app.routers import health as hb
    payload = hb._summary_payload(_MockRequest(
        session_factory=client.app.state.session_factory,
        engine=client.app.state.engine,
        ready=True,
    ))
    assert payload["ready"] is True
    assert "all_ok" in payload
    assert set(payload["checks"].keys()) == {
        "db", "errors", "backup", "deps", "disk",
    }


# --- helpers ---


class _MockRequest:
    """Minimal mock of fastapi.Request for summary-helper tests."""

    def __init__(self, session_factory=None, engine=None, ready=True):
        self.app = type(
            "App",
            (),
            {
                "state": type(
                    "State",
                    (),
                    {
                        "session_factory": session_factory
                        or (lambda: _FakeSession()),
                        "engine": engine or _FakeEngine(),
                        "ready": ready,
                    },
                )(),
            },
        )()


class _FakeSession:
    """Minimal session stub for the errors check."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        return _FakeScalar(0)


class _FakeScalar:
    def __init__(self, val):
        self._val = val

    def scalar(self):
        return self._val


class _FakeEngine:
    def connect(self):
        return _FakeConn()


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        return _FakeScalar(1)


class _FakeDiskUsage:
    """Namespace mimicking shutil.disk_usage result."""

    def __init__(self, total, used, free):
        self.total = total
        self.used = used
        self.free = free
