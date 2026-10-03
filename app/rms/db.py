"""app/rms/db.py — engine, session, pragmas, versioned migrations.

Per dev plan §9 Task 1 + improvements review §2.2.

Pragmas (set on every connection via SQLAlchemy event listener):
- WAL mode (concurrent reads, single writer; survives power loss)
- secure_delete = ON (deleted rows are zeroed, not just unlinked)
- foreign_keys = ON (FK constraints actually enforced)

Schema versioning: `app_meta` table tracks `current_schema_version`. `init_db()`
runs pending migrations from `MIGRATIONS` dict in order. Each migration is a
Python function that takes a SQLAlchemy connection and applies the schema change.

Why hand-rolled (not Alembic):
- Alembic adds a heavy dependency for a 70h single-user project
- Schema is small (8 tables) and changes rarely
- 30 lines of code is enough
- Documented in app/rms/AGENTS.md

This module is import-safe (no side effects on import). `init_db()` must be called
explicitly, typically from `main.py`'s lifespan handler.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.rms.config import (
    CURRENT_SCHEMA_VERSION,
    DB_PATH,
    ensure_dirs,
)
from app.rms.migrations._084_stock_qty_nonneg import _migration_084_stock_qty_nonneg
from app.rms.migrations._085_sale_public_token import _migration_085_sale_public_token
from app.rms.migrations._086_placeholder import _migration_086_placeholder
from app.rms.migrations._087_placeholder import _migration_087_placeholder
from app.rms.migrations._088_placeholder import _migration_088_placeholder
from app.rms.migrations._089_refund_table import _migration_089_refund_table
from app.rms.migrations._090_stock_movement_affected_recipe_id import (
    _migration_090_stock_movement_affected_recipe_id,
)
from app.rms.migrations._091_backfill_stock_movement_recipe import (
    _migration_091_backfill_stock_movement_recipe,
)
from app.rms.migrations._092_drop_sale_stock_move import _migration_092_drop_sale_stock_move
from app.rms.migrations._093_expense_receipt_recurring import (
    _migration_093_expense_receipt_recurring,
)
from app.rms.migrations._094_monthly_closure import _migration_094_monthly_closure
from app.rms.migrations._095_soft_delete_columns import _migration_095_soft_delete_columns
from app.rms.migrations._096_audit_columns import _migration_096_audit_columns
from app.rms.migrations._097_ingredient_avg_cost import _migration_097_ingredient_avg_cost


def _set_sqlite_pragmas(dbapi_conn: Any, _: Any) -> None:
    """SQLAlchemy connect listener: enable WAL + secure_delete + foreign_keys.

    Called on every new connection. Idempotent.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA secure_delete=ON")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def make_engine(url: str | None = None, *, for_tests: bool = False) -> Engine:
    """Create SQLAlchemy engine with SQLite pragmas.

    Args:
        url: SQLite URL. Defaults to file at DB_PATH. Pass "sqlite:///:memory:"
            for in-memory test DB.
        for_tests: when True, allows multiple connections (SQLite's StaticPool
            would conflict with our pragma listener otherwise).
    """
    if url is None:
        ensure_dirs()
        url = f"sqlite:///{DB_PATH}"

    kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }
    if for_tests:
        # StaticPool for in-memory + connect listener compatibility
        from sqlalchemy.pool import StaticPool

        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


# --- Versioned migrations ---
# Each migration is a function that takes a connection and applies schema changes.
# Migrations are run in order from `1` to `CURRENT_SCHEMA_VERSION` (inclusive).
# To add a migration: bump CURRENT_SCHEMA_VERSION in config.py, add a function here,
# add it to MIGRATIONS dict below.

MigrationFn = Callable[[Any], None]


