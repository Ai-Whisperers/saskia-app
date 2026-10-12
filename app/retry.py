"""app/retry.py — Transient-error retry helper (S2 robustness PR2).

Wraps a callable in a bounded retry loop with exponential backoff + jitter.
Distinguishes TRANSIENT (retryable) from TERMINAL (re-raise immediately)
errors so a single helper covers HTTP, DB, and storage call sites.

Why a helper and not call-site loops?
- Centralizes backoff math + jitter so call sites stay readable.
- Standardizes the "transient classifier" so we don't end up with 5
  different ad-hoc "is this retryable?" checks.
- Plays nicely with AGENTS.md rule 41 (silent-except ban): a call site
  that wants to swallow after N retries still has to decide via the
  classifier, never via bare `except: pass`.

Used by HTTP integrations (`app/integrations/scrapers.py`,
`app/services/r2_backup.py`, `app/services/backup_crypto.py`) once
they opt in. NO auto-wiring yet — this PR is helper + tests only.

Stdlib-only by design (rule 26: no new deps without Iván OK). Uses
`time.sleep` + `random` for jitter.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ─── Default transient classifier ─────────────────────────────────
#
# Picked to cover the Sazon surface without importing every library
# (rule 26 forbids optional imports at module level). Call sites can
# override by passing `transient_exceptions=...` or by passing a
# custom `is_transient=` predicate.


def _is_locked_db_error(name: str, msg: str) -> bool:
    """sqlite3 / sqlalchemy OperationalError "locked/busy/deadlock" shape."""
    return name == "OperationalError" and ("locked" in msg or "busy" in msg or "deadlock" in msg)


def _is_httpx_status_error(exc: BaseException, full_name: str) -> bool | None:
    """httpx.HTTPStatusError -> bool, or None if not that exception.

    httpx's ``raise_for_status()`` raises ``HTTPStatusError`` for BOTH
    4xx and 5xx. A 404 must NOT retry, but a 429 / 5xx should. We
    return ``None`` for "not an HTTPStatusError" so the caller can
    fall through to the next rule.
    """
    if type(exc).__name__ != "HTTPStatusError" or full_name != "httpx.HTTPStatusError":
        return None
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if not isinstance(status, int):
        # No status available -- terminal (retrying a malformed call
        # is not going to help).
        return False
    return status >= 500 or status == 429


# Set-lifted to module scope: keeps default_is_transient short and the
# membership test cheap.
_HTTP_TRANSPORT_NAMES: frozenset[str] = frozenset(
    {
        # requests family
        "RequestException",
        "ConnectionError",
        "ConnectTimeout",
        "ReadTimeout",
        "HTTPError",
        # httpx transport-level (HTTPStatusError handled separately)
        "ConnectError",
        "TimeoutException",
        "NetworkError",
        "TransportError",
    }
)

# stdlib socket errors. NOTE: in Python 3.11+ `socket.timeout` is an
# alias for the builtin `TimeoutError`, so the class name surfaces as
# "TimeoutError" not "timeout". We accept BOTH so the classifier stays
# valid on 3.10 (older runtime) and 3.13+ (current runtime).
_SOCKET_NAMES: frozenset[str] = frozenset(
    {
        "TimeoutError",
        "timeout",
        "gaierror",
        "ConnectionRefusedError",
        "ConnectionResetError",
    }
)


def default_is_transient(exc: BaseException) -> bool:
    """Best-effort check for "is this exception worth retrying?".

    Recognizes (via duck-typing so the module stays stdlib-only):

    - ``requests.RequestException`` -- transport-level errors
      (ConnectionError, Timeout, HTTPError for 5xx via status_code).
    - ``httpx.HTTPError`` subclasses -- ``ConnectError``,
      ``ConnectTimeout``, ``ReadTimeout``, ``TimeoutException``,
      ``NetworkError``, ``TransportError`` (transport-level, retry);
      ``HTTPStatusError`` retries only on 5xx and 429 (other 4xx are
      terminal).
    - ``urllib.error.URLError`` -- stdlib URL fetches.
    - ``sqlite3.OperationalError`` messages containing "locked" or
      "database is locked" -- common transient SQLite contention.
    - ``sqlalchemy.exc.OperationalError`` messages with the same shape.
    - ``socket.timeout``, ``socket.gaierror`` -- stdlib socket errors.

    Returns False for anything else. Call sites needing a finer
    classifier (e.g. only retry on ``ConnectionError``, never on
    ``HTTPError`` 4xx) pass their own predicate.
    """
    name = type(exc).__name__
    full_name = f"{type(exc).__module__}.{name}"
    msg = str(exc).lower()

    if _is_locked_db_error(name, msg):
        return True

    httpx_status = _is_httpx_status_error(exc, full_name)
    if httpx_status is not None:
        return httpx_status

    # requests.RequestException and other HTTPError subclasses
    # (ConnectionError, Timeout, generic HTTPError without a status).
    # We treat the transport-level family as transient -- same as the
    # PR2 contract -- because we have no status code to inspect.
    if full_name == "requests.exceptions.RequestException" or name in _HTTP_TRANSPORT_NAMES:
        return True

    # urllib (used by app.integrations.scrapers if requests is missing)
    if full_name == "urllib.error.URLError":
        return True

    # stdlib socket errors. NOTE: in Python 3.11+ `socket.timeout` is an
    # alias for the builtin `TimeoutError`, so the class name surfaces
    # as "TimeoutError" not "timeout". We accept BOTH so the classifier
    # stays valid on 3.10 (older runtime) and 3.13+ (current runtime).
    if name in {"TimeoutError", "timeout", "gaierror", "ConnectionRefusedError", "ConnectionResetError"}:
        return True

    return False


# ─── Helper ────────────────────────────────────────────────────────


def retry_transient(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    is_transient: Callable[[BaseException], bool] = default_is_transient,
    sleep: Callable[[float], None] = time.sleep,
    op_name: str = "operation",
) -> T:
    """Call `fn()` with exponential backoff on transient errors.

    Parameters
    ----------
    fn:
        Zero-arg callable. Each call is one attempt.
    attempts:
        Maximum total calls (NOT retries). `attempts=1` means "call
        once, no retries". `attempts=3` means "call up to 3 times".
        Default 3 (one try + two retries).
    base_delay:
        Seconds for the first backoff. Doubles each attempt.
        Default 0.2s.
    max_delay:
        Cap on the backoff window (prevents unbounded waits).
        Default 5s.
    is_transient:
        Predicate that decides whether an exception is worth retrying.
        Default = `default_is_transient`.
    sleep:
        Sleep function. Override in tests to avoid real waits.
        Default = `time.sleep`.
    op_name:
        Label included in every log line for grep-ability.

    Returns
    -------
    Whatever `fn()` returns on the first successful call.

    Raises
    ------
    Whatever `fn()` raises on its last attempt, after attempts are
    exhausted OR a non-transient error is hit (re-raised immediately,
    no retry).
    """
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1, got {attempts}")
    if base_delay < 0:
        raise ValueError(f"base_delay must be >= 0, got {base_delay}")

    last_exc: BaseException | None = None
    for attempt_index in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            if not is_transient(exc):
                # TERMINAL — don't swallow, don't retry.
                raise
            last_exc = exc
            if attempt_index >= attempts:
                # Out of attempts — re-raise with the helper's name.
                logger.error(
                    "retry_exhausted op=%s attempt=%d/%d error=%r",
                    op_name,
                    attempt_index,
                    attempts,
                    exc,
                )
                raise
            # Exponential backoff with ±25% jitter.
            delay = min(max_delay, base_delay * (2 ** (attempt_index - 1)))
            jitter = delay * 0.25 * (2 * random.random() - 1)
            sleep(max(0.0, delay + jitter))
            logger.warning(
                "retry op=%s attempt=%d/%d transient=%s delay_s=%.3f error=%r",
                op_name,
                attempt_index,
                attempts,
                type(exc).__name__,
                delay + jitter,
                exc,
            )
    # Unreachable: the loop returns on success or raises on terminal/exhausted.
    assert last_exc is not None
    raise last_exc
