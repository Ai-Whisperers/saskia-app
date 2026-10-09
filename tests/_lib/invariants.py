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


# --- New helpers (Pillar C2 — added 2026-10-04 as part of test-infra upgrade) ---


def audit_log_present_for(
    session,
    entity_type: str,
    entity_id: int,
    *,
    action: str | None = None,
) -> bool:
    """Audit log has at least one row for (entity_type, entity_id).

    Catches missing audit trail — every state change should leave a log.
    Optionally filter by action substring (e.g. 'void', 'update').

    Returns True if at least one matching row exists.
    """
    from app.rms.models import AuditLog

    q = session.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
    )
    if action is not None:
        q = q.filter(AuditLog.action.like(f"%{action}%"))
    return q.first() is not None


def recipe_cost_within_margin(
    session,
    recipe_id: int,
    *,
    min_margin_pct: float = 0.0,
    max_margin_pct: float = 100.0,
) -> bool:
    """A recipe's sale-vs-cost margin falls within [min, max] percent.

    Returns False if margin is outside the band. Catches regressions where
    a cost or price update breaks the expected business margin.
    """
    from app.rms.models import Product, Recipe

    recipe = session.get(Recipe, recipe_id)
    if recipe is None or not recipe.lines:
        return True  # no data = no assertion to make
    # Sum ingredient cost at recipe's unit (assumes same unit family)
    cost_total = 0
    for line in recipe.lines:
        if line.ingredient is None or line.ingredient.purchase_price_gs is None:
            continue
        cost_total += line.ingredient.purchase_price_gs * (line.qty or 0)
    # Find a product that uses this recipe (best effort)
    product = session.query(Product).filter(Product.recipe_id == recipe_id).first()
    if product is None or product.sale_price_gs is None or cost_total <= 0:
        return True
    margin_pct = (product.sale_price_gs - cost_total) / product.sale_price_gs * 100
    return min_margin_pct <= margin_pct <= max_margin_pct


def redirect_target(r, expected_path: str) -> bool:
    """HTTP helper: response r redirected to expected_path (or starts with it).

    Use in place of `assert r.headers["location"] == expected_path`.
    """
    from fastapi import Response

    if not isinstance(r, Response):
        return False
    if r.status_code not in (301, 302, 303, 307, 308):
        return False
    location = r.headers.get("location", "")
    return location == expected_path or location.startswith(expected_path)


def no_js_errors(page) -> list[str]:
    """Browser helper: extract collected JS console errors from a page object.

    The browser fixture records console errors on `page._saskia_js_errors`.
    Returns the list (empty = pass).
    """
    return list(getattr(page, "_saskia_js_errors", []))
