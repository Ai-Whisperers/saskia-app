"""Migration 103: production_demand_snapshot + production_plan_audit + completion status.

PRODUCCION-V2 (2026-10-05): The /produccion day view is being split into 4
columns (demanda | plan | real | pedidos). Phase 1 of that work needs:

  1. ``production_demand_snapshot`` — one row per (for_date, product_id)
     caching the demand composition (forecast + pedidos + evento). The
     read path (production_demand.get_demand) recomputes on every read in
     Phase 1 (cheap query) but writes the snapshot so future phases can
     add a TTL-based cache without changing the contract.

     Why a snapshot table (vs. always-compute):
       - The router will fire get_demand() for every /produccion render.
       - The pedidos query joins pedido + pedido_line, which is 3-4x
         slower than reading a single (for_date, product_id) PK row.
       - Cheap to maintain: 1 INSERT ON CONFLICT per (date, product).

  2. ``production_plan_audit`` — append-only log of changes to the PLAN
     (not the demand, not the completion). Every POST that mutates
     production_plan_template / production_plan_override /
     production_completion leaves a row. Used by /produccion/accuracy
     (BACKLOG #29/#33) for plan-vs-actual narrative, and by audits
     when "who changed what on Oct 5" is asked.

  3. ``production_completion.status`` + ``closure_notes`` — state
     machine for "is this shift closed?" Phase 2 (Cerrar Turno button)
     consumes this. Phase 1 only adds the column with default 'open'
     so existing reads see no semantic change.

Schema (dialect-aware: SQLite is the test target, Postgres is prod):

  CREATE TABLE production_demand_snapshot (
      for_date DATE NOT NULL,
      product_id INTEGER NOT NULL REFERENCES product(id),
      qty_forecast NUMERIC(12,2) NOT NULL DEFAULT 0,
      qty_pedidos NUMERIC(12,2) NOT NULL DEFAULT 0,
      qty_pedidos_confirmed NUMERIC(12,2) NOT NULL DEFAULT 0,
      qty_evento NUMERIC(12,2) NOT NULL DEFAULT 0,
      qty_total NUMERIC(12,2) NOT NULL DEFAULT 0,
      confidence_pct INTEGER NOT NULL DEFAULT 0,
      source TEXT NOT NULL DEFAULT 'computed',
      computed_at TIMESTAMP NOT NULL,
      PRIMARY KEY (for_date, product_id)
  );

  CREATE TABLE production_plan_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SERIAL on Postgres
      for_date DATE NOT NULL,
      product_id INTEGER NOT NULL REFERENCES product(id),
      old_qty NUMERIC(12,2),
      new_qty NUMERIC(12,2) NOT NULL,
      change_source TEXT NOT NULL,
      changed_by VARCHAR(64),
      changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      notes TEXT
  );
  CREATE INDEX ix_production_plan_audit_date ON production_plan_audit (for_date);
  CREATE INDEX ix_production_plan_audit_product ON production_plan_audit (product_id);

  ALTER TABLE production_completion
      ADD COLUMN status TEXT NOT NULL DEFAULT 'open';
  ALTER TABLE production_completion
      ADD COLUMN closure_notes TEXT;

Why atomic_ddl_block:
  Postgres DDL auto-commits. A list like [CREATE, CREATE, ALTER]
  where the second CREATE fails (e.g., name collision) leaves the
  first CREATE applied but the migration is "failed", so the next
  migration runs against a partial baseline. atomic_ddl_block wraps
  each statement in its own SAVEPOINT on Postgres (no-op on SQLite)
  so a failure in statement N rolls back ONLY N; statements 1..N-1
  stay applied; statements N+1..end never run. See app/rms/db.py.

Idempotency:
  CREATE TABLE / CREATE INDEX use IF NOT EXISTS. ALTERs wrapped in
  try/except (column may already exist on re-runs of an in-place
  migration). The schema_version bump is unconditional.
"""

