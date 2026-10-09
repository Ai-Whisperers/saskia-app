"""app/rms/services/closures.py — MonthlyClosure business logic.

Sprint 3.1: Expense CRUD + MonthlyClosure

MonthlyClosure operations:
- create_closure()
- get_closure()
- list_closures()
- close_month()
- reopen_month()
- compute_month_totals()

Standalone functions (not classes) for easier testing.
"""

import json
from datetime import date, datetime, timezone
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.rms.models.closure import MonthlyClosure
from app.rms.models_legacy import Expense


# Validation errors
class ClosureValidationError(ValueError):
    """Raised for invalid closure operations."""


class ClosureConflictError(ValueError):
    """Raised for conflicting closure operations."""


def get_closure(db: Session, period_yyyymm: str) -> MonthlyClosure | None:
    """Get closure for a specific period (YYYY-MM format)."""
    return db.query(MonthlyClosure).filter(MonthlyClosure.period_yyyymm == period_yyyymm).first()


def list_closures(db: Session, limit: int = 100) -> List[MonthlyClosure]:
    """List closures, newest first."""
    return db.query(MonthlyClosure).order_by(MonthlyClosure.period_yyyymm.desc()).limit(limit).all()


def close_month(db: Session, period_yyyymm: str, user_id: str | None = None) -> MonthlyClosure:
    """Close a monthly period.

    Args:
        db: Database session
        period_yyyymm: Period in YYYY-MM format
        user_id: User performing the closure

    Returns:
        MonthlyClosure: Created or updated closure

    Raises:
        ClosureValidationError: For invalid period format
        ClosureConflictError: If period is already closed
    """
    # Convert period to date and calculate totals
    try:
        year, month = map(int, period_yyyymm.split("-"))
        month_date = date(year, month, 1)
    except ValueError:
        raise ClosureValidationError(
            f"Period must be YYYY-MM format, got: {period_yyyymm}"
        ) from None

    # Check if already closed
    existing = get_closure(db, period_yyyymm)
    if existing and existing.is_closed:
        raise ClosureConflictError(f"Period {period_yyyymm} is already closed")

    # Calculate totals for the month
    start_date = month_date
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    total_expenses = (
        db.query(func.sum(Expense.amount_gs).label("total"))
        .filter(
            Expense.occurred_at >= start_date,
            Expense.occurred_at < end_date,
            Expense.is_voided.is_(False),
        )
        .scalar()
        or 0
    )

    # Create or update closure
    snapshot = json.dumps(
        {
            "period_yyyymm": period_yyyymm,
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "total_expenses_gs": total_expenses,
        }
    )
    if existing:
        existing.closed_at = datetime.now(timezone.utc)
        existing.closed_by_user_id = user_id
        existing.total_expenses_gs = total_expenses
        existing.snapshot_json = snapshot
        # Reset reopen info when closing again
        existing.reopened_at = None
        existing.reopened_by_user_id = None
        existing.reopen_reason = None
    else:
        closure = MonthlyClosure(
            period_yyyymm=period_yyyymm,
            total_expenses_gs=total_expenses,
            closed_at=datetime.now(timezone.utc),
            closed_by_user_id=user_id,
            snapshot_json=snapshot,
        )
        db.add(closure)
        existing = closure

    db.commit()
    db.refresh(existing)
    return existing


def reopen_month(
    db: Session, period_yyyymm: str, reason: str, user_id: str | None = None
) -> MonthlyClosure:
    """Reopen a closed monthly period.

    Args:
        db: Database session
        period_yyyymm: Period in YYYY-MM format
        reason: Reason for reopening (required)
        user_id: User performing the reopen

    Returns:
        MonthlyClosure: Updated closure

    Raises:
        ClosureValidationError: For invalid format or missing reason
        ClosureConflictError: If period is not closed
    """
    if not reason:
        raise ClosureValidationError("reason is required")

    closure = get_closure(db, period_yyyymm)
    if not closure:
        raise ClosureConflictError(f"Period {period_yyyymm} is not closed")

    # If already reopened, that's the conflict (check before "is_open")
    if closure.reopened_at is not None:
        raise ClosureConflictError(f"Period {period_yyyymm} is already reopened")

    if closure.is_open:
        raise ClosureConflictError(f"Period {period_yyyymm} is not closed")

    closure.reopened_at = datetime.now(timezone.utc)
    closure.reopened_by_user_id = user_id
    closure.reopen_reason = reason
    closure.closed_at = None
    closure.closed_by_user_id = None

    db.commit()
    db.refresh(closure)
    return closure


