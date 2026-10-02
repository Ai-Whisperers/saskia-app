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

from datetime import date, datetime
from datetime import timezone
from typing import List
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import json

from app.rms.models_legacy import Expense
from app.rms.models.closure import MonthlyClosure


# Validation errors
class ClosureValidationError(ValueError):
    """Raised for invalid closure operations."""
    pass


class ClosureConflictError(ValueError):
    """Raised for conflicting closure operations."""
    pass


def get_closure(db: Session, period_yyyymm: str) -> MonthlyClosure | None:
    """Get closure for a specific period (YYYY-MM format)."""
    # Convert YYYY-MM to first day of month
    try:
        year, month = map(int, period_yyyymm.split('-'))
        month_date = date(year, month, 1)
    except ValueError:
        raise ClosureValidationError(f"Period must be YYYY-MM format, got: {period_yyyymm}")
    
    return db.query(MonthlyClosure).filter(
        MonthlyClosure.month == month_date
    ).first()


def list_closures(db: Session, limit: int = 100) -> List[MonthlyClosure]:
    """List closures, newest first."""
    return db.query(MonthlyClosure).order_by(
        MonthlyClosure.month.desc()
    ).limit(limit).all()


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
        year, month = map(int, period_yyyymm.split('-'))
        month_date = date(year, month, 1)
    except ValueError:
        raise ClosureValidationError(f"Period must be YYYY-MM format, got: {period_yyyymm}")
    
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
    
    total_expenses = db.query(
        func.sum(Expense.amount_gs).label('total')
    ).filter(
        Expense.occurred_at >= start_date,
        Expense.occurred_at < end_date,
        Expense.is_voided.is_(False)
    ).scalar() or 0
    
    # Create or update closure
    if existing:
        existing.closed_at = datetime.now(timezone.utc)
        existing.closed_by_user_id = user_id
        existing.total_expenses_gs = total_expenses
    else:
        closure = MonthlyClosure(
            month=month_date,
            total_expenses_gs=total_expenses,
            closed_at=datetime.now(timezone.utc),
            closed_by_user_id=user_id
        )
        db.add(closure)
        existing = closure
    
    db.commit()
    db.refresh(existing)
    return existing


def reopen_month(db: Session, period_yyyymm: str, reason: str, user_id: str | None = None) -> MonthlyClosure:
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
        raise ClosureValidationError("Reopen reason is required")
    
    closure = get_closure(db, period_yyyymm)
    if not closure:
        raise ClosureConflictError(f"No closure found for {period_yyyymm}")
    
    if closure.is_open:
        raise ClosureConflictError(f"Period {period_yyyymm} is not closed")
    
    closure.reopened_at = datetime.now(timezone.utc)
    closure.reopened_by_user_id = user_id
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
    # Convert period to date range
    try:
        year, month = map(int, period_yyyymm.split('-'))
        month_date = date(year, month, 1)
        
        # Validate month
        if month < 1 or month > 12:
            raise ClosureValidationError(f"Invalid month: {period_yyyymm}")
            
    except ValueError:
        raise ClosureValidationError(f"Period must be YYYY-MM format, got: {period_yyyymm}")
    
    # Calculate date range
    start_date = month_date
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    # Query expenses for the month
    expenses = db.query(Expense).filter(
        Expense.occurred_at >= start_date,
        Expense.occurred_at < end_date,
        Expense.is_voided.is_(False)
    ).all()
    
    # Calculate totals
    total_gs = sum(exp.amount_gs for exp in expenses)
    by_category = {}
    for exp in expenses:
        if exp.category not in by_category:
            by_category[exp.category] = 0
        by_category[exp.category] += exp.amount_gs
    
    return {
        "total_expenses_gs": total_gs,
        "expense_row_count": len(expenses),
        "expenses_by_category": by_category
    }


def create_closure(db: Session, period_yyyymm: str, total_expenses_gs: int, notes: str | None = None, user_id: str | None = None) -> MonthlyClosure:
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
        year, month = map(int, period_yyyymm.split('-'))
        month_date = date(year, month, 1)
    except ValueError:
        raise ClosureValidationError(f"Period must be YYYY-MM format, got: {period_yyyymm}")
    
    # Check for existing closure
    existing = db.query(MonthlyClosure).filter(
        MonthlyClosure.month == month_date
    ).first()
    
    if existing:
        raise ClosureConflictError(f"Closure for {period_yyyymm} already exists")
    
    # Create closure
    closure = MonthlyClosure(
        month=month_date,
        total_expenses_gs=total_expenses_gs,
        notes=notes,
        created_by_user_id=user_id,
        updated_by_user_id=user_id
    )
    
    db.add(closure)
    db.commit()
    db.refresh(closure)
    return closure


__all__ = [
    "ClosureValidationError",
    "ClosureConflictError", 
    "get_closure",
    "list_closures",
    "close_month",
    "reopen_month",
    "compute_month_totals",
    "create_closure"
]