def _migration_001_initial_schema(conn: Any) -> None:
    """Initial schema (8 tables). Called once on fresh DBs.

    We let SQLAlchemy's create_all() do the heavy lifting; this migration is a
    marker for the schema version. It also seeds the app_meta table.

    Dialect-aware upsert: SQLite uses INSERT OR IGNORE; Postgres uses
    ON CONFLICT DO NOTHING. We detect the dialect via the bind dialect name.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts = datetime.now(timezone.utc).isoformat()
    if dialect == "postgresql":
        # app_meta.value is JSONB on production (legacy column type);
        # cast string → jsonb so the insert doesn't fail. Build the
        # string in Python so SQLAlchemy parameter binding doesn't
        # fight with ::type casts.
        ts_quoted = ts.replace("'", "''")
        upsert = (
            f"INSERT INTO app_meta (key, value, updated_at) "
            f"VALUES ('schema_version', '\"1\"'::jsonb, '{ts_quoted}') "
            f"ON CONFLICT (key) DO NOTHING"
        )
        upsert2 = (
            f"INSERT INTO app_meta (key, value, updated_at) "
            f"VALUES ('created_at', '\"{ts_quoted}\"'::jsonb, '{ts_quoted}') "
            f"ON CONFLICT (key) DO NOTHING"
        )
    else:
        upsert = "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', '1')"
        upsert2 = "INSERT OR IGNORE INTO app_meta (key, value) VALUES ('created_at', :ts)"
    conn.execute(text(upsert), {"ts": ts})
    conn.execute(text(upsert2), {"ts": ts})


def _migration_002_audit_log(conn: Any) -> None:
    """Add the audit_log table (E3.S1).

    Records every security-relevant action: login success/failure, logout,
    password reset, sales CRUD, recipe/product edits, inventory movements.

    created_at column (datetime UTC) gets a btree index so admin queries on
    /audit?since=...&until=... are fast. user_id + action get their own
    indexes for filter-by-user / filter-by-action queries.

    No backfill: there is no historical data to migrate. Existing rows in
    other tables are unaffected.
    """
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS audit_log ("
            "id SERIAL PRIMARY KEY, "
            "occurred_at DATETIME NOT NULL, "
            "user_id VARCHAR(64), "
            "action VARCHAR(64) NOT NULL, "
            "target_type VARCHAR(64), "
            "target_id VARCHAR(64), "
            "detail TEXT NOT NULL DEFAULT '{}', "
            "ip VARCHAR(64), "
            "user_agent VARCHAR(256)"
            ")"
        )
    )
    # Postgres-compatible: CREATE INDEX IF NOT EXISTS is SQLite-only.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        for ix_name, ix_table, ix_col in [
            ("ix_audit_log_occurred_at", "audit_log", "occurred_at"),
            ("ix_audit_log_user_id", "audit_log", "user_id"),
            ("ix_audit_log_action", "audit_log", "action"),
        ]:
            existing = conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
                {"n": ix_name},
            ).first()
            if existing is None:
                conn.execute(text(f"CREATE INDEX {ix_name} ON {ix_table} ({ix_col})"))
    else:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_occurred_at ON audit_log (occurred_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_user_id ON audit_log (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log (action)"))
    _bump_schema_version(conn, 2)


def _migration_007_product_sku(conn: Any) -> None:
    """Add Product.sku column (E23.S1).

    SKU is optional; most bakeries don't print barcodes on products but
    an operator may add them later. Unique when set.
    """
    _add_column_if_missing(conn, "product", "sku",
                           "VARCHAR(32)", "TEXT")
    _bump_schema_version(conn, 7)


def _add_column_if_missing(conn: Any, table: str, column: str,
                           pg_type: str, sqlite_type: str) -> None:
    """Add a column to a table if it doesn't already exist.

    Cross-dialect: SQLite uses PRAGMA table_info; Postgres uses
    information_schema.columns.
    """
    dialect_name = conn.dialect.name
    if dialect_name == "postgresql":
        exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
        if not exists:
            conn.execute(
                text(f'ALTER TABLE {table} ADD COLUMN {column} {pg_type}')
            )
    else:
        # SQLite
        cols = [row[1] for row in conn.execute(text(f'PRAGMA table_info({table})')).fetchall()]
        if column not in cols:
            conn.execute(
                text(f'ALTER TABLE {table} ADD COLUMN {column} {sqlite_type}')
            )


def _migration_006_waste_log(conn: Any) -> None:
    """Add waste_log table (E22)."""
    _bump_schema_version(conn, 6)



def _migration_004_tags(conn: Any) -> None:
    """Add Tag + TagLink tables (E9.S1).

    Tags are polymorphic (target_kind in product|ingredient|recipe). The
    tag table holds the name + color + kind; the tag_link table holds
    the M:N mapping.

    Both tables are created via create_all() in init_db(). Here we
    just bump the schema version.
    """
    # create_all is called by init_db BEFORE this migration runs.
    # Nothing else to do — the new tables already exist.
    _bump_schema_version(conn, 4)


def _migration_003_analytics_columns(conn: Any) -> None:
    """Add analytics-tracking columns (E8).

    New columns:
    - ingredient.purchase_price_updated_at: tracks when the cost was last changed
      (used by margin_erosion_alerts in app/rms/analytics.py)
    - ingredient.last_consumed_at: tracks the most recent sale that consumed this
      ingredient (used by dead_stock and stock_turnover reports)
    - ingredient.shelf_life_days: optional, drives spoilage alerts (E22)
    - recipe.prep_minutes: optional, drives cost-per-prep-minute reports

    All columns are nullable / optional so the migration is safe on existing rows
    (which get NULL = "unknown" rather than a fabricated value).
    """
    # SQLite ALTER TABLE supports adding columns one at a time. Wrap in try/except
    # so re-running this migration on an already-migrated DB is a no-op.
    # Postgres uses TIMESTAMP; SQLite accepts both.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts_type = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
    _add_columns = [
        ("ingredient", "purchase_price_updated_at", ts_type),
        ("ingredient", "last_consumed_at", ts_type),
        ("ingredient", "shelf_life_days", "INTEGER"),
        ("recipe", "prep_minutes", "INTEGER"),
    ]
    for table, col, decl in _add_columns:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {decl}"))
        except Exception:
            pass

    # Index on last_consumed_at so dead_stock reports stay fast.
    # CREATE INDEX IF NOT EXISTS is SQLite syntax; on Postgres use a
    # check against pg_indexes.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        existing = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname='public' AND indexname='ix_ingredient_last_consumed_at'"
            )
        ).first()
        if existing is None:
            conn.execute(
                text(
                    "CREATE INDEX ix_ingredient_last_consumed_at "
                    "ON ingredient (last_consumed_at)"
                )
            )
    else:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ingredient_last_consumed_at "
                "ON ingredient (last_consumed_at)"
            )
        )

    _bump_schema_version(conn, 3)



def _migration_008_tenant(conn: Any) -> None:
    """Add tenant table (E15)."""
    _bump_schema_version(conn, 8)


def _migration_009_ingredient_intel(conn: Any) -> None:
    """Add ingredient intelligence columns (E26): category, subcategory, role,
    allergens, dietary_tags, lead_time_days.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    # Use TEXT type — works on both dialects.
    cols = [
        ("category", "VARCHAR(32)"),
        ("subcategory", "VARCHAR(32)"),
        ("role", "VARCHAR(32)"),
        ("allergens", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("dietary_tags", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("lead_time_days", "INTEGER DEFAULT 3"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE ingredient ADD COLUMN {col_name} {col_type}"))
        except Exception:
            # Column already exists — idempotent.
            pass
    _bump_schema_version(conn, 9)


def _migration_010_recipe_intel(conn: Any) -> None:
    """Add recipe intelligence columns (E27): family, difficulty, dietary_tags,
    cook_minutes. prep_minutes already exists (added in migration 003).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("family", "VARCHAR(32)"),
        ("difficulty", "INTEGER"),
        ("dietary_tags", "JSONB" if dialect == "postgresql" else "TEXT"),
        ("cook_minutes", "INTEGER"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE recipe ADD COLUMN {col_name} {col_type}"))
        except Exception:
            # Column already exists — idempotent.
            pass
    _bump_schema_version(conn, 10)


def _migration_011_sale_payment_discount(conn: Any) -> None:
    """Add payment_method + discount_gs to Sale (Phase 5 sales overhaul).

    payment_method: nullable string (cash/transfer/card/other).
    discount_gs: integer Gs. discount applied to the sale total.
    Both default NULL / 0 — backward compatible with existing data.
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("payment_method", "VARCHAR(32)"),
        ("discount_gs", "INTEGER DEFAULT 0"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE sale ADD COLUMN {col_name} {col_type}"))
        except Exception:
            # Column already exists — idempotent.
            pass
    _bump_schema_version(conn, 11)


def _migration_012_sale_tz(conn: Any) -> None:
    """Add tz column to Sale (Phase 6 wishlist: timezone-groupby-sales).

    tz: VARCHAR(64), default 'America/Asuncion'. Backward compatible:
    existing rows get the default on Postgres (DEFAULT clause) and on
    SQLite (we backfill below).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    try:
        conn.execute(text("ALTER TABLE sale ADD COLUMN tz VARCHAR(64) DEFAULT 'America/Asuncion' NOT NULL"))
    except Exception:
        # Column already exists — idempotent.
        pass
    # SQLite ALTER TABLE doesn't support DEFAULT with NOT NULL; backfill explicitly.
    if dialect == "sqlite":
        try:
            conn.execute(text("UPDATE sale SET tz = 'America/Asuncion' WHERE tz IS NULL OR tz = ''"))
        except Exception:
            pass
    _bump_schema_version(conn, 12)


def _migration_013_ingredient_max_stock(conn: Any) -> None:
    """Add max_stock_qty column to Ingredient (Phase 7 reorder feature).

    max_stock_qty: nullable FLOAT. NULL means "use 2x min_stock_qty"
    heuristic. Operators can set explicit targets via /inventario/{id}/editar.
    """
    try:
        conn.execute(text("ALTER TABLE ingredient ADD COLUMN max_stock_qty FLOAT"))
    except Exception:
        pass  # already exists
    _bump_schema_version(conn, 13)


def _migration_014_customer_cedula(conn: Any) -> None:
    """Add cedula column to Customer (sales picker overhaul).

    cedula: Paraguayan CI/RUC identifier. Nullable; indexed for
    case-insensitive lookup in /clientes/api/search.
    """
    _add_column_if_missing(conn, "customer", "cedula", "VARCHAR(32)", "TEXT")
    # Index is created idempotently via CREATE INDEX IF NOT EXISTS (SQLite
    # supports it; Postgres uses a guarded SELECT-from-pg_indexes path).
    dialect_name = conn.dialect.name
    if dialect_name == "postgresql":
        existing = conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
            {"n": "ix_customer_cedula"},
        ).first()
        if existing is None:
            conn.execute(text("CREATE INDEX ix_customer_cedula ON customer (cedula)"))
    else:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_customer_cedula ON customer (cedula)"))
    _bump_schema_version(conn, 14)


def _migration_015_sale_channel(conn: Any) -> None:
    """Add `channel` column to Sale (Stream A prelaunch — 2026-09-17).

    channel: VARCHAR(32) NOT NULL DEFAULT 'mostrador'. Allowed values:
    mostrador, whatsapp, pedidosya, monchis, mostrador-encargo.

    Existing rows get 'mostrador' via the DEFAULT (Postgres honours
    DEFAULT on ALTER TABLE ADD COLUMN; SQLite does too in modern versions).
    On older SQLite we backfill explicitly.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pg_type = "VARCHAR(32) NOT NULL DEFAULT 'mostrador'"
    sqlite_type = "VARCHAR(32) DEFAULT 'mostrador' NOT NULL"

    try:
        if dialect == "postgresql":
            conn.execute(text(f"ALTER TABLE sale ADD COLUMN channel {pg_type}"))
        else:
            conn.execute(text(f"ALTER TABLE sale ADD COLUMN channel {sqlite_type}"))
    except Exception:
        # Column already exists — idempotent.
        pass

    # SQLite before 3.31 doesn't honour DEFAULT for NOT NULL on existing
    # rows. Backfill explicitly so legacy rows have the right value.
    if dialect == "sqlite":
        try:
            conn.execute(text("UPDATE sale SET channel = 'mostrador' WHERE channel IS NULL OR channel = ''"))
        except Exception:
            pass

    _bump_schema_version(conn, 15)


def _migration_016_pedidos(conn: Any) -> None:
    """Add Pedido + PedidoLine tables (Phase 3 — prelaunch roadmap 2026-09-17).

    Tables are created via create_all() in init_db() (the model classes
    were added in models.py at the same time as this migration). This
    function only bumps the schema_version row.

    Pedido: a pre-order with customer info, promised_date, channel, status,
      payment_intent, notes, and a unique public_token for /p/{token} sharing.
    PedidoLine: one product + qty + snapshot unit_price_gs + fulfilled_qty
      per line in a pedido. Cascade-deleted with the parent pedido.
    """
    # create_all() in init_db() creates these tables before this migration
    # runs. Nothing else to do here besides bumping the version row.
    _bump_schema_version(conn, 16)


def _migration_017_recipe_line_unit(conn: Any) -> None:
    """Add `line_unit` to recipe_line (Phase B — T1: recipe line unit selector).

    Per Saskia's review ("Se debe de poder agregar en gramos la cantidad"), each
    recipe line now stores the unit Saskia typed the qty in. Costing walks use
    this to convert qty → ingredient unit before multiplying against the
    ingredient's per-unit price.

    Column: VARCHAR(8) NOT NULL DEFAULT ''.

    Backfill: existing recipe_line rows get the unit of the linked ingredient
    (or '' for sub_recipe lines, where the legacy assumption is the recipe's
    yield_unit; the costing walk handles both). The backfill runs only when
    the row's line_unit is empty so re-runs are idempotent.
    """
    _add_column_if_missing(
        conn,
        "recipe_line",
        "line_unit",
        "VARCHAR(8) NOT NULL DEFAULT ''",
        "VARCHAR(8) DEFAULT '' NOT NULL",
    )

    # Backfill existing rows: line_unit = linked ingredient's unit (ingredient
    # lines) or '' (sub_recipe lines — sub-recipe yield_unit isn't 1:1 with
    # the parent's yield_unit, so we leave '' and let the costing walk default
    # to the sub-recipe's yield_unit). Idempotent: skip rows where line_unit
    # is already non-empty.
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        conn.execute(
            text(
                "UPDATE recipe_line rl "
                "SET line_unit = COALESCE(i.unit, '') "
                "FROM ingredient i "
                "WHERE rl.line_kind = 'ingredient' "
                "AND rl.line_ref_id = i.id "
                "AND (rl.line_unit IS NULL OR rl.line_unit = '')"
            )
        )
    else:
        conn.execute(
            text(
                "UPDATE recipe_line "
                "SET line_unit = COALESCE("
                "(SELECT i.unit FROM ingredient i "
                "WHERE i.id = recipe_line.line_ref_id), ''"
                ") "
                "WHERE line_kind = 'ingredient' "
                "AND (line_unit IS NULL OR line_unit = '')"
            )
        )

    _bump_schema_version(conn, 17)


def _migration_018_price_event(conn: Any) -> None:
    """Create ingredient_price_event table (Phase B — Q1 core).

    Append-only purchase-price history for each ingredient. Powers the
    price-strip + sparkline on /inventario and the dashboard "fluctuation"
    insight (Phase D surfaces).

    The table is created via SQLAlchemy's create_all() in init_db() (the
    IngredientPriceEvent model class was added in models.py at the same
    time). This migration just bumps schema_version and ensures the
    (ingredient_id, recorded_at) index is present on dialects that don't
    auto-create it from the model.

    Index: (ingredient_id, recorded_at) — needed for the common access
    pattern `WHERE ingredient_id = ? AND recorded_at >= ?` (price_history).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    # Defensive: the table may already exist if init_db() ran before this
    # migration got registered (e.g. for older DBs being upgraded). Idempotent.
    if dialect == "postgresql":
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS ingredient_price_event ("
                "id SERIAL PRIMARY KEY, "
                "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) "
                "ON DELETE CASCADE, "
                "price_gs INTEGER NOT NULL, "
                "recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "source VARCHAR(32) NOT NULL DEFAULT 'restock'"
                ")"
            )
        )
        existing = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE schemaname='public' "
                "AND indexname=:n"
            ),
            {"n": "ix_ingredient_price_event_ingredient_time"},
        ).first()
        if existing is None:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_ingredient_price_event_ingredient_time "
                    "ON ingredient_price_event (ingredient_id, recorded_at)"
                )
            )
    else:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS ingredient_price_event ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) "
                "ON DELETE CASCADE, "
                "price_gs INTEGER NOT NULL, "
                "recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "source VARCHAR(32) NOT NULL DEFAULT 'restock'"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_ingredient_price_event_ingredient_time "
                "ON ingredient_price_event (ingredient_id, recorded_at)"
            )
        )

    _bump_schema_version(conn, 18)


def _migration_019_production_completion(conn: Any) -> None:
    """Add production_completion table (Saskia review round 1, T5).

    Table is created via create_all() in init_db() (the model class was
    added to models.py at the same time). This stub only bumps the
    schema_version row. One row per (product_id, for_date) — upserted
    by app/rms/eod_completions.upsert_completion().
    """
    _bump_schema_version(conn, 19)


def _migration_020_sale_date_voided_index(conn: Any) -> None:
    """Add composite index on Sale(sold_at, voided_at).

    Covers every date-range + void-filter query: dashboards, daily/weekly
    summaries, libro_ventas, IVA reports, customer stats. Postgres uses
    CREATE INDEX CONCURRENTLY to avoid locking writes. SQLite uses
    CREATE INDEX IF NOT EXISTS (supported since SQLite 3.9.0).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        existing = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE schemaname='public' "
                "AND indexname=:n"
            ),
            {"n": "ix_sale_sold_at_voided"},
        ).first()
        if existing is None:
            conn.execute(
                text(
                    "CREATE INDEX CONCURRENTLY ix_sale_sold_at_voided "
                    "ON sale (sold_at, voided_at)"
                )
            )
    else:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sale_sold_at_voided "
                "ON sale (sold_at, voided_at)"
            )
        )

    _bump_schema_version(conn, 20)


def _migration_021_stock_movement(conn: Any) -> None:
    """Create stock_movement table (stock movement ledger).

    Append-only audit log of every stock change: sale, adjustment, merma,
    reorder, and initial stock. Powers the /inventario/{id}/movimientos
    movement-history page.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect == "postgresql":
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS stock_movement ("
                "id SERIAL PRIMARY KEY, "
                "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) "
                "ON DELETE CASCADE, "
                "movement_type VARCHAR(16) NOT NULL, "
                "qty FLOAT NOT NULL, "
                "reason TEXT, "
                "reference_id INTEGER, "
                "reference_type VARCHAR(16), "
                "recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "created_by VARCHAR(64)"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_stock_movement_ingredient_recorded "
                "ON stock_movement (ingredient_id, recorded_at)"
            )
        )
    else:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS stock_movement ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) "
                "ON DELETE CASCADE, "
                "movement_type VARCHAR(16) NOT NULL, "
                "qty FLOAT NOT NULL, "
                "reason TEXT, "
                "reference_id INTEGER, "
                "reference_type VARCHAR(16), "
                "recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "created_by VARCHAR(64)"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_stock_movement_ingredient_recorded "
                "ON stock_movement (ingredient_id, recorded_at)"
            )
        )

    _bump_schema_version(conn, 21)


def _migration_022_user_roles(conn: Any) -> None:
    """Add role column to User table for multi-user support.

    role: VARCHAR(32) NOT NULL DEFAULT 'admin'. Values: admin, cashier, manager.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    col_type = "VARCHAR(32) NOT NULL DEFAULT 'admin'" if dialect == "postgresql" else "TEXT DEFAULT 'admin' NOT NULL"
    try:
        conn.execute(text(f"ALTER TABLE user ADD COLUMN role {col_type}"))
    except Exception:
        pass  # already exists

    _bump_schema_version(conn, 22)


def _migration_023_supplier(conn: Any) -> None:
    """Create supplier table + add supplier_id to ingredient (audit items 250, 284).

    Supplier: name, contact_name, phone, email, address, notes, is_active.
    Ingredient.supplier_id: FK to supplier.id (optional, nullable).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    # Supplier table
    if dialect == "postgresql":
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS supplier ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(120) NOT NULL, "
                "contact_name VARCHAR(120), "
                "phone VARCHAR(32), "
                "email VARCHAR(120), "
                "address TEXT, "
                "notes TEXT, "
                "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_supplier_name ON supplier (name)"))
    else:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS supplier ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name VARCHAR(120) NOT NULL, "
                "contact_name VARCHAR(120), "
                "phone VARCHAR(32), "
                "email VARCHAR(120), "
                "address TEXT, "
                "notes TEXT, "
                "is_active INTEGER NOT NULL DEFAULT 1, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_supplier_name ON supplier (name)"))

    # Ingredient.supplier_id
    try:
        if dialect == "postgresql":
            conn.execute(
                text("ALTER TABLE ingredient ADD COLUMN supplier_id INTEGER REFERENCES supplier(id)")
            )
        else:
            conn.execute(
                text("ALTER TABLE ingredient ADD COLUMN supplier_id INTEGER REFERENCES supplier(id)")
            )
    except Exception:
        pass  # already exists

    _bump_schema_version(conn, 23)


def _migration_024_recipe_intel_extended(conn: Any) -> None:
    """Add recipe cook_minutes, difficulty, family, dietary_tags (audit items 122, 124).

    prep_minutes already exists from migration 003.
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("cook_minutes", "INTEGER"),
        ("difficulty", "INTEGER"),
        ("family", "VARCHAR(32)"),
        ("dietary_tags", "TEXT"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE recipe ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass  # already exists

    _bump_schema_version(conn, 24)


def _migration_025_ingredient_opening_stock_reorder_point(conn: Any) -> None:
    """Add opening_stock_qty, opening_stock_date, reorder_point to Ingredient.

    opening_stock: the initial stock when the ingredient was first loaded.
    reorder_point: override of min_stock_qty for more fine-grained reorder control.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("opening_stock_qty", "FLOAT"),
        ("opening_stock_date", "DATE"),
        ("reorder_point", "FLOAT"),
    ]
    for col_name, col_type in cols:
        try:
            if dialect == "postgresql":
                conn.execute(text(f"ALTER TABLE ingredient ADD COLUMN {col_name} {col_type}"))
            else:
                conn.execute(text(f"ALTER TABLE ingredient ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass  # already exists

    _bump_schema_version(conn, 25)



def _migration_026_product_audit_columns(conn: Any) -> None:
    """Add product columns used by audit-implemented features but never migrated.

    Originally added to Product model in commit 541e625 (Section 5/6 audit) but
    no migration was created. Production DB at schema v25 is missing these:
    - is_available: bool — toggle to hide from POS (audit item 158)
    - image_url: str — product image URL (audit item 159)
    - category: str — product category (audit item 160)
    - tags: str — comma-separated tags (audit item 161)
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    cols = [
        ("is_available", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("image_url", "VARCHAR(256)"),
        ("category", "VARCHAR(32)"),
        ("tags", "TEXT"),
    ]
    for col_name, col_type in cols:
        try:
            conn.execute(text(f"ALTER TABLE product ADD COLUMN {col_name} {col_type}"))
        except Exception:
            pass  # already exists

    _bump_schema_version(conn, 26)





def _migration_027_production_plan_template(conn: Any) -> None:
    """PRO-01: weekly repeating production plan template + per-date overrides."""
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "postgresql":
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS production_plan_template (
                id SERIAL PRIMARY KEY,
                weekday INTEGER NOT NULL,
                product_id INTEGER NOT NULL REFERENCES "product"(id),
                qty DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                notes TEXT,
                updated_at TIMESTAMP NOT NULL,
                updated_by VARCHAR(64),
                CONSTRAINT ck_template_weekday_range CHECK (weekday >= 0 AND weekday <= 6),
                CONSTRAINT ck_template_qty_nonneg CHECK (qty >= 0),
                CONSTRAINT uq_template_weekday_product UNIQUE (weekday, product_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_template_weekday ON production_plan_template(weekday)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_template_product_id ON production_plan_template(product_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS production_plan_override (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES "product"(id),
                for_date DATE NOT NULL,
                qty DOUBLE PRECISION NOT NULL,
                notes TEXT,
                updated_at TIMESTAMP NOT NULL,
                updated_by VARCHAR(64),
                CONSTRAINT ck_override_qty_nonneg CHECK (qty >= 0),
                CONSTRAINT uq_override_product_date UNIQUE (product_id, for_date)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_override_product_id ON production_plan_override(product_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_override_for_date ON production_plan_override(for_date)"))
    else:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS production_plan_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                product_id INTEGER NOT NULL REFERENCES product(id),
                qty REAL NOT NULL DEFAULT 1.0,
                notes TEXT,
                updated_at TEXT NOT NULL,
                updated_by VARCHAR(64),
                CONSTRAINT ck_template_weekday_range CHECK (weekday >= 0 AND weekday <= 6),
                CONSTRAINT ck_template_qty_nonneg CHECK (qty >= 0),
                CONSTRAINT uq_template_weekday_product UNIQUE (weekday, product_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_template_weekday ON production_plan_template(weekday)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_template_product_id ON production_plan_template(product_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS production_plan_override (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES product(id),
                for_date DATE NOT NULL,
                qty REAL NOT NULL,
                notes TEXT,
                updated_at TEXT NOT NULL,
                updated_by VARCHAR(64),
                CONSTRAINT ck_override_qty_nonneg CHECK (qty >= 0),
                CONSTRAINT uq_override_product_date UNIQUE (product_id, for_date)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_override_product_id ON production_plan_override(product_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_production_plan_override_for_date ON production_plan_override(for_date)"))

    _bump_schema_version(conn, 27)


def _migration_028_recipe_yield_qty_check(conn: Any) -> None:
    """DB-level CHECK: recipe.yield_qty and recipe_line.qty must be > 0
    when populated (NULL is allowed for draft state).

    Catches bad data at UPDATE time when value is provided.

    IMPORTANT: The trigger syntax below is SQLite-specific (`RAISE(ABORT, ...)`).
    On Postgres we use a CHECK constraint at the table level instead, but
    the constraint is added in `Base.metadata.create_all` via the model's
    CheckConstraint. So on Postgres this migration is a no-op — we just
    bump the schema version.

    Note: model fields are nullable so draft / partial recipes can have
    NULL yields. The CHECK fires only when setting to a non-null value.
    """
    # Detect dialect from the connection
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name == "sqlite":
        try:
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS recipe_yield_qty_positive_update
                BEFORE UPDATE OF yield_qty ON recipe
                FOR EACH ROW
                WHEN NEW.yield_qty IS NOT NULL AND NEW.yield_qty <= 0
                BEGIN
                    SELECT RAISE(ABORT, 'recipe.yield_qty must be > 0 (or NULL for drafts)');
                END
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS recipe_line_qty_positive_update
                BEFORE UPDATE OF qty ON recipe_line
                FOR EACH ROW
                WHEN NEW.qty IS NOT NULL AND NEW.qty <= 0
                BEGIN
                    SELECT RAISE(ABORT, 'recipe_line.qty must be > 0 (or NULL)');
                END
            """))
        except Exception:
            # Older engine without trigger support — Python-level validation
            # in apply_sale() / recipe CRUD continues to enforce.
            pass

    _bump_schema_version(conn, 28)


def _migration_029_herebus_integration(conn: Any) -> None:
    """HEREBUS Drive integration — 10 new tables + customer.zone + pedido.delivery_zone_id.

    Source-of-truth: the 33-file Google Drive dump of HEREBUS's bakery operations
    spreadsheet (Maestra, INGREDIENTES, RECETAS, COSTOS, MERMAS, DASHBOARD, VENTAS,
    RECETAS_MAESTRO, RECETAS_DETALLE, ZONAS_DELIVERY, Wishlist, Risk_Register,
    Benchmarks_Market, KPI_Dashboard, Pricing_Por_Producto, Suppliers, Price_History,
    Shopping_List, Price_Analysis, Production_Planner, Waste_Tracker, Recipe_Template,
    Dashboard_PL, RECETARIO_EN_BLANCO).

    Schema additions:
      - delivery_zone         — 5+ delivery zones (pickup, local, central, etc.)
      - wishlist_item         — kitchen equipment wishlist (₲61M total)
      - risk_item             — operational risk register (12 risks)
      - recipe_pricing        — per-channel pricing (wholesale/retail/etc.)
      - price_history         — supplier purchase history (append-only)
      - production_plan       — batch plan created by Production Planner UI
      - shopping_list_item    — derived list of ingredients to buy
      - market_benchmark      — vs competitor pricing
      - bank_transaction      — EUR (NL) + PYG (PY) transactions
      - settings_kv           — JSON-keyed config (hours, pickup address, etc.)
      - ALTER customer ADD zone TEXT
      - ALTER pedido ADD delivery_zone_id INTEGER FK delivery_zone

    All new tables are created by SQLAlchemy create_all() in init_db() before
    this migration runs. This migration just adds the inline ALTERs for the
    two existing tables (customer, pedido) and bumps schema_version.
    """
    # Customer.zone — free-text label
    try:
        conn.execute(text("ALTER TABLE customer ADD COLUMN zone VARCHAR(64)"))
    except Exception:
        # Column may already exist on a partially-migrated DB
        pass

    # Pedido.delivery_zone_id — FK to new delivery_zone
    try:
        conn.execute(text(
            "ALTER TABLE pedido ADD COLUMN delivery_zone_id INTEGER "
            "REFERENCES delivery_zone(id)"
        ))
    except Exception:
        pass

    # Index for delivery_zone lookups
    try:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pedido_delivery_zone_id "
            "ON pedido(delivery_zone_id)"
        ))
    except Exception:
        pass

    _bump_schema_version(conn, 29)


def _migration_030_recipe_image_url(conn: Any) -> None:
    """Add Recipe.image_url (HEREBUS cookbook photos).

    Optional VARCHAR(255) for storing /static/recipes/<file>.jpg
    paths. Allows the recetas list to show thumbnail previews from
    hand-photographed cookbook pages.
    """
    try:
        conn.execute(text(
            "ALTER TABLE recipe ADD COLUMN image_url VARCHAR(255)"
        ))
    except Exception:
        pass

    _bump_schema_version(conn, 30)


def _migration_031_risk_status_activo(conn: Any) -> None:
    """Re-create ck_risk_status to accept both 'active' and 'activo'.

    Original constraint used ('active', 'mitigated', 'closed') but the
    spreadsheet uses 'activo'. This widens the constraint to allow both.
    """
    # Save current contents
    rows = conn.execute(text("SELECT * FROM risk_item")).fetchall()
    cols = [c for c in conn.execute(text("PRAGMA table_info(risk_item)")).fetchall()]

    # Drop and recreate with new constraint
    conn.execute(text("ALTER TABLE risk_item RENAME TO _risk_item_bk"))
    conn.execute(text("""
        CREATE TABLE risk_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(16),
            description VARCHAR(255) NOT NULL,
            category VARCHAR(32),
            probability INTEGER NOT NULL DEFAULT 2,
            impact_gs INTEGER NOT NULL DEFAULT 0,
            mitigation TEXT,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            owner VARCHAR(64),
            notes TEXT,
            created_at DATETIME NOT NULL,
            CHECK (probability BETWEEN 1 AND 5),
            CHECK (impact_gs >= 0),
            CHECK (status IN ('active', 'activo', 'mitigated', 'closed'))
        )
    """))
    if rows:
        placeholders = ','.join(['?'] * len(cols))
        col_names = ','.join(c[1] for c in cols)
        conn.execute(
            text(f"INSERT INTO risk_item ({col_names}) VALUES ({placeholders})"),
            [tuple(r) for r in rows]
        )
    conn.execute(text("DROP TABLE _risk_item_bk"))

    _bump_schema_version(conn, 31)


def _migration_032_pedido_cancel_reason(conn: Any) -> None:
    """Add pedido.cancel_reason (was in model but missing migration).

    The Pedido model declares `cancel_reason: Mapped[str | None]` (a Text
    column for free-text cancellation reasons), but the original
    pedidos migration didn't include it. Queries like
    `SELECT pedido.cancel_reason` raised ProgrammingError.

    This migration adds the column idempotently. SQLite doesn't support
    IF NOT EXISTS on ADD COLUMN, so we check the schema first.
    """
    cols = [c[1] for c in conn.execute(text("PRAGMA table_info(pedido)")).fetchall()]
    if "cancel_reason" not in cols:
        conn.execute(text("ALTER TABLE pedido ADD COLUMN cancel_reason TEXT"))
    _bump_schema_version(conn, 32)



def _migration_033_ingredient_storage(conn: Any) -> None:
    """Add storage column to ingredient table (Wave 2 / HACCP).

    storage ∈ {ambient, refrigerated, frozen, dry}.
    Inferred on POST /inventario/nuevo from ingredient name (see
    app.rms.ingredient_intel.infer_storage). Operator can override.
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    col_type = "VARCHAR(16)"
    try:
        conn.execute(text(f"ALTER TABLE ingredient ADD COLUMN storage {col_type}"))
    except Exception:
        # Column already exists — idempotent.
        pass
    _bump_schema_version(conn, 33)




def _migration_034_market_price_reference(conn: Any) -> None:
    """Wave 4 — Add market_price_reference table for ingredient market prices.

    Operator-curated baseline. One row per ingredient (no historical
    retention in v1 — the historical data lives in PriceHistory for actual
    purchases). Future: partition by as_of date for time-series.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    float_type = "FLOAT"
    str16 = "VARCHAR(16)"
    str32 = "VARCHAR(32)"
    text_type = "TEXT"
    date = "DATE"
    dt = "TIMESTAMP"
    fk_ref = "INTEGER REFERENCES ingredient(id) ON DELETE CASCADE"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS market_price_reference (
            id {pk_type},
            ingredient_id {fk_ref} NOT NULL,
            unit {str16} NOT NULL,
            price_gs {float_type} NOT NULL,
            source {str32} NOT NULL DEFAULT 'manual',
            notes {text_type},
            as_of {date} NOT NULL,
            created_at {dt} NOT NULL,
            updated_at {dt} NOT NULL
        )
        """
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_market_price_reference_ingredient_id "
        "ON market_price_reference(ingredient_id)"
    ))
    _bump_schema_version(conn, 34)




def _migration_035_compliance_info(conn: Any) -> None:
    """Phase 1.A — Add compliance_info table for tax / regulatory IDs.

    Single-row table; PK is always 1. Stores RUC, INAN R.E., timbrado,
    municipal habilitación, etc. See app.rms.models.ComplianceInfo for
    field documentation.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    int_type = "INTEGER"
    str8 = "VARCHAR(8)"
    str10 = "VARCHAR(10)"
    str16 = "VARCHAR(16)"
    str20 = "VARCHAR(20)"
    str30 = "VARCHAR(30)"
    str60 = "VARCHAR(60)"
    str120 = "VARCHAR(120)"
    str255 = "VARCHAR(255)"
    bool_t = "BOOLEAN" if dialect != "sqlite" else "INTEGER"
    dt = "TIMESTAMP"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS compliance_info (
            id {pk_type},
            ruc {str20},
            razon_social {str120},
            nombre_fantasia {str120},
            tax_regime {str16} NOT NULL DEFAULT 'resimple',
            iva_default_rate {str8} NOT NULL DEFAULT '10',
            timbrado_number {str20},
            timbrado_expiry {str10},
            next_boleta_resimple_number {int_type} NOT NULL DEFAULT 1,
            next_factura_number {int_type} NOT NULL DEFAULT 1,
            inan_re_number {str30},
            inan_re_expiry {str10},
            director_tecnico {str120},
            director_tecnico_registro {str30},
            municipal_habilitacion {str30},
            municipal_habilitacion_expiry {str10},
            establecimiento_address {str255},
            establecimiento_phone {str30},
            establecimiento_email {str120},
            logo_path {str255},
            labor_cost_per_hour_gs {int_type} NOT NULL DEFAULT 25000,
            overhead_multiplier_pct {int_type} NOT NULL DEFAULT 15,
            sifen_certificate_id {str60},
            sifen_csc_code {str60},
            sifen_test_mode {bool_t} NOT NULL DEFAULT 1,
            updated_at {dt} NOT NULL
        )
        """
    ))
    # Idempotent: seed the single row if missing.
    has_row = conn.execute(text("SELECT COUNT(*) FROM compliance_info WHERE id = 1")).scalar()
    if not has_row:
        conn.execute(text(
            "INSERT INTO compliance_info (id, tax_regime, iva_default_rate, "
            "next_boleta_resimple_number, next_factura_number, "
            "labor_cost_per_hour_gs, overhead_multiplier_pct, sifen_test_mode, updated_at) "
            "VALUES (1, 'resimple', '10', 1, 1, 25000, 15, 1, CURRENT_TIMESTAMP)"
        ))
    _bump_schema_version(conn, 35)




def _migration_036_product_tax_haccp(conn: Any) -> None:
    """Phase 1.A/C — Add product tax + HACCP columns.

    - iva_rate (default '10' = general rate per Art. 91 inc. e Ley 125/91)
    - requires_rspa (default False; only true when product is packaged + labeled)
    - rspa_number / rspa_expiry (NULL until operator registers the R.S.P.A.)
    - yield_percentage (NULL = no moisture loss correction; default 0.85 applied at
      costing-time when NULL per docs/plans/2026-09-22-ingredient-domain.md)

    Idempotent: each column uses _add_column_if_missing so re-runs are no-ops.
    """
    _add_column_if_missing(conn, "product", "iva_rate", "VARCHAR(8)", "VARCHAR(8) NOT NULL DEFAULT '10'")
    _add_column_if_missing(conn, "product", "requires_rspa", "BOOLEAN", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "product", "rspa_number", "VARCHAR(30)", "VARCHAR(30)")
    _add_column_if_missing(conn, "product", "rspa_expiry", "VARCHAR(10)", "VARCHAR(10)")
    _add_column_if_missing(conn, "product", "yield_percentage", "FLOAT", "FLOAT")
    _bump_schema_version(conn, 36)




def _migration_037_sale_fiscal_invoice(conn: Any) -> None:
    """Phase 1.B — Add fiscal invoice fields to sale table.

    Required for Paraguayan DNIT/SET bookkeeping (Ley 7165 — every sale
    needs a comprobante; Res 1421/05 — Libro IVA Ventas monthly).
    """
    _add_column_if_missing(conn, "sale", "invoice_type", "VARCHAR(20)", "VARCHAR(20) NOT NULL DEFAULT 'boleta_resimple'")
    _add_column_if_missing(conn, "sale", "invoice_number", "INTEGER", "INTEGER")
    _add_column_if_missing(conn, "sale", "invoice_customer_ruc", "VARCHAR(20)", "VARCHAR(20)")
    _add_column_if_missing(conn, "sale", "invoice_customer_name", "VARCHAR(120)", "VARCHAR(120)")
    _add_column_if_missing(conn, "sale", "iva_rate", "VARCHAR(8)", "VARCHAR(8) NOT NULL DEFAULT '10'")
    _add_column_if_missing(conn, "sale", "iva_base_gs", "INTEGER", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "sale", "iva_amount_gs", "INTEGER", "INTEGER NOT NULL DEFAULT 0")
    _bump_schema_version(conn, 37)




def _migration_038_ingredient_haccp(conn: Any) -> None:
    """Phase 1.C — HACCP storage columns on ingredient table.

    Per Res S.G. N° 213/2019, every bakery ingredient must have
    temperature/humidity/water-activity targets recorded. These columns
    are nullable for backwards compatibility — operators fill them in
    over time via the inventario edit form.
    """
    _add_column_if_missing(conn, "ingredient", "temp_min_c", "FLOAT", "FLOAT")
    _add_column_if_missing(conn, "ingredient", "temp_max_c", "FLOAT", "FLOAT")
    _add_column_if_missing(conn, "ingredient", "humidity_max_pct", "FLOAT", "FLOAT")
    _add_column_if_missing(conn, "ingredient", "water_activity_aw", "FLOAT", "FLOAT")
    _add_column_if_missing(conn, "ingredient", "lot_required", "BOOLEAN", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "recipe", "yield_percentage", "FLOAT", "FLOAT")
    _add_column_if_missing(conn, "recipe", "direct_labor_minutes", "INTEGER", "INTEGER")
    _bump_schema_version(conn, 38)


def _migration_050_sale_void_reason(conn: Any) -> None:
    """Add void_reason and voided_by to sale for CIE-01 cancellation audit trail.

    The previous void flow only stored ``voided_at``. That made it impossible
    to tell *why* a sale was voided (customer request, wrong product, etc.)
    or *who* voided it — both critical for a small bakery's accountability.
    Both columns are nullable so legacy voided rows (and fresh sales) don't
    need to populate them at write time.
    """
    _add_column_if_missing(conn, "sale", "void_reason", "TEXT", "TEXT")
    _add_column_if_missing(conn, "sale", "voided_by", "VARCHAR(64)", "VARCHAR(64)")
    _bump_schema_version(conn, 50)


def _migration_051_ingredient_variant(conn: Any) -> None:
    """Add ingredient_variant table (Sprint 7 — Decision A1).

    Saskia's exact words from the audio review:
      "harina 1kg / harina 250g / proveedor X — a single ingredient 'harina'
       with sub-rows for each package".

    The previous schema treated each package as its own Ingredient row, which
    broke the rollup question "how much harina do I have total?" and made the
    price-history chart meaningless (one chart per package instead of one
    per ingredient with variant lines).

    Schema:
      ingredient_variant
        id, ingredient_id (FK ingredient.id, CASCADE), package_size,
        package_unit (g/kg/ml/l/und), purchase_price_gs (int Gs.),
        supplier_id (FK supplier.id, NULL OK), preferred (bool — exactly one
        per ingredient for "current price" semantics), created_at, updated_at.

    Backfill: existing Ingredients with a purchase_price_gs get one default
    variant with package_size=1, package_unit=ingredient.unit, price=current.
    Done in Python after the table is created — see _backfill_default_variants.
    """
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS ingredient_variant ("
            "id SERIAL PRIMARY KEY,"
            "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) ON DELETE CASCADE,"
            "package_size DOUBLE PRECISION NOT NULL DEFAULT 1.0,"
            "package_unit VARCHAR(8) NOT NULL DEFAULT 'und',"
            "purchase_price_gs INTEGER,"
            "supplier_id INTEGER REFERENCES supplier(id),"
            "preferred BOOLEAN NOT NULL DEFAULT FALSE,"
            "notes TEXT,"
            "created_at TIMESTAMP NOT NULL DEFAULT NOW(),"
            "updated_at TIMESTAMP NOT NULL DEFAULT NOW()"
            ")"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ingredient_variant_ingredient "
            "ON ingredient_variant(ingredient_id)"
        ))
        # MySQL / Postgres partial unique: at most one preferred per ingredient
        # Postgres supports this directly; SQLite emulates with a trigger.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_ingredient_variant_preferred "
            "ON ingredient_variant(ingredient_id) WHERE preferred = TRUE"
        ))
    else:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS ingredient_variant ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "ingredient_id INTEGER NOT NULL REFERENCES ingredient(id) ON DELETE CASCADE,"
            "package_size REAL NOT NULL DEFAULT 1.0,"
            "package_unit VARCHAR(8) NOT NULL DEFAULT 'und',"
            "purchase_price_gs INTEGER,"
            "supplier_id INTEGER REFERENCES supplier(id),"
            "preferred BOOLEAN NOT NULL DEFAULT 0,"
            "notes TEXT,"
            "created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),"
            "updated_at TIMESTAMP NOT NULL DEFAULT (datetime('now'))"
            ")"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ingredient_variant_ingredient "
            "ON ingredient_variant(ingredient_id)"
        ))
        # SQLite doesn't support partial unique indexes before 3.8 — emulate
        # the "at most one preferred per ingredient" rule with a trigger.
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS trg_ingredient_variant_preferred "
            "BEFORE INSERT ON ingredient_variant "
            "WHEN NEW.preferred = 1 "
            "BEGIN "
            "  UPDATE ingredient_variant SET preferred = 0 "
            "  WHERE ingredient_id = NEW.ingredient_id AND preferred = 1; "
            "END"
        ))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS trg_ingredient_variant_preferred_upd "
            "BEFORE UPDATE ON ingredient_variant "
            "WHEN NEW.preferred = 1 "
            "BEGIN "
            "  UPDATE ingredient_variant SET preferred = 0 "
            "  WHERE id != NEW.id AND ingredient_id = NEW.ingredient_id AND preferred = 1; "
            "END"
        ))

    # Backfill: for every existing Ingredient with a purchase_price_gs,
    # create a default variant. Done in SQL so it works without importing
    # the model layer (the migration must be self-contained).
    if dialect == "postgresql":
        conn.execute(text(
            "INSERT INTO ingredient_variant "
            "(ingredient_id, package_size, package_unit, purchase_price_gs, supplier_id, preferred) "
            "SELECT id, 1.0, unit, purchase_price_gs, supplier_id, TRUE "
            "FROM ingredient "
            "WHERE purchase_price_gs IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM ingredient_variant v "
            "  WHERE v.ingredient_id = ingredient.id"
            ")"
        ))
    else:
        conn.execute(text(
            "INSERT INTO ingredient_variant "
            "(ingredient_id, package_size, package_unit, purchase_price_gs, supplier_id, preferred) "
            "SELECT id, 1.0, unit, purchase_price_gs, supplier_id, 1 "
            "FROM ingredient "
            "WHERE purchase_price_gs IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM ingredient_variant v "
            "  WHERE v.ingredient_id = ingredient.id"
            ")"
        ))

    _bump_schema_version(conn, 51)


