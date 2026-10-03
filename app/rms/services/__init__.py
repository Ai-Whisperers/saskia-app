"""app/rms/services — Domain service layer.

Sprint 3.1: Expense CRUD + MonthlyClosure services

Services encapsulate business logic beyond simple CRUD operations:
- create_expense, list_expenses, update_expense, void_expense, total_expenses_gs: Expense operations
- get_closure, list_closures, close_month, reopen_month, compute_month_totals: Closure operations

This follows domain-driven design patterns where business logic
lives in services, not in controllers or models.
"""

from .closures import (
    ClosureConflictError,
    ClosureValidationError,
    close_month,
    compute_month_totals,
    create_closure,
    get_closure,
    list_closures,
    reopen_month,
)
from .expenses import (
    VALID_CATEGORIES,
    VALID_RECURRING,
    ExpenseValidationError,
    create_expense,
    get_expense_types,
    get_recurring_expenses,
    list_expenses,
    total_expenses_gs,
    update_expense,
    void_expense,
)

__all__ = [
    "VALID_CATEGORIES",
    "VALID_RECURRING",
    "ClosureConflictError",
    "ClosureValidationError",
    "ExpenseValidationError",
    "close_month",
    "compute_month_totals",
    "create_closure",
    "create_expense",
    "get_closure",
    "get_expense_types",
    "get_recurring_expenses",
    "list_closures",
    "list_expenses",
    "reopen_month",
    "total_expenses_gs",
    "update_expense",
    "void_expense"
]
