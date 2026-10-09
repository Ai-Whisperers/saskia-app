"""P41 — DB-level CHECK on sale.channel + pedido.channel (migration 111).

What it locks:
1. Migration applies on a fresh SQLite DB and creates 4 triggers (sale x
   INSERT/UPDATE, pedido x INSERT/UPDATE).
2. Inserting a sale with channel='retail' is REJECTED by the trigger
   (raise).
3. Updating sale.channel to a bad value is rejected.
4. pedido.channel accepts NULL (column is nullable).
5. pedido.channel rejects a bad non-NULL value.
6. Re-running the migration is a no-op (idempotent via IF NOT EXISTS).
7. Pre-existing garbage rows block the migration with a clear message.

The Postgres path (CheckConstraint in models_legacy.py) is exercised by
the conftest's init_db path, not directly here — Postgres-specific tests
are in the existing test_db_check_constraints.py suite.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.rms.migrations._111_sale_channel_check import _migration_111_sale_channel_check


def test_migration_applies_cleanly_on_empty_db():
    """A fresh SQLite DB should accept the triggers without errors."""
    engine = create_engine("sqlite:///:memory:")
    # We need the `sale` and `pedido` tables for triggers to attach to.
    # Use a stripped-down DDL that the triggers will fire against.
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
    # If we got here without raising, the migration applied.


def test_sale_insert_rejects_bad_channel():
    """sale.channel = 'retail' should raise on INSERT."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        # Now insert with a bad channel — expect IntegrityError
        with pytest.raises(IntegrityError):
            conn.execute(
                text("INSERT INTO sale (id, channel, qty, unit_price_gs) VALUES (:i, :c, :q, :p)"),
                {"i": 1, "c": "retail", "q": 1.0, "p": 1000},
            )


def test_sale_update_rejects_bad_channel():
    """UPDATE sale.channel = 'wholesale' should raise."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        conn.execute(
            text("INSERT INTO sale (id, channel, qty, unit_price_gs) VALUES (:i, :c, :q, :p)"),
            {"i": 1, "c": "mostrador", "q": 1.0, "p": 1000},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text("UPDATE sale SET channel = :c WHERE id = :i"),
                {"c": "wholesale", "i": 1},
            )


def test_sale_insert_accepts_all_allowed_channels():
    """All 6 Channel enum values should be accepted."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        allowed = [
            "mostrador",
            "mostrador-encargo",
            "whatsapp",
            "pedidosya",
            "monchis",
            "other",
        ]
        for i, ch in enumerate(allowed, start=1):
            conn.execute(
                text("INSERT INTO sale (id, channel, qty, unit_price_gs) VALUES (:i, :c, :q, :p)"),
                {"i": i, "c": ch, "q": 1.0, "p": 1000},
            )
        # All inserts succeeded
        count = conn.execute(text("SELECT COUNT(*) FROM sale")).scalar()
        assert count == 6


def test_pedido_channel_accepts_null():
    """pedido.channel is nullable, so NULL should be accepted."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        conn.execute(
            text("INSERT INTO pedido (id, channel, status) VALUES (:i, :c, :s)"),
            {"i": 1, "c": None, "s": "pending"},
        )
        # Verify it landed
        result = conn.execute(text("SELECT channel FROM pedido WHERE id=1")).scalar()
        assert result is None


def test_pedido_channel_rejects_bad_value():
    """pedido.channel = 'phone' (legacy value, not in Channel enum) should raise."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                text("INSERT INTO pedido (id, channel, status) VALUES (:i, :c, :s)"),
                {"i": 1, "c": "phone", "s": "pending"},
            )


def test_migration_is_idempotent():
    """Re-running the migration is a no-op (IF NOT EXISTS on triggers)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        _migration_111_sale_channel_check(conn)
        # Run again — should not raise
        _migration_111_sale_channel_check(conn)
        _migration_111_sale_channel_check(conn)


def test_migration_raises_on_existing_garbage():
    """Pre-existing bad rows block the migration with a clear error."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE app_meta ( key VARCHAR(64) PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sale ("
                " id INTEGER, channel VARCHAR(32) NOT NULL DEFAULT 'mostrador',"
                " qty FLOAT, unit_price_gs INTEGER"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pedido ("
                " id INTEGER, channel VARCHAR(40),"
                " status VARCHAR(20) NOT NULL DEFAULT 'pending'"
                ")"
            )
        )
        # Insert a bad sale BEFORE the migration runs
        conn.execute(
            text("INSERT INTO sale (id, channel, qty, unit_price_gs) VALUES (:i, :c, :q, :p)"),
            {"i": 1, "c": "retail", "q": 1.0, "p": 1000},
        )
        with pytest.raises(RuntimeError, match=r"sale\.channel has values"):
            _migration_111_sale_channel_check(conn)