from typing import Any

from sqlalchemy import text


def _migration_103_production_demand_split(conn: Any) -> None:
    """Create demand snapshot + plan audit + completion status columns."""
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    is_postgres = dialect_name == "postgresql"
    pk_type = "BIGSERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

    statements: list[str] = [
        # 1) production_demand_snapshot
        """
        CREATE TABLE IF NOT EXISTS production_demand_snapshot (
            for_date DATE NOT NULL,
            product_id INTEGER NOT NULL REFERENCES product(id),
            qty_forecast NUMERIC(12,2) NOT NULL DEFAULT 0,
            qty_pedidos NUMERIC(12,2) NOT NULL DEFAULT 0,
            qty_pedidos_confirmed NUMERIC(12,2) NOT NULL DEFAULT 0,
            qty_evento NUMERIC(12,2) NOT NULL DEFAULT 0,
            qty_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            confidence_pct INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'computed',
            computed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (for_date, product_id)
        )
        """,
        # 2) production_plan_audit
        f"""
        CREATE TABLE IF NOT EXISTS production_plan_audit (
            id {pk_type},
            for_date DATE NOT NULL,
            product_id INTEGER NOT NULL REFERENCES product(id),
            old_qty NUMERIC(12,2),
            new_qty NUMERIC(12,2) NOT NULL,
            change_source TEXT NOT NULL,
            changed_by VARCHAR(64),
            changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
        """,
        # 3) production_plan_audit indexes — guarded for Postgres (no
        # CREATE INDEX IF NOT EXISTS) and SQLite (supports it).
        # We use atomic_ddl_block so a failure in the second index doesn't
        # leave the table without the first index.
        "CREATE INDEX IF NOT EXISTS ix_production_plan_audit_date ON production_plan_audit (for_date)",
        "CREATE INDEX IF NOT EXISTS ix_production_plan_audit_product ON production_plan_audit (product_id)",
    ]

    # Use the cross-dialect helper that wraps each statement in a SAVEPOINT
    # on Postgres. On SQLite it's a no-op (DDL is already transactional).
    from app.rms.db import atomic_ddl_block

    atomic_ddl_block(conn, statements)

    # 4) ALTER production_completion — separate try/except per column
    # because SQLite has no ADD COLUMN IF NOT EXISTS and Postgres raises
    # "column already exists" if the migration is re-run. The status
    # CHECK constraint is added as a separate statement so a pre-existing
    # bad row doesn't block the column add.
    try:
        if is_postgres:
            conn.execute(
                text(
                    "ALTER TABLE production_completion "
                    "ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'open'"
                )
            )
        else:
            conn.execute(
                text(
                    "ALTER TABLE production_completion "
                    "ADD COLUMN status TEXT NOT NULL DEFAULT 'open'"
                )
            )
    except Exception:
        pass

    try:
        if is_postgres:
            conn.execute(
                text(
                    "ALTER TABLE production_completion "
                    "ADD COLUMN IF NOT EXISTS closure_notes TEXT"
                )
            )
        else:
            conn.execute(
                text(
                    "ALTER TABLE production_completion "
                    "ADD COLUMN closure_notes TEXT"
                )
            )
    except Exception:
        pass

    # 5) Best-effort CHECK constraint on status. The model layer also
    # enforces this (CK in app/rms/models/production.py), so a failure
    # here is a warning, not a blocker. Existing rows are all 'open'
    # thanks to the DEFAULT above, so the constraint validates cleanly.
    try:
        conn.execute(
            text(
                "ALTER TABLE production_completion "
                "ADD CONSTRAINT ck_completion_status "
                "CHECK (status IN ('open', 'done', 'cancelled'))"
            )
        )
    except Exception:
        pass

    # BACKLOG #4 (2026-10-02): always bump schema_version at the end.
    from app.rms.db import _bump_schema_version

    _bump_schema_version(conn, 103)
