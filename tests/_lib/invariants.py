"""tests/_lib/invariants.py — cross-session invariant assertions (D3).

One import, reused by every scenario:

    from tests._lib.invariants import stock_never_negative, money_is_int

These encode the business rules from AGENTS.md + the e2e suite's inline
assertions so scenarios stop copy-pasting them.
"""

from __future__ import annotations


def stock_never_negative(session) -> list[str]:
    """Return ingredient names with negative stock (empty = pass)."""
    from app.rms.models import Ingredient

    neg = session.query(Ingredient).filter(Ingredient.stock_qty < 0).all()
    return [i.name for i in neg]


def money_is_int(session) -> list[str]:
    """Assert every money column value is an int (AGENTS.md money rule 4).

    Returns list of violations "table.id.column=value".
    """
    from sqlalchemy import text

    checks = [
        ("sale", "unit_price_gs"),
        ("product", "sale_price_gs"),
        ("ingredient", "purchase_price_gs"),
        ("pedido_line", "unit_price_gs"),
    ]
    violations = []
    for table, col in checks:
        try:
            rows = session.execute(text(f"SELECT id, {col} FROM {table}")).all()
        except Exception:
            continue
        for rid, val in rows:
            if val is not None and not isinstance(val, int):
                violations.append(f"{table}.{rid}.{col}={val!r}")
    return violations


def money_columns_integer_typed(engine) -> list[str]:
    """Schema-level check (D4): money columns must be INTEGER in sqlite_master."""
    from sqlalchemy import text

    money_cols = {
        "sale": {"unit_price_gs"},
        "product": {"sale_price_gs"},
        "ingredient": {"purchase_price_gs"},
        "pedido_line": {"unit_price_gs"},
        "waste_log": {"cost_gs"},
    }
    violations = []
    with engine.connect() as conn:
        for table, cols in money_cols.items():
            rows = conn.execute(text(f"PRAGMA table_info({table})")).all()
            types = {r[1]: r[2].upper() for r in rows}
            for col in cols:
                t = types.get(col, "")
                if t and "INT" not in t:
                    violations.append(f"{table}.{col}={t}")
    return violations


def audit_covers(session, *action_keywords: str) -> list[str]:
    """Every keyword must appear in some AuditLog action. Returns missing."""
    from app.rms.models import AuditLog

    actions = {a.action for a in session.query(AuditLog).all()}
    missing = []
    for kw in action_keywords:
        if not any(kw in a for a in actions):
            missing.append(kw)
    return missing


def snapshots_immutable(session, sale_id: int, expected_price: int) -> bool:
    """I2: a sale's unit price snapshot never changes."""
    from app.rms.models import Sale

    s = session.get(Sale, sale_id)
    return s is not None and s.unit_price_gs == expected_price


def foreign_keys_clean(engine) -> list[str]:
    """H3: PRAGMA foreign_key_check returns zero violations."""
    from sqlalchemy import text

    with engine.connect() as conn:
        return [str(r) for r in conn.execute(text("PRAGMA foreign_key_check")).all()]
