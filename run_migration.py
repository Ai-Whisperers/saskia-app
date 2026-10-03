#!/usr/bin/env python3

import os

os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

# Import the session factory and migration function
from sqlalchemy import text

from app.rms.db import make_engine, make_session_factory
from app.rms.migrations._084_stock_qty_nonneg import _migration_084_stock_qty_nonneg

print(f"Running migration 084: {_migration_084_stock_qty_nonneg.__name__}")

engine = make_engine()
session_factory = make_session_factory(engine)

with session_factory() as conn:
    _migration_084_stock_qty_nonneg(conn)

print("Checking if triggers exist...")
# Check triggers directly
try:
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ingredient_stock_qty%'")
    )
    triggers = result.fetchall()
    print(f"Triggers found: {triggers}")
except Exception as e:
    print(f"Error checking triggers: {e}")

print("Migration 084 completed!")
