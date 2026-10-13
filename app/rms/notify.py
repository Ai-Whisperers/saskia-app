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
    req = urllib.request.Request(  # noqa: S310
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            req, timeout=_TIMEOUT_S
        ) as resp:
            return resp.status == 200
    except Exception as exc:
        print(f"WARNING: Telegram notify failed: {exc}", file=sys.stderr)
        return False


def sentry_before_send(event: dict, hint: dict) -> dict:
    """Sentry `before_send` hook: mirror errors to Telegram, then pass
    the event through untouched.

    Two responsibilities:

    1. **AppError -> Sentry level mapping** (S2 robustness PR5,
       2026-10-13). Before any other decision, consult
       ``app.rms.sentry.sentry_level_for`` with the originating exception
       from ``hint["exc_info"]`` and override ``event["level"]`` so:

       - 4xx AppErrors (NotFound, ValidationError, ...) land as "warning"
         so the operator's Sentry inbox isn't polluted by user-input
         noise.
       - 5xx AppErrors (DataIntegrityError, DependencyError, ...) land as
         "error" so on-call gets pinged.

       Non-AppError exceptions fall through untouched -- Sentry's default
       "error" level for ``capture_exception`` is the right call for them.

    2. Mirror ``error``/``fatal`` events to Telegram (rate-damped at one
       mirror per fingerprint per 60s, in-process; the VPS runs one
       uvicorn worker). After step 1, "warning"-level AppErrors (the 4xx
       user-input noise) are correctly filtered out of the Telegram
       mirror so the operator's phone doesn't buzz on every NotFound.
    """
    import time

    # 1. AppError -> Sentry level mapping. Lazy import keeps the existing
    #    lazy-load contract intact: an unset TG_BOT_TOKEN/TG_CHAT_ID does
    #    not trigger this module's heavy imports.
    try:
        from app.rms.sentry import sentry_level_for

        exc_info = (hint or {}).get("exc_info") if hint else None
        # Sentry SDK puts (type, value, traceback) in hint["exc_info"];
        # element [1] is the live exception instance.
        if exc_info and len(exc_info) >= 2 and isinstance(exc_info[1], BaseException):
            mapped_level = sentry_level_for(exc_info[1])
            if mapped_level:
                # Ensure the event dict exists; mutate in place (Sentry
                # passes the same object to before_send and the filter
                # below consumes it).
                if not isinstance(event, dict):
                    event = {"level": mapped_level}
                else:
                    event["level"] = mapped_level
    except Exception as _exc:
        # Defensive: a buggy level mapper must not break the SDK
        # pipeline. Worst case, the event keeps its default level and
        # the operator sees the raw Sentry stacktrace in the dashboard.
        # Logged to stderr (no loguru import here -- lazy-load contract).
        print(f"WARNING: AppError level mapper failed: {_exc!r}", file=sys.stderr)

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
