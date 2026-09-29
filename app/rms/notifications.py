"""app/rms/notifications.py — WhatsApp-style daily summary (E14).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E14.

Adds:
- format_daily_summary_message(...): produce a concise text summary
  suitable for WhatsApp / SMS / print
- delivery helpers: send_whatsapp_summary + send_email_summary
  (integration with Twilio + SMTP behind a seam)
- delivery delivery log (app_meta key + history for audit)

The default backend is "dry-run" so this works in CI/tests without
external creds. Operator can switch by setting env vars:
    AIW_NOTIFY_KIND = whatsapp|email|dryrun
    AIW_TWILIO_SID / AIW_TWILIO_TOKEN / AIW_TWILIO_FROM / AIW_TWILIO_TO
    AIW_SMTP_HOST / AIW_SMTP_PORT / AIW_SMTP_USER / AIW_SMTP_PASS
"""
from __future__ import annotations

import json
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rms.workflow import DailySummaryFull


# --- Message formatting ---


def format_daily_summary_message(
    summary: "DailySummaryFull",
    *,
    business_name: str = "Mi Panadería",
    max_lines: int = 12,
) -> str:
    """Render a concise WhatsApp-ready message.

    Length cap to avoid SMS truncation. Spanish.
    """
    date_str = summary.date.strftime("%Y-%m-%d")
    lines = [
        f"*{business_name} — {date_str}*",
        "",
        f"Ventas: {summary.n_sales}  ({_money(summary.revenue_gs)} Gs.)",
        f"Margen: {_money(summary.margin_gs)} Gs. ({summary.margin_pct:.1f}%)",
        f"Anuladas: {summary.n_voided}",
    ]
    if summary.top_products:
        lines.append("")
        lines.append("*Top productos:*")
        for row in summary.top_products[:3]:
            lines.append(f"• {row.product_name} x{row.qty_sold:.0f}")
    if summary.low_stock_ingredients:
        lines.append("")
        names = ", ".join(summary.low_stock_ingredients[:5])
        lines.append(f"⚠ {len(summary.low_stock_ingredients)} ingredientes bajos: {names}")
    if summary.warnings:
        lines.append("")
        lines.append("⚠")
        for w in summary.warnings[:max_lines]:
            lines.append(f"- {w}")
    return "\n".join(lines)


def _money(n: int) -> str:
    """Format an integer guaraní amount with thousands separators."""
    return f"{n:,}".replace(",", ".")


# --- Delivery backends ---


class NotifyKind(str, Enum):
    """Where the daily summary goes."""

    DRYRUN = "dryrun"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


@dataclass
class NotifyResult:
    """Outcome of a delivery."""

    ok: bool
    kind: str
    detail: str
    bytes_sent: int = 0
    error: str | None = None


# Local spool dir for dry-run + audit trail
SPOOL_DIR = Path("./notifications_spool")


def _spool_message(name: str, body: str) -> Path:
    """Write a delivery to local spool (audit; failure-isolation)."""
    SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = SPOOL_DIR / f"{name}-{ts}.txt"
    out.write_text(body, encoding="utf-8")
    return out


def send_whatsapp_summary(body: str, *, to: str | None = None) -> NotifyResult:
    """Send via Twilio's WhatsApp API.

    env:
      AIW_TWILIO_SID, AIW_TWILIO_TOKEN
      AIW_TWILIO_FROM = 'whatsapp:+14155238886' (sandbox) or your number
      AIW_TWILIO_TO   = 'whatsapp:+595...'

    No external SDK dep — uses Twilio REST over HTTPS (uses stdlib
    urllib). Keeps the dep tree small.
    """
    sid = os.environ.get("AIW_TWILIO_SID", "")
    token = os.environ.get("AIW_TWILIO_TOKEN", "")
    from_ = os.environ.get("AIW_TWILIO_FROM", "")
    to = to or os.environ.get("AIW_TWILIO_TO", "")

    if not (sid and token and from_ and to):
        return NotifyResult(
            ok=False,
            kind="whatsapp",
            detail="missing Twilio credentials",
            error="missing AIW_TWILIO_SID/TOKEN/FROM/TO env vars",
        )

    import urllib.parse
    import urllib.request

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = urllib.parse.urlencode({
        "From": from_,
        "To": to,
        "Body": body,
    }).encode()
    request = urllib.request.Request(
        url, data=payload, method="POST",
    )
    import base64
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    request.add_header("Authorization", f"Basic {auth}")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request, timeout=10.0) as resp:
            _ = resp.read().decode()  # drain body for connection reuse
            spool = _spool_message("whatsapp", body)
            return NotifyResult(
                ok=True,
                kind="whatsapp",
                detail=f"sent to {to} (spool: {spool})",
                bytes_sent=len(body),
                error=None,
            )
    except Exception as e:  # network / twilio error  # noqa: BLE001
        spool = _spool_message("whatsapp-FAILED", body)
        return NotifyResult(
            ok=False,
            kind="whatsapp",
            detail=f"twilio error; spooled at {spool}",
            bytes_sent=len(body),
            error=str(e),
        )


