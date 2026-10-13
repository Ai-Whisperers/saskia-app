"""app/rms/sentry.py — Sentry level mapping for AppError.

Extracted (S2 robustness PR5, 2026-10-13) from the inline status-code check
in app/rms/notify.py:sentry_before_send and grown into a tested helper so
the 13 AppError subclasses get a deterministic Sentry level:

  - 4xx AppErrors (NotFound, ValidationError, BadRequest, etc.) → "warning"
    so the operator's Sentry inbox isn't polluted by user-input noise.
  - 5xx AppErrors (DataIntegrityError, DependencyError, AppInternalError,
    and their domain subclasses) → "error" (or higher) so they page on
    duty.

Why a dedicated module?
  - test_sentry_telegram_wiring.py already locks the wiring at the init
    block in app/rms/main.py. The level mapping is a separate concern:
    shipped as a pure function so tests can parametrize every subclass
    without standing up the SDK.
  - Keeps notify.py focused on the Telegram side-effect; sentry.py owns
    the level policy.

Public surface:
  - sentry_level_for(exc: Exception) -> str
        Return the Sentry level string ("warning" | "error" | "fatal")
        that should be applied to the event whose exception is `exc`.

Why "warning" for 4xx:
  Sentry defines "warning" as "informational message, no action required"
  and "error" as "an exception that the app couldn't recover from".
  User-driven 4xx (NotFound, ValidationError, Forbidden) fit "warning":
  the app is responding correctly, the user typed something wrong. 5xx
  server-side faults (DB integrity, dependency down, internal bug) are
  real outages — they go through "error" so on-call gets pinged.

The function has no Sentry SDK import — it works on plain Python
exception objects so unit tests can call it without `import sentry_sdk`.
The actual `before_send` hook in app/rms/notify.py consults this helper
to set the event's "level" field before Sentry stores it.
"""

from __future__ import annotations

from typing import Final


# Avoid importing at module top — ``app.rms.errors`` is the leaf import
# and doesn't pull in anything heavy, but a defensive local import keeps
# this module zero-dep for unit tests.
def _resolve_status(exc: Exception) -> int | None:
    """Return ``exc.status_code`` if it's an AppError, else None.

    AppError instances carry an integer HTTP status (subclasses can
    override ``status_code``). For non-AppError exceptions we have no
    canonical mapping, so we return None and let the caller fall back
    to the Sentry default ("error" for ``capture_exception``).

    Imported lazily to keep this module dependency-free for tests.
    """
    from app.rms.errors import AppError

    if isinstance(exc, AppError) and isinstance(getattr(exc, "status_code", None), int):
        return exc.status_code
    return None


# Sentry-defined levels (see sentry-sdk's ``SeverityLevel`` enum):
#   "fatal"  — app is broken, needs immediate intervention
#   "error"  — recoverable exception, on-call should look
#   "warning" — informational, no action required
#   "info"   — debug breadcrumbs only
#   "debug"  — verbose dev-time noise
#
# Thresholds: anything below 500 is by definition a client mistake from
# the HTTP standpoint, so it never deserves "error" in Sentry. Anything
# >= 500 is an actual server fault and warrants "error" (the operator
# can still promote to "fatal" manually in the alert rule). We do NOT
# map anything to "fatal" here — Sentry does that automatically for
# certain unhandled-exception defaults if the operator configures it.

# 4xx family → "warning"
_APPERROR_4XX_LEVEL: Final[str] = "warning"
# 5xx family → "error"
_APPERROR_5XX_LEVEL: Final[str] = "error"
# Default for non-AppError exceptions (untyped RuntimeError, KeyError, etc.)
_DEFAULT_LEVEL: Final[str] = "error"


def sentry_level_for(exc: Exception) -> str:
    """Return the Sentry level string for the given exception.

    Mapping:

    =====================  ======================================  =====
    Exception class        Rule                                    Level
    =====================  ======================================  =====
    ``AppError`` subclass  ``status_code < 500`` (4xx user-input)  ``"warning"``
    ``AppError`` subclass  ``status_code >= 500`` (server fault)   ``"error"``
    anything else          Sentry default (untyped exception)      ``"error"``
    =====================  ======================================  =====

    4xx examples: NotFound, MenuNotFound (subclass), ValidationError,
    RecipeValidationError (subclass), BadRequest, AlreadyExists,
    Conflict, EODClosedError (subclass), FiadoError (subclass),
    CashSessionError (subclass), ClosureError (subclass),
    ExpenseError (subclass), RefundError (subclass), Unauthenticated,
    Forbidden, RateLimited.

    5xx examples: DataIntegrityError, RecipeTreeError (subclass),
    DependencyError, LLMError (subclass), StorageError (subclass),
    AppInternalError, TenantError, RollbackError (subclass).

    The base :class:`AppError` is unreachable from real code paths
    (every call site uses a 4xx/5xx subclass), but for completeness the
    function returns the 4xx default ("warning") for it because the
    default ``status_code`` is 400.

    This function is pure — no Sentry SDK import, no side effects, no
    I/O — so the unit tests parametrize it cheaply.
    """
    status = _resolve_status(exc)
    if status is None:
        return _DEFAULT_LEVEL
    if status >= 500:
        return _APPERROR_5XX_LEVEL
    return _APPERROR_4XX_LEVEL


__all__ = ["sentry_level_for"]
