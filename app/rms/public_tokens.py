"""app/rms/public_tokens.py — shared public-token helpers.

Two public-share routes use the same pattern:

  - ``GET /p/{token}`` for pedidos (P1-2 hardening, migration 067).
  - ``GET /r/{token}`` for sales receipts (BACKLOG #17, migration 085).

Both:
  - Use a 22-char URL-safe token (96 bits of entropy from
    ``secrets.token_urlsafe(16)``).
  - Have a 30-day expiry.
  - Are rate-limited per client IP (see pedidos._enforce_public_token_rate_limit).
  - Are audited as ``public.<resource>.view``.

Why a shared module:
  - One place to bump entropy / expiry conventions in the future.
  - One place to centralize the ``is_token_valid(now) -> bool`` helper
    (saves duplicating the datetime/string normalization in each router).
  - Tests in this module cover both routes' invariants; routers only
    test their own wiring.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional


# 96 bits of entropy. With birthday-paradox collision math,
# ~10^14 tokens before 1% collision rate — effectively zero
# for a single bakery. See pedidos.py:generate_public_token
# for the original rationale.
_TOKEN_BYTES = 16

# 30 days. Long enough to cover the customer-comes-back-for-receipt
# window; short enough that a leaked link has bounded blast radius.
# Same number as /p/{token} for operational consistency.
_DEFAULT_TTL = timedelta(days=30)


def generate_public_token() -> str:
    """Return a fresh URL-safe token.

    22 chars from ``token_urlsafe(16)`` → 96 bits of entropy.
    Collision probability is negligible for a single bakery.
    """
    return secrets.token_urlsafe(_TOKEN_BYTES)


def issue_token(now: Optional[datetime] = None, ttl: timedelta = _DEFAULT_TTL) -> tuple[str, datetime]:
    """Return a fresh ``(token, expires_at)`` pair.

    ``expires_at`` is a timezone-aware UTC datetime so the column
    stores unambiguous expiry regardless of DB dialect.
    """
    when = now if now is not None else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return generate_public_token(), when + ttl


def is_token_valid(expires_at: object, now: Optional[datetime] = None) -> bool:
    """Return True iff ``expires_at`` is set and in the future.

    Defensive: ``None`` and unparseable strings both return False.
    Matches the ``pedidos._is_token_valid(pedido)`` semantics from P1-2
    so the public-sale route behaves identically.
    """
    if expires_at is None:
        return False

    # The ORM may hand back either a datetime or a string depending on
    # the underlying DB and column type. Normalize to datetime first.
    parsed: Optional[datetime] = None
    if isinstance(expires_at, datetime):
        parsed = expires_at
    elif isinstance(expires_at, str):
        normalized = expires_at.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return False

    # If the column came back tz-naive, treat it as UTC (matches the
    # rest of the app's UTC-stored-as-naive convention).
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    when = now if now is not None else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return parsed > when


__all__ = [
    "generate_public_token",
    "issue_token",
    "is_token_valid",
    "_DEFAULT_TTL",
]