def send_email_summary(
    body: str, *, to: str | None = None, subject: str = "Daily summary"
) -> NotifyResult:
    """Send via SMTP (Gmail / Outlook / SES / etc.).

    env:
      AIW_SMTP_HOST, AIW_SMTP_PORT, AIW_SMTP_USER, AIW_SMTP_PASS, AIW_SMTP_TO
    """
    host = os.environ.get("AIW_SMTP_HOST", "")
    port = int(os.environ.get("AIW_SMTP_PORT", "587"))
    user = os.environ.get("AIW_SMTP_USER", "")
    password = os.environ.get("AIW_SMTP_PASS", "")
    to = to or os.environ.get("AIW_SMTP_TO", "")

    if not (host and user and password and to):
        return NotifyResult(
            ok=False, kind="email",
            detail="missing SMTP creds",
            error="missing AIW_SMTP_* env vars",
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10.0) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        spool = _spool_message("email", body)
        return NotifyResult(
            ok=True, kind="email",
            detail=f"sent to {to}; spool: {spool}",
            bytes_sent=len(body),
        )
    except Exception as e:  # noqa: BLE001 — defensive default
        spool = _spool_message("email-FAILED", body)
        return NotifyResult(
            ok=False, kind="email",
            detail=f"smtp error; spool: {spool}",
            bytes_sent=len(body),
            error=str(e),
        )


def send_notification(
    body: str,
    *,
    kind: NotifyKind | str | None = None,
    to: str | None = None,
) -> NotifyResult:
    """Dispatch to the active notification backend.

    kind = None → read AIW_NOTIFY_KIND env var; default "dryrun".
    """
    if kind is None:
        kind_str = os.environ.get("AIW_NOTIFY_KIND", "dryrun").lower()
    elif isinstance(kind, NotifyKind):
        kind_str = kind.value
    else:
        kind_str = str(kind).lower()

    if kind_str == "dryrun":
        spool = _spool_message("dryrun", body)
        return NotifyResult(
            ok=True, kind="dryrun",
            detail=f"dry-run; spool: {spool}",
            bytes_sent=len(body),
        )
    if kind_str == "whatsapp":
        return send_whatsapp_summary(body, to=to)
    if kind_str == "email":
        return send_email_summary(body, to=to)
    return NotifyResult(
        ok=False, kind=kind_str, detail="unknown kind",
        error=f"unknown kind: {kind_str}",
    )


def notification_log_path() -> Path:
    """Path to the JSON-lines log of notifications."""
    SPOOL_DIR.mkdir(parents=True, exist_ok=True)
    return SPOOL_DIR / "history.jsonl"


def append_notification_log(result: NotifyResult) -> None:
    """Append a JSON line to the history."""
    log = notification_log_path()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": result.kind,
        "ok": result.ok,
        "detail": result.detail,
        "bytes": result.bytes_sent,
        "error": result.error,
    }
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = [
    "SPOOL_DIR",
    "NotifyKind",
    "NotifyResult",
    "append_notification_log",
    "format_daily_summary_message",
    "notification_log_path",
    "send_email_summary",
    "send_notification",
    "send_whatsapp_summary",
]
