"""app/rms/schemas.py — Pydantic 2 request models for state-changing endpoints.

Why: raw form parsing lets bad data through (negative discounts, huge
quantities, missing fields). Pydantic rejects at the validation layer
(FastAPI returns 422) before any business logic runs.

Each model is a thin wrapper over FastAPI's `Form(...)` constraints.
We *could* use full Pydantic BaseModels with `as_form()` parsing, but
that adds complexity. FastAPI's parameter-level `Form(..., gt=0)`
constraints are simpler and explicit.
"""
from __future__ import annotations

MAX_QTY = 1_000_000  # sanity cap — never selling a million of anything
MAX_DISCOUNT_GS = 100_000_000  # 100M Gs. = $14,000 USD discount upper bound
ALLOWED_PAYMENT_METHODS = frozenset({
    "efectivo",
    "transferencia",
    "qr",
    "tarjeta",
    "otro",
})

# Display order for the /ventas form-select. `efectivo` is the most
# common sale type for Saskia (per her Ciudad del Este workflow) so
# it sits at the top.
PAYMENT_METHODS_DISPLAY: tuple[str, ...] = (
    "efectivo",
    "transferencia",
    "qr",
    "tarjeta",
    "otro",
)
PAYMENT_METHOD_DEFAULT = "efectivo"


# Re-export common constants. Routers import these for validation.
__all__ = [
    "MAX_QTY",
    "MAX_DISCOUNT_GS",
    "ALLOWED_PAYMENT_METHODS",
    "PAYMENT_METHODS_DISPLAY",
    "PAYMENT_METHOD_DEFAULT",
]
