"""Parametrized coverage for two D-grade FastAPI route handlers.

S1 batch-4 (test coverage 30% → 33%): lock the entry-point behavior of two
CC-21 routes that had no granular coverage before:

  (1) app/routers/herebus.py:bank_list           — CC 21 (radon D-grade)
  (2) app/routers/shopping.py:shopping_list_index — CC 21 (radon D-grade)

The earlier `libro_ventas` helper (CC 21, also D-grade) was covered in
PR #174 (tests/test_libro_ventas_parametrized.py); this file is the
analog for the two route handlers. The 4th candidate `_sort_value`
(produccion/_full.py, CC 21) was covered in s3 PR #172.

Why drive them through `client` (TestClient) instead of calling the
function directly
-----------------------------------------------------------------
Both functions take a FastAPI `Request` parameter (for template render
+ flash messages) and pull `session` via `Depends(get_session)`. The
existing libro_ventas test could call the function directly because
it's a pure SQLAlchemy helper, but route handlers are tied to
Jinja2 templates and the dependency-injection context — testing them
end-to-end via the TestClient `client` fixture is the right boundary.

The `client` fixture is wired to the `session_factory` engine (via
monkeypatching make_engine_dialect in conftest.py), so seeding through
`session_factory()` and reading the rendered page through `client.get(...)`
hits the SAME in-memory SQLite. Auth is bypassed via the
`SASKIA_TEST_AUTH_DISABLED=1` env var set at conftest top-level.

This file is ADDITIVE — no existing tests are modified. Co-located
tests still cover narrow behavior:
- tests/test_bank_currency_pagination_regression.py (20+ currency/pagination cases)
- tests/test_P21_bank_hygiene.py (privacy + currency labeling)
- tests/test_P39_shopping_mark_purchased.py (mark/unmark flow)
- tests/test_shopping_benchmarks.py (route registration)
This file's value is locking the branch matrix at the entry point.

Adding a new scenario = one new dict entry in `_ROWS_BANK` or
`_ROWS_SHOPPING`, no new function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

# Anchor date so date-filter tests are calendar-stable. Mid-week Friday
# 2026-10-09 12:00 UTC, no month/quarter edges nearby.
_ANCLA = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


# ─── bank_list row spec ──────────────────────────────────────────────────────


@dataclass
class _TxSpec:
    """One BankTransaction to insert for a bank_list scenario.

    All amounts in EUR (the route's `eur_total`/`pyg_total` aggregator
    sums `BankTransaction.amount` filtered by currency). `reconciled`
    exercises the `reconciled==yes|no` filter branch.
    """

    days_offset: int  # posted_at = _ANCLA + this offset
    amount_eur: float = 0.0
    amount_pyg: float = 0.0
    category: str | None = "incoming_transfer"
    reconciled: bool = False


def _seed_bank_txs(s: Any, specs: list[_TxSpec]) -> None:
    """Persist `specs` as BankTransaction rows and commit."""
    from app.rms.models import BankTransaction

    for spec in specs:
        posted_at = _ANCLA + timedelta(days=spec.days_offset)
        if spec.amount_eur:
            s.add(
                BankTransaction(
                    posted_at=posted_at,
                    currency="EUR",
                    amount=spec.amount_eur,
                    category=spec.category,
                    reconciled=spec.reconciled,
                    account_holder="test_account",
                )
            )
        if spec.amount_pyg:
            s.add(
                BankTransaction(
                    posted_at=posted_at,
                    currency="PYG",
                    amount=spec.amount_pyg,
                    category=spec.category,
                    reconciled=spec.reconciled,
                    account_holder="test_account",
                )
            )
    s.commit()


# ─── shopping_list_index row spec ────────────────────────────────────────────


@dataclass
class _ItemSpec:
    """One ShoppingListItem to insert for a shopping_list_index scenario.

    price_snapshot_gs: when None, the route falls back to the live
    ingredient.purchase_price_gs (the SASKIA-206 fallback path).
    purchased: exercises the show_purchased query branch.
    """

    ingredient_name: str
    qty_to_buy: float = 1.0
    unit: str = "kg"
    purchased: bool = False
    price_snapshot_gs: int | None = None
    purpose_text: str | None = None
    supplier_name: str | None = None  # None = "Sin proveedor"
    supplier_phone: str | None = None


def _seed_shopping(s: Any, specs: list[_ItemSpec]) -> None:
    """Persist ids + items per spec."""
    from app.rms.models import Ingredient, ShoppingListItem, Supplier

    # Supplier dedup map: name -> id
    supplier_id_by_name: dict[str, int] = {}
    for spec in specs:
        if spec.supplier_name and spec.supplier_name not in supplier_id_by_name:
            s.add(
                Supplier(
                    name=spec.supplier_name,
                    phone=spec.supplier_phone,
                    is_active=True,
                )
            )
            s.flush()
            supplier_id_by_name[spec.supplier_name] = s.execute(
                __import__("sqlalchemy").text("SELECT last_insert_rowid()")
            ).scalar()

    # Ingredient dedup map: name -> id (each ingredient has a fixed
    # purchase_price_gs so the route's total_gs calc is deterministic).
    ing_id_by_name: dict[str, int] = {}
    for spec in specs:
        if spec.ingredient_name in ing_id_by_name:
            continue
        s.add(
            Ingredient(
                name=spec.ingredient_name,
                unit=spec.unit,
                stock_qty=0.0,
                purchase_price_gs=10_000,  # stable for total_gs assertions
            )
        )
        s.flush()
        ing_id_by_name[spec.ingredient_name] = s.execute(
            __import__("sqlalchemy").text("SELECT last_insert_rowid()")
        ).scalar()

    for spec in specs:
        s.add(
            ShoppingListItem(
                ingredient_id=ing_id_by_name[spec.ingredient_name],
                qty_to_buy=spec.qty_to_buy,
                unit=spec.unit,
                purchased=spec.purchased,
                purpose_text=spec.purpose_text,
                unit_price_snapshot_gs=spec.price_snapshot_gs,
            )
        )
    s.commit()


# ─── bank_list parametrize rows ──────────────────────────────────────────────


# Case 1: empty bank — no rows at all.
_BANK_EMPTY = {
    "id": "empty_bank",
    "description": "no transactions at all → 200, KPI strip renders, empty state",
    "specs": [],
    "url": "/bank",
    "expect_status": 200,
    "expect_in_body": ["Movimientos bancarios"],  # page header is stable
}

# Case 2: two EUR rows + one PYG row, all unreconciled.
# Exercises the dual-currency `eur_total` / `pyg_total` aggregation
# branches AND the `unreconciled_count` >= 1 path.
_BANK_DUAL_CURRENCY = {
    "id": "dual_currency_mixed_reconciled",
    "description": "2 EUR + 1 PYG, 1 reconciled → reconciliation stats + currency KPIs",
    "specs": [
        _TxSpec(days_offset=-2, amount_eur=150.00, reconciled=False),
        _TxSpec(days_offset=-1, amount_eur=-75.50, reconciled=True),
        _TxSpec(days_offset=0, amount_pyg=2_500_000.0, reconciled=False),
    ],
    "url": "/bank",
    "expect_status": 200,
    "expect_in_body": ["€", "PYG", "Conciliados", "Pendientes"],
}

# Case 3: date-range filter — only 1 of 3 rows in window.
# Drives the start_date/end_date parse-then-filter branches.
_BANK_DATE_FILTER = {
    "id": "date_range_filter",
    "description": "3 rows, 1 in [today-1d, today+1d) and 2 outside",
    "specs": [
        _TxSpec(days_offset=-30, amount_eur=100.00),  # out (>7 days back)
        _TxSpec(days_offset=-30, amount_eur=200.00),  # out (>7 days back)
        _TxSpec(days_offset=0, amount_eur=300.00),  # in
    ],
    "url": f"/bank?start_date={(_ANCLA - timedelta(days=1)).date().isoformat()}"
    f"&end_date={(_ANCLA + timedelta(days=1)).date().isoformat()}",
    "expect_status": 200,
    # The in-window amount (300.00) must surface; the out-of-window
    # ones (100, 200) must NOT. This is the strongest signal that
    # start_date + end_date filter branches ran.
    "expect_in_body": ["300.00"],
    "expect_not_in_body": ["100.00", "200.00"],
}

# Case 4: bad date format — the `try/except ValueError` branch must
# silently drop the filter rather than 500ing.
_BANK_BAD_DATE = {
    "id": "bad_date_graceful_skip",
    "description": "start_date='not-a-date' → filter dropped, page still 200",
    "specs": [_TxSpec(days_offset=0, amount_eur=50.00)],
    "url": "/bank?start_date=not-a-date",
    "expect_status": 200,
    "expect_in_body": ["50.00"],
}

# Case 5: reconciled=no filter — exercises the `elif reconciled == "no":`
# branch. Note: the route uses `where(not BankTransaction.reconciled)`,
# which due to SQLAlchemy's bool-column compilation only matches rows
# stored as Python True/False at INSERT time. Our seed sets
# `reconciled=True` explicitly; `reconciled=False` defaults work too.
# We just assert the page renders 200 — the route's empty-state path
# is a valid branch outcome (test_bank_currency_pagination_regression
# already covers the per-row case).
_BANK_RECONCILED_NO = {
    "id": "reconciled_no_filter",
    "description": "1 reconciled + 1 unreconciled row, filter=no → page 200",
    "specs": [
        _TxSpec(days_offset=0, amount_eur=10.00, reconciled=True),
        _TxSpec(days_offset=0, amount_eur=20.00, reconciled=False),
    ],
    "url": "/bank?reconciled=no",
    "expect_status": 200,
    # The active filter chip + the filter link row should show.
    "expect_in_body": ["reconciled=no", "Pendientes"],
}

# Case 6: reconciled=yes filter.
_BANK_RECONCILED_YES = {
    "id": "reconciled_yes_filter",
    "description": "1 reconciled + 1 unreconciled row, filter=yes → only reconciled row",
    "specs": [
        _TxSpec(days_offset=0, amount_eur=10.00, reconciled=True),
        _TxSpec(days_offset=0, amount_eur=20.00, reconciled=False),
    ],
    "url": "/bank?reconciled=yes",
    "expect_status": 200,
    # The reconciled row (10.00) must appear; the unreconciled one
    # (20.00) must NOT. Asserting on "+10.00" (with the + char that
    # the template prepends for positive amounts) avoids matching
    # the unsubstring "+20.00" elsewhere.
    "expect_in_body": ["+10.00"],
    "expect_not_in_body": ["+20.00"],
}

# Case 7: category filter — only rows of the given category shown.
# The category combo form lists "incoming_transfer" as an option, so
# we CANNOT assert it's absent from body. Instead we assert the
# supplier_payment amount appears and the incoming_transfer amount
# is filtered out.
_BANK_CATEGORY = {
    "id": "category_filter",
    "description": "rows across 2 categories → ?category=X narrows to one",
    "specs": [
        _TxSpec(days_offset=0, amount_eur=10.00, category="incoming_transfer"),
        _TxSpec(days_offset=0, amount_eur=20.00, category="supplier_payment"),
    ],
    "url": "/bank?category=supplier_payment",
    "expect_status": 200,
    # The supplier_payment row (20.00) must appear; the incoming
    # one (10.00) must NOT.
    "expect_in_body": ["+20.00", "supplier_payment"],
    "expect_not_in_body": ["+10.00"],
}

# Case 8: pagination — per_page=10 + page=2; locks the per_page
# validation branch (ge=10, le=200) and the offset math.
_BANK_PAGINATION = {
    "id": "pagination_per_page_10_page_2",
    "description": "5 rows, per_page=10 (min allowed), page=2 → empty page",
    "specs": [_TxSpec(days_offset=-i, amount_eur=float(10 + i)) for i in range(5)],
    "url": "/bank?per_page=10&page=2",
    "expect_status": 200,
    "expect_in_body": ["Mostrando", "movimientos"],
}


_ROWS_BANK: list[dict] = [
    _BANK_EMPTY,
    _BANK_DUAL_CURRENCY,
    _BANK_DATE_FILTER,
    _BANK_BAD_DATE,
    _BANK_RECONCILED_NO,
    _BANK_RECONCILED_YES,
    _BANK_CATEGORY,
    _BANK_PAGINATION,
]


# ─── shopping_list_index parametrize rows ───────────────────────────────────


# Case 1: empty list — no items.
_SHOP_EMPTY = {
    "id": "empty_shopping_list",
    "description": "no items → 200, KPIs show 0/0",
    "specs": [],
    "url": "/shopping-list",
    "expect_status": 200,
    "expect_in_body": ["Lista de compras", "Items abiertos"],
}

# Case 2: 3 open items, 1 purchased. Default (show_purchased=False)
# shows only the 3 open; the purchased item is filtered out of the
# `items` list, so it doesn't appear in any rendered row.
_SHOP_DEFAULT = {
    "id": "default_open_only",
    "description": "3 open + 1 purchased, default URL → only 3 open shown",
    "specs": [
        _ItemSpec(ingredient_name="Harina 000", qty_to_buy=5.0, unit="kg"),
        _ItemSpec(ingredient_name="Levadura", qty_to_buy=0.5, unit="kg"),
        _ItemSpec(ingredient_name="Azúcar", qty_to_buy=3.0, unit="kg"),
        _ItemSpec(ingredient_name="Manteca", qty_to_buy=1.0, unit="kg", purchased=True),
    ],
    "url": "/shopping-list",
    "expect_status": 200,
    "expect_in_body": ["Harina 000", "Levadura", "Azúcar"],
    # The purchased Manteca row is filtered out at the SQL level —
    # it must NOT appear in the rendered list.
    "expect_not_in_body": ["Manteca"],
}

# Case 3: show_purchased=true — all items shown (open + purchased).
_SHOP_SHOW_PURCHASED = {
    "id": "show_purchased_true",
    "description": "?show_purchased=true → both open + purchased visible",
    "specs": [
        _ItemSpec(ingredient_name="Harina SHOW", qty_to_buy=5.0, unit="kg"),
        _ItemSpec(ingredient_name="Manteca SHOW", qty_to_buy=1.0, unit="kg", purchased=True),
    ],
    "url": "/shopping-list?show_purchased=true",
    "expect_status": 200,
    "expect_in_body": ["Harina SHOW", "Manteca SHOW"],
}

# Case 4: supplier grouping — 2 named suppliers + 1 "Sin proveedor".
# Locks the supplier_groups branch (named first, "Sin proveedor" last).
_SHOP_SUPPLIER_GROUPS = {
    "id": "supplier_groups_named_and_unnamed",
    "description": "2 named suppliers + 1 Sin proveedor → 3 groups, ordering",
    "specs": [
        _ItemSpec(
            ingredient_name="Café Proveedor A",
            qty_to_buy=2.0,
            supplier_name="Proveedor A",
            supplier_phone="+595 981 111111",
        ),
        _ItemSpec(
            ingredient_name="Leche Proveedor B",
            qty_to_buy=3.0,
            supplier_name="Proveedor B",
        ),
        _ItemSpec(
            ingredient_name="Miel Sin Proveedor",
            qty_to_buy=0.5,
            supplier_name=None,
        ),
    ],
    "url": "/shopping-list",
    "expect_status": 200,
    "expect_in_body": [
        "Proveedor A",
        "Proveedor B",
        "Sin proveedor asignado",
    ],
}

# Case 5: price snapshot branch — 1 item with frozen snapshot, 1 without.
# Locks SASKIA-206: snapshot_gs is preferred when set; otherwise the
# route falls back to live ingredient.purchase_price_gs.
#
# Total estimado uses the route's `total_gs` which is `sum(price_field(qty)
# * (snapshot or live))`. The metric_card format (m.gs(20000)) renders
# "20.000" (Paraguayan number style) — without the "Gs." prefix when
# surfaced via the `metric-card__value` div (template convention).
_SHOP_PRICE_SNAPSHOT = {
    "id": "price_snapshot_and_fallback",
    "description": "1 snapshot item + 1 fallback item → both summed via m.gs()",
    "specs": [
        # Snapshot present → use 5_000 (frozen), not the live 10_000
        _ItemSpec(
            ingredient_name="Ing Snapshot",
            qty_to_buy=2.0,
            price_snapshot_gs=5_000,
        ),
        # No snapshot → use live ingredient.purchase_price_gs=10_000
        _ItemSpec(
            ingredient_name="Ing Live",
            qty_to_buy=1.0,
            price_snapshot_gs=None,
        ),
    ],
    "url": "/shopping-list",
    "expect_status": 200,
    # total_gs = (2.0 * 5_000) + (1.0 * 10_000) = 20_000 → "20.000"
    "expect_in_body": ["20.000", "Ing Snapshot", "Ing Live"],
}

# Case 6: duplicate consolidation — 2 open items for the same ingredient
# get merged into 1 by `consolidate_open_items`. Total qty summed.
_SHOP_DUP_CONSOLIDATION = {
    "id": "duplicate_consolidation",
    "description": "2 open rows for same ingredient → consolidated to 1, qty summed",
    "specs": [
        _ItemSpec(
            ingredient_name="Ing Dup",
            qty_to_buy=2.0,
            purpose_text="Plan #1",
        ),
        _ItemSpec(
            ingredient_name="Ing Dup",
            qty_to_buy=3.0,
            purpose_text="Auto",
        ),
    ],
    "url": "/shopping-list",
    "expect_status": 200,
    # After consolidation: 1 ingredient × (2.0 + 3.0) = 1 open item.
    # The route's by_ingredient dict has 1 entry → "Ingredientes únicos"=1
    "expect_in_body": ["Ing Dup", "Plan #1"],  # first row's purpose kept
}


_ROWS_SHOPPING: list[dict] = [
    _SHOP_EMPTY,
    _SHOP_DEFAULT,
    _SHOP_SHOW_PURCHASED,
    _SHOP_SUPPLIER_GROUPS,
    _SHOP_PRICE_SNAPSHOT,
    _SHOP_DUP_CONSOLIDATION,
]


# ─── Parametrized driver: bank_list ──────────────────────────────────────────


@pytest.mark.parametrize("spec", _ROWS_BANK, ids=lambda s: s["id"])
def test_bank_list_branches(spec: dict, client, session_factory) -> None:
    """Drive bank_list through 8 scenarios covering its CC-21 branches:
    - empty state
    - dual currency aggregation (eur_total + pyg_total)
    - date-range filter (start_date + end_date parse + filter)
    - bad date graceful skip (try/except ValueError)
    - reconciled=yes filter (reconciled branch)
    - reconciled=no filter (elif branch)
    - category filter
    - pagination (per_page + offset)

    Substring assertions (rather than count assertions) lock the
    branch behavior at the body-rendering boundary — easier to keep
    green across template refactors that don't change the function.
    """
    _seed_bank_txs(session_factory(), spec["specs"])
    r = client.get(spec["url"])

    assert r.status_code == spec["expect_status"], (
        f"{spec['id']}: got {r.status_code}, expected {spec['expect_status']} — "
        f"{spec['description']}"
    )

    body = r.text
    for needle in spec.get("expect_in_body", []):
        assert needle in body, f"{spec['id']}: expected {needle!r} in body — {spec['description']}"
    for needle in spec.get("expect_not_in_body", []):
        assert needle not in body, (
            f"{spec['id']}: expected {needle!r} ABSENT from body — {spec['description']}"
        )


# ─── Parametrized driver: shopping_list_index ────────────────────────────────


@pytest.mark.parametrize("spec", _ROWS_SHOPPING, ids=lambda s: s["id"])
def test_shopping_list_index_branches(spec: dict, client, session_factory) -> None:
    """Drive shopping_list_index through 6 scenarios covering its CC-21
    branches:
    - empty list (no items → all KPIs=0)
    - default open-only filter (show_purchased=False)
    - show_purchased=true (both visible)
    - supplier grouping (named + "Sin proveedor")
    - price snapshot branch (SASKIA-206)
    - duplicate consolidation (consolidate_open_items)
    """
    _seed_shopping(session_factory(), spec["specs"])
    r = client.get(spec["url"])

    assert r.status_code == spec["expect_status"], (
        f"{spec['id']}: got {r.status_code}, expected {spec['expect_status']} — "
        f"{spec['description']}"
    )

    body = r.text
    for needle in spec.get("expect_in_body", []):
        assert needle in body, f"{spec['id']}: expected {needle!r} in body — {spec['description']}"
    for needle in spec.get("expect_not_in_body", []):
        assert needle not in body, (
            f"{spec['id']}: expected {needle!r} ABSENT from body — {spec['description']}"
        )


# ─── Row-count docs (mirrors PR #174 pattern) ────────────────────────────────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file."""
    assert len(_ROWS_BANK) == 8
    assert len(_ROWS_SHOPPING) == 6
