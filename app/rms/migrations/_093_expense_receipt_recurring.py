"""Migration 085: Add recurring_period and receipt_url to expense table.

Sprint 3.1: Expense CRUD + MonthlyClosure

Adds two optional columns to the expense table:
- recurring_period: VARCHAR(32) — 'once' | 'monthly' | 'quarterly' | 'yearly'
- receipt_url: VARCHAR(512) — URL to uploaded receipt image (nullable)

Both columns are nullable for backwards compatibility.
"""

from typing import Any

from sqlalchemy import text
