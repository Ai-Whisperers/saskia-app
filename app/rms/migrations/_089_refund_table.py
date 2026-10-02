"""Migration 089: Refund entity + cap trigger (BACKLOG M1, Phase 14+).

A refund is a partial (or full) monetary reversal of a Sale or Pedido,
distinct from a void. Multiple refunds can target the same Sale (a customer
might bring back 1 of 3 items today, 2 tomorrow). The DB enforces:

  1. amount_gs > 0 (model CheckConstraint + this trigger as backup)
  2. target_amount_gs > 0 (model CheckConstraint + this trigger as backup)
  3. SUM(amount_gs) across all refunds for a given (target_type, target_id)
     must not exceed target_amount_gs

The model CheckConstraints already cover (1) and (2). The third constraint
(the cap) is implemented as a SQLite trigger because SQLite doesn't support
deferred CHECK constraints that can reference aggregates. On Postgres,
the cap is enforced via a CHECK constraint that fires on insert/update.

Why a trigger not a CHECK:
  SQLite CHECK constraints can't reference aggregates (SUM, MAX, etc.).
  PostgreSQL CHECK constraints also can't reference aggregates directly.
  Triggers are the only portable way to enforce a multi-row sum bound.

Why target_amount_gs is a snapshot column:
  We could compute it on the fly from sale.unit_price_gs * qty, but:
  (a) For Pedido/PedidoLine the math is complex (multi-line, discounts)
  (b) The customer might dispute the refund total — the snapshot captures
      what the operator believed the target total was at refund time
  (c) If the underlying sale/pedido is later voided, the snapshot remains

Idempotent: re-running on an already-migrated DB is a no-op.
"""

from typing import Any

from sqlalchemy import text


