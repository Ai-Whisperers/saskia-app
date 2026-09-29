"""Apply v056 bank_reconciliation migration on the live DB.

Live DB is missing reconciled/reconciled_with_type/reconciled_with_id/
reconciled_at/reconciled_by columns on bank_transaction. The migration
file exists and is registered in db.py but the columns never landed
(probably the live DB was restored from a pre-v56 snapshot).

Run once via SSH+docker exec:
    docker cp apply_v056.py <container>:/tmp/
    docker exec <container> python3 /tmp/apply_v056.py
"""
from app.rms.db import make_engine
from app.rms.migrations._056_bank_reconciliation import (
    _migration_056_bank_reconciliation,
    _add_col_if_missing,
)
from sqlalchemy import inspect, text

eng = make_engine()
with eng.begin() as conn:
    # Confirm columns missing
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns("bank_transaction")}
    print(f"Before: {len(cols)} columns")
    missing = {"reconciled", "reconciled_with_type", "reconciled_with_id",
               "reconciled_at", "reconciled_by"} - cols
    print(f"Missing: {missing}")
    if not missing:
        print("Already applied. Nothing to do.")
    else:
        _migration_056_bank_reconciliation(conn)
        # Re-check
        insp = inspect(conn)
        cols = {c["name"] for c in insp.get_columns("bank_transaction")}
        print(f"After: {len(cols)} columns")
        print(f"Now present: {missing & cols}")
