"""app/rms/errors.py — Production-grade exception hierarchy.

All errors carry:
- message (user-facing, localized)
- reason_code (programmatic, snake_case, for i18n lookup)
- context (dict of structured details — request_id, entity ids, etc.)
- cause (the underlying exception, if any)

Why a hierarchy?
- Routers can `raise NotFound("pedido", id=42)` and the global
  exception handler maps it to a 404 with a consistent JSON shape.
- The audit log picks up the reason_code automatically, making
  incident triage a one-step SQL query.
- User-facing error pages render the `message` in Spanish (vos form).

Error category → HTTP status:
  AppError         (400, generic bad input)
    BadRequest      (400, generic bad input)
    ValidationError (422, schema validation failed)
    NotFound        (404, entity not found)
    AlreadyExists   (409, unique constraint)
    Forbidden       (403, RBAC denies)
    Unauthenticated (401, no session)
    Conflict        (409, business rule)
    RateLimited     (429, too many requests)
  DataIntegrityError (500, FK / constraint violation)
  DependencyError   (502/503, upstream failed)
  AppInternalError  (500, unexpected)

This mirrors what a real production team would do: every error has a
typed code that ops can grep for, a localized message that support can
show to the user, and a context dict for log aggregation.
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base for all expected, recoverable application errors.

    Carries user-facing message, programmatic reason_code, and a
    structured context dict that gets logged but NOT shown verbatim
    to the user (the context might contain PII or secrets).
    """

    status_code: int = 400
    reason_code: str = "app_error"

    # Map HTTP status codes → (Spanish title, default Spanish message)
    # used by the 4xx.html error template (BACKLOG #48). The exception's
    # own `message` field overrides the default when present.
    _STATUS_TITLES: dict[int, tuple[str, str]] = {
        400: ("Solicitud inválida", "La solicitud tiene datos incorrectos."),
        401: ("No autenticado", "Iniciá sesión para continuar."),
        403: ("Sin permiso", "No tenés permiso para hacer esto."),
        404: ("No encontrado", "El recurso que buscás no existe."),
        409: ("Conflicto", "La operación entra en conflicto con el estado actual."),
        422: ("Datos inválidos", "Revisá los campos marcados."),
        429: ("Demasiadas solicitudes", "Esperá un momento antes de volver a intentar."),
    }

    def __init__(
        self,
        message: str,
        *,
        reason_code: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        if reason_code is not None:
            self.reason_code = reason_code
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        if self.cause:
            return f"{self.message} (caused by {type(self.cause).__name__}: {self.cause})"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "type": self.__class__.__name__,
            "status": self.status_code,
            "reason": self.reason_code,
            "context": self.context,
        }


# ─── 4xx Client errors ────────────────────────────────────────────


class BadRequest(AppError):
    """Generic 400: malformed request that doesn't fit other categories."""
    status_code = 400
    reason_code = "bad_request"


class ValidationError(AppError):
    """422: Pydantic / schema validation failure."""
    status_code = 422
    reason_code = "validation_failed"


class NotFound(AppError):
    """404: requested entity doesn't exist or user can't see it."""
    status_code = 404
    reason_code = "not_found"

    def __init__(
        self,
        entity: str,
        id: Any = None,
        *,
        context: dict[str, Any] | None = None,
        message: str | None = None,
    ):
        if message is None:
            message = f"{entity} #{id} no existe" if id is not None else f"{entity} no encontrado"
        ctx = {"entity": entity, **(context or {})}
        if id is not None:
            ctx["id"] = str(id)
        super().__init__(message, reason_code=f"{entity}_not_found", context=ctx)
        self.entity = entity
        self.entity_id = id


class AlreadyExists(AppError):
    """409: unique constraint violation."""
    status_code = 409
    reason_code = "already_exists"


class Conflict(AppError):
    """409: business rule conflict (e.g. trying to delete a referenced entity)."""
    status_code = 409
    reason_code = "conflict"


class Unauthenticated(AppError):
    """401: no session or session expired."""
    status_code = 401
    reason_code = "unauthenticated"


class Forbidden(AppError):
    """403: RBAC denies this user."""
    status_code = 403
    reason_code = "forbidden"


class RateLimited(AppError):
    """429: too many requests."""
    status_code = 429
    reason_code = "rate_limited"


# ─── 5xx Server errors ────────────────────────────────────────────


class DataIntegrityError(AppError):
    """500: DB constraint, FK, or migration mismatch."""
    status_code = 500
    reason_code = "data_integrity_error"


class DependencyError(AppError):
    """502/503: an external dependency failed (Drive, bank feed, etc.)."""
    status_code = 502
    reason_code = "dependency_unavailable"


class AppInternalError(AppError):
    """500: unexpected internal failure."""
    status_code = 500
    reason_code = "internal_error"


# ─── Mapping helpers ──────────────────────────────────────────────


def to_http_exception(err: AppError) -> object:
    """Convert an AppError to a FastAPI HTTPException with our extended payload."""
    from fastapi import HTTPException
    return HTTPException(
        status_code=err.status_code,
        detail=err.to_dict(),
        headers={"X-Reason-Code": err.reason_code},
    )


# Module-level alias for the status title map (BACKLOG #48). The 4xx
# error template looks up a (Spanish title, default message) tuple by
# HTTP status code; raising the class attribute to module scope keeps
# the global exception handler importable as a single name.
_ERROR_TITLES: dict[int, tuple[str, str]] = AppError._STATUS_TITLES
