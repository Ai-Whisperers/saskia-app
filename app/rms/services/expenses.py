"""app/rms/services/expenses.py — Expense business logic.

Sprint 3.1: Expense CRUD + MonthlyClosure

Expense operations:
- create_expense()
- list_expenses()
- update_expense()
- void_expense()
- total_expenses_gs()

Standalone functions (not classes) for easier testing.
"""

from datetime import datetime
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.rms.models import Expense


# Validation errors
class ExpenseValidationError(ValueError):
    """Raised for invalid expense operations."""


# Valid enums
VALID_CATEGORIES = frozenset({"INGREDIENT", "RENT", "UTILITIES", "PAYROLL", "PACKAGING", "OTHER"})

VALID_RECURRING = frozenset({"once", "monthly", "quarterly", "yearly"})


def create_expense(
    db: Session,
    occurred_at: datetime,
    amount_gs: int,
    category: str,
    description: str | None = None,
    supplier_id: int | None = None,
    receipt_url: str | None = None,
    recurring_period: str | None = None,
    created_by: str | None = None,
) -> Expense:
    """Create a new expense.

    Args:
        db: Database session
        occurred_at: When the expense occurred (must be tz-aware)
        amount_gs: Amount in Guaraníes (must be > 0)
        category: Expense category
        description: Optional description
        supplier_id: Optional supplier ID
        receipt_url: Optional receipt link
        recurring_period: Optional recurring period ('once', 'monthly', etc.)
        created_by: Who created the expense

    Returns:
        Expense: Created expense record

    Raises:
        ExpenseValidationError: For invalid data
    """
    # Validate inputs
    if not occurred_at.tzinfo:
        raise ExpenseValidationError("tz-aware")

    if amount_gs <= 0:
        raise ExpenseValidationError("amount_gs must be > 0")

    if category not in VALID_CATEGORIES:
        raise ExpenseValidationError(f"category must be one of {VALID_CATEGORIES}")

    if recurring_period and recurring_period not in VALID_RECURRING:
        raise ExpenseValidationError(f"recurring_period must be one of {VALID_RECURRING}")

    # Create expense
    expense = Expense(
        occurred_at=occurred_at,
        amount_gs=amount_gs,
        category=category,
        description=description or "",
        supplier_id=supplier_id,
        receipt_url=receipt_url,
        recurring_period=recurring_period or "once",
        created_by=created_by,
    )

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def list_expenses(
    db: Session,
    limit: int = 100,
    category: str | None = None,
    supplier_id: int | None = None,
    include_voided: bool = False,
) -> List[Expense]:
    """List expenses with optional filtering.

    Args:
        db: Database session
        limit: Maximum number of results
        category: Filter by category (optional)
        supplier_id: Filter by supplier ID (optional)
        include_voided: Include voided expenses (default: False)

    Returns:
        List[Expense]: Matching expenses
    """
    query = db.query(Expense)

    if not include_voided:
        query = query.filter(Expense.is_voided.is_(False))

    if category:
        query = query.filter(Expense.category == category)

    if supplier_id:
        query = query.filter(Expense.supplier_id == supplier_id)

    return query.order_by(Expense.created_at.desc()).limit(limit).all()


def update_expense(
    db: Session,
    expense_id: int,
    description: str | None = None,
    amount_gs: int | None = None,
    category: str | None = None,
    receipt_url: str | None = None,
    recurring_period: str | None = None,
) -> Expense:
    """Update an expense.

    Args:
        db: Database session
        expense_id: ID of expense to update
        description: New description (optional)
        amount_gs: New amount (optional)
        category: New category (optional)
        receipt_url: New receipt URL (optional)
        recurring_period: New recurring period (optional)

    Returns:
        Expense: Updated expense

    Raises:
        ExpenseValidationError: If expense not found or is voided
    """
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise ExpenseValidationError(f"Expense {expense_id} not found")

    if expense.is_voided:
        raise ExpenseValidationError("Cannot update voided expense")

    # Apply updates
    if description is not None:
        expense.description = description
    if amount_gs is not None:
        if amount_gs <= 0:
            raise ExpenseValidationError("amount_gs must be > 0")
        expense.amount_gs = amount_gs
    if category is not None:
        if category not in VALID_CATEGORIES:
            raise ExpenseValidationError(f"category must be one of {VALID_CATEGORIES}")
        expense.expense_type = category
    if receipt_url is not None:
        expense.receipt_url = receipt_url
    if recurring_period is not None:
        if recurring_period not in VALID_RECURRING:
            raise ExpenseValidationError(f"recurring_period must be one of {VALID_RECURRING}")
        expense.recurring_period = recurring_period

    db.commit()
    db.refresh(expense)
    return expense


def void_expense(db: Session, expense_id: int, reason: str | None = None) -> None:
    """Void an expense (soft delete).

    Args:
        db: Database session
        expense_id: ID of expense to void
        reason: Reason for voiding (appended to description)

    Raises:
        ExpenseValidationError: If expense not found or already voided
    """
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise ExpenseValidationError(f"Expense {expense_id} not found")

    if expense.is_voided:
        raise ExpenseValidationError("Expense is already voided")

    # Mark as voided
    expense.is_voided = True
    reason_text = reason or "voided"
    expense.description = f"{expense.description} | voided: {reason_text}"

    db.commit()


def total_expenses_gs(db: Session, expenses: List[Expense]) -> int:
    """Calculate total amount from a list of expenses, skipping voided ones.

    Args:
        db: Database session (not used, but kept for interface consistency)
        expenses: List of expense objects

    Returns:
        int: Total amount in Guaraníes (voided expenses excluded)
    """
    return sum(exp.amount_gs for exp in expenses if not exp.is_voided)


def get_expense_types(db: Session) -> List[str]:
    """Get all unique expense types."""
    result = (
        db.query(func.distinct(Expense.expense_type)).filter(Expense.deleted_at.is_(None)).all()
    )

    return [row[0] for row in result]


def get_recurring_expenses(db: Session) -> List[Expense]:
    """Get all recurring expenses."""
    return (
        db.query(Expense)
        .filter(Expense.recurring_period != "once", Expense.deleted_at.is_(None))
        .all()
    )


__all__ = [
    "VALID_CATEGORIES",
    "VALID_RECURRING",
    "ExpenseValidationError",
    "create_expense",
    "get_expense_types",
    "get_recurring_expenses",
    "list_expenses",
    "total_expenses_gs",
    "update_expense",
    "void_expense",
]