def _migration_089_refund_table(conn: Any) -> None:
    """Create refund table + cap trigger."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name == "sqlite":
        # Create the refund table. Indexes and CheckConstraints are in
        # the model; we add them here as DDL because SQLAlchemy create_all
        # only runs on a fresh DB.
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS refund (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type VARCHAR(16) NOT NULL,
                target_id INTEGER NOT NULL,
                target_amount_gs INTEGER NOT NULL,
                amount_gs INTEGER NOT NULL,
                payment_method VARCHAR(32) NOT NULL,
                restock_qty BOOLEAN NOT NULL DEFAULT 0,
                restocked_qty FLOAT NOT NULL DEFAULT 0,
                reason TEXT,
                recorded_at DATETIME NOT NULL,
                recorded_by VARCHAR(64),
                eod_date DATE,
                loyalty_reversed INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_target_id ON refund (target_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_recorded_at ON refund (recorded_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_eod_date ON refund (eod_date)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_target_combo ON refund (target_type, target_id)"
        ))
        # Check constraints (mirror the model)
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS ck_refund_target_type_insert "
            "BEFORE INSERT ON refund "
            "FOR EACH ROW WHEN NEW.target_type NOT IN ('sale','pedido','pedido_line') "
            "BEGIN SELECT RAISE(ABORT, 'refund.target_type must be sale|pedido|pedido_line'); END"
        ))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS ck_refund_amount_positive_insert "
            "BEFORE INSERT ON refund "
            "FOR EACH ROW WHEN NEW.amount_gs <= 0 "
            "BEGIN SELECT RAISE(ABORT, 'refund.amount_gs must be > 0'); END"
        ))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS ck_refund_amount_positive_update "
            "BEFORE UPDATE ON refund "
            "FOR EACH ROW WHEN NEW.amount_gs <= 0 "
            "BEGIN SELECT RAISE(ABORT, 'refund.amount_gs must be > 0'); END"
        ))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS ck_refund_target_amount_positive_insert "
            "BEFORE INSERT ON refund "
            "FOR EACH ROW WHEN NEW.target_amount_gs <= 0 "
            "BEGIN SELECT RAISE(ABORT, 'refund.target_amount_gs must be > 0'); END"
        ))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS ck_refund_restocked_qty_nonneg_insert "
            "BEFORE INSERT ON refund "
            "FOR EACH ROW WHEN NEW.restocked_qty < 0 "
            "BEGIN SELECT RAISE(ABORT, 'refund.restocked_qty must be >= 0'); END"
        ))
        # CAP trigger: sum of refund amounts for a given target must not exceed target_amount_gs
        # SQLite supports subqueries in triggers; we use a correlated lookup.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ck_refund_amount_cap_insert
            BEFORE INSERT ON refund
            FOR EACH ROW WHEN (
                SELECT COALESCE(SUM(amount_gs), 0)
                FROM refund
                WHERE target_type = NEW.target_type AND target_id = NEW.target_id
            ) + NEW.amount_gs > NEW.target_amount_gs
            BEGIN
                SELECT RAISE(ABORT, 'refund.amount_cap: refund total would exceed target_amount_gs');
            END
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS ck_refund_amount_cap_update
            BEFORE UPDATE ON refund
            FOR EACH ROW WHEN (
                SELECT COALESCE(SUM(amount_gs), 0) - OLD.amount_gs
                FROM refund
                WHERE target_type = NEW.target_type AND target_id = NEW.target_id
            ) + NEW.amount_gs > NEW.target_amount_gs
            BEGIN
                SELECT RAISE(ABORT, 'refund.amount_cap: refund total would exceed target_amount_gs');
            END
        """))
    else:
        # Postgres: model CheckConstraints handle (1) and (2). For (3),
        # use a trigger since CHECK can't aggregate.
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS refund (
                id SERIAL PRIMARY KEY,
                target_type VARCHAR(16) NOT NULL,
                target_id INTEGER NOT NULL,
                target_amount_gs INTEGER NOT NULL,
                amount_gs INTEGER NOT NULL,
                payment_method VARCHAR(32) NOT NULL,
                restock_qty BOOLEAN NOT NULL DEFAULT FALSE,
                restocked_qty DOUBLE PRECISION NOT NULL DEFAULT 0,
                reason TEXT,
                recorded_at TIMESTAMP NOT NULL,
                recorded_by VARCHAR(64),
                eod_date DATE,
                loyalty_reversed INTEGER NOT NULL DEFAULT 0,
                CONSTRAINT ck_refund_target_type CHECK (target_type IN ('sale','pedido','pedido_line')),
                CONSTRAINT ck_refund_amount_positive CHECK (amount_gs > 0),
                CONSTRAINT ck_refund_target_amount_positive CHECK (target_amount_gs > 0),
                CONSTRAINT ck_refund_restocked_qty_nonneg CHECK (restocked_qty >= 0)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_target_id ON refund (target_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_recorded_at ON refund (recorded_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_eod_date ON refund (eod_date)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_refund_target_combo ON refund (target_type, target_id)"
        ))
        # Cap trigger
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION refund_amount_cap_check()
            RETURNS TRIGGER AS $$
            BEGIN
                IF (
                    SELECT COALESCE(SUM(amount_gs), 0)
                    FROM refund
                    WHERE target_type = NEW.target_type AND target_id = NEW.target_id
                ) + NEW.amount_gs > NEW.target_amount_gs THEN
                    RAISE EXCEPTION 'refund.amount_cap: refund total would exceed target_amount_gs';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        conn.execute(text("DROP TRIGGER IF EXISTS ck_refund_amount_cap_insert ON refund"))
        conn.execute(text(
            "CREATE TRIGGER ck_refund_amount_cap_insert BEFORE INSERT ON refund "
            "FOR EACH ROW EXECUTE FUNCTION refund_amount_cap_check()"
        ))
        conn.execute(text("DROP TRIGGER IF EXISTS ck_refund_amount_cap_update ON refund"))
        conn.execute(text(
            "CREATE TRIGGER ck_refund_amount_cap_update BEFORE UPDATE ON refund "
            "FOR EACH ROW EXECUTE FUNCTION refund_amount_cap_check()"
        ))

    # Phase 14+ fix: 089 originally forgot _bump_schema_version, so init_db
    # ran the table creation but the schema_version stayed at 88. Adding
    # the bump here so /healthz/db no longer reports drift on a freshly-
    # migrated DB. Idempotent: re-runs of 089 already at 89 will simply
    # overwrite the same value.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 89)
