"""tests/test_expense_migration_082.py — Phase 14 (2026-10-01).

Tests:
- Migration 082 creates the expense table with expected columns
- daily_summary() now reports real expenses (was 0 before)
- expenses_in_window() respects the [start, end) window
- Voided expenses are excluded from aggregates
- expenses_in_window returns 0 when there are no rows
"""

import datetime as dt

from sqlalchemy import create_engine

from app.rms.accounting import daily_summary, expenses_in_window
from app.rms.config import DB_PATH
from app.rms.db import init_db
from app.rms.models import Expense


def test_expense_table_exists_with_expected_columns():
    """Migration 082 created the table with the expected schema."""
    engine = create_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    from sqlalchemy import inspect

    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("expense")}
    expected = {
        "id",
        "occurred_at",
        "category",
        "description",
        "amount_gs",
        "is_voided",
        "created_at",
        "created_by",
        "supplier_id",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_daily_summary_now_subtracts_real_expenses(session_factory):
    """Two $5,000 expenses in the same UTC day produce
    `expenses_placeholder_gs=10_000` in the daily summary."""
    today = dt.datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
    with session_factory() as s:
        s.add(
            Expense(
                occurred_at=today,
                category="RENT",
                description="local alquiler",
                amount_gs=5_000_000,  # 5M Gs
            )
        )
        s.add(
            Expense(
                occurred_at=today,
                category="UTILITIES",
                description="ANDE luz",
                amount_gs=2_000_000,  # 2M Gs
            )
        )
        s.commit()

    with session_factory() as s:
        ds = daily_summary(s, today)
    # We just need to confirm the field is wired; even with zero
    # sales in the test day, the expenses field must be populated.
    assert ds.expenses_placeholder_gs == 7_000_000, (
        f"expected 7_000_000, got {ds.expenses_placeholder_gs}"
    )


def test_expenses_in_window_end_exclusive(session_factory):
    """`expenses_in_window(start, end)` is half-open [start, end)."""
    morning = dt.datetime(2026, 5, 1, 8, 0, 0)
    next_day = dt.datetime(2026, 5, 2, 0)
    with session_factory() as s:
        s.add(Expense(occurred_at=morning, category="OTHER", description="a", amount_gs=1_000_000))
        # At exactly `next_day`: NOT in [morning, next_day)
        s.add(Expense(occurred_at=next_day, category="OTHER", description="b", amount_gs=9_000_000))
        s.commit()

    with session_factory() as s:
        total = expenses_in_window(s, start=morning, end=next_day)
    assert total == 1_000_000


def test_voided_expenses_excluded(session_factory):
    """expenses_in_window excludes rows with is_voided=True by default."""
    now = dt.datetime.utcnow()
    with session_factory() as s:
        s.add(Expense(occurred_at=now, category="OTHER", description="real", amount_gs=1_000_000))
        s.add(
            Expense(
                occurred_at=now,
                category="OTHER",
                description="void",
                amount_gs=999_999_999,
                is_voided=True,
            )
        )
        s.commit()

    with session_factory() as s:
        total = expenses_in_window(s, start=now, end=now + dt.timedelta(days=1))
    assert total == 1_000_000

    # But if you opt out, voided rows are summed too
    with session_factory() as s:
        total_with_void = expenses_in_window(
            s,
            start=now,
            end=now + dt.timedelta(days=1),
            exclude_voided=False,
        )
    assert total_with_void == 1_000_000 + 999_999_999


def test_expenses_in_window_returns_zero_when_empty(session_factory):
    """Empty DB → 0, never None or fail."""
    far_past = dt.datetime(2000, 1, 1)
    with session_factory() as s:
        total = expenses_in_window(s, start=far_past, end=far_past + dt.timedelta(days=1))
    assert total == 0