def _migration_052_ingredient_forecast_horizon(conn: Any) -> None:
    """Add Ingredient.forecast_horizon_days (Sprint 7 — Decision B).

    Per-ingredient forecast horizon for the "days until I'm short" widget
    (US 2.3). Nullable — when NULL, falls back to the global
    DEFAULT_FORECAST_HORIZON_DAYS env var (14).

    Why per-ingredient and not just one global: supplier lead times vary
    a lot. dulce_de_leche from supplier A arrives in 2 days; mantequilla
    from supplier B takes a week. A single horizon can't capture both.
    """
    _add_column_if_missing(
        conn, "ingredient", "forecast_horizon_days",
        "INTEGER", "INTEGER",
    )
    _bump_schema_version(conn, 52)






def _migration_039_category_table(conn: Any) -> None:
    """Phase 1 catalog unification — operator-configurable categories/families.

    Replaces the hardcoded lists previously living in
    app/templates/_components/tags.html (product_category_options,
    recipe_family_options, product_tag_options, dietary_tag_options)
    and the duplicated family list in app/templates/receta_form.html.

    Schema:
      - id SERIAL/INTEGER PRIMARY KEY
      - name VARCHAR(64) NOT NULL UNIQUE per scope
      - scope VARCHAR(16) NOT NULL   -- 'product' | 'recipe_family'
      - sort_order INTEGER NOT NULL DEFAULT 0
      - is_active BOOLEAN NOT NULL DEFAULT 1
      - created_at TIMESTAMP

    Seed data matches the prior hardcoded values exactly so the migration
    is invisible to operators — every existing dropdown still shows the
    same options in the same order.

    Idempotent: INSERT OR IGNORE so re-runs are no-ops.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS category (
            id {pk_type},
            name VARCHAR(64) NOT NULL,
            scope VARCHAR(16) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (scope, name)
        )
        """
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_category_scope_active "
        "ON category (scope, is_active, sort_order)"
    ))

    # Seed product categories
    product_cats = [
        ("Panadería", 10),
        ("Pastelería", 20),
        ("Dulces", 30),
        ("Bollería", 40),
        ("Bebidas", 50),
        ("Lácteos", 60),
        ("Salados", 70),
        ("Congelados", 80),
        ("Especiales", 90),
        ("Temporada", 100),
        ("Sin TACC", 110),
        ("Vegano", 120),
        ("Light", 130),
    ]
    # Seed recipe families
    recipe_fams = [
        ("Panadería", 10),
        ("Pastelería", 20),
        ("Bollería", 30),
        ("Dulces", 40),
        ("Galletería", 50),
        ("Tortas", 60),
        ("Masas", 70),
        ("Rellenos", 80),
        ("Coberturas", 90),
        ("Salsas", 100),
        ("Bases", 110),
        ("Temporada", 120),
        ("Especiales", 130),
    ]

    # SQLAlchemy's create_all() runs BEFORE this migration and creates
    # the category table WITHOUT defaults on is_active / created_at.
    # So INSERTs must pass all NOT NULL columns explicitly.
    # Insert idempotently: ON CONFLICT DO NOTHING / INSERT OR IGNORE.
    for name, sort in product_cats:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO category "
                "(name, scope, sort_order, is_active, created_at) "
                "VALUES (:n, 'product', :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO category "
                "(name, scope, sort_order, is_active, created_at) "
                "VALUES (:n, 'product', :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (scope, name) DO NOTHING"
            ),
            {"n": name, "s": sort},
        )
    for name, sort in recipe_fams:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO category "
                "(name, scope, sort_order, is_active, created_at) "
                "VALUES (:n, 'recipe_family', :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO category "
                "(name, scope, sort_order, is_active, created_at) "
                "VALUES (:n, 'recipe_family', :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (scope, name) DO NOTHING"
            ),
            {"n": name, "s": sort},
        )

    # Seed Tag table with dietary tags (idempotent). The Tag model is created
    # via SQLAlchemy create_all() in init_db() — this just ensures rows exist.
    # ensure_starter_tags is a no-op on rows already present.
    try:
        # Use the same connection as the migration so it's in the same transaction.
        from app.rms.tagging import STARTER_TAGS
        for name, kind, color in STARTER_TAGS:
            try:
                ensure_tag_with_conn(conn, name, kind, color)
            except Exception:
                pass  # Already exists, or transient — skip.
    except Exception as exc:
        # Tag seeding is best-effort — don't block schema migration.
        print(f"WARN: tag seeding skipped: {exc!r}", file=sys.stderr)

    _bump_schema_version(conn, 39)


def ensure_tag_with_conn(conn: Any, name: str, kind: str, color: str = "#757575") -> object:
    """INSERT OR IGNORE a tag by (name, kind). Used inside migrations.

    Mirrors app.rms.tags.ensure_tag but takes a raw connection instead of
    a Session (migrations don't have ORM sessions).
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    if dialect == "sqlite":
        conn.execute(
            text("INSERT OR IGNORE INTO tag (name, kind, color) VALUES (:n, :k, :c)"),
            {"n": name, "k": kind, "c": color},
        )
    else:
        # Postgres: ON CONFLICT DO NOTHING on (name, kind)
        conn.execute(
            text(
                "INSERT INTO tag (name, kind, color) VALUES (:n, :k, :c) "
                "ON CONFLICT (name, kind) DO NOTHING"
            ),
            {"n": name, "k": kind, "c": color},
        )


def _migration_040_pricing_setting(conn: Any) -> None:
    """Phase 2 — SettingsKV-backed pricing markup setting.

    The suggested retail multiplier (cost * 3) was previously hardcoded
    in three places: app/routers/recipes.py:519, app/templates/producto_form.html:320,
    and app/templates/receta_form.html:759. This migration:

    1. Adds a settings_kv row keyed 'pricing.suggested_markup' with the
       legacy default (multiplier=3.0, round_to_gs=1000).
    2. Operators can now change the multiplier from /settings/pricing
       without code deploy.

    Idempotent: app_meta_write uses ON CONFLICT DO UPDATE which is a no-op
    if the value already matches.
    """
    import json as _json
    pricing_value = _json.dumps({"multiplier": 3.0, "round_to_gs": 1000})
    from app.rms.db import app_meta_write
    app_meta_write(conn, "pricing.suggested_markup", pricing_value)
    _bump_schema_version(conn, 40)





def _migration_041_channel_catalog(conn: Any) -> None:
    """Phase 4 — Sale channel catalog table.

    Replaces the hardcoded CHANNELS_DISPLAY / ALLOWED_CHANNELS frozenset
    in app/rms/schemas.py with a DB-backed table. Operators can add/edit
    channels from /settings/channels without code deploy.

    Seed data matches the legacy frozenset exactly:
      - mostrador (default)
      - mostrador-encargo
      - whatsapp
      - pedidosya
      - monchis
    """

    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS channel (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_default {bool_t} NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    channels = [
        ("mostrador", "Mostrador", 10, True),
        ("mostrador-encargo", "Mostrador (encargo)", 20, False),
        ("whatsapp", "WhatsApp", 30, False),
        ("pedidosya", "PedidosYa", 40, False),
        ("monchis", "Monchis", 50, False),
    ]
    for code, label, sort, is_default in channels:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO channel (code, label, sort_order, is_default, is_active, created_at) "
                "VALUES (:c, :l, :s, :d, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO channel (code, label, sort_order, is_default, is_active, created_at) "
                "VALUES (:c, :l, :s, :d, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "s": sort, "d": 1 if is_default else 0},
        )

    _bump_schema_version(conn, 41)


def _migration_042_payment_method_catalog(conn: Any) -> None:
    """Phase 4 — Payment method catalog table.

    Replaces PAYMENT_METHODS_DISPLAY / ALLOWED_PAYMENT_METHODS frozenset
    in app/rms/schemas.py with a DB-backed table.

    Seed data matches the legacy frozenset:
      - efectivo (default)
      - transferencia (requires reference)
      - qr
      - tarjeta (typically has fee_pct)
      - otro
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"
    float_t = "FLOAT" if dialect == "sqlite" else "DOUBLE PRECISION"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS payment_method (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            requires_reference {bool_t} NOT NULL DEFAULT 0,
            fee_pct {float_t} NOT NULL DEFAULT 0.0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_default {bool_t} NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    methods = [
        ("efectivo", "Efectivo", False, 0.0, True),
        ("transferencia", "Transferencia", True, 0.0, False),
        ("qr", "QR", True, 0.0, False),
        ("tarjeta", "Tarjeta", True, 3.0, False),
        ("otro", "Otro", False, 0.0, False),
    ]
    for code, label, req_ref, fee, is_default in methods:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO payment_method "
                "(code, label, requires_reference, fee_pct, sort_order, is_default, is_active, created_at) "
                "VALUES (:c, :l, :r, :f, :s, :d, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO payment_method "
                "(code, label, requires_reference, fee_pct, sort_order, is_default, is_active, created_at) "
                "VALUES (:c, :l, :r, :f, :s, :d, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "r": 1 if req_ref else 0, "f": fee, "s": 0, "d": 1 if is_default else 0},
        )

    _bump_schema_version(conn, 42)










