"""app/rms/notify.py — Telegram alert channel (C.1, polish lot 2026-10-07).

Sends plain-text alerts to a Telegram bot chat. Designed for the
Sentry→Telegram bridge: when Sentry captures an error, the
`before_send` hook mirrors a short digest to Telegram so the operator
sees production incidents without opening Sentry.

Config (env vars, both required or the channel is OFF):
  TG_BOT_TOKEN  — bot token from @BotFather
  TG_CHAT_ID    — chat/channel id to post into

Design rules (locked by tests in tests/test_notify_telegram.py):
  - OFF (silent no-op) unless both env vars are set.
  - NEVER raises: a Telegram outage must not break the request path,
    the Sentry pipeline, or app startup. All failures are swallowed
    and logged to stderr.
  - Payload truncated to 3,500 chars (Telegram caption limit is 4096
    with HTML parse mode; we stay under with margin).
  - Timeout 5s, single attempt, fire-and-forget (synchronous urllib,
    no new dependencies — AGENTS.md hard rule 26).

Wiring (1 line, applied where Sentry inits — kept out of this module
so the Sentry init site owns its config):

    from app.rms.notify import sentry_before_send
    sentry_sdk.init(..., before_send=sentry_before_send)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_LEN = 3500
_TIMEOUT_S = 5


def telegram_configured() -> bool:
    """True when both TG_BOT_TOKEN and TG_CHAT_ID are set."""
    return bool(os.getenv("TG_BOT_TOKEN")) and bool(os.getenv("TG_CHAT_ID"))


def send_telegram(text: str) -> bool:
    """Post `text` to the configured chat. Returns True on HTTP 200.

    Never raises. Silent no-op (returns False) when unconfigured.
    """
    token = os.getenv("TG_BOT_TOKEN", "")
    chat_id = os.getenv("TG_CHAT_ID", "")
    if not token or not chat_id:
        return False
    if len(text) > _MAX_LEN:
        text = text[: _MAX_LEN - 1] + "…"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    url = _TELEGRAM_API.format(token=token)
    assert url.startswith("https://api.telegram.org/")  # S310: scheme locked
    req = urllib.request.Request(  # noqa: S310 — https scheme locked above
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 — https locked
                req, timeout=_TIMEOUT_S
            ) as resp:
            return resp.status == 200
    except Exception as exc:  # noqa: BLE001 — alerts must never raise
        print(f"WARNING: Telegram notify failed: {exc}", file=sys.stderr)
        return False


def sentry_before_send(event: dict, hint: dict) -> dict:
    """Sentry `before_send` hook: mirror errors to Telegram, then pass
    the event through untouched.

    Mirrors only `error`-level events (Sentry level "error"/"fatal") to
    avoid spamming from warnings. Rate damping: at most one Telegram
    message per event-type per 60s (in-process; enough for a
    single-process deployment — the VPS runs one uvicorn worker).
    """
    import time

    level = (event or {}).get("level", "")
    if level not in ("error", "fatal"):
        return event

    # In-process damping: same fingerprint inside 60s → skip mirror.
    fp = json.dumps((event or {}).get("fingerprint", []), sort_keys=True)
    now = time.monotonic()
    last = getattr(sentry_before_send, "_last_sent", {})
    if fp in last and now - last[fp] < 60:
        return event

    exc = (event.get("exception") or {}).get("values") or []
    title = "Sentry error"
    if exc:
        last_exc = exc[-1]
        title = f"{last_exc.get('type', 'Error')}: {last_exc.get('value', '')[:200]}"
    req = event.get("request") or {}
    lines = [
        f"🚨 {title}",
        f"nivel: {level}",
        f"release: {event.get('release', '—')}",
    ]
    if req.get("url"):
        lines.append(f"url: {req['url']}")
    event_id = (event or {}).get("event_id")
    if event_id:
        env = os.getenv("SENTRY_ENVIRONMENT", "production")
        lines.append(f"sentry: https://sentry.io (evento {event_id}, {env})")

    if send_telegram("\n".join(lines)):
        last[fp] = now
        sentry_before_send._last_sent = last  # type: ignore[attr-defined]
    return event
