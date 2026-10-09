"""tests/test_invoice_number_atomicity.py — verify allocate_invoice_number is atomic.

Phase 1A ticket #3: Per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F10,
`allocate_invoice_number` does a SELECT-then-UPDATE on the ComplianceInfo
counter row without row-level locking. On Postgres, two concurrent sales
can read the same counter value and emit duplicate fiscal invoice numbers,
which is rejected by the tax authority.

This test verifies the fix on two layers:

  1. **Introspection test (dialect-agnostic):** Inspect the SQL emitted by
     `allocate_invoice_number` to confirm it uses `with_for_update()` on
     Postgres. SQLite is single-writer so `with_for_update()` is a no-op
     there — we verify the function emits the right SQL via the dialect.

  2. **Behavior test (SQLite serial semantics):** Verify sequential calls
     produce strictly increasing invoice numbers. The single-writer model
     means race-free on SQLite by construction.

For a TRUE concurrency test on Postgres, see test_pg_invoice_number_race
in tests/test_pg_*.py (uses real Postgres + threading).
"""

from __future__ import annotations

import pytest

# ─── Helpers ────────────────────────────────────────────────────────────────


def _seed_compliance_info(session_factory):
    """Seed ComplianceInfo with both counters starting at 1."""
    from app.rms.models import ComplianceInfo

    with session_factory() as s:
        # Replace any existing row
        existing = s.get(ComplianceInfo, 1)
        if existing:
            s.delete(existing)
            s.flush()
        s.add(
            ComplianceInfo(
                id=1,
                tax_regime="general",
                iva_default_rate="10",
                next_boleta_resimple_number=1,
                next_factura_number=1,
            )
        )
        s.commit()


# ─── Behavior tests ─────────────────────────────────────────────────────────


def test_allocate_boleta_resimple_returns_strictly_increasing_numbers(session_factory):
    """Sequential allocations produce 1, 2, 3, ... (no duplicates).

    Allocation happens within one session because the function does
    read-then-mutate without committing; the caller's commit is what
    persists the increment.
    """
    from app.rms.invoicing import allocate_invoice_number

    _seed_compliance_info(session_factory)

    with session_factory() as s:
        n1 = allocate_invoice_number(s, "boleta_resimple")
        n2 = allocate_invoice_number(s, "boleta_resimple")
        n3 = allocate_invoice_number(s, "boleta_resimple")
        s.commit()

    assert (n1, n2, n3) == (1, 2, 3), f"expected (1,2,3), got ({n1},{n2},{n3})"


def test_allocate_factura_returns_strictly_increasing_numbers(session_factory):
    """Sequential factura allocations produce 1, 2, 3, ... (no duplicates)."""
    from app.rms.invoicing import allocate_invoice_number

    _seed_compliance_info(session_factory)

    with session_factory() as s:
        n1 = allocate_invoice_number(s, "factura")
        n2 = allocate_invoice_number(s, "factura")
        n3 = allocate_invoice_number(s, "factura")
        s.commit()

    assert (n1, n2, n3) == (1, 2, 3), f"expected (1,2,3), got ({n1},{n2},{n3})"


def test_boleta_and_factura_have_separate_counters(session_factory):
    """Each invoice type has its own counter; allocating boleta does not advance factura."""
    from app.rms.invoicing import allocate_invoice_number

    _seed_compliance_info(session_factory)

    with session_factory() as s:
        b1 = allocate_invoice_number(s, "boleta_resimple")
        f1 = allocate_invoice_number(s, "factura")
        b2 = allocate_invoice_number(s, "boleta_resimple")
        s.commit()

    assert b1 == 1
    assert f1 == 1  # separate counter, not affected by boleta
    assert b2 == 2


def test_unknown_invoice_type_raises(session_factory):
    """allocate_invoice_number with bad type raises ValueError."""
    from app.rms.invoicing import allocate_invoice_number

    _seed_compliance_info(session_factory)

    with pytest.raises(ValueError, match="Cannot allocate invoice number"):
        with session_factory() as s:
            allocate_invoice_number(s, "not_a_real_type")


# ─── Introspection test (Postgres-targeted) ────────────────────────────────


def test_allocate_uses_with_for_update_on_postgres(monkeypatch):
    """Verify the function emits FOR UPDATE on Postgres.

    On Postgres, two concurrent transactions reading the counter row need
    row-level locks to prevent both reading the same value. We mock the
    session to simulate Postgres dialect and assert that `session.get`
    is called with `with_for_update=True`.

    This is an introspection test — it doesn't run a real race. For a real
    race test, see test_pg_invoice_number_race (requires testcontainers).
    """
    from unittest.mock import MagicMock

    from app.rms import invoicing

    # Mock a Postgres session whose dialect.name == "postgresql".
    # SQLAlchemy's session.get accesses engine via session.bind.
    mock_bind = MagicMock()
    mock_bind.dialect.name = "postgresql"
    mock_session = MagicMock()
    mock_session.bind = mock_bind

    # Mock ComplianceInfo.get to return a row with counters at 5
    mock_row = MagicMock()
    mock_row.next_boleta_resimple_number = 5
    mock_row.next_factura_number = 7
    mock_session.get.return_value = mock_row

    result = invoicing.allocate_invoice_number(mock_session, "boleta_resimple")

    # The function MUST use with_for_update=True on session.get() to take
    # a row-level lock on Postgres. Verify by inspecting call args.
    assert mock_session.get.called, "session.get was not called"
    call_args = mock_session.get.call_args
    # call_args is (args, kwargs). Check that with_for_update is True.
    # The signature should be: session.get(ComplianceInfo, 1, with_for_update=True)
    # OR: session.get(ComplianceInfo, 1, with_for_update={"key": True})
    # OR: lockmode="update" (older SQLAlchemy)
    with_for_update = call_args.kwargs.get("with_for_update")
    assert with_for_update is True or with_for_update == {"key": True} or with_for_update == "*", (
        f"with_for_update must be set for Postgres row-level locking; got call_args={call_args}"
    )
    assert result == 5, f"expected allocated number 5, got {result}"