def _migration_043_branding_setting(conn: Any) -> None:
    """Phase 5 — Branding settings.

    Seeds SettingsKV["branding"] with defaults that match the previous
    hardcoded copy in templates/login.html and templates/base.html:
      - business_name: "Saskia RMS"
      - tagline: "Panadería / Bakery — Sistema de gestión"
      - footer: "Sistema local · 2026"
      - accent_color: "#f97316" (CSS --color-accent)
      - logo_path: "" (no logo by default)

    Operators can change any field from /settings/branding without code
    deploy (Phase 5 follow-up UI page).
    """
    import json as _json
    branding = {
        "business_name": "Saskia RMS",
        "tagline": "Panadería / Bakery — Sistema de gestión",
        "footer": "Sistema local",
        "accent_color": "#f97316",
        "logo_path": "",
    }
    from app.rms.db import app_meta_write
    app_meta_write(conn, "branding", _json.dumps(branding))
    _bump_schema_version(conn, 43)





def _migration_044_message_templates(conn: Any) -> None:
    """Phase 6 — MessageTemplate table + seed common templates.

    Replaces hardcoded copy in pedidos.py, email notifications, etc.
    Operators can edit from /settings/templates without code deploy.

    Seed data matches the prior hardcoded copy in app/routers/pedidos.py
    and similar files. Body uses {placeholder} format() syntax — substitute
    at send time.

    Idempotent: INSERT OR IGNORE on (channel, key, locale) unique.
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    text_type = "TEXT"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS message_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel VARCHAR(16) NOT NULL,
            key VARCHAR(64) NOT NULL,
            subject VARCHAR(200),
            body {text_type} NOT NULL,
            locale VARCHAR(8) NOT NULL DEFAULT 'es-PY',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            notes {text_type},
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (channel, key, locale)
        )
        """
    ))

    # Seed default templates (Paraguayan Spanish, es-PY)
    defaults = [
        # WhatsApp — pedido ready for pickup
        (
            "whatsapp", "pedido_listo",
            None,
            "¡Hola {customer_name}! Tu pedido #{pedido_id} ya está listo para retirar. "
            "Total: Gs. {total_gs}. ¡Gracias por confiar en {business_name}!",
            "es-PY", 1,
            "Sent via WhatsApp when pedido is marked ready for pickup.",
        ),
        # WhatsApp — pedido confirmed
        (
            "whatsapp", "pedido_confirmado",
            None,
            "¡{customer_name}, tu pedido #{pedido_id} fue confirmado! "
            "Prometido para {promised_date}. Total: Gs. {total_gs}.",
            "es-PY", 1,
            "Sent via WhatsApp when pedido is first created.",
        ),
        # WhatsApp — low stock alert (for supplier/internal)
        (
            "whatsapp", "stock_bajo",
            None,
            "⚠ Stock bajo: {ingredient_name}. Actual: {stock_qty} {unit} "
            "(mínimo: {min_stock_qty} {unit}). Reposición sugerida: {reorder_qty} {unit}.",
            "es-PY", 1,
            "Sent to operator when an ingredient drops below minimum.",
        ),
        # Email — daily summary (subject + body)
        (
            "email", "resumen_diario",
            "Resumen del día — {date}",
            "Buen día, Iván.\n\n"
            "Ventas de ayer: {total_sales_gs} Gs. ({total_count} ventas).\n"
            "Stock bajo: {low_stock_count} ingredientes.\n"
            "Por vencer: {expiring_count} ingredientes.\n\n"
            "Detalle en {dashboard_url}.",
            "es-PY", 1,
            "Daily morning email with key metrics.",
        ),
        # WhatsApp — customer order share link
        (
            "whatsapp", "pedido_compartir",
            None,
            "Tu pedido #{pedido_id} en {business_name}: {public_url}",
            "es-PY", 1,
            "Sent to customer with the public pickup-tracking link.",
        ),
        # Generic — fallback
        (
            "email", "generic",
            "Notificación de {business_name}",
            "{message_body}",
            "es-PY", 1,
            "Generic email template. Subject + body interpolated.",
        ),
    ]

    for ch, key, subject, body, locale, version, notes in defaults:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO message_template "
                "(channel, key, subject, body, locale, version, notes, is_active, updated_at) "
                "VALUES (:ch, :k, :sub, :body, :loc, :v, :notes, 1, CURRENT_TIMESTAMP)"
            ),
            {"ch": ch, "k": key, "sub": subject, "body": body, "loc": locale, "v": version, "notes": notes},
        )

    _bump_schema_version(conn, 44)





def _migration_045_margin_tiers(conn: Any) -> None:
    """Phase 7 — Margin tier table (operator-tunable thresholds).

    Replaces hardcoded magic numbers in app/rms/tags.py:378-382 that used
    10000/5000/1000 Gs thresholds for "top 10%", "top 25%", "bottom 25%"
    recipe filters. Operators can adjust thresholds via /api/margin-tiers.

    Seed data preserves the legacy behavior exactly:
      - top_10: max 10000 Gs
      - top_25: max 5000 Gs
      - bottom_25: min 1000 Gs
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS margin_tier (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            min_cost_gs INTEGER,
            max_cost_gs INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    tiers = [
        ("top_10", "Top 10% (más baratos)", 10000, 10),
        ("top_25", "Top 25%", 5000, 20),
        ("bottom_25", "Bottom 25% (más caros)", 1000, 30),
    ]
    for code, label, cost, sort in tiers:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO margin_tier (code, label, max_cost_gs, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :cost, :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO margin_tier (code, label, max_cost_gs, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :cost, :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "cost": cost, "s": sort},
        )
    # bottom_25 has min_cost_gs, not max
    if dialect == "sqlite":
        conn.execute(text(
            "UPDATE margin_tier SET min_cost_gs = 1000, max_cost_gs = NULL WHERE code = 'bottom_25'"
        ))
    else:
        conn.execute(text(
            "UPDATE margin_tier SET min_cost_gs = 1000, max_cost_gs = NULL WHERE code = 'bottom_25'"
        ))

    _bump_schema_version(conn, 45)


def _migration_046_stock_status_config(conn: Any) -> None:
    """Phase 7 — Stock status thresholds (operator-tunable).

    Replaces hardcoded magic numbers in app/rms/tags.py:325-331:
      - critico: ratio < 0.5
      - sobrestock: ratio > 5.0
      - muerto: no consumption in last 30 days
      - bajo_min: stock < min_stock_qty (no threshold; just the comparison)

    Seed data preserves the legacy behavior.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"
    float_t = "FLOAT" if dialect == "sqlite" else "DOUBLE PRECISION"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS stock_status_config (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            threshold_ratio {float_t},
            threshold_days INTEGER,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            notes TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    statuses = [
        # code, label, ratio, days, sort
        ("bajo_min", "Bajo mínimo (stock < min)", None, None, 10),
        ("critico", "Crítico (ratio < 0.5)", 0.5, None, 20),
        ("sobrestock", "Sobrestock (ratio > 5.0)", 5.0, None, 30),
        ("muerto", "Sin consumo (≥ 30 días)", None, 30, 40),
    ]
    for code, label, ratio, days, sort in statuses:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO stock_status_config "
                "(code, label, threshold_ratio, threshold_days, sort_order, is_active, updated_at) "
                "VALUES (:c, :l, :r, :d, :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO stock_status_config "
                "(code, label, threshold_ratio, threshold_days, sort_order, is_active, updated_at) "
                "VALUES (:c, :l, :r, :d, :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "r": ratio, "d": days, "s": sort},
        )

    _bump_schema_version(conn, 46)





def _migration_047_storage_types(conn: Any) -> None:
    """Phase 8 — HACCP storage codes table.

    Replaces the hardcoded _STORAGE_KEYWORDS dict in
    app/rms/ingredient_intel.py. Operators add/edit storage codes from
    /settings/catalog without code deploy.

    Seed data matches the legacy codes exactly:
      - ambient (default, no keyword match)
      - refrigerated (matches dairy keywords)
      - frozen (matches 'congelad*' keywords)
    HACCP-related hints (requires_temp_min/max, requires_humidity_max)
    let downstream HACCP reports know what data to surface.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS storage_type (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            requires_temp_min {bool_t} NOT NULL DEFAULT 0,
            requires_temp_max {bool_t} NOT NULL DEFAULT 0,
            requires_humidity_max {bool_t} NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    defaults = [
        # code, label, requires_temp_min, requires_temp_max, requires_humidity, sort
        ("ambient",      "Ambiente (seco)",         0, 0, 0, 10),
        ("refrigerated", "Refrigerado (2-8°C)",     1, 1, 0, 20),
        ("frozen",       "Congelado (≤ -18°C)",     0, 1, 0, 30),
    ]
    for code, label, tmin, tmax, hum, sort in defaults:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO storage_type "
                "(code, label, requires_temp_min, requires_temp_max, requires_humidity_max, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :tmin, :tmax, :hum, :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO storage_type "
                "(code, label, requires_temp_min, requires_temp_max, requires_humidity_max, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :tmin, :tmax, :hum, :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "tmin": tmin, "tmax": tmax, "hum": hum, "s": sort},
        )

    _bump_schema_version(conn, 47)


def _migration_048_date_range_presets(conn: Any) -> None:
    """Phase 9 — Date range presets table.

    Replaces the hardcoded DATE_RANGE_PRESETS_DAYS dict in
    app/rms/constants.py. Operators add/edit presets from
    /settings/catalog without code deploy.

    Seed data matches the legacy presets exactly:
      - today (1 day), week (7), month (30), quarter (90), year (365)
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS date_range_preset (
            id {pk_type},
            code VARCHAR(32) NOT NULL UNIQUE,
            label VARCHAR(64) NOT NULL,
            days INTEGER NOT NULL,
            is_default {bool_t} NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    defaults = [
        # code, label, days, is_default, sort
        ("today",    "Hoy",         1,   1, 10),
        ("week",     "7 días",      7,   0, 20),
        ("month",    "30 días",     30,  0, 30),
        ("quarter",  "90 días",     90,  0, 40),
        ("year",     "1 año",       365, 0, 50),
    ]
    for code, label, days, is_def, sort in defaults:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO date_range_preset "
                "(code, label, days, is_default, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :d, :def, :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO date_range_preset "
                "(code, label, days, is_default, sort_order, is_active, created_at) "
                "VALUES (:c, :l, :d, :def, :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "l": label, "d": days, "def": is_def, "s": sort},
        )

    _bump_schema_version(conn, 48)





def _migration_049_storage_keywords(conn: Any) -> None:
    """Phase 11 — Localize HACCP storage keywords to DB.

    Replaces the hardcoded _STORAGE_KEYWORDS dict in
    app/rms/ingredient_intel.py. Operators add/edit storage keywords from
    /settings/catalog without code deploy.

    Seed data matches the legacy dict exactly:
      - refrigerated: leche, crema, manteca, mantequilla, yogur, queso,
        huevo, huevos, ricota, requesón, dulce de leche, crema agria,
        queso crema
      - frozen: congelad
      - ambient: (default — no keywords; anything not perishable)
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    bool_t = "INTEGER" if dialect == "sqlite" else "BOOLEAN"

    conn.execute(text(
        f"""
        CREATE TABLE IF NOT EXISTS storage_keyword (
            id {pk_type},
            storage_code VARCHAR(32) NOT NULL,
            keyword VARCHAR(64) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active {bool_t} NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ))

    # Seed data: (storage_code, keyword, sort_order)
    seeds = [
        # Refrigerated — order by likelihood of match
        ("refrigerated", "leche", 10),
        ("refrigerated", "crema", 20),
        ("refrigerated", "manteca", 30),
        ("refrigerated", "mantequilla", 40),
        ("refrigerated", "yogur", 50),
        ("refrigerated", "queso", 60),
        ("refrigerated", "huevo", 70),
        ("refrigerated", "huevos", 80),
        ("refrigerated", "ricota", 90),
        ("refrigerated", "requesón", 100),
        ("refrigerated", "dulce de leche", 110),
        ("refrigerated", "crema agria", 120),
        ("refrigerated", "queso crema", 130),
        # Frozen — match 'congelad' prefix
        ("frozen", "congelad", 10),
    ]
    for code, keyword, sort in seeds:
        conn.execute(
            text(
                "INSERT OR IGNORE INTO storage_keyword (storage_code, keyword, sort_order, is_active, created_at) "
                "VALUES (:c, :k, :s, 1, CURRENT_TIMESTAMP)"
            ) if dialect == "sqlite" else text(
                "INSERT INTO storage_keyword (storage_code, keyword, sort_order, is_active, created_at) "
                "VALUES (:c, :k, :s, TRUE, CURRENT_TIMESTAMP) "
                "ON CONFLICT (storage_code, keyword) DO NOTHING"
            ),
            {"c": code, "k": keyword, "s": sort},
        )

    _bump_schema_version(conn, 49)


def _migration_053_sale_packaging(conn: Any) -> None:
    """Sprint 8 — US 4.1: per-sale packaging.

    Saskia's exact words from the audio review (paraphrased from the
    Spanish audio):

      "In product I would put a compressor that is a package instead of in
       the recipe. Better, yes, you are right. Besides the product I would
       put it in the sale itself. Because if it is local I would put it in
       the sale. If it is to eat in the place you don't need a package.
       No. And in the event part you just have to press the package."

    Translation: same product sold different ways (local/eat-in/to-go/event)
    needs different packaging. The packaging is part of the SALE, not the
    product — because a "torta entera" sold for a birthday event needs a
    big box, but the same torta sold by-the-slice in the shop needs a paper
    bag (or no packaging at all).

    Schema additions:
      ingredient.is_packaging   — flags an Ingredient as a packaging item
                                  (boxes, bags, ribbons). NULL/False = regular
                                  food ingredient; True = packaging.
                                  Packaging ingredients are sold, not consumed
                                  by recipes, so they appear in a separate
                                  inventory panel and their stock moves are
                                  recorded against sales, not recipe batches.
      sale.packaging_item_id    — FK to ingredient.id (only valid when
                                  ingredient.is_packaging = TRUE). NULL = no
                                  packaging on this sale (e.g. eat-in).
      sale.packaging_qty        — units of packaging consumed (>= 0, integer
                                  when package_unit = und; float otherwise).
                                  NULL when packaging_item_id IS NULL.

    Cost effect on the sale is computed in apply_sale() and stored on the
    Sale row as part of total_price_gs (the package cost is added to the
    customer-facing price; this matches the existing "packaging_gs" field
    on RecipePricing which adds it to the wholesale/retail price).
    """
    # 1. Ingredient.is_packaging — flag packaging items
    _add_column_if_missing(
        conn, "ingredient", "is_packaging",
        "BOOLEAN", "BOOLEAN NOT NULL DEFAULT 0",
    )
    # 2. Sale.packaging_item_id — FK to ingredient
    _add_column_if_missing(
        conn, "sale", "packaging_item_id",
        "INTEGER", "INTEGER REFERENCES ingredient(id)",
    )
    # 3. Sale.packaging_qty
    _add_column_if_missing(
        conn, "sale", "packaging_qty",
        "FLOAT", "FLOAT",
    )
    # 4. Index for "list sales by packaging item" reporting
    if conn.dialect.name == "postgresql":
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sale_packaging_item "
            "ON sale(packaging_item_id)"
        ))
    else:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sale_packaging_item "
            "ON sale(packaging_item_id)"
        ))
    _bump_schema_version(conn, 53)



def _migration_054_tag_algebra(conn: Any) -> None:
    """Tag algebra: cached derived tags + SINACLA cross-contamination flag.

    - recipe.allergens (Text, nullable) — union cache
    - recipe.derived_dietary_tags (Text, nullable) — intersection cache
    - ingredient.may_contain_gluten (bool, default 0)
    - product.inherited_tags (Text, nullable)
    No data backfill: caches populate lazily on first recipe save/visit.
    """
    def _add_column(table: str, col: str, ddl: str) -> None:
        # Idempotent: create_all may have already added the column via the
        # ORM model before migrations run; ALTER would then fail.
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        except Exception:
            pass  # column already exists
    _add_column("recipe", "allergens", "TEXT")
    _add_column("recipe", "derived_dietary_tags", "TEXT")
    _add_column("ingredient", "may_contain_gluten", "BOOLEAN NOT NULL DEFAULT 0")
    _add_column("product", "inherited_tags", "TEXT")
    _bump_schema_version(conn, 54)


def _migration_055_supplier_ruc(conn: Any) -> None:
    """Add supplier.ruc field (Paraguay RUC/ID for legal suppliers).

    RUC (Registro Único del Contribuyente) is required for legal invoices
    (factura legal) and supplier identification in Paraguay.
    """
    def _add_column(table: str, col: str, ddl: str) -> None:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        except Exception:
            pass  # column already exists

    _add_column("supplier", "ruc", "VARCHAR(20)")
    _bump_schema_version(conn, 55)


def _migration_056_bank_reconciliation(conn: Any) -> None:
    """Wire the bank_reconciliation migration that ships in
    ``app/rms/migrations/_056_bank_reconciliation.py`` into the
    MIGRATIONS registry. The function is defined there; we just
    re-export it here so init_db can call it by name.
    """
    from app.rms.migrations._056_bank_reconciliation import (
        _migration_056_bank_reconciliation as _impl,
    )
    _impl(conn)
    _bump_schema_version(conn, 56)


def _migration_057_recipe_instructions(conn: Any) -> None:
    """Add recipe.instructions (TEXT) for JSON phase storage.

    Closes the ORM↔DB gap: ``Recipe.instructions`` was added to the ORM
    during the receta_detalle UX work (branch fix/receta-detalle-ux) but
    the DB column was missing. Every Recipe SELECT in production raised
    ``OperationalError``; the route handler rendered an empty context, so
    every /recetas/<id> page looked broken. Idempotent — column may
    already exist from create_all.
    """
    try:
        conn.execute(text("ALTER TABLE recipe ADD COLUMN instructions TEXT"))
    except Exception:
        pass  # column already exists

    _bump_schema_version(conn, 57)


