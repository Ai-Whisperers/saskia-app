"""tests/test_expense_and_closure_services.py — Sprint 3.1 service tests.

Sprint 3.1 of the 2026-10-02 backend overhaul: tests the service layer for
Expense CRUD + MonthlyClosure. Pure DB-touching tests (no HTTP).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.rms.models import Expense
from app.rms.services.closures import (
    ClosureConflictError,
    ClosureValidationError,
    close_month,
    compute_month_totals,
    list_closures,
    reopen_month,
)
from app.rms.services.expenses import (
    VALID_CATEGORIES,
    VALID_RECURRING,
    ExpenseValidationError,
    create_expense,
    list_expenses,
    total_expenses_gs,
    update_expense,
    void_expense,
)


def _now() -> datetime:
    return datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


# ─── Service: Expense.create_expense ─────────────────────────────────────


def test_create_expense_minimal(session_factory):
    with session_factory() as s:
        exp = create_expense(s, occurred_at=_now(), amount_gs=50_000, category="RENT")
        s.commit()
        assert exp.id is not None
        assert exp.amount_gs == 50_000
        assert exp.category == "RENT"
        assert exp.recurring_period == "once"
        assert exp.is_voided is False
        assert exp.receipt_url is None


def test_create_expense_full(session_factory):
    with session_factory() as s:
        exp = create_expense(
            s,
            occurred_at=_now(),
            amount_gs=120_000,
            category="INGREDIENT",
            description="harina x 50kg",
            supplier_id=None,
            receipt_url="https://storage.example/receipts/abc.jpg",
            recurring_period="monthly",
            created_by="saskia",
        )
        s.commit()
        assert exp.receipt_url == "https://storage.example/receipts/abc.jpg"
        assert exp.recurring_period == "monthly"
        assert exp.created_by == "saskia"


def test_create_expense_rejects_negative_amount(session_factory):
    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="amount_gs must be > 0"):
            create_expense(s, occurred_at=_now(), amount_gs=-100, category="RENT")


def test_create_expense_rejects_bad_category(session_factory):
    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="category must be"):
            create_expense(s, occurred_at=_now(), amount_gs=100, category="BOGUS")


def test_create_expense_rejects_bad_recurring(session_factory):
    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="recurring_period must be"):
            create_expense(
                s, occurred_at=_now(), amount_gs=100, category="RENT", recurring_period="biweekly"
            )


def test_create_expense_requires_tz_aware_datetime(session_factory):
    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="tz-aware"):
            create_expense(
                s, occurred_at=datetime(2026, 10, 1, 12, 0), amount_gs=100, category="RENT"
            )


# ─── Service: Expense.list_expenses ──────────────────────────────────────


def test_list_expenses_default_excludes_voided(session_factory):
    with session_factory() as s:
        e1 = create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        e2 = create_expense(s, occurred_at=_now(), amount_gs=200, category="OTHER")
        s.commit()

    with session_factory() as s:
        rows = list_expenses(s)
        assert len(rows) == 2

    with session_factory() as s:
        void_expense(s, e2.id, reason="test")
        s.commit()

    with session_factory() as s:
        rows = list_expenses(s)
        assert len(rows) == 1
        assert rows[0].id == e1.id

    with session_factory() as s:
        rows = list_expenses(s, include_voided=True)
        assert len(rows) == 2


def test_list_expenses_filters_by_category(session_factory):
    with session_factory() as s:
        create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        create_expense(s, occurred_at=_now(), amount_gs=200, category="OTHER")
        create_expense(s, occurred_at=_now(), amount_gs=300, category="RENT")
        s.commit()

    with session_factory() as s:
        rows = list_expenses(s, category="RENT")
        assert len(rows) == 2


def test_list_expenses_filters_by_supplier(session_factory):
    from app.rms.models import Supplier

    with session_factory() as s:
        sup_a = Supplier(name="A", ruc="111")
        sup_b = Supplier(name="B", ruc="222")
        s.add_all([sup_a, sup_b])
        s.commit()
        create_expense(
            s, occurred_at=_now(), amount_gs=100, category="INGREDIENT", supplier_id=sup_a.id
        )
        create_expense(
            s, occurred_at=_now(), amount_gs=200, category="INGREDIENT", supplier_id=sup_b.id
        )
        create_expense(s, occurred_at=_now(), amount_gs=300, category="RENT")
        s.commit()

    with session_factory() as s:
        rows = list_expenses(s, supplier_id=sup_a.id)
        assert len(rows) == 1


# ─── Service: Expense.update_expense ─────────────────────────────────────


def test_update_expense_partial(session_factory):
    with session_factory() as s:
        e = create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT", description="old")
        s.commit()

    with session_factory() as s:
        updated = update_expense(s, e.id, description="new", amount_gs=250)
        s.commit()
        assert updated.description == "new"
        assert updated.amount_gs == 250
        assert updated.category == "RENT"


def test_update_expense_rejects_voided(session_factory):
    with session_factory() as s:
        e = create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        s.commit()

    with session_factory() as s:
        void_expense(s, e.id)
        s.commit()

    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="voided"):
            update_expense(s, e.id, amount_gs=200)


# ─── Service: Expense.void_expense ───────────────────────────────────────


def test_void_expense_keeps_row(session_factory):
    with session_factory() as s:
        e = create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        s.commit()

    with session_factory() as s:
        void_expense(s, e.id, reason="test")
        s.commit()

    with session_factory() as s:
        exp = s.get(Expense, e.id)
        assert exp is not None
        assert exp.is_voided is True
        assert "voided: test" in exp.description


def test_void_expense_double_void_raises(session_factory):
    with session_factory() as s:
        e = create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        s.commit()

    with session_factory() as s:
        void_expense(s, e.id)
        s.commit()

    with session_factory() as s:
        with pytest.raises(ExpenseValidationError, match="already voided"):
            void_expense(s, e.id)


# ─── Service: Expense.total_expenses_gs ──────────────────────────────────


def test_total_expenses_gs_skips_voided(session_factory):
    with session_factory() as s:
        create_expense(s, occurred_at=_now(), amount_gs=100, category="RENT")
        e2 = create_expense(s, occurred_at=_now(), amount_gs=200, category="OTHER")
        create_expense(s, occurred_at=_now(), amount_gs=300, category="RENT")
        s.commit()

    with session_factory() as s:
        void_expense(s, e2.id)
        s.commit()

    with session_factory() as s:
        rows = list_expenses(s, include_voided=True)
        assert total_expenses_gs(s, rows) == 400


# ─── Service: enums ──────────────────────────────────────────────────────


def test_valid_categories_set():
    assert VALID_CATEGORIES == frozenset(
        {"INGREDIENT", "RENT", "UTILITIES", "PAYROLL", "PACKAGING", "OTHER"}
    )


def test_valid_recurring_set():
    assert VALID_RECURRING == frozenset({"once", "monthly", "quarterly", "yearly"})


# ─── Service: Closure.compute_month_totals ───────────────────────────────


def test_compute_totals_no_expenses(session_factory):
    with session_factory() as s:
        totals = compute_month_totals(s, "2026-09")
        assert totals["total_expenses_gs"] == 0
        assert totals["expense_row_count"] == 0
        assert totals["expenses_by_category"] == {}


def test_compute_totals_with_expenses(session_factory):
    from datetime import timedelta

    sept_15_local = datetime(2026, 9, 15, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
    with session_factory() as s:
        create_expense(s, occurred_at=sept_15_local, amount_gs=100_000, category="RENT")
        create_expense(s, occurred_at=sept_15_local, amount_gs=50_000, category="UTILITIES")
        create_expense(s, occurred_at=sept_15_local, amount_gs=200_000, category="PAYROLL")
        e = create_expense(s, occurred_at=sept_15_local, amount_gs=999_999, category="OTHER")
        s.commit()

    with session_factory() as s:
        void_expense(s, e.id)
        s.commit()

    with session_factory() as s:
        totals = compute_month_totals(s, "2026-09")
        assert totals["total_expenses_gs"] == 350_000
        assert totals["expense_row_count"] == 3
        assert totals["expenses_by_category"]["RENT"] == 100_000
        assert totals["expenses_by_category"]["UTILITIES"] == 50_000
        assert totals["expenses_by_category"]["PAYROLL"] == 200_000


def test_compute_totals_excludes_other_months(session_factory):
    from datetime import timedelta

    aug_local = datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
    sept_local = datetime(2026, 9, 15, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
    with session_factory() as s:
        create_expense(s, occurred_at=aug_local, amount_gs=100, category="RENT")
        create_expense(s, occurred_at=sept_local, amount_gs=200, category="RENT")
        s.commit()

    with session_factory() as s:
        totals = compute_month_totals(s, "2026-09")
        assert totals["total_expenses_gs"] == 200


# ─── Service: Closure period validation ──────────────────────────────────


def test_period_validation_rejects_bad_format():
    with pytest.raises(ClosureValidationError, match="YYYY-MM"):
        compute_month_totals(_FakeSession(), "2026/09")
    with pytest.raises(ClosureValidationError, match="YYYY-MM"):
        compute_month_totals(_FakeSession(), "26-09")
    with pytest.raises(ClosureValidationError, match="YYYY-MM"):
        compute_month_totals(_FakeSession(), "")
    with pytest.raises(ClosureValidationError, match="YYYY-MM"):
        compute_month_totals(_FakeSession(), "2026-13")
    with pytest.raises(ClosureValidationError, match="YYYY-MM"):
        compute_month_totals(_FakeSession(), "2026-00")


# ─── Service: Closure close / reopen ─────────────────────────────────────


def test_close_month_creates_row(session_factory):
    with session_factory() as s:
        closure = close_month(s, "2026-09")
        s.commit()
        assert closure.id is not None
        assert closure.period_yyyymm == "2026-09"
        assert closure.closed_at is not None
        snap = json.loads(closure.snapshot_json)
        assert snap["period_yyyymm"] == "2026-09"


def test_close_month_double_close_raises(session_factory):
    with session_factory() as s:
        close_month(s, "2026-09")
        s.commit()

    with session_factory() as s:
        with pytest.raises(ClosureConflictError, match="already closed"):
            close_month(s, "2026-09")


def test_reopen_month_requires_reason(session_factory):
    with session_factory() as s:
        close_month(s, "2026-09")
        s.commit()

    with session_factory() as s:
        with pytest.raises(ClosureValidationError, match="reason is required"):
            reopen_month(s, "2026-09", reason="")


def test_reopen_month_unclosed_raises(session_factory):
    with session_factory() as s:
        with pytest.raises(ClosureConflictError, match="not closed"):
            reopen_month(s, "2026-09", reason="test")


def test_reopen_month_sets_audit_trail(session_factory):
    with session_factory() as s:
        close_month(s, "2026-09")
        s.commit()

    with session_factory() as s:
        reopened = reopen_month(s, "2026-09", reason="found a missing utility bill")
        s.commit()
        assert reopened.reopened_at is not None
        assert reopened.reopen_reason == "found a missing utility bill"


def test_reopen_month_double_reopen_raises(session_factory):
    with session_factory() as s:
        close_month(s, "2026-09")
        s.commit()

    with session_factory() as s:
        reopen_month(s, "2026-09", reason="first")
        s.commit()

    with session_factory() as s:
        with pytest.raises(ClosureConflictError, match="already reopened"):
            reopen_month(s, "2026-09", reason="second")


def test_close_after_reopen_updates_existing(session_factory):
    with session_factory() as s:
        close_month(s, "2026-09")
        s.commit()

    with session_factory() as s:
        reopen_month(s, "2026-09", reason="redo")
        s.commit()

    with session_factory() as s:
        # After reopen, close should work again — same row, updated.
        closure = close_month(s, "2026-09")
        s.commit()
        assert closure.reopened_at is None
        assert closure.reopen_reason is None


def test_list_closures_newest_first(session_factory):
    with session_factory() as s:
        close_month(s, "2026-08")
        close_month(s, "2026-09")
        close_month(s, "2026-10")
        s.commit()

    with session_factory() as s:
        rows = list_closures(s)
        assert [r.period_yyyymm for r in rows] == ["2026-10", "2026-09", "2026-08"]


# ─── helpers ──────────────────────────────────────────────────────────────


class _FakeSession:
    """Stub for tests that only exercise validation; never touch DB."""
