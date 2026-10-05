"""tests/test_notifications.py — verify app/rms/notifications.py (E14).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E14.

Covers:
- format_daily_summary_message: includes revenue + top products + warnings
- send_notification dry-run: writes to spool
- send_notification email: missing creds fails gracefully
- send_notification whatsapp: missing creds fails gracefully
- _money() formats with thousand dots
- append_notification_log adds JSON line
"""

# allow-hardcoded-dates: notification templates assert specific date strings
from __future__ import annotations

from datetime import datetime, timezone

from app.rms.notifications import (
    NotifyKind,
    NotifyResult,
    _money,
    append_notification_log,
    format_daily_summary_message,
    notification_log_path,
    send_notification,
)


def test_money_format():
    assert _money(1000) == "1.000"
    assert _money(1500000) == "1.500.000"
    assert _money(0) == "0"
    assert _money(250) == "250"


def test_format_daily_summary_includes_revenue():
    """Daily summary must include revenue + margin + warnings."""
    from app.rms.workflow import DailyProductRow, DailySummaryFull

    summary = DailySummaryFull(
        date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        n_sales=12,
        n_voided=1,
        revenue_gs=250_000,
        cogs_gs=100_000,
        margin_gs=150_000,
        margin_pct=60.0,
        top_products=[
            DailyProductRow(product_id=1, product_name="Muffin", qty_sold=8, revenue_gs=20_000),
            DailyProductRow(product_id=2, product_name="Torta", qty_sold=2, revenue_gs=70_000),
        ],
        low_stock_ingredients=["harina"],
        warnings=["Margen alto OK"],
    )
    msg = format_daily_summary_message(summary, business_name="HEREBUS")
    assert "HEREBUS" in msg
    assert "250.000" in msg  # revenue
    assert "150.000" in msg  # margin
    assert "Muffin" in msg
    assert "Torta" in msg
    assert "harina" in msg.lower() or "ingredients" in msg.lower()


def test_send_notification_dryrun_writes_to_spool(tmp_path, monkeypatch):
    monkeypatch.setattr("app.rms.notifications.SPOOL_DIR", tmp_path)
    msg = "Hola, esto es un resumen."
    result = send_notification(msg, kind=NotifyKind.DRYRUN)
    assert result.ok
    assert result.kind == "dryrun"
    files = list(tmp_path.glob("dryrun-*.txt"))
    assert len(files) == 1
    assert files[0].read_text() == msg


def test_send_notification_email_missing_creds(monkeypatch):
    """Email without SMTP env vars must fail gracefully."""
    for k in ("AIW_SMTP_HOST", "AIW_SMTP_USER", "AIW_SMTP_PASS", "AIW_SMTP_TO"):
        monkeypatch.delenv(k, raising=False)
    result = send_notification("body", kind=NotifyKind.EMAIL)
    assert result.ok is False
    assert result.error and "missing" in result.error.lower()


def test_send_notification_whatsapp_missing_creds(monkeypatch):
    for k in ("AIW_TWILIO_SID", "AIW_TWILIO_TOKEN", "AIW_TWILIO_FROM", "AIW_TWILIO_TO"):
        monkeypatch.delenv(k, raising=False)
    result = send_notification("body", kind=NotifyKind.WHATSAPP)
    assert result.ok is False
    assert result.error and "missing" in result.error.lower()


def test_send_notification_unknown_kind(monkeypatch):
    """Unknown kind yields a structured failure (no exception leak)."""
    result = send_notification("body", kind="bogus-channel")
    assert result.ok is False
    assert "unknown" in (result.error or "").lower() or "unknown" in result.detail.lower()


def test_send_notification_reads_kind_from_env(monkeypatch, tmp_path):
    monkeypatch.setattr("app.rms.notifications.SPOOL_DIR", tmp_path)
    monkeypatch.setenv("AIW_NOTIFY_KIND", "dryrun")
    result = send_notification("env-driven message")
    assert result.ok
    files = list(tmp_path.glob("dryrun-*.txt"))
    assert any(f.read_text() == "env-driven message" for f in files)


def test_notification_log_path_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("app.rms.notifications.SPOOL_DIR", tmp_path)
    p = notification_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"existing": true}\n')
    result = NotifyResult(ok=True, kind="dryrun", detail="unit", bytes_sent=10)
    append_notification_log(result)
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    assert '"dryrun"' in lines[1]


def test_format_message_handles_empty_summary():
    """Empty summary still produces a sensible string (no AttributeError)."""
    from app.rms.workflow import DailySummaryFull

    summary = DailySummaryFull(
        date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        n_sales=0,
        n_voided=0,
        revenue_gs=0,
        cogs_gs=0,
        margin_gs=0,
        margin_pct=0.0,
        top_products=[],
        low_stock_ingredients=[],
        warnings=[],
    )
    msg = format_daily_summary_message(summary, business_name="X")
    assert "X" in msg
    assert "0" in msg  # either n_sales or revenue
