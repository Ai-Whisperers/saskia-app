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
    get_closure,
    list_closures,
    reopen_month,
    create_closure
)
from .expenses import (
    ExpenseValidationError,
    VALID_CATEGORIES,
    VALID_RECURRING,
    create_expense,
    list_expenses,
    total_expenses_gs,
    update_expense,
    void_expense,
    get_expense_types,
    get_recurring_expenses
)

__all__ = [
    "ClosureConflictError",
    "ClosureValidationError", 
    "close_month",
    "compute_month_totals", 
    "get_closure",
    "list_closures",
    "reopen_month",
    "create_closure",
    "ExpenseValidationError",
    "VALID_CATEGORIES", 
    "VALID_RECURRING",
    "create_expense",
    "list_expenses",
    "total_expenses_gs",
    "update_expense", 
    "void_expense",
    "get_expense_types",
    "get_recurring_expenses"
]