def compute_month_totals(db: Session, period_yyyymm: str) -> dict:
    """Calculate expense totals for a month.

    Args:
        db: Database session
        period_yyyymm: Period in YYYY-MM format

    Returns:
        dict: With keys: total_expenses_gs, expense_row_count, expenses_by_category

    Raises:
        ClosureValidationError: For invalid period format
    """
    start_date, end_date = _parse_period_range(period_yyyymm)
    expenses = _fetch_expenses_in_range(db, start_date, end_date)
    return _build_expense_totals(expenses)


def _parse_period_range(period_yyyymm: str) -> tuple[date, date]:
    """Parse a YYYY-MM period string and return the (start, end) date range.

    Extracted from compute_month_totals to reduce complexity.
    """
    try:
        year, month = map(int, period_yyyymm.split("-"))
        if month < 1 or month > 12:
            raise ClosureValidationError(f"Invalid month: {period_yyyymm}")
        if year < 1900 or year > 3000:
            raise ClosureValidationError(f"Invalid year: {period_yyyymm}")
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, month + 1, 1)
        return start, end
    except (ValueError, AttributeError):
        raise ClosureValidationError(
            f"Period must be YYYY-MM format, got: {period_yyyymm}"
        ) from None


def _fetch_expenses_in_range(db: Session, start_date: date, end_date: date) -> list:
    """Fetch non-voided expenses in the [start_date, end_date) range.

    Extracted from compute_month_totals to reduce complexity.
    """
    return (
        db.query(Expense)
        .filter(
            Expense.occurred_at >= start_date,
            Expense.occurred_at < end_date,
            Expense.is_voided.is_(False),
        )
        .all()
    )


def _build_expense_totals(expenses: list) -> dict:
    """Build the totals dict from a list of expenses.

    Extracted from compute_month_totals to reduce complexity.
    """
    total_gs = sum(exp.amount_gs for exp in expenses)
    by_category: dict = {}
    for exp in expenses:
        by_category.setdefault(exp.category, 0)
        by_category[exp.category] += exp.amount_gs
    return {
        "total_expenses_gs": total_gs,
        "expense_row_count": len(expenses),
        "expenses_by_category": by_category,
    }


def create_closure(
    db: Session,
    period_yyyymm: str,
    total_expenses_gs: int,
    notes: str | None = None,
    user_id: str | None = None,
) -> MonthlyClosure:
    """Create a new closure record.

    Args:
        db: Database session
        period_yyyymm: Period in YYYY-MM format
        total_expenses_gs: Total expenses for the period
        notes: Optional notes
        user_id: User creating the closure

    Returns:
        MonthlyClosure: Created closure

    Raises:
        ClosureValidationError: For invalid period format
        ClosureConflictError: If closure already exists
    """
    # Convert period to date
    try:
        year, month = map(int, period_yyyymm.split("-"))
        date(year, month, 1)
    except ValueError:
        raise ClosureValidationError(
            f"Period must be YYYY-MM format, got: {period_yyyymm}"
        ) from None

    # Check for existing closure
    existing = (
        db.query(MonthlyClosure).filter(MonthlyClosure.period_yyyymm == period_yyyymm).first()
    )

    if existing:
        raise ClosureConflictError(f"Closure for {period_yyyymm} already exists")

    # Create closure
    closure = MonthlyClosure(
        period_yyyymm=period_yyyymm,
        total_expenses_gs=total_expenses_gs,
        closed_by_user_id=user_id,
    )

    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure


__all__ = [
    "ClosureConflictError",
    "ClosureValidationError",
    "close_month",
    "compute_month_totals",
    "create_closure",
    "get_closure",
    "list_closures",
    "reopen_month",
]
