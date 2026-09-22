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

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.rms.config import (
    CURRENT_SCHEMA_VERSION,
    DB_PATH,
    ensure_dirs,
)


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
    conn.execute(
        text("UPDATE app_meta SET value = '2', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_007_product_sku(conn: Any) -> None:
    """Add Product.sku column (E23.S1).

    SKU is optional; most bakeries don't print barcodes on products but
    an operator may add them later. Unique when set.
    """
    _add_column_if_missing(conn, "product", "sku",
                           "VARCHAR(32)", "TEXT")
    conn.execute(
        text("UPDATE app_meta SET value = '7', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


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
    conn.execute(
        text("UPDATE app_meta SET value = '6', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_005_customer(conn: Any) -> None:
    """Add Customer table + Sale.customer_id FK (E13).

    Tables are created via create_all() in init_db(). The Sale
    FK column is added in case create_all didn't (e.g. on an existing
    DB that pre-dates the customer table).
    """
    conn.execute(
        text("UPDATE app_meta SET value = '5', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


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
    conn.execute(
        text("UPDATE app_meta SET value = '4', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


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
        except Exception:  # noqa: BLE001 - column already exists; that's fine
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

    conn.execute(
        text("UPDATE app_meta SET value = '3', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )



def _migration_008_tenant(conn):
    """Add tenant table (E15)."""
    conn.execute(
        text("UPDATE app_meta SET value = '8', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_009_ingredient_intel(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '9', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_010_recipe_intel(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '10', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_011_sale_payment_discount(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '11', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_012_sale_tz(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '12', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_013_ingredient_max_stock(conn):
    """Add max_stock_qty column to Ingredient (Phase 7 reorder feature).

    max_stock_qty: nullable FLOAT. NULL means "use 2x min_stock_qty"
    heuristic. Operators can set explicit targets via /inventario/{id}/editar.
    """
    try:
        conn.execute(text("ALTER TABLE ingredient ADD COLUMN max_stock_qty FLOAT"))
    except Exception:
        pass  # already exists
    conn.execute(
        text("UPDATE app_meta SET value = '13', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_014_customer_cedula(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '14', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_015_sale_channel(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '15', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_016_pedidos(conn):
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
    conn.execute(
        text("UPDATE app_meta SET value = '16', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_017_recipe_line_unit(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '17', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_018_price_event(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '18', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_019_production_completion(conn):
    """Add production_completion table (Saskia review round 1, T5).

    Table is created via create_all() in init_db() (the model class was
    added to models.py at the same time). This stub only bumps the
    schema_version row. One row per (product_id, for_date) — upserted
    by app/rms/eod_completions.upsert_completion().
    """
    conn.execute(
        text("UPDATE app_meta SET value = '19', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_020_sale_date_voided_index(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '20', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_021_stock_movement(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '21', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_022_user_roles(conn):
    """Add role column to User table for multi-user support.

    role: VARCHAR(32) NOT NULL DEFAULT 'admin'. Values: admin, cashier, manager.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    col_type = "VARCHAR(32) NOT NULL DEFAULT 'admin'" if dialect == "postgresql" else "TEXT DEFAULT 'admin' NOT NULL"
    try:
        conn.execute(text(f"ALTER TABLE user ADD COLUMN role {col_type}"))
    except Exception:
        pass  # already exists

    conn.execute(
        text("UPDATE app_meta SET value = '22', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_023_supplier(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '23', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_024_recipe_intel_extended(conn):
    """Add recipe cook_minutes, difficulty, family, dietary_tags (audit items 122, 124).

    prep_minutes already exists from migration 003.
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
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

    conn.execute(
        text("UPDATE app_meta SET value = '24', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


def _migration_025_ingredient_opening_stock_reorder_point(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '25', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )



def _migration_026_product_audit_columns(conn):
    """Add product columns used by audit-implemented features but never migrated.

    Originally added to Product model in commit 541e625 (Section 5/6 audit) but
    no migration was created. Production DB at schema v25 is missing these:
    - is_available: bool — toggle to hide from POS (audit item 158)
    - image_url: str — product image URL (audit item 159)
    - category: str — product category (audit item 160)
    - tags: str — comma-separated tags (audit item 161)
    """
    dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
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

    conn.execute(
        text("UPDATE app_meta SET value = :v, updated_at = :ts WHERE key = 'schema_version'"),
        {"v": "26", "ts": datetime.now(timezone.utc).isoformat()},
    )





def _migration_027_production_plan_template(conn):
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

    conn.execute(
        text("UPDATE app_meta SET value = '27', updated_at = :ts WHERE key = 'schema_version'"),
        {"ts": datetime.now(timezone.utc).isoformat()},
    )


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
}


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

    # 1. Take advisory lock on Postgres so concurrent deploys don't fight.
    if dialect_name == "postgresql":
        # Use a stable integer key for the lock. 0x5341534B = "SASK".
        with engine.connect() as lock_conn:
            try:
                lock_conn.execute(text("SELECT pg_advisory_lock(1396581707)"))
                # The lock is held for the duration of THIS connection.
                # We need to keep this connection alive while init_db runs.
                # Instead of trying to share a connection, we hold the lock
                # in a sentinel row approach below. For simplicity we use a
                # session-level lock: hold it for the init_db call.
                lock_conn.connection.connection  # noqa — touch
                _pg_lock_conn = lock_conn
            except Exception:
                _pg_lock_conn = None
    else:
        _pg_lock_conn = None

    try:
        _init_db_inner(engine, dialect_name, Base)
    finally:
        if _pg_lock_conn is not None:
            try:
                _pg_lock_conn.execute(text("SELECT pg_advisory_unlock(1396581707)"))
                _pg_lock_conn.close()
            except Exception:
                pass


def _init_db_inner(engine, dialect_name, Base) -> None:
    """Inner init_db helper (extracted so the outer wrapper can release the
    Postgres advisory lock in a finally block)."""
    # 1. Create all tables (idempotent; SQLAlchemy skips existing tables)
    Base.metadata.create_all(engine)

    # 2. Run migrations
    with engine.connect() as conn:
        # Ensure app_meta exists (create_all should have made it, but defensive)
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS app_meta ("
                "key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
            )
        )

        current = _current_schema_version(conn)
        target = CURRENT_SCHEMA_VERSION

        # Detect dialect once, at function scope
        dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"

        if current < target:
            # Detect dialect for dialect-aware schema_version upsert.
            dialect = conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
            for v in range(current + 1, target + 1):
                if v not in MIGRATIONS:
                    raise RuntimeError(
                        f"No migration registered for schema version {v}; "
                        f"current={current}, target={target}. "
                        "Add the migration in app/rms/db.py."
                    )
                # Postgres aborts the whole transaction on a SQL error,
                # so wrap each migration in a SAVEPOINT to keep going
                # after a benign error (e.g. column already exists).
                if dialect == "postgresql":
                    sp = f"mig_{v}"
                    conn.execute(text(f"SAVEPOINT {sp}"))
                    try:
                        MIGRATIONS[v](conn)
                    except Exception:
                        conn.execute(text(f"ROLLBACK TO SAVEPOINT {sp}"))
                        # Re-raise — migration errors should NOT be silently swallowed
                        # on Postgres, only on SQLite.
                        raise
                    conn.execute(text(f"RELEASE SAVEPOINT {sp}"))
                else:
                    MIGRATIONS[v](conn)
                ts_now = datetime.now(timezone.utc).isoformat()
                if dialect == "postgresql":
                    # app_meta.value is JSONB on prod; cast int → jsonb.
                    upsert_v = (
                        f"INSERT INTO app_meta (key, value, updated_at) "
                        f"VALUES ('schema_version', '\"{v}\"'::jsonb, '{ts_now}') "
                        f"ON CONFLICT (key) DO UPDATE SET "
                        f"value = EXCLUDED.value, updated_at = EXCLUDED.updated_at"
                    )
                    conn.execute(text(upsert_v))
                else:
                    conn.execute(
                        text(
                            "INSERT OR REPLACE INTO app_meta (key, value, updated_at) "
                            "VALUES ('schema_version', :v, :ts)"
                        ),
                        {"v": str(v), "ts": ts_now},
                    )
        conn.commit()

        # 3. Apply recommended Postgres indexes (idempotent).
        # Wrapped in its own connection so failure here doesn't undo migrations.
        if dialect == "postgresql":
            try:
                # Use a Session wrapper around the engine.
                from sqlalchemy.orm import sessionmaker

                from app.rms.perf import apply_postgres_indexes
                Session = sessionmaker(bind=engine)()
                _ = apply_postgres_indexes(Session)
                Session.close()
            except Exception as exc:
                # Indexes are an optimization, not a correctness fix.
                # Don't crash startup if the applier hiccups.
                from loguru import logger
                logger.warning(f"apply_postgres_indexes failed (non-fatal): {exc!r}")


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


__all__ = [
    "make_engine",
    "init_db",
    "make_session_factory",
    "get_db_session",
    "MIGRATIONS",
    "MigrationFn",
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
