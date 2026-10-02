"""app/services/demo_reset.py — wipe synthetic demo data.

Used by POST /ops/reset-demo-data so Saskia can start fresh before the
2026-09-17 prelaunch.

What this resets (all synthetic — none is real production data):
- All Sale rows
- Sale-driven StockMovement rows (movement_type='sale', reference_type='sale')
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
- Non-sale StockMovement rows (reorder, merma, adjustment — these are
  operator-initiated actions, not sale-driven)
- schema_version, backup timestamps, etc.

Idempotent: re-running deletes 0 rows (the targeted Sale/AuditLog/
AppMeta slices are already empty).

Records its own action as an audit_log row with action='system.demo_reset'
so the operator can see when the cleanup happened.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.rms.models import AppMeta, AuditLog, Sale, StockMovement


def reset_demo_data(session: Session) -> dict[str, int]:
    """Wipe synthetic state. Returns a dict of deleted-row counts.

    Counts are returned (not raised) so the caller can show them in
    the response / audit detail. The function commits at the end so
    callers don't need to.

    Counts reported:
      sales             — sale rows deleted
      stock_moves_sale  — stock_movement rows deleted (sale type, orphan + cascade)
      audit_seed        — AuditLog rows with action='seed.complete'
      app_meta_seed     — AppMeta rows with key='last_seed_at'
    """
    # 1. Count sale-type StockMovement rows BEFORE deleting Sale so we
    # know how many existed when the wipe started. The DB will not
    # cascade (no FK from stock_movement to sale), so we run an
    # explicit delete here.
    stock_moves_before = session.execute(
        select(func.count(StockMovement.id))
        .where(StockMovement.movement_type == "sale")
    ).scalar_one()

    sales_deleted = session.execute(delete(Sale)).rowcount

    # Delete sale-driven StockMovement rows (the read-path equivalent
    # of the legacy sale_stock_move table — see BACKLOG #1).
    session.execute(
        delete(StockMovement).where(StockMovement.movement_type == "sale")
    )

    stock_moves_deleted = stock_moves_before

    audit_seed_deleted = session.execute(
        delete(AuditLog).where(AuditLog.action == "seed.complete")
    ).rowcount

    app_meta_seed_deleted = session.execute(
        delete(AppMeta).where(AppMeta.key == "last_seed_at")
    ).rowcount

    # Record the cleanup itself BEFORE commit so the audit row joins
    # the same transaction.

    from app.rms.audit import record as audit_record

    audit_record(
        session,
        user_id="system",
        action="system.demo_reset",
        target_type="demo_state",
        target_id=None,
        detail={
            "sales_deleted": sales_deleted,
            "stock_moves_sale_deleted": stock_moves_deleted,
            "audit_seed_deleted": audit_seed_deleted,
            "app_meta_seed_deleted": app_meta_seed_deleted,
        },
    )

    session.commit()

    return {
        "sales": sales_deleted,
        "stock_moves_sale": stock_moves_deleted,
        "audit_seed": audit_seed_deleted,
        "app_meta_seed": app_meta_seed_deleted,
    }


__all__ = ["reset_demo_data"]
