"""app/services/demo_reset.py — wipe synthetic demo data.

Used by POST /ops/reset-demo-data so Saskia can start fresh before the
2026-09-17 prelaunch.

What this resets (all synthetic — none is real production data):
- All Sale rows
- All SaleStockMove rows (cascade from Sale)
- AuditLog rows with action='seed.complete' (the seed marker we use to
  identify "this row was produced by the demo seeder, not real activity")
- AppMeta rows with key='last_seed_at' (only the seed timestamp; we leave
  schema_version + last_backup_at alone)

What this DOES NOT touch:
- Products, Recipes, RecipeLines, Ingredients — these define the
  catalog and are reusable across the demo-data wipe + real-data phase
- Customers (none exist yet)
- Users (the family accounts + the demo user stay)
- Other AuditLog rows (login/logout/sales activity — historical signal
  the operator may want to keep)
- schema_version, backup timestamps, etc.

Idempotent: re-running deletes 0 rows (the targeted Sale/AuditLog/
AppMeta slices are already empty).

Records its own action as an audit_log row with action='system.demo_reset'
so the operator can see when the cleanup happened.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta, AuditLog, Sale, SaleStockMove


def reset_demo_data(session: Session) -> dict[str, int]:
    """Wipe synthetic state. Returns a dict of deleted-row counts.

    Counts are returned (not raised) so the caller can show them in
    the response / audit detail. The function commits at the end so
    callers don't need to.

    Counts reported:
      sales             — sale rows deleted
      sale_stock_moves  — stock-move rows deleted (orphan + cascade)
      audit_seed        — AuditLog rows with action='seed.complete'
      app_meta_seed     — AppMeta rows with key='last_seed_at'
    """
    # 1. Count SaleStockMove BEFORE deleting Sale so we know how many
    # existed when the wipe started. The DB will cascade-delete them
    # on Sale delete, but in case the cascade doesn't fire on some
    # engine (or in case of orphan moves that no longer reference a
    # sale), we run a follow-up explicit delete and report the larger
    # of the two counts.
    stock_moves_before = session.execute(
        select(func.count(SaleStockMove.id))
    ).scalar_one()

    sales_deleted = session.execute(delete(Sale)).rowcount

    # Belt-and-suspenders: wipe any remaining stock moves (some engines
    # may not cascade; SQLite + Postgres do, but be defensive).
    session.execute(delete(SaleStockMove))

    stock_moves_deleted = stock_moves_before

    audit_seed_deleted = session.execute(
        delete(AuditLog).where(AuditLog.action == "seed.complete")
    ).rowcount

    app_meta_seed_deleted = session.execute(
        delete(AppMeta).where(AppMeta.key == "last_seed_at")
    ).rowcount

    # Record the cleanup itself BEFORE commit so the audit row joins
    # the same transaction.
    from datetime import datetime, timezone

    from app.rms.audit import record as audit_record

    audit_record(
        session,
        user_id="system",
        action="system.demo_reset",
        target_type="demo_state",
        target_id=None,
        detail={
            "sales_deleted": sales_deleted,
            "sale_stock_moves_deleted": stock_moves_deleted,
            "audit_seed_deleted": audit_seed_deleted,
            "app_meta_seed_deleted": app_meta_seed_deleted,
        },
    )

    session.commit()

    return {
        "sales": sales_deleted,
        "sale_stock_moves": stock_moves_deleted,
        "audit_seed": audit_seed_deleted,
        "app_meta_seed": app_meta_seed_deleted,
    }


__all__ = ["reset_demo_data"]