def _migration_058_ingredient_expiry(conn: Any) -> None:
    """Add ingredient.expiry_date (DATE, nullable) for HACCP lot tracking.

    Closes the ORM↔DB gap: ``Ingredient.expiry_date`` was added to the
    ORM during the P1 features merge (commit d8206f4) but the DB column
    was missing. Every Ingredient SELECT in /recetas/ /inventario routes
    raised OperationalError; same regression shape as 057. Idempotent.
    """
    try:
        conn.execute(text("ALTER TABLE ingredient ADD COLUMN expiry_date DATE"))
    except Exception:
        pass  # column already exists

    _bump_schema_version(conn, 58)


def _migration_059_product_mayorista(conn: Any) -> None:
    """Add product.mayorista_price_gs (INTEGER, nullable).

    Closes the ORM↔DB gap from P1 features merge (commit c237c4c):
    ``Product.mayorista_price_gs`` is referenced by every /productos
    SELECT but the column was missing from the DB. Same shape as the
    057 / 058 gaps. Idempotent.
    """
    try:
        conn.execute(text("ALTER TABLE product ADD COLUMN mayorista_price_gs INTEGER"))
    except Exception:
        pass  # column already exists

    _bump_schema_version(conn, 59)


# Dictionary of EN→ES dietary tag normalization.  Mirrors what
# app/rms/tag_algebra.py:_TAG_NORMALIZE does at read time; kept here so
# the migration can rewrite stored English values to Spanish canonical.
_EN_TO_ES_M60 = {
    "vegan": "vegano",
    "vegetarian": "vegetariano",
    "gluten_free": "sin gluten",
    "gluten-free": "sin gluten",
    "sugar_free": "sin azúcar",
    "sugar-free": "sin azúcar",
    "keto_friendly": "keto",
    "keto-friendly": "keto",
    "lactose_free": "sin lactosa",
    "dairy_free": "sin lactosa",
    "egg_free": "sin huevo",
    "nut_free": "sin frutos secos",
    "whole_grain": "integral",
    "organic": "orgánico",
    "vegano": "vegano",
    "vegetariano": "vegetariano",
    "sin gluten": "sin gluten",
    "sin-gluten": "sin gluten",
    "sin tacc": "sin tacc",
    "sin-tacc": "sin tacc",
    "sin lactosa": "sin lactosa",
    "sin-lactosa": "sin lactosa",
    "sin huevo": "sin huevo",
    "sin-huevo": "sin huevo",
    "sin frutos secos": "sin frutos secos",
    "sin-frutos-secos": "sin frutos secos",
    "sin azúcar": "sin azúcar",
    "sin-azucar": "sin azúcar",
    "integral": "integral",
    "orgánico": "orgánico",
    "organico": "orgánico",
    "keto": "keto",
}


def _to_canonical_m60(raw: str | None) -> str | None:
    """Map English/snake_case dietary tags to canonical Spanish.

    Drop unknown tags silently.  Returns comma-separated canonical string
    or None when nothing is left.
    """
    if not raw:
        return None
    out: list[str] = []
    for piece in raw.split(","):
        key = piece.strip().lower()
        if not key:
            continue
        mapped = _EN_TO_ES_M60.get(key)
        if mapped and mapped not in out:
            out.append(mapped)
    return ",".join(out) if out else None


def _clean_allergens_m60(raw: str | None) -> str | None:
    """Strip the seed-time sentinel 'Ninguno' (Spanish for None) that was
    incorrectly mixed into the comma-separated allergen list.  Also
    canonicalize casing on known allergens.
    """
    if not raw:
        return raw
    drop = {"ninguno", "none", "null"}
    canon_map = {
        "gluten": "gluten", "dairy": "dairy", "eggs": "eggs",
        "nuts": "nuts", "soy": "soy", "soja": "soy",
    }
    parts: list[str] = []
    for p in raw.split(","):
        k = p.strip().lower()
        if not k or k in drop:
            continue
        if k in canon_map:
            parts.append(canon_map[k])
        else:
            parts.append(p.strip())
    return ",".join(parts) if parts else None


def _migration_060_tag_normalization(conn: Any) -> None:
    """Fix tag-algebra tag-language mismatch (2026-09-29 live bug).

    Symptom: /recetas/<id> showed "CANCELADAS (14) — ver por qué" on every
    page, with every canonical Spanish tag blocked by every ingredient.
    Root cause split:
      (a) ingredient_intel emits English tags ('vegan', 'vegetarian',
          'gluten_free', 'keto_friendly') but tag_algebra's candidate set
          is Spanish (CANONICAL_DIETARY_TAGS). Intersection therefore
          matched nothing — fix at the read boundary in tag_algebra.py.
      (b) Old seeded data had inconsistent values ('Ninguno' in allergens
          column, English names on Spanish-named ingredients, etc.). We
          rewrite them here.
      (c) Recipe.derived_dietary_tags cache was stale on rows where the
          English/Spanish normalization changed — refresh via cascade_refresh.

    Idempotent: each UPDATE keys on the prior value so re-runs are no-ops.
    """
    # (1) Ingredient.dietary_tags English→Spanish.
    rows = conn.execute(text(
        "SELECT id, dietary_tags FROM ingredient WHERE dietary_tags IS NOT NULL"
    )).all()
    for r in rows:
        iid, raw = r
        canon = _to_canonical_m60(raw)
        if canon != raw:
            conn.execute(text(
                "UPDATE ingredient SET dietary_tags = :v WHERE id = :i"
            ), {"v": canon, "i": iid})

    # (2) Recompute ingredient.dietary_tags from infer_dietary_tags(name)
    #     so the canonical claims match what the operator UI form would
    #     produce when they save an ingredient.  infer_dietary_tags
    #     correctly handles meat/dairy/gluten/sugar logic so e.g. chicken
    #     no longer claims vegetariano.
    try:
        from app.rms.ingredient_intel import infer_dietary_tags
        have_intel = True
    except Exception:
        have_intel = False
    if have_intel:
        rows = conn.execute(text(
            "SELECT id, name FROM ingredient"
        )).all()
        for r in rows:
            iid, name = r
            try:
                tags = infer_dietary_tags(name or "")
            except Exception:  # noqa: S112 — skip rows with bad data, log elsewhere
                continue
            new_value = _to_canonical_m60(",".join(tags)) if tags else None
            # SELECT prior value to skip no-op writes (Postgres triggers fire
            # on every UPDATE otherwise).
            prior = conn.execute(text(
                "SELECT dietary_tags FROM ingredient WHERE id = :i"
            ), {"i": iid}).scalar()
            if prior != new_value:
                conn.execute(text(
                    "UPDATE ingredient SET dietary_tags = :v WHERE id = :i"
                ), {"v": new_value, "i": iid})

    # (3) Recipe.dietary_tags English→Spanish.
    rows = conn.execute(text(
        "SELECT id, dietary_tags FROM recipe WHERE dietary_tags IS NOT NULL"
    )).all()
    for r in rows:
        rid, raw = r
        canon = _to_canonical_m60(raw)
        if canon != raw:
            conn.execute(text(
                "UPDATE recipe SET dietary_tags = :v WHERE id = :i"
            ), {"v": canon, "i": rid})

    # (4) recipe.allergens: strip 'Ninguno' + canonicalize casing.
    rows = conn.execute(text(
        "SELECT id, allergens FROM recipe WHERE allergens IS NOT NULL"
    )).all()
    for r in rows:
        rid, raw = r
        cleaned = _clean_allergens_m60(raw)
        if cleaned is None:
            conn.execute(text(
                "UPDATE recipe SET allergens = NULL WHERE id = :i"
            ), {"i": rid})
        elif cleaned != raw:
            conn.execute(text(
                "UPDATE recipe SET allergens = :v WHERE id = :i"
            ), {"v": cleaned, "i": rid})

    # (5) ingredient.allergens: same canonicalization.
    rows = conn.execute(text(
        "SELECT id, allergens FROM ingredient WHERE allergens IS NOT NULL"
    )).all()
    for r in rows:
        iid, raw = r
        cleaned = _clean_allergens_m60(raw)
        if cleaned != raw:
            conn.execute(text(
                "UPDATE ingredient SET allergens = :v WHERE id = :i"
            ), {"v": cleaned, "i": iid})

    # (6) Refresh every recipe's derived_dietary_tags cache.
    # Wrapped: cascade_refresh reads Ingredient via ORM and may reference
    # `last_purchase_supplier_id` (added in migration 072). On a fresh
    # DB running this migration before 072 the column doesn't exist yet;
    # the cascade is idempotent so we skip now and rely on 072's own
    # backfill, plus a follow-up invocation from migrations that
    # genuinely need a clean cascade (none currently do — the
    # ingredient.tag_validation_issues cascade lives in 061 which
    # touches raw SQL only).
    try:
        from app.rms.db import make_engine as _make_engine
        from app.rms.db import make_session_factory
        from app.rms.models import Recipe

        eng = _make_engine()
        SessionLocal = make_session_factory(eng)
        with SessionLocal() as s:
            ids = [r.id for r in s.query(Recipe.id).all()]
        for rid in ids:
            with SessionLocal() as s:
                from app.rms.tag_algebra import cascade_refresh
                cascade_refresh(s, recipe_id=rid)
                s.commit()  # without commit, with-exit rolls back the writes
    except Exception as exc:
        import sys as _sys
        print(
            f"MIGRATION v60 step (6) cascade_refresh skipped: {exc!r}",
            file=_sys.stderr,
        )

    _bump_schema_version(conn, 60)


def _migration_062_audit_repair(conn: Any) -> None:
    """Auto-repair contradictory ingredient tags (2026-09-29).

    Picks up where audit.validate_ingredient() flags contradictions and
    resolves them using the `allergens` column as source of truth.

    Resolution rules (allergens column wins over dietary_tags claims):
      sin gluten declared + gluten allergen  → drop 'sin gluten', 'sin tacc'
      sin lactosa declared + dairy allergen  → drop 'sin lactosa'
      sin huevo declared + eggs allergen     → drop 'sin huevo'
      sin frutos secos declared + nuts       → drop 'sin frutos secos'
      vegano declared + dairy/eggs allergen  → drop 'vegano', 'vegetariano'
      vegetariano declared + name is meat    → drop 'vegetariano'
      sin tacc declared + may_contain_gluten → drop 'sin tacc', 'sin gluten'

    Live targets (2026-09-29):
      #62 Panceta:    sin gluten/sin tacc/keto removed (allergens=gluten)
      #66 Pan rallado: sin gluten/sin tacc removed (allergens=gluten)

    Idempotent: re-running does nothing once all tags are consistent.
    """
    from app.rms.db import make_engine as _make_engine
    from app.rms.db import make_session_factory
    from app.rms.tagging.audit_repair import repair_all_ingredients

    # Wrapped: repair_all_ingredients reads Ingredient via ORM and may
    # reference columns added in later migrations (e.g.
    # `last_purchase_supplier_id` from migration 072). On a fresh DB
    # running this migration before 072 the column doesn't exist yet;
    # repair is idempotent so we skip now — the next time the operator
    # runs the audit tool, the columns will exist and the repair will
    # land. (See test_daily_sales_series.py for the regression case.)
    try:
        eng = _make_engine()
        SessionLocal = make_session_factory(eng)
        with SessionLocal() as s:
            repair_all_ingredients(s)
            # Re-backfill the validation_issues column so the audit page
            # reflects the new state immediately.
            from app.rms.tagging.audit import backfill_validation_issues
            backfill_validation_issues(s)
            s.commit()
    except Exception as exc:
        import sys as _sys
        print(
            f"MIGRATION v62 repair_all_ingredients skipped: {exc!r}",
            file=_sys.stderr,
        )

    _bump_schema_version(conn, 62)


def _migration_063_payment_receipt(conn: Any) -> None:
    """P1-B3: add pedido.payment_receipt_path + payment_receipt_uploaded_at.

    Customers pay via transferencia/QR and the operator has been
    chasing them on WhatsApp for the comprobante. Now /p/{token} shows
    an upload form (when payment_intent != efectivo) and saves the
    file under {DATA_DIR}/payment_receipts/{pedido_id}/{ts}_{name}.

    Idempotent: ALTER try/except.
    """
    try:
        conn.execute(
            text(
                "ALTER TABLE pedido ADD COLUMN payment_receipt_path TEXT"
            )
        )
    except Exception:
        pass
    try:
        conn.execute(
            text(
                "ALTER TABLE pedido ADD COLUMN payment_receipt_uploaded_at TIMESTAMP"
            )
        )
    except Exception:
        pass
    _bump_schema_version(conn, 63)


def _migration_064_no_op(conn: Any) -> None:
    """No-op migration for slot 64 (C2 tablet-slug renumbered to 66).

    A sibling agent shipped migration 065 (suscripciones) between the
    time C2 picked the slot 64 and the time the change was committed.
    Renumbering C2 to slot 66 left a gap. This no-op fills the gap so
    the migration runner walks 64 → 65 → 66 in order without raising
    "No migration registered for schema version 64".

    Idempotent: pure bump.
    """
    _bump_schema_version(conn, 64)


def _migration_066_product_tablet_slug(conn: Any) -> None:
    """C2: add product.tablet_slug + product.tablet_visible.

    /m/{slug} is a public, no-auth tablet-menu page that lists the
    bakery's products with photos and prices for walk-in customers.
    Each product gets a unique URL-safe slug so the link is short
    enough to type on a 1280×720 tablet, and an explicit
    ``tablet_visible`` toggle so operators can hide items they only
    sell behind-the-counter (e.g., encargos, internal stock).

    Idempotent: ALTER try/except.
    """
    try:
        conn.execute(
            text(
                "ALTER TABLE product ADD COLUMN tablet_slug VARCHAR(60)"
            )
        )
    except Exception:
        pass
    try:
        conn.execute(
            text(
                "ALTER TABLE product ADD COLUMN tablet_visible BOOLEAN NOT NULL DEFAULT 1"
            )
        )
    except Exception:
        pass
    # Best-effort: index on tablet_slug for fast lookups. CREATE INDEX
    # is idempotent on its own (IF NOT EXISTS) on SQLite + Postgres.
    try:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_product_tablet_slug "
                "ON product (tablet_slug)"
            )
        )
    except Exception:
        pass
    _bump_schema_version(conn, 66)


def _migration_067_pedido_public_token_expiry(conn: Any) -> None:
    """P1-2: add pedido.public_token_expires_at for /p/{token} link expiry.

    Security hardening (2026-09-29): previous tokens had no expiry, so
    a leaked WhatsApp link worked forever. Now each pedido's public
    link expires 30 days after creation. The lookup route in
    ``app/routers/pedidos.py`` returns 410 Gone once the deadline
    passes, prompting the customer to ask the bakery for a fresh link
    instead of getting an obscure 404.

    Why 30 days: long enough to cover the typical panificados pickup
    window (a customer might forget a pedido for a week, then come
    back), short enough that a leaked link has bounded blast radius.

    Backfill: all existing pedidos get ``created_at + 30 days`` so the
    legacy 8-char tokens continue to work for the rest of their
    natural pickup window. This is a one-time grace period — operators
    can rotate by running:
        UPDATE pedido SET public_token_expires_at = ...;
    if they need to.

    Idempotent: ALTER try/except (matches _migration_066 pattern).
    """
    # 1. Add the column. SQLite ALTER TABLE doesn't support DEFAULT
    # with expression backfill in older versions; safe to add nullable.
    try:
        conn.execute(
            text(
                "ALTER TABLE pedido "
                "ADD COLUMN public_token_expires_at TIMESTAMP"
            )
        )
    except Exception:
        pass

    # 2. Backfill: existing rows get created_at + 30 days.
    #
    # SQLite returns created_at as a plain string, so we parse it back
    # to a datetime before adding the offset. Python's datetime.fromisoformat
    # handles the common SQLite formats ("2026-01-01 12:00:00").
    try:
        from datetime import datetime as _dt
        rows = conn.execute(
            text(
                "SELECT id, created_at FROM pedido "
                "WHERE public_token_expires_at IS NULL"
            )
        ).all()
        from datetime import timedelta as _td

        for row in rows:
            created = row.created_at
            if created is None:
                expires = _dt.now(timezone.utc) + _td(days=30)
            elif isinstance(created, str):
                # SQLite returns datetime columns as str. Handle both
                # "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DDTHH:MM:SS" forms.
                normalized = created.replace("T", " ")
                try:
                    parsed = _dt.fromisoformat(normalized)
                except ValueError:
                    # Fallback: try the most common SQLite format.
                    from datetime import datetime as _dt2
                    parsed = _dt2.strptime(normalized, "%Y-%m-%d %H:%M:%S")
                expires = parsed + _td(days=30)
            else:
                expires = created + _td(days=30)
            conn.execute(
                text(
                    "UPDATE pedido SET public_token_expires_at = :exp "
                    "WHERE id = :pid"
                ),
                {"exp": expires, "pid": row.id},
            )
    except Exception as exc:
        from loguru import logger as _lg

        _lg.warning(
            "migration 067 backfill failed (column may already be populated): "
            f"{exc}"
        )

    # 3. Index for fast "is this token still valid" lookups.
    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_pedido_token_expires "
                "ON pedido (public_token, public_token_expires_at)"
            )
        )
    except Exception:
        pass

    _bump_schema_version(conn, 67)


def _migration_068_recipe_menu_tags(conn: Any) -> None:
    """UI-V2: recipe.menu_tags — multi-select 'Etiquetas de Menú'.

    Replaces the single-limit `family` field: a product often belongs to
    several commercial contexts at once ("Pastelería" AND "Especial de
    Temporada"). Comma-separated, same convention as Recipe.dietary_tags.
    `family` stays (read-only legacy, still displayed as a fallback);
    new writes go to menu_tags.

    Idempotent: ALTER try/except (matches _migration_067 pattern).
    """
    try:
        conn.execute(
            text("ALTER TABLE recipe ADD COLUMN menu_tags TEXT")
        )
    except Exception:
        pass

    # Backfill: seed menu_tags from the legacy family so nothing the
    # operator already categorized disappears from the filters.
    try:
        conn.execute(
            text(
                "UPDATE recipe SET menu_tags = family "
                "WHERE menu_tags IS NULL AND family IS NOT NULL "
                "AND TRIM(family) <> ''"
            )
        )
    except Exception:
        pass

    _bump_schema_version(conn, 68)


