"""app/rms/rate_limit.py — sliding-window rate limiter backed by the audit log.

Per the 2026-09-04 critical-path plan, E3.S2.

Design:
- Counts `login.failure` audit rows per IP in a sliding N-minute window.
- If the count meets or exceeds the limit, returns 429.
- Bypassed when AIW_SASKIA_AUTH_DISABLED=1 (so tests don't trip it).
- Bypassed for /healthz/* (UptimeRobot hits /healthz every 5 min; that
  would otherwise fill the audit log with junk).

Failure-mode: if the DB is unavailable, FAIL OPEN (do not block login
just because the rate-limiter can't count). This is a security
trade-off; we accept it because blocking legitimate users during a
DB outage is worse than letting one attacker slip through.

Limit defaults:
  - 5 failed logins per 5 minutes per IP. After that, 429 + audit
    row action="login.rate_limited" for forensics.

Per the risk register §7: "rate-limit blocks UptimeRobot" — handled
here by excluding /healthz/* via the route-level check in
app/routers/auth.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.models import AuditLog

DEFAULT_LIMIT = 5
DEFAULT_WINDOW_MINUTES = 5


@dataclass
class RateLimitDecision:
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int


def _client_ip(request: object) -> str:
    """Pull first-hop IP from X-Forwarded-For, fall back to request.client.host.

    Mirrors the same logic in app/rms/audit.py so the rate-limit
    threshold and audit IP match exactly.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    client = getattr(request, "client", None)
    return getattr(client, "host", "unknown") if client else "unknown"


def is_rate_limited(
    session: Session,
    request: object,
    *,
    limit: int = DEFAULT_LIMIT,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    now: datetime | None = None,
) -> RateLimitDecision:
    """Return whether `request` is currently rate-limited for login.

    Side effect: if blocked, writes a `login.rate_limited` audit row.

    Pass `now` for deterministic tests.
    """
    when = now or datetime.now(timezone.utc)
    threshold = when - timedelta(minutes=window_minutes)
    ip = _client_ip(request)

    # Count login.failure rows for this IP in the window.
    # FAIL OPEN: if the DB raises, return allowed=True so a DB outage
    # does not brick the login endpoint. (See module docstring.)
    try:
        count = (
            session.query(AuditLog)
            .filter(
                AuditLog.action == "login.failure",
                AuditLog.ip == ip,
                AuditLog.occurred_at >= threshold,
            )
            .count()
        )
    except Exception:  # noqa: BLE001 — defensive default
        logger.warning("rate_limit_check failed: DB query failed, failing open for safety")
        return RateLimitDecision(
            allowed=True,
            current_count=0,
            limit=limit,
            retry_after_seconds=0,
        )

    if count >= limit:
        # Block. Write audit row.
        audit_record(
            session,
            user_id=None,
            action="login.rate_limited",
            request=request,
            detail={
                "ip": ip,
                "window_minutes": window_minutes,
                "limit": limit,
                "observed_count": count,
            },
        )
        session.commit()
        return RateLimitDecision(
            allowed=False,
            current_count=count,
            limit=limit,
            retry_after_seconds=window_minutes * 60,
        )

    return RateLimitDecision(
        allowed=True,
        current_count=count,
        limit=limit,
        retry_after_seconds=0,
    )


def is_disabled() -> bool:
    """Auth/test escape hatch: AIW_SASKIA_AUTH_DISABLED=1 bypasses rate limit.

    Mirrors the convention of SASKIA_TEST_AUTH_DISABLED used by the test
    conftest, but exposed as a stable env var so prod code can also
    flip it for maintenance windows.
    """
    return os.getenv("AIW_SASKIA_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


def is_write_rate_limited(
    session: Session,
    request: object,
    *,
    max_per_minute: int = 10,
    window_seconds: int = 60,
    now: object=None,
) -> bool:
    """Return True if this client has exceeded max_per_minute writes.

    Counts rows with `action LIKE 'write.%'` for this IP within the
    sliding window. Used to throttle state-changing POSTs (sale.create,
    merma.register, product.create) so a bot can't flood.

    FAIL OPEN: if the DB raises, return False so a DB outage does not
    brick write endpoints. A flood during a DB outage is the lesser
    evil compared to blocking legitimate operators.

    Pass `now` for deterministic tests.
    """
    when = now or datetime.now(timezone.utc)
    threshold = when - timedelta(seconds=window_seconds)
    ip = _client_ip(request)
    try:
        count = (
            session.query(AuditLog)
            .filter(
                AuditLog.action.like("write.%"),
                AuditLog.ip == ip,
                AuditLog.occurred_at >= threshold,
            )
            .count()
        )
    except Exception:  # noqa: BLE001 — defensive default
        logger.warning("is_write_rate_limited DB query failed, failing closed for safety")
        return False
    return count >= max_per_minute


__all__ = [
    "DEFAULT_LIMIT",
    "DEFAULT_WINDOW_MINUTES",
    "RateLimitDecision",
    "is_disabled",
    "is_rate_limited",
    "is_write_rate_limited",
]
