"""tests/test_monthly_closure_and_expense_model.py — Sprint 3.1 schema pin.

Sprint 3.1 of the 2026-10-02 backend overhaul: pins the new schema additions
(Expense.receipt_url + recurring_period, MonthlyClosure table, migrations
085 + 086).

These are model-level pinning tests (no HTTP). The HTTP/service layer
follows in the next Sprint 3.1 commit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest


# ─── Model: Expense extensions ────────────────────────────────────────────


def test_expense_model_has_receipt_url_column():
    """Expense must expose receipt_url (BACKLOG #15)."""
    from app.rms.models import Expense

    assert "receipt_url" in Expense.__table__.columns


def test_expense_model_has_recurring_period_column():
    """Expense must expose recurring_period (BACKLOG #15)."""
    from app.rms.models import Expense

    assert "recurring_period" in Expense.__table__.columns


def test_expense_recurring_period_default_is_once():
    """recurring_period defaults to 'once' so existing rows are valid."""
    from app.rms.models import Expense

    col = Expense.__table__.columns["recurring_period"]
    assert col.default is not None
    assert col.default.arg == "once"


def test_expense_recurring_period_check_constraint():
    """recurring_period must be one of once/monthly/quarterly/yearly."""
    from app.rms.models import Expense

    check_constraints = [
        c for c in Expense.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any(
        "recurring_period" in str(c.sqltext)
        for c in check_constraints
    ), "Missing recurring_period check constraint on Expense"


# ─── Model: MonthlyClosure ────────────────────────────────────────────────


def test_monthly_closure_model_exists():
    """MonthlyClosure model must exist for cierres mensuales."""
    from app.rms.models import MonthlyClosure

    assert MonthlyClosure is not None
    assert MonthlyClosure.__tablename__ == "monthly_closure"


def test_monthly_closure_required_columns():
    """MonthlyClosure must have the 12 expected columns."""
    from app.rms.models import MonthlyClosure

    expected = {
        "id", "period_yyyymm", "closed_at", "closed_by_user_id",
        "total_iva_gs", "total_revenue_gs", "total_cogs_gs",
        "total_expenses_gs", "net_gs", "snapshot_json",
        "reopened_at", "reopen_reason",
    }
    actual = set(MonthlyClosure.__table__.columns.keys())
    missing = expected - actual
    assert not missing, f"MonthlyClosure missing columns: {missing}"


def test_monthly_closure_period_is_unique():
    """One row per period_yyyymm — enforces idempotent close."""
    from app.rms.models import MonthlyClosure

    # The unique constraint is at the column level via unique=True
    col = MonthlyClosure.__table__.columns["period_yyyymm"]
    assert col.unique is True


def test_monthly_closure_period_format_check():
    """period_yyyymm must be exactly 7 chars with a dash at position 5."""
    from app.rms.models import MonthlyClosure

    check_constraints = [
        c for c in MonthlyClosure.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any(
        "length(period_yyyymm)" in str(c.sqltext)
        for c in check_constraints
    ), "Missing period format check constraint"


# ─── Migrations ───────────────────────────────────────────────────────────


def test_migrations_085_and_086_are_registered():
    """Both migrations must be in the MIGRATIONS dict."""
    from app.rms.db import MIGRATIONS

    assert 85 in MIGRATIONS, "migration 085 not registered"
    assert 86 in MIGRATIONS, "migration 086 not registered"


def test_migration_085_is_callable():
    """Migration 085 must be callable and have docstring."""
    from app.rms.db import MIGRATIONS

    m = MIGRATIONS[85]
    assert callable(m)
    assert m.__doc__, "migration 085 missing docstring"


def test_migration_086_is_callable():
    """Migration 086 must be callable and have docstring."""
    from app.rms.db import MIGRATIONS

    m = MIGRATIONS[86]
    assert callable(m)
    assert m.__doc__, "migration 086 missing docstring"


def test_migration_085_idempotent_via_prag_table_info():
    """The 085 implementation must be idempotent (PRAGMA table_info gate)."""
    # Import the underlying module, not the db.py re-export
    import app.rms.migrations._085_expense_receipt_recurring as m085

    src = open(m085.__file__).read()
    assert "PRAGMA table_info" in src, (
        "085 must use PRAGMA table_info to be idempotent"
    )


def test_migration_086_creates_monthly_closure_table():
    """The 086 implementation must CREATE TABLE monthly_closure."""
    import app.rms.migrations._086_monthly_closure as m086

    src = open(m086.__file__).read()
    assert "CREATE TABLE" in src and "monthly_closure" in src, (
        "086 must CREATE TABLE monthly_closure"
    )


# ─── Schema version ──────────────────────────────────────────────────────


def test_current_schema_version_is_88():
    """Sprint 3.1 (85/86) + Sprint 3.2 (87/88) bump CURRENT_SCHEMA_VERSION to 88."""
    from app.rms.config import CURRENT_SCHEMA_VERSION

    assert CURRENT_SCHEMA_VERSION == 88, (
        f"expected 88, got {CURRENT_SCHEMA_VERSION}"
    )


def test_monthly_closure_table_actually_created_on_init_db(session_factory, app_engine):
    """init_db() must have created the monthly_closure table."""
    from sqlalchemy import text

    with session_factory() as s:
        rows = s.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_closure'"
        )).fetchall()
        assert rows, "monthly_closure table was not created"


def test_expense_table_has_receipt_url_column_after_init_db(session_factory):
    """After init_db, the expense table must have receipt_url."""
    from sqlalchemy import text

    with session_factory() as s:
        cols = s.execute(text("PRAGMA table_info(expense)")).fetchall()
        col_names = {row[1] for row in cols}
        assert "receipt_url" in col_names
        assert "recurring_period" in col_names


def test_expense_recurring_period_column_defaults_to_once(session_factory):
    """Inserting an Expense without recurring_period must default to 'once'."""
    from datetime import datetime, timezone

    from app.rms.models import Expense

    with session_factory() as s:
        exp = Expense(
            occurred_at=datetime(2026, 10, 1, 12, tzinfo=timezone.utc),
            amount_gs=100_000,
            category="RENT",
        )
        s.add(exp)
        s.commit()
        s.refresh(exp)
        assert exp.recurring_period == "once"
        assert exp.receipt_url is None


def test_monthly_closure_persists_full_snapshot(session_factory):
    """Closing a month must persist the snapshot_json for audit trail."""
    from app.rms.models import MonthlyClosure

    with session_factory() as s:
        closure = MonthlyClosure(
            period_yyyymm="2026-09",
            closed_at=datetime(2026, 10, 1, 12, tzinfo=timezone.utc),
            total_revenue_gs=1_000_000,
            total_cogs_gs=400_000,
            total_expenses_gs=150_000,
            net_gs=450_000,
            snapshot_json=json.dumps({
                "period_yyyymm": "2026-09",
                "revenue": 1_000_000,
                "cogs": 400_000,
                "expenses": 150_000,
            }),
        )
        s.add(closure)
        s.commit()
        s.refresh(closure)
        assert closure.period_yyyymm == "2026-09"
        assert closure.net_gs == 450_000
        snap = json.loads(closure.snapshot_json)
        assert snap["revenue"] == 1_000_000