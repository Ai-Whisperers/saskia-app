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


def _apply_applog_level_mapping(event: dict, hint: dict) -> dict:
    """Step 1: AppError -> Sentry level mapping.

    Consult ``app.rms.sentry.sentry_level_for`` with the originating
    exception from ``hint["exc_info"]`` and override ``event["level"]``
    in-place so 4xx AppErrors land as "warning" (user-input noise) and
    5xx AppErrors land as "error" (server fault; pages on-call).

    Non-AppError exceptions and any exception whose ``exc_info`` is
    missing or malformed fall through untouched -- Sentry's default
    level is the right call for them.

    Lazy import inside the helper keeps the existing lazy-load contract:
    an unset TG_BOT_TOKEN / TG_CHAT_ID does NOT trigger this module's
    heavy imports. A buggy level mapper is logged to stderr and the
    event keeps its default level.
    """
    try:
        from app.rms.sentry import sentry_level_for

        exc_info = (hint or {}).get("exc_info") if hint else None
        # Sentry SDK puts (type, value, traceback) in hint["exc_info"];
        # element [1] is the live exception instance.
        if exc_info and len(exc_info) >= 2 and isinstance(exc_info[1], BaseException):
            mapped_level = sentry_level_for(exc_info[1])
            if mapped_level:
                # Mutate in place -- Sentry passes the same object to
                # before_send and the step-2 filter below consumes it.
                event["level"] = mapped_level
    except Exception as _exc:
        # Defensive: a buggy level mapper must not break the SDK
        # pipeline. Worst case, the event keeps its default level and
        # the operator sees the raw Sentry stacktrace in the dashboard.
        # Logged to stderr (no loguru import here -- lazy-load contract).
        print(f"WARNING: AppError level mapper failed: {_exc!r}", file=sys.stderr)
    return event


def _should_mirror_to_telegram(event: dict, now: float) -> tuple[bool, dict]:
    """Step 2: level gate + in-process fingerprint damping.

    Returns ``(should_mirror, damping_cache)``. ``damping_cache`` is
    either the existing module-level cache (when the same fingerprint
    was already mirrored inside the 60s window -- caller should skip
    and return the event unchanged) or the *same dict object* the
    cache holds, ready for the caller to record the timestamp after
    a successful mirror.

    Level gate: ``"error"`` and ``"fatal"`` are mirrored; anything
    else (including ``"warning"`` after the AppError mapping demoted
    a 4xx NotFound) passes through untouched. In-process damping:
    same fingerprint inside 60s -> skip. The VPS runs one uvicorn
    worker so the in-process cache is sufficient; if/when the deploy
    topology adds workers, this should move to a shared store (POSTed
    last-mirror time, or Redis SETEX).
    """
    level = (event or {}).get("level", "")
    if level not in ("error", "fatal"):
        return False, getattr(sentry_before_send, "_last_sent", {})

    fp = json.dumps((event or {}).get("fingerprint", []), sort_keys=True)
    last = getattr(sentry_before_send, "_last_sent", {})
    if fp in last and now - last[fp] < 60:
        return False, last
    return True, last


def _build_telegram_message(event: dict, level: str) -> str:
    """Step 3: render the human-readable Telegram message body.

    Pure formatter -- no I/O, no side effects, no Sentry mutation.
    The returned string is what gets passed to ``send_telegram()``.
    Lines:

      🚨 <type>: <value (truncated to 200 chars)>
      nivel: <level>
      release: <event.release or em-dash>
      url: <event.request.url>      (only when present)
      sentry: https://sentry.io (evento <id>, <environment>)
                                  (only when event_id is present)

    The em-dash for a missing release mirrors the pre-split output.
    """
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
    return "\n".join(lines)


def sentry_before_send(event: dict, hint: dict) -> dict:
    """Sentry ``before_send`` hook: mirror errors to Telegram, then pass
    the event through untouched.

    Orchestrator (CC <= 6): delegates to three single-purpose helpers,
    each grade-A/B:

      1. ``_apply_applog_level_mapping(event, hint)`` -- override
         ``event["level"]`` so 4xx AppErrors become "warning" (filtered
         out of the Telegram mirror in step 2) and 5xx AppErrors
         become "error" (paged on-call).
      2. ``_should_mirror_to_telegram(event, now)`` -- level gate
         (``error`` / ``fatal`` only) + 60s in-process fingerprint
         damping. Returns ``(should_mirror, damping_cache)``.
      3. ``_build_telegram_message(event, level)`` -- pure formatter
         that produces the Telegram payload string.

    After step 2 admits the event, the orchestrator builds the message
    via step 3 and dispatches via ``send_telegram()``. On HTTP 200,
    the damping cache is updated so the next mirror of the same
    fingerprint inside 60s short-circuits. The event is returned in
    all cases -- Sentry passes the same object through to its storage
    layer.

    Two responsibilities documented for operators (locked by tests):

      - AppError -> Sentry level mapping (S2 robustness PR5, 2026-10-13).
      - In-process Telegram mirror with rate-damping (C.1, 2026-10-07).
    """
    import time

    # Step 1: AppError -> Sentry level mapping. Mutates ``event`` in
    # place based on the originating exception in ``hint`` (or no-op
    # if the exception isn't an AppError).
    event = _apply_applog_level_mapping(event, hint)

    # Step 2: level gate + fingerprint damping. Reject anything that's
    # not an "error" or "fatal"; reject repeats inside the 60s window.
    now = time.monotonic()
    should_mirror, last = _should_mirror_to_telegram(event, now)
    if not should_mirror:
        return event

    # Step 3: build the payload, dispatch to Telegram. On 200, record
    # the mirror timestamp so a future duplicate fingerprint short-
    # circuits inside the damping window.
    level = (event or {}).get("level", "")  # already vetted by step 2
    if send_telegram(_build_telegram_message(event, level)):
        fp = json.dumps((event or {}).get("fingerprint", []), sort_keys=True)
        last[fp] = now
        sentry_before_send._last_sent = last  # type: ignore[attr-defined]
    return event