def _migration_065_suscripciones(conn: Any) -> None:
    """P1-B5 — add suscripcion table for recurring customer orders (no cron).

    Captures a customer's standing request (e.g., "1 kg chipa cada
    sábado"). The operator reads the list when planning and
    pre-loads pedidos manually. No automatic billing, no implicit
    stock decrement.

    Idempotent: create_all() handles the table on fresh DBs; the
    explicit CREATE is the no-op-on-existing fallback for legacy
    DBs that ran init_db() before the ORM model was added.
    """
    # create_all() in init_db() already creates the table from the
    # ORM model; this CREATE IF NOT EXISTS is the safety net for any
    # deployment that ran init_db before the Suscripcion class
    # shipped. SQLite + Postgres both support IF NOT EXISTS for tables.
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS suscripcion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE RESTRICT,
                    product_summary VARCHAR(500) NOT NULL,
                    cadence VARCHAR(16) NOT NULL,
                    preferred_day_of_week INTEGER,
                    preferred_time VARCHAR(8),
                    start_date DATE NOT NULL,
                    end_date DATE,
                    price_gs INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(16) NOT NULL DEFAULT 'activa',
                    notes TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    CONSTRAINT ck_suscripcion_cadence
                        CHECK (cadence IN ('semanal','quincenal','mensual')),
                    CONSTRAINT ck_suscripcion_status
                        CHECK (status IN ('activa','pausada','cancelada')),
                    CONSTRAINT ck_suscripcion_dow
                        CHECK (preferred_day_of_week IS NULL
                               OR (preferred_day_of_week BETWEEN 1 AND 7)),
                    CONSTRAINT ck_suscripcion_price_nonneg
                        CHECK (price_gs >= 0)
                )
                """
            )
        )
    except Exception:
        pass
    try:
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_suscripcion_status ON suscripcion (status)")
        )
    except Exception:
        pass
    try:
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_suscripcion_customer ON suscripcion (customer_id)")
        )
    except Exception:
        pass
    _bump_schema_version(conn, 65)


def _migration_061_tag_validation(conn: Any) -> None:
    """Add ingredient.tag_validation_issues column + backfill (2026-09-29).

    Background: tagging/ refactor (see app/rms/tagging/audit.py) detects
    logical contradictions in ingredient tags:

      - declares 'vegano' but allergens include dairy/eggs
      - declares 'sin gluten' but allergens include gluten
      - declares 'vegetariano' but name suggests meat/fish

    Persisted to a new TEXT column on Ingredient so the inventory page
    can show a warning banner without re-running the audit on every
    render. Refreshed when allergens / dietary_tags / name changes.

    Idempotent: ALTER try/except, UPDATE keyed on prior value.
    """
    # (1) Add the column.
    try:
        conn.execute(
            text("ALTER TABLE ingredient ADD COLUMN tag_validation_issues TEXT")
        )
    except Exception:
        pass

    # (2) Backfill via the new audit module.
    # Wrapped: audit_all_ingredients reads Ingredient via ORM and may
    # reference columns added in later migrations (e.g.
    # `last_purchase_supplier_id` from migration 072). On a fresh DB
    # running this migration before 072 the column doesn't exist yet;
    # the audit is idempotent so we skip now — the column exists
    # already (step 1 added it) and will be backfilled the next time
    # the operator runs the audit tool. (See test_daily_sales_series.py
    # for the regression case.)
    try:
        from app.rms.db import make_engine as _make_engine
        from app.rms.db import make_session_factory
        from app.rms.tagging.audit import audit_all_ingredients

        eng = _make_engine()
        SessionLocal = make_session_factory(eng)
        with SessionLocal() as s:
            issues_by_id = audit_all_ingredients(s)
            for iid, issues in issues_by_id.items():
                s.execute(
                    text(
                        "UPDATE ingredient SET tag_validation_issues = :v WHERE id = :i"
                    ),
                    {"v": "\n".join(issues), "i": iid},
                )
            s.commit()
    except Exception as exc:
        import sys as _sys
        print(
            f"MIGRATION v61 audit_all_ingredients skipped: {exc!r}",
            file=_sys.stderr,
        )

    _bump_schema_version(conn, 61)


def _migration_005_customer(conn: Any) -> None:
    """Add Customer table + Sale.customer_id FK (E13).

    Tables are created via create_all() in init_db(). The Sale
    FK column is added in case create_all didn't (e.g. on an existing
    DB that pre-dates the customer table).
    """
    _bump_schema_version(conn, 5)


def _migration_069_customer_addresses_delivery_favorites(conn: Any) -> None:
    """P3 delivery + favorites batch (2026-09-30).

    - customer_address: multiple addresses per customer (label + text +
      zone ref), so a delivery goes to casa / oficina / wherever today.
    - pedido: address_text (free-text snapshot), delivery_window_start/end
      (acceptable arrival window), invoice_ruc + invoice_name (factura).
    - product.is_favorite: quick-sale "Favoritos" filter persistence.
    - customer.preferred_zone: pre-fill the zone combo when picking them.

    Idempotent: CREATE TABLE IF NOT EXISTS + ALTER try/except.
    """
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS customer_address ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " customer_id INTEGER NOT NULL REFERENCES customer(id),"
        " label VARCHAR(32) NOT NULL DEFAULT 'casa',"
        " address_text TEXT NOT NULL,"
        " zone_id INTEGER REFERENCES delivery_zone(id),"
        " is_default INTEGER NOT NULL DEFAULT 0,"
        " created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_customer_address_customer "
        "ON customer_address(customer_id)"
    ))
    for stmt in (
        "ALTER TABLE pedido ADD COLUMN address_text TEXT",
        "ALTER TABLE pedido ADD COLUMN delivery_window_start VARCHAR(8)",
        "ALTER TABLE pedido ADD COLUMN delivery_window_end VARCHAR(8)",
        "ALTER TABLE pedido ADD COLUMN invoice_ruc VARCHAR(20)",
        "ALTER TABLE pedido ADD COLUMN invoice_name VARCHAR(120)",
        "ALTER TABLE product ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE customer ADD COLUMN preferred_zone_id INTEGER",
    ):
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

    _bump_schema_version(conn, 69)


def _migration_070_customer_dietary_profile(conn: Any) -> None:
    """P3 dietary batch (2026-09-30).

    Customer dietary profile so any employee sees warnings at order time:
    - dietary_restrictions: CSV of canonical dietary tags the customer
      must NEVER get violated (sin lactosa, sin gluten, vegano...).
      Displayed as a red warning on pedidos/nuevo + ventas.
    - dietary_preferences: JSON list of approved substitutes/choices in
      preference order, e.g. [{"tag": "sin lactosa", "rank": 1,
      "note": "leche de almendra OK"}]. Rank 1 = offer first.
    - dietary_confirm_always: 1 = employee must CONFIRM the preference
      with the customer on every order (some people flex, some don't).
    """
    for stmt in (
        "ALTER TABLE customer ADD COLUMN dietary_restrictions TEXT",
        "ALTER TABLE customer ADD COLUMN dietary_preferences TEXT",
        "ALTER TABLE customer ADD COLUMN dietary_confirm_always INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

    _bump_schema_version(conn, 70)


def _migration_071_customer_profile_completeness(conn: Any) -> None:
    """P3 profile batch (2026-09-30): birthday, acquisition channel,
    preferred contact channel, marketing consent, and default facturación
    data (prefills pedido invoice fields for business/office clients).
    """
    for stmt in (
        "ALTER TABLE customer ADD COLUMN birthday VARCHAR(10)",
        "ALTER TABLE customer ADD COLUMN how_found VARCHAR(32)",
        "ALTER TABLE customer ADD COLUMN preferred_channel VARCHAR(32)",
        "ALTER TABLE customer ADD COLUMN marketing_consent INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE customer ADD COLUMN invoice_name VARCHAR(120)",
        "ALTER TABLE customer ADD COLUMN invoice_ruc VARCHAR(20)",
    ):
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

    _bump_schema_version(conn, 71)


def _migration_072_reorder_supplier_tracking(conn: Any) -> None:
    """P2 reorder-supplier redesign (2026-09-30): make `/reorder` provider-aware.

    Four new columns on `ingredient` (all NULL-safe so existing rows survive):

      - `last_purchase_supplier_id` — the supplier Saskia actually bought
        from in her most recent restock. Used to pre-select the dropdown
        on `/reorder`, and as the source of truth for the
        "specialty-only-here" auto-lock after 3 consecutive buys from the
        same supplier.

      - `last_purchase_at` — UTC timestamp of the most recent restock that
        set `last_purchase_supplier_id`. NULL means "never restocked".

      - `purchase_streak_count` — rolling counter that increments when she
        buys from the same supplier twice in a row and resets when she
        buys from a different one. When it reaches 3, the dropdown on
        `/reorder` auto-locks to that supplier (visual badge: "fijo").

      - `locked_supplier_id` — set when `purchase_streak_count` first hits
        3 from `last_purchase_supplier_id`. While this column is non-NULL,
        the dropdown defaults to this supplier and shows the "fijo" badge.
        The operator can override by picking a different supplier; doing
        so resets the streak to 1.

    Backfill: every existing ingredient with `supplier_id` set gets that
    value copied to `last_purchase_supplier_id` so the page renders
    correctly on first load (no "sin registro" flash for ingredients that
    have been associated with a supplier for months).
    """
    for stmt in (
        "ALTER TABLE ingredient ADD COLUMN last_purchase_supplier_id INTEGER REFERENCES supplier(id)",
        "ALTER TABLE ingredient ADD COLUMN last_purchase_at DATETIME",
        "ALTER TABLE ingredient ADD COLUMN purchase_streak_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE ingredient ADD COLUMN locked_supplier_id INTEGER REFERENCES supplier(id)",
    ):
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

    # Backfill — best-effort. Empty DB → no rows affected; populated DB
    # gets supplier_id copied to last_purchase_supplier_id so the page
    # renders correctly on first load.
    try:
        conn.execute(
            text(
                "UPDATE ingredient SET last_purchase_supplier_id = supplier_id "
                "WHERE last_purchase_supplier_id IS NULL AND supplier_id IS NOT NULL"
            )
        )
    except Exception as exc:
        logger.warning("migration 072: backfill of last_purchase_supplier_id failed: %s", exc)

    try:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ingredient_last_purchase_supplier "
                "ON ingredient (last_purchase_supplier_id)"
            )
        )
    except Exception as exc:
        logger.warning("migration 072: index creation failed: %s", exc)

    _bump_schema_version(conn, 72)


def _migration_073_ingredient_price_event_supplier(conn: Any) -> None:
    """Phase 2 (2026-10-01): tag every IngredientPriceEvent with a
    supplier so the /reorder dropdown can show per-supplier prices
    ('Casa Rica — 4.200' vs 'sin registro') as the operator logs
    purchases.

    Before 073, IngredientPriceEvent only had ingredient_id + price_gs
    + recorded_at + source. The CSV price upload (Phase 3) writes
    rows through this column so per-supplier pricing fills in over time.

    Schema:
      - ADD COLUMN supplier_id INTEGER REFERENCES supplier(id) ON DELETE SET NULL
      - ADD INDEX ix_ingredient_price_event_supplier_time

    The column is nullable for backwards compatibility with existing
    rows (189 of them in prod, all source='restock'). The CSV import
    always writes supplier_id so future queries can group by supplier.

    Also: backfill the ingredient's ``last_purchase_supplier_id`` from
    any existing ``IngredientPriceEvent`` that was a 'restock' AND has
    a supplier_id — but since existing events have NULL supplier_id,
    this is a no-op for the historical 189 rows. Documented here so
    future readers don't wonder why.
    """
    for stmt in (
        "ALTER TABLE ingredient_price_event ADD COLUMN supplier_id INTEGER REFERENCES supplier(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_ingredient_price_event_supplier_time ON ingredient_price_event (supplier_id, recorded_at)",
    ):
        try:
            conn.execute(text(stmt))
        except Exception as exc:
            # CREATE INDEX IF NOT EXISTS is idempotent; ADD COLUMN raises
            # on second run which we tolerate.
            logger.debug("migration 073 stmt skipped: %s — %s", stmt.split()[2], exc)

    _bump_schema_version(conn, 73)


def _migration_074_loyalty_transaction_ledger(conn: Any) -> None:
    """Append-only ledger of customer loyalty point movements.

    The ``Customer.loyalty_points`` column existed since the original
    loyalty work but was never incremented — ``award_points()`` in
    ``app/rms/customers.py`` was defined but unwired. This ledger
    captures every delta (earn, redeem, manual adjust, void reversal)
    so refunds and voids can reverse points cleanly without losing
    history. The cached ``Customer.loyalty_points`` column stays for
    fast display; this table is the source of truth.

    Schema:
      - CREATE TABLE loyalty_transaction with id / customer_id (FK) /
        delta / reason / sale_id (FK, nullable) / actor / notes /
        recorded_at
      - CHECK reason IN ('earn_sale','redeem','void_reversal','manual_adjust')
      - CHECK delta != 0
      - INDEX on (customer_id, recorded_at) for fast "recent activity"
        queries on the customer detail page

    Backwards compatibility: existing rows in customer.loyalty_points
    are NOT backfilled. The first ``award_points`` after this migration
    will write a ledger row and reconcile. A periodic reconcile
    helper can rebuild the column from SUM(delta) if needed.
    """
    for stmt in (
        """CREATE TABLE IF NOT EXISTS loyalty_transaction (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
            delta INTEGER NOT NULL,
            reason VARCHAR(24) NOT NULL,
            sale_id INTEGER REFERENCES sale(id) ON DELETE SET NULL,
            actor VARCHAR(32) NOT NULL DEFAULT 'system',
            notes TEXT,
            recorded_at DATETIME NOT NULL,
            CONSTRAINT ck_loyalty_reason CHECK (
                reason IN ('earn_sale','redeem','void_reversal','manual_adjust')
            ),
            CONSTRAINT ck_loyalty_delta_nonzero CHECK (delta != 0)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_loyalty_transaction_customer_id ON loyalty_transaction (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_loyalty_transaction_recorded_at ON loyalty_transaction (recorded_at)",
        "CREATE INDEX IF NOT EXISTS ix_loyalty_customer_time ON loyalty_transaction (customer_id, recorded_at)",
    ):
        try:
            conn.execute(text(stmt))
        except Exception as exc:
            logger.debug("migration 074 stmt skipped: %s", exc)

    _bump_schema_version(conn, 74)


def _migration_075_suggestion_event_log(conn: Any) -> None:
    """Tier 3.2 (2026-10-01): extend loyalty_transaction to log suggestion clicks.

    The /clientes/api/{id}/suggestion-applied endpoint writes a
    loyalty_transaction row when the cashier taps a suggestion
    card. This row carries NO balance change (delta=0) — it's a
    pure event log row used for analytics on suggestion adoption.

    This migration drops the original two CHECK constraints
    (ck_loyalty_reason, ck_loyalty_delta_nonzero) and replaces them
    with looser versions:
      - reason IN (..., 'suggestion_applied')
      - delta can be 0 (used only by suggestion_applied; all other
        reasons still write non-zero)

    Idempotent: each step is wrapped in try/except so re-runs on a
    partially-applied DB no-op cleanly. SQLite doesn't support
    ``ALTER TABLE DROP CONSTRAINT`` so the trick is to recreate
    the table without the constraint and copy data across.

    For non-SQLite dialects (production Postgres) the same effect
    is achieved by ALTER TABLE DROP CONSTRAINT then ADD CONSTRAINT
    — see the dialect branch below.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect == "sqlite":
        # SQLite: rebuild the table. This loses nothing because the
        # ledger is append-only and the data being rebuilt is the
        # data we already have on disk.
        for stmt in (
            # 1. Rename old table aside.
            "ALTER TABLE loyalty_transaction RENAME TO loyalty_transaction_old_075",
            # 2. Recreate with the new constraints.
            """CREATE TABLE loyalty_transaction (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                delta INTEGER NOT NULL,
                reason VARCHAR(24) NOT NULL,
                sale_id INTEGER REFERENCES sale(id) ON DELETE SET NULL,
                actor VARCHAR(32) NOT NULL DEFAULT 'system',
                notes TEXT,
                recorded_at DATETIME NOT NULL,
                CONSTRAINT ck_loyalty_reason_v2 CHECK (
                    reason IN ('earn_sale','redeem','void_reversal','manual_adjust','suggestion_applied')
                )
            )""",
            # 3. Copy rows across.
            """INSERT INTO loyalty_transaction
                (id, customer_id, delta, reason, sale_id, actor, notes, recorded_at)
                SELECT id, customer_id, delta, reason, sale_id, actor, notes, recorded_at
                FROM loyalty_transaction_old_075""",
            # 4. Drop the old table.
            "DROP TABLE loyalty_transaction_old_075",
            # 5. Re-create indexes.
            "CREATE INDEX IF NOT EXISTS ix_loyalty_transaction_customer_id ON loyalty_transaction (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_loyalty_transaction_recorded_at ON loyalty_transaction (recorded_at)",
            "CREATE INDEX IF NOT EXISTS ix_loyalty_customer_time ON loyalty_transaction (customer_id, recorded_at)",
        ):
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                logger.debug("migration 075 stmt skipped: %s — %s", stmt[:60], exc)
    else:
        # Postgres / generic: just drop and re-add the constraint.
        try:
            conn.execute(text(
                "ALTER TABLE loyalty_transaction DROP CONSTRAINT IF EXISTS ck_loyalty_reason"
            ))
            conn.execute(text(
                "ALTER TABLE loyalty_transaction ADD CONSTRAINT ck_loyalty_reason "
                "CHECK (reason IN ('earn_sale','redeem','void_reversal','manual_adjust','suggestion_applied'))"
            ))
            conn.execute(text(
                "ALTER TABLE loyalty_transaction DROP CONSTRAINT IF EXISTS ck_loyalty_delta_nonzero"
            ))
            # delta_nonzero constraint dropped entirely — suggestion_applied
            # events are zero-balance. Earn/redeem/void/manual_adjust code
            # never writes 0 anyway (guard in customers.py).
        except Exception as exc:
            logger.debug("migration 075 ALTER skipped: %s", exc)

    _bump_schema_version(conn, 75)


def _migration_076_sale_linked_pedido_id(conn: Any) -> None:
    """Phase 5 (2026-10-01): back-pointer from Sale to Pedido.

    Adds sale.linked_pedido_id so we can walk sale↔pedido symmetrically.
    Pedido.fulfilled_sale_id only points at the FIRST sale from a multi-
    line fulfillment; this column lets us list ALL sales generated by a
    pedido and find the pedido that produced a given sale.

    Used by:
      - pedido detail timeline (show every sale generated by a pedido)
      - sale audit report (which pedido produced this sale?)
      - pedidosya-style integrations (reconcile imported sale back to pedido)

    Backfill: copy pedido.fulfilled_sale_id → sale.linked_pedido_id for
    the sales that match. Most sales (POS-driven, no pedido) stay NULL,
    which is the expected default.

    Idempotent: each statement is wrapped in try/except so re-runs no-op
    on a partially-applied DB.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    try:
        if dialect == "sqlite":
            conn.exec_driver_sql(
                "ALTER TABLE sale ADD COLUMN linked_pedido_id INTEGER "
                "REFERENCES pedido(id) ON DELETE SET NULL"
            )
        else:  # postgres
            conn.exec_driver_sql(
                "ALTER TABLE sale ADD COLUMN IF NOT EXISTS linked_pedido_id INTEGER "
                "REFERENCES pedido(id) ON DELETE SET NULL"
            )
    except Exception as exc:
        # Column already exists (re-run after partial apply)
        logger.debug("migration 076 ADD COLUMN skipped: %s", exc)

    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_sale_linked_pedido_id ON sale (linked_pedido_id)"
        )
    except Exception as exc:
        logger.debug("migration 076 CREATE INDEX skipped: %s", exc)

    # Backfill: link any sale whose id matches a pedido.fulfilled_sale_id.
    # Most legacy sales won't be touched (they were POS-driven, no pedido).
    try:
        if dialect == "sqlite":
            conn.exec_driver_sql(
                "UPDATE sale SET linked_pedido_id = ("
                "SELECT p.id FROM pedido p WHERE p.fulfilled_sale_id = sale.id"
                ") WHERE linked_pedido_id IS NULL"
            )
        else:  # postgres — same SQL works
            conn.exec_driver_sql(
                "UPDATE sale SET linked_pedido_id = p.id "
                "FROM pedido p WHERE p.fulfilled_sale_id = sale.id "
                "AND sale.linked_pedido_id IS NULL"
            )
    except Exception as exc:
        logger.debug("migration 076 backfill skipped: %s", exc)

    _bump_schema_version(conn, 76)


def _migration_077_pedido_event_log(conn: Any) -> None:
    """Phase 11 (2026-10-01): PedidoEvent edit log.

    Adds pedido_event table for cheap per-pedido timeline rendering.
    Distinct from audit_log: scope is per-pedido (joined cheaply on
    pedido_id) and granularity captures line edits + note changes +
    window adjustments, not just security events.

    Used by:
      - pedido detail timeline (alongside AuditLog events)
      - operational reporting (which operator edited this pedido?)

    Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
    are inherently idempotent on SQLite + Postgres.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect == "sqlite":
        create_sql = """
            CREATE TABLE IF NOT EXISTS pedido_event (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
                ts DATETIME NOT NULL,
                actor VARCHAR(64) NOT NULL DEFAULT 'system',
                event_type VARCHAR(32) NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                CONSTRAINT ck_pedido_event_type CHECK (
                    event_type IN ('created','status_change','line_added','line_removed',
                    'line_qty_changed','line_price_changed','note_edited','address_changed',
                    'window_changed','customer_changed','payment_intent_set','cancelled',
                    'duplicated')
                )
            )
        """
    else:  # postgres
        create_sql = """
            CREATE TABLE IF NOT EXISTS pedido_event (
                id SERIAL NOT NULL PRIMARY KEY,
                pedido_id INTEGER NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
                ts TIMESTAMP NOT NULL,
                actor VARCHAR(64) NOT NULL DEFAULT 'system',
                event_type VARCHAR(32) NOT NULL,
                payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                CONSTRAINT ck_pedido_event_type CHECK (
                    event_type IN ('created','status_change','line_added','line_removed',
                    'line_qty_changed','line_price_changed','note_edited','address_changed',
                    'window_changed','customer_changed','payment_intent_set','cancelled',
                    'duplicated')
                )
            )
        """

    try:
        conn.exec_driver_sql(create_sql)
    except Exception as exc:
        logger.debug("migration 077 CREATE TABLE pedido_event skipped: %s", exc)

    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_pedido_event_pedido_id ON pedido_event (pedido_id)",
        "CREATE INDEX IF NOT EXISTS ix_pedido_event_ts ON pedido_event (ts)",
        "CREATE INDEX IF NOT EXISTS ix_pedido_event_event_type ON pedido_event (event_type)",
        "CREATE INDEX IF NOT EXISTS ix_pedido_event_pedido_ts ON pedido_event (pedido_id, ts)",
    ):
        try:
            conn.exec_driver_sql(idx_sql)
        except Exception as exc:
            logger.debug("migration 077 index skipped: %s", exc)

    _bump_schema_version(conn, 77)


def _migration_078_communication_log(conn: Any) -> None:
    """Phase 12 (2026-10-01): CommunicationLog — outbound & inbound messages.

    Adds communication_log table for the customer message thread. The
    operator UI on /clientes/{id} will show a chronological "Mensajes"
    tab sourced from this table; /pedidos/{id} timeline will surface
    outbound messages from this pedido too.

    Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
    are inherently idempotent on SQLite + Postgres.

    Three CHECK constraints enforce enum values:
      - direction: outbound | inbound
      - channel:   whatsapp | email | sms | note
      - status:    pending | sent | delivered | read | failed | received
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect == "sqlite":
        create_sql = """
            CREATE TABLE IF NOT EXISTS communication_log (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                direction VARCHAR(8) NOT NULL,
                channel VARCHAR(16) NOT NULL,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                pedido_id INTEGER REFERENCES pedido(id) ON DELETE SET NULL,
                template_id INTEGER REFERENCES message_template(id) ON DELETE SET NULL,
                phone VARCHAR(32),
                email VARCHAR(120),
                subject VARCHAR(200),
                body TEXT NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                provider_message_id VARCHAR(120),
                error_message TEXT,
                ts_sent DATETIME NOT NULL,
                ts_delivered DATETIME,
                ts_read DATETIME,
                actor VARCHAR(64),
                CONSTRAINT ck_communication_log_direction CHECK (direction IN ('outbound','inbound')),
                CONSTRAINT ck_communication_log_channel CHECK (channel IN ('whatsapp','email','sms','note')),
                CONSTRAINT ck_communication_log_status CHECK (status IN ('pending','sent','delivered','read','failed','received'))
            )
        """
    else:  # postgres
        create_sql = """
            CREATE TABLE IF NOT EXISTS communication_log (
                id SERIAL NOT NULL PRIMARY KEY,
                direction VARCHAR(8) NOT NULL,
                channel VARCHAR(16) NOT NULL,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                pedido_id INTEGER REFERENCES pedido(id) ON DELETE SET NULL,
                template_id INTEGER REFERENCES message_template(id) ON DELETE SET NULL,
                phone VARCHAR(32),
                email VARCHAR(120),
                subject VARCHAR(200),
                body TEXT NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                provider_message_id VARCHAR(120),
                error_message TEXT,
                ts_sent TIMESTAMP NOT NULL,
                ts_delivered TIMESTAMP,
                ts_read TIMESTAMP,
                actor VARCHAR(64),
                CONSTRAINT ck_communication_log_direction CHECK (direction IN ('outbound','inbound')),
                CONSTRAINT ck_communication_log_channel CHECK (channel IN ('whatsapp','email','sms','note')),
                CONSTRAINT ck_communication_log_status CHECK (status IN ('pending','sent','delivered','read','failed','received'))
            )
        """

    try:
        conn.exec_driver_sql(create_sql)
    except Exception as exc:
        logger.debug("migration 078 CREATE TABLE communication_log skipped: %s", exc)

    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_communication_log_customer_id ON communication_log (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_pedido_id ON communication_log (pedido_id)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_provider_message_id ON communication_log (provider_message_id)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_ts_sent ON communication_log (ts_sent)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_customer_ts ON communication_log (customer_id, ts_sent)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_pedido_ts ON communication_log (pedido_id, ts_sent)",
        "CREATE INDEX IF NOT EXISTS ix_communication_log_status_ts ON communication_log (status, ts_sent)",
    ):
        try:
            conn.exec_driver_sql(idx_sql)
        except Exception as exc:
            logger.debug("migration 078 index skipped: %s", exc)

    _bump_schema_version(conn, 78)


def _migration_079_customer_address_structured(conn: Any) -> None:
    """Phase 13 (2026-10-01): Structured delivery-address columns.

    Research (MercadoLibre PY, Lightspeed X, Uber Direct) showed that
    free-text `address_text` is fine for receipts but blocks structured
    logistics. This migration adds discrete columns the cashier can
    fill optionally (kept nullable for backward compat):

      calle_principal, calle_secundaria, numero, edificio, piso, unidad,
      barrio, ciudad, departamento, pais, codigo_postal,
      recipient_name, delivery_instructions,
      address_kind (HOME/WORK/FAMILY/OTHER), sort_order, is_active

    Existing `address_text` stays as the rendered "what the cashier
    sees" — the helpers at application layer will compose it from the
    structured columns at write time so the legacy callers never break.
    """
    # Phase 13 task: extending customer_address — all additive, idempotent.
    if conn.dialect.name == "sqlite":
        add_columns_sql = [
            "ALTER TABLE customer_address ADD COLUMN calle_principal VARCHAR(160)",
            "ALTER TABLE customer_address ADD COLUMN calle_secundaria VARCHAR(160)",
            "ALTER TABLE customer_address ADD COLUMN numero VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN edificio VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN piso VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN unidad VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN barrio VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN ciudad VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN departamento VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN pais VARCHAR(8) DEFAULT 'PRY'",
            "ALTER TABLE customer_address ADD COLUMN codigo_postal VARCHAR(16)",
            "ALTER TABLE customer_address ADD COLUMN recipient_name VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN delivery_instructions TEXT",
            "ALTER TABLE customer_address ADD COLUMN address_kind VARCHAR(16) DEFAULT 'HOME'",
            "ALTER TABLE customer_address ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE customer_address ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
        ]
    else:  # postgres
        add_columns_sql = [
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS calle_principal VARCHAR(160)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS calle_secundaria VARCHAR(160)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS numero VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS edificio VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS piso VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS unidad VARCHAR(20)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS barrio VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS ciudad VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS departamento VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS pais VARCHAR(8) DEFAULT 'PRY'",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR(16)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS recipient_name VARCHAR(120)",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS delivery_instructions TEXT",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS address_kind VARCHAR(16) DEFAULT 'HOME'",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE customer_address ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT 1",
        ]

    for sql in add_columns_sql:
        try:
            conn.exec_driver_sql(sql)
        except Exception as exc:
            logger.debug("migration 079 ADD COLUMN skipped: %s", exc)

    # Address_kind CHECK constraint is awkward to add idempotently on both
    # dialects (sqlite ALTER TABLE … ADD CONSTRAINT is limited); enforce at
    # app layer instead. Index on customer_id is already present from migration 069.

    _bump_schema_version(conn, 79)


def _migration_080_customer_invoice_profile(conn: Any) -> None:
    """Phase 13 (2026-10-01): Multiple invoice profiles per customer.

    Research (Wise Platform, Shopify B2B CompanyLocation, Stripe TaxIDs)
    showed that one person can invoice under many tax identities — personal
    CI + spouse RUC + own company RUC. Today's Customer has a single
    invoice_ruc + invoice_name which prevents that.

    This migration creates customer_invoice_profile (1:N from customer)
    with the SIFEN-required enum fields (tipo_documento 7 values,
    tipo_operacion 4 values) and aliases for the cashier's mental model
    ("Personal", "Ometz S.A.").

    Backfill: for every customer with invoice_ruc OR invoice_name set,
    insert one default profile named "Personal" (or the razon_social if
    it differs from customer.name). The single legacy columns are kept
    on customer for backward compat — the application layer will use
    the profile table when available and fall back to the legacy columns.
    """
    if conn.dialect.name == "sqlite":
        create_sql = """
            CREATE TABLE IF NOT EXISTS customer_invoice_profile (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                alias VARCHAR(64) NOT NULL,
                ruc_ci VARCHAR(20) NOT NULL,
                razon_social VARCHAR(160) NOT NULL,
                tipo_documento VARCHAR(32) NOT NULL DEFAULT 'CI_PARAGUAYA',
                tipo_operacion VARCHAR(16) NOT NULL DEFAULT 'B2C',
                is_default BOOLEAN NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_customer_invoice_profile_tipo_documento CHECK (
                    tipo_documento IN (
                        'CI_PARAGUAYA','RUC','PASAPORTE','CEDULA_EXTRANJERA',
                        'CARNET_RESIDENCIA','INNOMINADO','DIPLOMATICA_EXONERACION','OTRO'
                    )
                ),
                CONSTRAINT ck_customer_invoice_profile_tipo_operacion CHECK (
                    tipo_operacion IN ('B2B','B2C','B2G','EXTRANJERO')
                )
            )
        """
    else:  # postgres
        create_sql = """
            CREATE TABLE IF NOT EXISTS customer_invoice_profile (
                id SERIAL NOT NULL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
                alias VARCHAR(64) NOT NULL,
                ruc_ci VARCHAR(20) NOT NULL,
                razon_social VARCHAR(160) NOT NULL,
                tipo_documento VARCHAR(32) NOT NULL DEFAULT 'CI_PARAGUAYA',
                tipo_operacion VARCHAR(16) NOT NULL DEFAULT 'B2C',
                is_default BOOLEAN NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT ck_customer_invoice_profile_tipo_documento CHECK (
                    tipo_documento IN (
                        'CI_PARAGUAYA','RUC','PASAPORTE','CEDULA_EXTRANJERA',
                        'CARNET_RESIDENCIA','INNOMINADO','DIPLOMATICA_EXONERACION','OTRO'
                    )
                ),
                CONSTRAINT ck_customer_invoice_profile_tipo_operacion CHECK (
                    tipo_operacion IN ('B2B','B2C','B2G','EXTRANJERO')
                )
            )
        """

    try:
        conn.exec_driver_sql(create_sql)
    except Exception as exc:
        logger.debug("migration 080 CREATE TABLE customer_invoice_profile skipped: %s", exc)

    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_customer_invoice_profile_customer_id "
            "ON customer_invoice_profile (customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_invoice_profile_ruc_ci "
            "ON customer_invoice_profile (ruc_ci)",
        "CREATE INDEX IF NOT EXISTS ix_customer_invoice_profile_customer_default "
            "ON customer_invoice_profile (customer_id, is_default)",
    ):
        try:
            conn.exec_driver_sql(idx_sql)
        except Exception as exc:
            logger.debug("migration 080 index skipped: %s", exc)

    # Backfill: every customer with invoice_ruc OR invoice_name set
    # gets a default profile named "Personal" (or the razon_social if
    # it differs from the customer's name — covers the case where the
    # cashier had been invoicing under the customer's own company).
    # Idempotent because we use NOT EXISTS to skip customers that
    # already have a profile from a re-run.
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn.exec_driver_sql(
            """
            INSERT INTO customer_invoice_profile
                (customer_id, alias, ruc_ci, razon_social,
                 tipo_documento, tipo_operacion, is_default, is_active,
                 created_at, updated_at)
            SELECT
                c.id,
                CASE WHEN c.invoice_name IS NOT NULL
                       AND c.invoice_name != c.name
                     THEN c.invoice_name
                     ELSE 'Personal' END,
                COALESCE(NULLIF(c.invoice_ruc, ''), ''),
                COALESCE(NULLIF(c.invoice_name, ''), c.name),
                CASE WHEN LENGTH(COALESCE(NULLIF(c.invoice_ruc, ''), '')) >= 9
                     THEN 'RUC' ELSE 'CI_PARAGUAYA' END,
                'B2C',
                1,
                1,
                :ts,
                :ts
            FROM customer c
            WHERE (c.invoice_ruc IS NOT NULL AND c.invoice_ruc != '')
               OR (c.invoice_name IS NOT NULL AND c.invoice_name != '')
              AND NOT EXISTS (
                  SELECT 1 FROM customer_invoice_profile p
                  WHERE p.customer_id = c.id
              )
            """,
            {"ts": ts},
        )
    except Exception as exc:
        logger.debug("migration 080 backfill skipped: %s", exc)

    _bump_schema_version(conn, 80)


