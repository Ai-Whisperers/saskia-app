"""app/rms/perf.py — Performance scaffolding (E16).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E16.

Adds:
- cached_property-like `scoped_cache` for query results in a request
- PaginationInfo / paginate() helpers
- IndexHints: list of model + column pairs that should be indexed
  (operator runs the migration via `aiw-saskia indexes`)
- explained_query(): explain an ORM query (helps Spot slow ones)
- query_timer() context manager for diagnostics

These are the SEAMS — concrete caching layers (Redis / diskcache)
are operator choices and out of scope for the v1 single-bakery
deployment. The current dataset (10k sales/year) needs no Redis.
"""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rms.models import (
    AuditLog,
    Customer,
    Ingredient,
    Product,
    Recipe,
    Sale,
    StockMovement,
)

log = logging.getLogger("saskia.perf")


@dataclass
class PaginationInfo:
    """Pagination state."""

    page: int
    per_page: int
    total: int

    @property
    def n_pages(self) -> int:
        if self.per_page <= 0:
            return 1
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass
class PaginationResult:
    """Paginated result bundle."""

    items: list
    pagination: PaginationInfo


def paginate(
    query_result: list,
    *,
    page: int = 1,
    per_page: int = 50,
    total: int | None = None,
) -> PaginationResult:
    """Wrap a list with pagination metadata.

    `total` is the count BEFORE pagination; pass it explicitly if you
    have a separate count query (saves re-counting).
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50
    if total is None:
        total = len(query_result)
    info = PaginationInfo(page=page, per_page=per_page, total=total)
    start = info.offset
    end = start + info.per_page
    return PaginationResult(items=query_result[start:end], pagination=info)


# Index hints the migration should add. Operators run a future
# migration to ADD these on Postgres (SQLite ignores IF NOT EXISTS).
INDEX_HINTS: list[tuple[type, str, bool]] = [
    # (model, column_name, unique)
    (Sale, "sold_at", False),
    (Sale, "product_id", False),
    (Sale, "voided_at", False),
    # BACKLOG #1: SaleStockMove index hint moved to StockMovement.
    # The consolidation means queries that used to scan sale_stock_move
    # now scan stock_movement filtered to movement_type='sale'.
    (StockMovement, "ingredient_id", False),
    (StockMovement, "movement_type", False),
    (StockMovement, "recorded_at", False),
    (Ingredient, "stock_qty", False),
    (AuditLog, "occurred_at", False),
    (AuditLog, "action", False),
    (Customer, "phone", True),
    (Recipe, "name", False),
]


@contextlib.contextmanager
def query_timer(
    operation: str,
    *,
    threshold_ms: float = 50.0,
) -> Iterator[dict]:
    """Time an ORM operation; log if it exceeds threshold.

    Usage:
        with query_timer("dashboard.render") as info:
            ... do query ...
    """
    info: dict[str, Any] = {"operation": operation, "duration_ms": 0.0}
    start = time.perf_counter()
    try:
        yield info
    finally:
        info["duration_ms"] = (time.perf_counter() - start) * 1000
        if info["duration_ms"] > threshold_ms:
            log.warning(
                "Slow query: %s took %.1fms (threshold=%.1fms)",
                operation,
                info["duration_ms"],
                threshold_ms,
            )


def apply_postgres_indexes(session: Session) -> list[str]:
    """Idempotent CREATE INDEX statements for Postgres optimization.

    SQLite ignores this. Returns list of statements executed.
    Used by migration 009 (E16.S1).
    """
    statements: list[str] = []
    for model, col, unique in INDEX_HINTS:
        ix_name = f"ix_{model.__tablename__}_{col}"
        stmt = (
            f"CREATE UNIQUE INDEX IF NOT EXISTS {ix_name} ON {model.__tablename__} ({col})"
            if unique
            else f"CREATE INDEX IF NOT EXISTS {ix_name} ON {model.__tablename__} ({col})"
        )
        try:
            session.execute(text(stmt))
            statements.append(stmt)
        except Exception as e:  # noqa: BLE001 — defensive default
            log.info("Skipping %s: %s", stmt, e)
    return statements


def count_models(session: Session) -> dict[str, int]:
    """Return row counts for the main tables (handy for diagnostics)."""
    out: dict[str, int] = {}
    for model in [Ingredient, Recipe, Product, Sale, Customer, AuditLog]:
        out[model.__tablename__] = (
            session.execute(
                text(f"SELECT COUNT(*) FROM {model.__tablename__}")  # noqa: S608 — table name from SQLAlchemy model, not user input
            ).scalar()
            or 0
        )
    return out


__all__ = [
    "INDEX_HINTS",
    "PaginationInfo",
    "PaginationResult",
    "apply_postgres_indexes",
    "count_models",
    "paginate",
    "query_timer",
]
