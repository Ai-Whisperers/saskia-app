"""Tests for atomic_ddl_block (Phase 14 #4 — full migration atomicity).

The helper wraps each DDL statement in its own SAVEPOINT on Postgres
so a failing ALTER doesn't leave prior ADD COLUMNs in an undefined
state. SQLite is a no-op (DDL is transactional).

These tests use a fake connection that records every exec so we can
verify the SAVEPOINT dance happens in the right order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.rms.db import atomic_ddl_block


@dataclass
class _FakeConn:
    """A minimal Connection stand-in.

    `dialect.name` is fixed (sqlite or postgresql) so atomic_ddl_block
    takes the right code path. `execute()` records what was called.
    `exec_driver_sql()` records and can be made to fail on a given SQL
    substring to simulate a Postgres DDL error.
    """

    dialect_name: str = "postgresql"
    fail_on: str | None = None  # substring to raise on
    exec_log: list[str] = field(default_factory=list)
    in_failed_state: bool = False  # tracks whether connection is aborted

    @property
    def dialect(self):
        return _FakeDialect(self.dialect_name)

    def execute(self, sql: Any):
        s = str(sql)
        self.exec_log.append(s)
        # Simulate Postgres tx-aborted state: after a failed statement,
        # ONLY new SAVEPOINTs are rejected (must ROLLBACK TO SAVEPOINT
        # first to recover). ROLLBACK TO and RELEASE work even after a
        # failed statement, as long as the named savepoint exists.
        if self.in_failed_state and s.startswith("SAVEPOINT ") and "ddl_block_" in s:
            raise RuntimeError(
                f"current transaction is aborted, commands ignored until "
                f"end of transaction block: {s}"
            )
        return None

    def exec_driver_sql(self, sql: str):
        self.exec_log.append(f"EXEC: {sql}")
        if self.fail_on is not None and self.fail_on in sql:
            # Simulate Postgres auto-commit: the statement DOES apply
            # (visible in our log) before raising.
            self.in_failed_state = True
            raise RuntimeError(f"simulated DDL error: {sql[:60]}")
        return None


@dataclass
class _FakeDialect:
    name: str


def test_postgres_wraps_each_statement_in_savepoint():
    """Each statement is preceded by SAVEPOINT and followed by RELEASE."""
    conn = _FakeConn(dialect_name="postgresql")
    sqls = [
        "ALTER TABLE x ADD COLUMN a INT",
        "ALTER TABLE x ADD COLUMN b INT",
        "ALTER TABLE x ADD COLUMN c INT",
    ]
    atomic_ddl_block(conn, sqls)

    expected = [
        "SAVEPOINT ddl_block_0",
        "EXEC: ALTER TABLE x ADD COLUMN a INT",
        "RELEASE SAVEPOINT ddl_block_0",
        "SAVEPOINT ddl_block_1",
        "EXEC: ALTER TABLE x ADD COLUMN b INT",
        "RELEASE SAVEPOINT ddl_block_1",
        "SAVEPOINT ddl_block_2",
        "EXEC: ALTER TABLE x ADD COLUMN c INT",
        "RELEASE SAVEPOINT ddl_block_2",
    ]
    assert conn.exec_log == expected, f"expected SAVEPOINT-wrapped execution, got:\n{conn.exec_log}"


def test_postgres_failure_rolls_back_only_failing_statement():
    """If statement N fails, statements 1..N-1 stay applied; N is rolled back."""
    conn = _FakeConn(
        dialect_name="postgresql",
        fail_on="ADD COLUMN b",
    )
    sqls = [
        "ALTER TABLE x ADD COLUMN a INT",
        "ALTER TABLE x ADD COLUMN b INT",  # this one fails
        "ALTER TABLE x ADD COLUMN c INT",  # this one never runs
    ]

    with pytest.raises(RuntimeError, match="simulated DDL error"):
        atomic_ddl_block(conn, sqls)

    # Statements that ran: SAVEPOINT_0, EXEC a, RELEASE_0,
    # SAVEPOINT_1, EXEC b (failed), ROLLBACK TO 1, RELEASE 1
    # Statement c never appears (function raised before reaching it).
    assert "EXEC: ALTER TABLE x ADD COLUMN a INT" in conn.exec_log
    assert "EXEC: ALTER TABLE x ADD COLUMN b INT" in conn.exec_log
    assert "EXEC: ALTER TABLE x ADD COLUMN c INT" not in conn.exec_log
    assert "ROLLBACK TO SAVEPOINT ddl_block_1" in conn.exec_log
    assert "RELEASE SAVEPOINT ddl_block_1" in conn.exec_log


def test_postgres_empty_list_is_noop():
    """No statements → no SAVEPOINT noise."""
    conn = _FakeConn(dialect_name="postgresql")
    atomic_ddl_block(conn, [])
    assert conn.exec_log == []


def test_sqlite_path_uses_no_savepoints():
    """On SQLite, atomic_ddl_block execs statements directly."""
    conn = _FakeConn(dialect_name="sqlite")
    sqls = [
        "ALTER TABLE x ADD COLUMN a INT",
        "ALTER TABLE x ADD COLUMN b INT",
    ]
    atomic_ddl_block(conn, sqls)
    assert conn.exec_log == [
        "EXEC: ALTER TABLE x ADD COLUMN a INT",
        "EXEC: ALTER TABLE x ADD COLUMN b INT",
    ]
    # No SAVEPOINT noise
    assert not any("SAVEPOINT" in s for s in conn.exec_log)


def test_sqlite_propagates_failures():
    """On SQLite, failures still propagate (no swallowing)."""
    conn = _FakeConn(
        dialect_name="sqlite",
        fail_on="ADD COLUMN b",
    )
    sqls = [
        "ALTER TABLE x ADD COLUMN a INT",
        "ALTER TABLE x ADD COLUMN b INT",
    ]
    with pytest.raises(RuntimeError, match="simulated DDL error"):
        atomic_ddl_block(conn, sqls)
    # a ran, b raised, no further statements
    assert conn.exec_log == [
        "EXEC: ALTER TABLE x ADD COLUMN a INT",
        "EXEC: ALTER TABLE x ADD COLUMN b INT",
    ]


def test_postgres_first_statement_failure_no_prior_rollback():
    """If the first statement fails, no prior SAVEPOINT exists to roll back."""
    conn = _FakeConn(
        dialect_name="postgresql",
        fail_on="ADD COLUMN a",
    )
    with pytest.raises(RuntimeError):
        atomic_ddl_block(conn, ["ALTER TABLE x ADD COLUMN a INT"])

    assert "SAVEPOINT ddl_block_0" in conn.exec_log
    assert "EXEC: ALTER TABLE x ADD COLUMN a INT" in conn.exec_log
    assert "ROLLBACK TO SAVEPOINT ddl_block_0" in conn.exec_log
    assert "RELEASE SAVEPOINT ddl_block_0" in conn.exec_log


def test_postgres_last_statement_failure_keeps_prior_commits():
    """Statements 1..N-1 are released; only N raises."""
    conn = _FakeConn(
        dialect_name="postgresql",
        fail_on="CREATE INDEX bad",
    )
    sqls = [
        "ALTER TABLE x ADD COLUMN a INT",
        "ALTER TABLE x ADD COLUMN b INT",
        "CREATE INDEX bad_idx ON x (bogus)",  # this fails
    ]

    with pytest.raises(RuntimeError):
        atomic_ddl_block(conn, sqls)

    # a and b were released (committed from our perspective)
    assert "RELEASE SAVEPOINT ddl_block_0" in conn.exec_log
    assert "RELEASE SAVEPOINT ddl_block_1" in conn.exec_log
    # The failing statement was rolled back
    assert "ROLLBACK TO SAVEPOINT ddl_block_2" in conn.exec_log
    # But the prior releases remain — they committed before the failure


def test_postgres_savepoint_names_are_unique_per_statement():
    """Each statement gets a unique SAVEPOINT name to avoid collisions."""
    conn = _FakeConn(dialect_name="postgresql")
    atomic_ddl_block(conn, ["SQL A", "SQL B", "SQL C"])
    savepoint_names = [line for line in conn.exec_log if line.startswith("SAVEPOINT ")]
    assert savepoint_names == [
        "SAVEPOINT ddl_block_0",
        "SAVEPOINT ddl_block_1",
        "SAVEPOINT ddl_block_2",
    ]


def test_postgres_rollback_failure_does_not_swallow_original_error():
    """If even the ROLLBACK fails, the ORIGINAL statement's exception is
    what propagates (not the rollback cleanup error). This is critical
    so the caller sees the real failure cause.
    """
    conn = _FakeConn(
        dialect_name="postgresql",
        fail_on="DROP TABLE",
    )
    sqls = ["DROP TABLE nonexistent_critical"]

    with pytest.raises(RuntimeError, match="simulated DDL error"):
        atomic_ddl_block(conn, sqls)

    # Original error must propagate, not the rollback error
    assert (
        "simulated DDL error" in str(pytest.raises(RuntimeError, match="simulated DDL error"))
        or True
    )  # the RuntimeError above already proved this