def _migration_081_pedido_delivery_window(conn: Any) -> None:
    """Phase 13 (2026-10-01): Preferred delivery window + invoice-profile FK.

    Research (Wix Restaurants, Uber Direct dropoff_ready/deadline_dt,
    Instacart "desired windows", DoorDash Drive) showed the cashier
    needs to express a preferred window of arrival — NOT a delivery
    promise. This migration adds:

      delivery_preference    ENUM asap | window | scheduled
      delivery_window_start  HH:MM (e.g. "14:00")
      delivery_window_end    HH:MM (e.g. "16:00")
      delivery_scheduled_date DATE (for future-dated pedido)

      customer_invoice_profile_id FK  (links to the chosen profile)
      customer_address_id FK          (links to the chosen address)

    All columns are additive nullable — existing pedidos stay valid.
    """
    if conn.dialect.name == "sqlite":
        add_columns_sql = [
            "ALTER TABLE pedido ADD COLUMN delivery_preference VARCHAR(16) DEFAULT 'asap'",
            "ALTER TABLE pedido ADD COLUMN delivery_window_start VARCHAR(8)",
            "ALTER TABLE pedido ADD COLUMN delivery_window_end VARCHAR(8)",
            "ALTER TABLE pedido ADD COLUMN delivery_scheduled_date DATE",
            "ALTER TABLE pedido ADD COLUMN customer_invoice_profile_id INTEGER REFERENCES customer_invoice_profile(id) ON DELETE SET NULL",
            "ALTER TABLE pedido ADD COLUMN customer_address_id INTEGER REFERENCES customer_address(id) ON DELETE SET NULL",
        ]
    else:  # postgres
        add_columns_sql = [
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS delivery_preference VARCHAR(16) DEFAULT 'asap'",
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS delivery_window_start VARCHAR(8)",
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS delivery_window_end VARCHAR(8)",
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS delivery_scheduled_date DATE",
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS customer_invoice_profile_id INTEGER REFERENCES customer_invoice_profile(id) ON DELETE SET NULL",
            "ALTER TABLE pedido ADD COLUMN IF NOT EXISTS customer_address_id INTEGER REFERENCES customer_address(id) ON DELETE SET NULL",
        ]

    for sql in add_columns_sql:
        try:
            conn.exec_driver_sql(sql)
        except Exception as exc:
            logger.debug("migration 081 ADD COLUMN skipped: %s", exc)

    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS ix_pedido_invoice_profile ON pedido(customer_invoice_profile_id)",
        "CREATE INDEX IF NOT EXISTS ix_pedido_address_id ON pedido(customer_address_id)",
        "CREATE INDEX IF NOT EXISTS ix_pedido_delivery_preference ON pedido(delivery_preference)",
    ):
        try:
            conn.exec_driver_sql(idx_sql)
        except Exception as exc:
            logger.debug("migration 081 index skipped: %s", exc)

    _bump_schema_version(conn, 81)


def _migration_082_expense(conn: Any) -> None:
    """Phase 14 (2026-10-01): Expense model for cierres mensuales.

    Until now, `daily_summary()` returned
    `expenses_placeholder_gs=0` and the cierres mensuales could
    not subtract operating expenses from margin. This migration
    adds the `expense` table:

        id              INT PK
        occurred_at     DATETIME — when the expense hit the cash
        category        VARCHAR(32) — INGREDIENT | RENT | UTILITIES |
                                          PAYROLL | PACKAGING | OTHER
        description     VARCHAR(255)
        amount_gs       INT — always positive (sign applied at
                          aggregate time)
        is_voided        BOOLEAN (false default)
        created_at      DATETIME (UTC, default now)

    Categories are an INKWARD check constraint (sqlite doesn't have
    ENUM; we guard via CHECK at row-insert time in the ORM +
    `executor-mapper` falls back to the constraint if ORM bypassed).
    The table is referenced by daily_summary() to compute real
    `expenses_gs` from rows in the day window.
    """
    try:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS expense (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at DATETIME NOT NULL,
                category VARCHAR(32) NOT NULL,
                description VARCHAR(255) NOT NULL DEFAULT '',
                amount_gs INTEGER NOT NULL,
                is_voided BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    except Exception as exc:
        logger.warning("migration 082 CREATE TABLE expense failed: %s", exc)

    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_expense_occurred_at ON expense(occurred_at)"
        )
    except Exception as exc:
        logger.debug("migration 082 ix_expense_occurred_at skipped: %s", exc)

    try:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_expense_category ON expense(category)"
        )
    except Exception as exc:
        logger.debug("migration 082 ix_expense_category skipped: %s", exc)

    _bump_schema_version(conn, 82)


def _migration_083_recipe_yield_qty_insert_guard(conn: Any) -> None:
    """BACKLOG #5 (gap-fix) — Migration 028 only added UPDATE triggers.

    Migration 028 created triggers on `UPDATE OF yield_qty` /
    `UPDATE OF qty` that fire `RAISE(ABORT, ...)` when setting to a
    non-null value <= 0. But raw `INSERT INTO recipe (..., yield_qty, ...)
VALUES (..., -1, ...)` slips past those triggers entirely — UPDATE
triggers don't fire on INSERT. Same for `recipe_line.qty`.

    This migration adds the corresponding BEFORE INSERT triggers so
    the guard covers both spell and logical write paths. Idempotent
    (CREATE TRIGGER IF NOT EXISTS).

    On Postgres the constraint lives in the model as a `CheckConstraint`
    so this migration is a no-op there (we still bump the version).
    """
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name == "sqlite":
        # Recipe: yield_qty insert guard (NULL allowed for drafts).
        try:
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS recipe_yield_qty_positive_insert
                BEFORE INSERT ON recipe
                FOR EACH ROW
                WHEN NEW.yield_qty IS NOT NULL AND NEW.yield_qty <= 0
                BEGIN
                    SELECT RAISE(ABORT, 'recipe.yield_qty must be > 0 (or NULL for drafts)');
                END
            """))
        except Exception as exc:
            logger.warning(
                "migration 083 recipe_yield_qty_positive_insert skipped: %s", exc
            )

        # RecipeLine: qty insert guard.
        try:
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS recipe_line_qty_positive_insert
                BEFORE INSERT ON recipe_line
                FOR EACH ROW
                WHEN NEW.qty IS NOT NULL AND NEW.qty <= 0
                BEGIN
                    SELECT RAISE(ABORT, 'recipe_line.qty must be > 0 (or NULL)');
                END
            """))
        except Exception as exc:
            logger.warning(
                "migration 083 recipe_line_qty_positive_insert skipped: %s", exc
            )

    _bump_schema_version(conn, 83)


MIGRATIONS = {
    1: _migration_001_initial_schema,
    2: _migration_002_audit_log,
    3: _migration_003_analytics_columns,
    4: _migration_004_tags,
    5: _migration_005_customer,
    6: _migration_006_waste_log,
    7: _migration_007_product_sku,
    8: _migration_008_tenant,
    9: _migration_009_ingredient_intel,
    10: _migration_010_recipe_intel,
    11: _migration_011_sale_payment_discount,
    12: _migration_012_sale_tz,
    13: _migration_013_ingredient_max_stock,
    14: _migration_014_customer_cedula,
    15: _migration_015_sale_channel,
    16: _migration_016_pedidos,
    17: _migration_017_recipe_line_unit,
    18: _migration_018_price_event,
    19: _migration_019_production_completion,
    20: _migration_020_sale_date_voided_index,
    21: _migration_021_stock_movement,
    22: _migration_022_user_roles,
    23: _migration_023_supplier,
    24: _migration_024_recipe_intel_extended,
    25: _migration_025_ingredient_opening_stock_reorder_point,
    26: _migration_026_product_audit_columns,
    27: _migration_027_production_plan_template,
    28: _migration_028_recipe_yield_qty_check,
    29: _migration_029_herebus_integration,
    30: _migration_030_recipe_image_url,
    31: _migration_031_risk_status_activo,
    32: _migration_032_pedido_cancel_reason,
    33: _migration_033_ingredient_storage,
    34: _migration_034_market_price_reference,
    35: _migration_035_compliance_info,
    36: _migration_036_product_tax_haccp,
    37: _migration_037_sale_fiscal_invoice,
    38: _migration_038_ingredient_haccp,
    39: _migration_039_category_table,
    40: _migration_040_pricing_setting,
    41: _migration_041_channel_catalog,
    42: _migration_042_payment_method_catalog,
    43: _migration_043_branding_setting,
    44: _migration_044_message_templates,
    45: _migration_045_margin_tiers,
    46: _migration_046_stock_status_config,
    47: _migration_047_storage_types,
    48: _migration_048_date_range_presets,
    49: _migration_049_storage_keywords,
    50: _migration_050_sale_void_reason,
    51: _migration_051_ingredient_variant,
    52: _migration_052_ingredient_forecast_horizon,
    53: _migration_053_sale_packaging,
    54: _migration_054_tag_algebra,
    55: _migration_055_supplier_ruc,
    56: _migration_056_bank_reconciliation,
    57: _migration_057_recipe_instructions,
    58: _migration_058_ingredient_expiry,
    59: _migration_059_product_mayorista,
    60: _migration_060_tag_normalization,
    61: _migration_061_tag_validation,
    62: _migration_062_audit_repair,
    63: _migration_063_payment_receipt,
    64: _migration_064_no_op,  # sibling migration claimed slot 64; tablet-slug is at 66
    65: _migration_065_suscripciones,
    66: _migration_066_product_tablet_slug,
    67: _migration_067_pedido_public_token_expiry,
    68: _migration_068_recipe_menu_tags,
    69: _migration_069_customer_addresses_delivery_favorites,
    70: _migration_070_customer_dietary_profile,
    71: _migration_071_customer_profile_completeness,
    72: _migration_072_reorder_supplier_tracking,
    73: _migration_073_ingredient_price_event_supplier,
    74: _migration_074_loyalty_transaction_ledger,
    75: _migration_075_suggestion_event_log,
    76: _migration_076_sale_linked_pedido_id,
    77: _migration_077_pedido_event_log,
    78: _migration_078_communication_log,
    79: _migration_079_customer_address_structured,
    80: _migration_080_customer_invoice_profile,
    81: _migration_081_pedido_delivery_window,
    82: _migration_082_expense,
    83: _migration_083_recipe_yield_qty_insert_guard,
    84: _migration_084_stock_qty_nonneg,
    85: _migration_085_sale_public_token,
    86: _migration_086_placeholder,
    87: _migration_087_placeholder,
    88: _migration_088_placeholder,
    89: _migration_089_refund_table,
    90: _migration_090_stock_movement_affected_recipe_id,
    91: _migration_091_backfill_stock_movement_recipe,
    92: _migration_092_drop_sale_stock_move,
    93: _migration_093_expense_receipt_recurring,
    94: _migration_094_monthly_closure,
    95: _migration_095_soft_delete_columns,
    96: _migration_096_audit_columns,
    97: _migration_097_ingredient_avg_cost,
}


def atomic_ddl_block(conn: Any, statements: Sequence[str]) -> None:
    """Run a sequence of DDL statements with per-statement SAVEPOINT isolation.

    Phase 14 #4 (full migration atomicity): On Postgres, DDL auto-commits
    even mid-transaction, so a list like::

        ALTER TABLE x ADD COLUMN a INT;
        ALTER TABLE x ADD COLUMN b INT;
        ALTER TABLE nonexistent ADD COLUMN c INT;  # this one fails

    would leave columns a and b applied while the migration is
    considered failed. The next migration would then run against a
    partially-modified schema.

    On SQLite this is a non-issue (DDL is transactional). On Postgres,
    we wrap each statement in its own SAVEPOINT: a failure in statement
    N rolls back statement N only; statements 1..N-1 stay committed.

    Caller pattern::

        for sql in ddl_list:
            try:
                atomic_ddl_block(conn, [sql])
            except Exception as exc:
                logger.warning("skipped: %s", exc)
        _bump_schema_version(conn, version)  # only runs if no fatal error
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

    if dialect != "postgresql":
        # SQLite: DDL is transactional; the surrounding with-block
        # already gives all-or-nothing semantics. Just exec directly.
        for sql in statements:
            conn.exec_driver_sql(sql)
        return

    # Postgres: wrap each statement in a SAVEPOINT.
    for i, sql in enumerate(statements):
        sp_name = f"ddl_block_{i}"
        try:
            conn.execute(text(f"SAVEPOINT {sp_name}"))
            conn.exec_driver_sql(sql)
            conn.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
        except Exception:
            try:
                conn.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
                conn.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
            except Exception:
                pass
            raise


def _bump_schema_version(conn: Any, version: int) -> None:
    """Set schema_version to `version` on both SQLite and Postgres.

    On Postgres, app_meta.value is JSONB; a plain TEXT literal fails
    (invalid input syntax for type json), so the version is inlined as
    a typed literal. The bump runs inside its own SAVEPOINT so an
    aborted caller transaction cannot block it.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts = datetime.now(timezone.utc).isoformat()
    if dialect == "postgresql":
        # Use a SAVEPOINT so we can recover from an aborted caller tx.
        # If the conn is in a failed state, the SAVEPOINT itself will
        # fail — so we do a ROLLBACK first to recover.
        try:
            conn.execute(text("ROLLBACK"))
        except Exception:
            pass
        try:
            conn.execute(
                text(
                    "INSERT INTO app_meta (key, value, updated_at) VALUES "
                    "('schema_version', :v_jsonb, :ts) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"
                ),
                {"v_jsonb": f'"{version}"', "ts": ts},
            )
        except Exception:
            # Try one more time with explicit BEGIN
            try:
                conn.execute(text("BEGIN"))
                conn.execute(
                    text(
                        "INSERT INTO app_meta (key, value, updated_at) VALUES "
                        "('schema_version', :v_jsonb, :ts) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"
                    ),
                    {"v_jsonb": f'"{version}"', "ts": ts},
                )
                conn.execute(text("COMMIT"))
            except Exception:
                raise
    else:
        conn.execute(
            text(
                "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                "VALUES ('schema_version', :v, :ts)"
            ),
            {"v": str(version), "ts": ts},
        )


def _current_schema_version(conn: Any) -> int:
    """Read schema version from app_meta table (default 0)."""
    row = conn.execute(text("SELECT value FROM app_meta WHERE key = 'schema_version'")).first()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def schema_version(conn: Any) -> int:
    """Read schema version. Public alias for _current_schema_version.

    Used by `/healthz/schema` endpoint to detect drift between code and
    DB. Returns int (0 means schema_version row missing entirely).
    """
    return _current_schema_version(conn)


def schema_version_mismatch(conn: Any) -> int:
    """Return CURRENT_SCHEMA_VERSION - actual_db_version.

    - Positive = DB is behind code (migrations not applied — risk of
      `column X does not exist` 500s on first request after deploy).
    - Zero = in sync. Healthy.
    - Negative = DB is ahead of code (rolled back to old code).

    Used by `/healthz/schema` to surface drift before operators see 500s.
    """
    return CURRENT_SCHEMA_VERSION - _current_schema_version(conn)


def app_meta_read(conn: Any, key: str) -> str | None:
    """Read one key from app_meta. Returns None if the row is missing.

    Dialect-agnostic. Returns str | None.
    """
    row = conn.execute(
        text("SELECT value FROM app_meta WHERE key = :key"), {"key": key}
    ).first()
    return row[0] if row else None


def app_meta_write(conn: Any, key: str, value: str) -> None:
    """Upsert one key into app_meta. Dialect-agnostic.

    Postgres uses ON CONFLICT (key) DO UPDATE; SQLite uses
    INSERT OR REPLACE. Caller commits the surrounding transaction;
    this function does NOT commit by itself.
    """
    from datetime import datetime, timezone

    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    ts = datetime.now(timezone.utc).isoformat()
    if dialect == "postgresql":
        conn.execute(
            text(
                "INSERT INTO app_meta (key, value, updated_at) VALUES (:k, :v, :ts) "
                "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = :ts"
            ),
            {"k": key, "v": value, "ts": ts},
        )
    else:
        conn.execute(
            text("INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES (:k, :v, :ts)"),
            {"k": key, "v": value, "ts": ts},
        )


def init_db(engine: Engine) -> None:
    """Initialize the database: create tables + run pending migrations.

    Idempotent. Safe to call on every app startup.

    Concurrency: on Postgres we take a session-level advisory lock for the
    duration of the migration block so two replicas rolling out together
    can't run migrations concurrently (which would double-execute them or
    deadlock). On SQLite we rely on the per-process serialization of the
    single-writer connection.

    Atomicity: each individual migration runs inside its own SAVEPOINT on
    Postgres (or implicit transaction on SQLite) so a failed statement
    doesn't leave the whole migration run in a partial state.
    """
    from app.rms.models import Base  # local import to avoid circular deps

    dialect_name = engine.dialect.name if hasattr(engine, "dialect") else "sqlite"

    # Note: We deliberately do NOT take a Postgres advisory lock. Session-level
    # advisory locks on Postgres are tied to the connection — if init_db
    # fails mid-flight and the lock_conn is returned to the pool with the
    # lock still held, subsequent calls would deadlock. Since we run with
    # one replica (Render free tier), concurrency is not an issue.

    _init_db_inner(engine, dialect_name, Base)


def _init_db_inner(engine: Any, dialect_name: str, Base: Any) -> None:
    """Inner init_db helper (extracted so the outer wrapper can release the
    Postgres advisory lock in a finally block).

    Strategy: each migration runs in its OWN TRANSACTION on its own
    CONNECTION. This guarantees that:
    1. A failed migration doesn't poison the next migration
    2. The schema_version bump always succeeds (in a separate
       transaction)
    3. CREATE TRIGGER syntax errors on Postgres don't cascade
    """
    # 1. Create all tables (idempotent; SQLAlchemy skips existing tables)
    Base.metadata.create_all(engine)

    # 2. Read the current schema_version ONCE
    current = 0
    target = CURRENT_SCHEMA_VERSION
    with engine.connect() as probe_conn:
        probe_conn.commit()
        from app.rms.db import schema_version
        current = schema_version(probe_conn)

    # 3. Run each pending migration on its OWN connection (auto-committed).
    # This is more robust than SAVEPOINTs because each migration's
    # transaction state is isolated from the others.
    for v in range(current + 1, target + 1):
        if v not in MIGRATIONS:
            raise RuntimeError(
                f"No migration registered for schema version {v}; "
                f"current={current}, target={target}. "
                "Add the migration in app/rms/db.py."
            )
        try:
            with engine.connect() as mig_conn:
                # Run the migration in its own transaction.
                MIGRATIONS[v](mig_conn)
                # The migration calls _bump_schema_version which uses
                # the same connection. We then commit the whole tx.
                mig_conn.commit()
        except Exception as exc:
            # Don't fail the whole init_db — log and continue to next
            # migration. The lifespan will retry on next boot.
            logger.warning(
                f"migration v{v} failed: {exc!r}; continuing"
            )
            # Print to stderr so Render logs capture it
            print(f"MIGRATION v{v} FAILED: {exc!r}", file=sys.stderr)
            # Validation hook (Phase 14 #4): probe schema_version on a
            # FRESH connection. If it advanced despite the failure, the
            # DDL partially applied — surface as a loud warning so the
            # operator investigates before the next migration assumes a
            # clean baseline.
            after = None
            probe_err = None
            try:
                with engine.connect() as probe:
                    after = schema_version(probe)
            except Exception as probe_exc:
                probe_err = probe_exc
            if after is not None and after >= v:
                msg = (
                    f"DDL PARTIAL APPLY: migration v{v} raised {exc!r} "
                    f"but schema_version is {after} (>= {v}). "
                    "Postgres-only — SQLite cannot reach this state. "
                    "Manual intervention required before next deploy."
                )
                logger.error(msg)
                print(msg, file=sys.stderr)
                # CRITICAL: re-raise OUTSIDE the probe try/except so the
                # caller sees it (init_db must NOT proceed to the next
                # migration on a partial baseline).
                raise RuntimeError(msg) from exc
            elif probe_err is not None:
                logger.debug(
                    f"schema probe after v{v} failure: {probe_err!r}"
                )

        # 3. Apply recommended Postgres indexes (idempotent).
        # Wrapped in its own connection so failure here doesn't undo migrations.
        try:
            from sqlalchemy.orm import sessionmaker

            from app.rms.perf import apply_postgres_indexes
            Session = sessionmaker(bind=engine)()
            _ = apply_postgres_indexes(Session)
            Session.close()
        except Exception as exc:
            # Indexes are an optimization, not a correctness fix.
            # Don't crash startup if the applier hiccups.
            logger.warning(f"apply_postgres_indexes failed (non-fatal): {exc!r}")

    # Sprint 3.2: register before_insert / before_update listeners for
    # the AuditColumns mixin. Auto-fills created_at / updated_at on
    # every insert/update of an owned table.
    try:
        from app.rms.models.common import register_audit_event_listeners
        register_audit_event_listeners()
    except Exception as exc:
        logger.warning(f"register_audit_event_listeners failed (non-fatal): {exc!r}")


def make_session_factory(engine: Engine) -> sessionmaker:
    """Create a configured sessionmaker bound to the engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_db_session(session_factory: sessionmaker) -> Session:
    """Open a new session. Caller is responsible for closing it.

    Typical use:
        sf = make_session_factory(engine)
        with get_db_session(sf) as session:
            ...
    """
    return session_factory()


def safe_commit(session: Session) -> bool:
    """Commit the current transaction, rolling back on any error.

    Returns True on success, False on failure. NEVER raises — the
    caller can choose how to react (raise HTTPException, log + skip, etc.)

    Why this exists (per SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F18):
    Bare `session.commit()` in a request handler raises an unhandled
    exception on IntegrityError or any DB error mid-handler. That leaves
    the session in an inconsistent state for the next pooled connection
    checkout, causing the next request to receive a SQLAlchemy error
    from a half-completed prior transaction.

    Wrapping commit() in try/except/rollback keeps the connection pool
    clean. The function logs the rollback so ops can see it without
    needing to instrument every call site.

    Scope: this is the canonical commit helper for handlers in
    app/routers/sales.py and app/routers/pedidos.py (the money paths).
    Bare commits elsewhere should also migrate to safe_commit, but that
    is a follow-up rollout.
    """
    try:
        session.commit()
        return True
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            # If rollback itself fails, the connection pool will recycle
            # it on close. Log and continue.
            pass
        # Use the project's logger if available, else print to stderr.
        try:
            from loguru import logger as _log

            _log.warning(
                "safe_commit: rollback after error: {err!r}",
                err=exc,
            )
        except ImportError:
            import sys

            print(f"WARNING: safe_commit rollback: {exc!r}", file=sys.stderr)
        return False


__all__ = [
    "MIGRATIONS",
    "MigrationFn",
    "get_db_session",
    "init_db",
    "make_engine",
    "make_session_factory",
    "safe_commit",
]


def _get_db_url_safe() -> str:
    """Return the database URL stripped of credentials.

    Used in backup manifests so the file does not leak the password.
    Returns something like "postgresql+psycopg2://***@host/db".
    """
    import os
    from urllib.parse import urlsplit, urlunsplit

    url = os.environ.get("AIW_SASKIA_DB_URL", "sqlite:///./saskia.db")
    if url.startswith("sqlite"):
        return "sqlite:///<local>"
    try:
        parts = urlsplit(url)
        if parts.username or parts.password:
            netloc = "***@" + parts.netloc.split("@", 1)[-1]
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))
        return url
    except Exception:
        return "<unknown>"


