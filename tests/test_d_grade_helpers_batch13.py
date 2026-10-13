"""Parametrized coverage for two more D-grade helpers with no branch matrix.
# allow-hardcoded-dates: frozen-time fixture: _ANCLA = date(2026, 10, 9) pins 'now' for reclassify + produccion_print

S1 batch-13 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/routers/produccion/print_export.py:produccion_print` (CC 22, D-grade)
      GET /produccion/print — printable kitchen worksheet. Reuses
      `plan_production()` + `completions_for_date()` and walks each
      plan row to build `print_rows`: skip rows with no produce + no
      completion; merge ad-hoc bakes (completions without a plan row);
      render the strip-down worksheet with optional multi-day pack,
      worksheet mode, shift_saved flag, and ISO-week header. Branches
      covered:

      - empty DB (zero products, zero completions) → 200 with empty
        `days_pack`, print_rows fallback is `[]` (locks the
        `days_pack[0]["rows"] if days_pack else []` branch)
      - 1 product, qty_to_produce=10, no completion → row included
        with `qty_completed=0.0` (locks the positive qty path)
      - 1 product, qty_to_produce=0 BUT a ProductionCompletion row
        exists → row included with qty_to_produce=0 and
        qty_completed > 0 (locks the `r.qty_to_produce <= 0 and
        r.product_id not in completions_by_pid: continue` else-branch)
      - 1 product, qty_to_produce=0 AND no completion → row SKIPPED
        (locks the `continue` branch)
      - product without recipe (`recipe_id IS NULL`) → recipe is
        None, yield_qty/yield_unit/portion_label all None
        (locks the `if r.recipe_id else None` else-branch)
      - product with qty_to_produce=0 (auto-forecast) BUT a
        ProductionCompletion row exists → row kept by the main loop
        (locks the `else` branch of the skip guard)
      - days=3 multi-day pack → 3 sections in days_pack, for_date
        echoed in body (locks the `for day_idx in range(days)` loop
        expanding N consecutive dates)

      Page also exercises these render-only branches via the URL:
      `?mode=worksheet` (locks `request.query_params.get("mode") ==
      "worksheet"`); `?shift_saved=1` (locks
      `request.query_params.get("shift_saved", 0)` parse + int
      coercion); `for_date=None` (locks the `target_date = for_date
      or _asuncion_today()` fallback).

  (2) `scripts/reclassify_sale_channels.py:reclassify` (CC 22, D-grade)
      Reads a VENTAS CSV, normalizes each row's `Canal de Venta`
      value to the canonical Channel enum, and (when not dry-run)
      applies UPDATE Sale.channel WHERE (sold_at ±1s, qty, channel!=)
      via SQLAlchemy. Pure-Python on the CSV side; touches the DB
      only when applying. Branches covered:

      - csv_path does not exist → raises FileNotFoundError (locks
        the `if not csv_path.exists(): raise FileNotFoundError(...)`
        branch)
      - empty CSV (header only, no data rows) → stats with
        csv_rows_total=0, csv_rows_skipped_mostrador=0,
        csv_rows_to_reclassify=0 (locks the `for row in reader`
        zero-iter case)
      - 1 row with channel=Mostrador → csv_rows_skipped_mostrador=1,
        csv_rows_to_reclassify=0, raw distribution has
        `'Mostrador'` and canonical distribution has `'mostrador'`
        (locks the `if canonical == Channel.MOSTRADOR.value:
        csv_skipped += 1; continue` branch)
      - 1 row with channel='Retail' (HEREBUS uppercase English) →
        csv_rows_to_reclassify=1, raw has `'Retail'`, canonical has
        `'retail'` (locks the non-mostrador append branch AND
        the case-insensitive normalize_channel lookup)
      - mixed CSV: 2 mostrador + 1 retail + 1 unknown (e.g. 'FooBar')
        → csv_rows_total=4, csv_rows_skipped_mostrador=2,
        csv_rows_to_reclassify=2 (retail + other), with 'other' as the
        canonical fallback for unknown (locks the
        `normalize_channel` `OTHER` fallback)
      - CSV with unparseable date → that row dropped from
        csv_updates (locks the `csv_updates = [u for u in csv_updates
        if u["sold_at"] is not None]` filter)
      - CSV with PY-format decimal (`1.234.567`) → parse_decimal
        strips the thousands separator; with US-format
        (`1,500.50`) → parse_decimal treats comma as decimal sep
        (locks both decimal-parse branches)
      - dry_run=True → stats returned, no DB writes; rows_updated
        stays 0 (locks the `if dry_run: ... return stats` early
        return)
      - dry_run=False with a matching Sale row in DB →
        rows_updated >= 1, DB row.channel flipped from
        'mostrador' to 'retail' (locks the `result.rowcount` truthy
        branch + the SQL UPDATE window)
      - dry_run=False with NO matching Sale row in DB →
        rows_unchanged += 1, DB unchanged (locks the `else:
        stats["rows_unchanged"] += 1` else-branch)
      - CSV with Spanish header 'Canal de Venta' AND alt header
        'channel' → both raw values picked up; the row uses
        whichever column is present (locks the `row.get("Canal de Venta")
        or row.get("channel")` or-fallback)
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

# ─── produccion_print scenario row spec ─────────────────────────────────────


@dataclass
class _PrintSpec:
    """One scenario for `produccion_print`.

    We seed (optional) products + (optional) completions, then GET
    /produccion/print with a fixed `for_date` and assert the response.
    The spec separates "data seeding" from "URL + body assertions" so
    adding a new scenario is one dict entry.
    """

    id: str = ""
    description: str = ""
    # Seed: list of dicts with keys {name, yield_qty, sale_price_gs,
    # recipe_id_or_none, qty_to_produce_via_override}.
    products: list[dict] = field(default_factory=list)
    # Seed: list of dicts with keys {product_name_or_idx, completed_qty}.
    completions: list[dict] = field(default_factory=list)
    # URL query (for_date always appended by driver; additional params here).
    extra_query: str = ""
    days: int = 1
    expect_status: int = 200
    # Substrings the response body MUST contain.
    expect_in_body: list[str] = field(default_factory=list)
    # Substrings the response body must NOT contain.
    expect_not_in_body: list[str] = field(default_factory=list)


def _seed_print_spec(s: Any, spec: _PrintSpec) -> dict[str, int]:
    """Seed products + completions per `spec` and return name→id map.

    Uses `tests.factories.make_recipe` / `make_product` for the
    standard ingredient+recipe+product preamble. Each product's
    `qty_to_produce_via_override` is set on a per-date override so the
    `plan_production()` call inside the handler returns a deterministic
    row list.
    """
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.rms.models import Product, ProductionCompletion, ProductionPlanOverride
    from tests.factories import ing_line, make_ingredient, make_product, make_recipe

    name_to_id: dict[str, int] = {}
    for p in spec.products:
        ing = make_ingredient(s, name=f"ing_{p['name']}", unit="kg", purchase_price_gs=5000)
        if p.get("yield_qty") is not None:
            rec = make_recipe(
                s,
                name=f"rec_{p['name']}",
                yield_qty=float(p["yield_qty"]),
                yield_unit="und",
                lines=[ing_line(ingredient=ing, qty=0.1, unit="kg")],
            )
            prod = make_product(
                s,
                name=p["name"],
                recipe=rec,
                sale_price_gs=int(p.get("sale_price_gs", 25000)),
                portion_label=p.get("portion_label", "1 unidad"),
            )
        else:
            # No recipe (recipe_id IS NULL).
            prod = make_product(
                s,
                name=p["name"],
                sale_price_gs=int(p.get("sale_price_gs", 25000)),
                portion_label=p.get("portion_label", "1 unidad"),
            )
        name_to_id[p["name"]] = prod.id
        # Pin the qty via override so plan_production() returns this
        # exact value (bypasses auto-forecast which depends on sales
        # history).
        if p.get("qty_to_produce") is not None:
            s.add(
                ProductionPlanOverride(
                    for_date=date(2026, 10, 9),
                    product_id=prod.id,
                    qty=float(p["qty_to_produce"]),
                    updated_at=_dt(2026, 10, 9, 0, 0, tzinfo=_tz.utc),
                    updated_by="test",
                )
            )

    for c in spec.completions:
        # Completions may reference a product that was pre-seeded in
        # the driver's phase 1 (FK donor) — look it up by name if it's
        # not already in our name_to_id map from this spec's products.
        if c["product_name"] not in name_to_id:
            existing = s.query(Product).filter(Product.name == c["product_name"]).one_or_none()
            assert existing is not None, (
                f"Completion references product {c['product_name']!r} that was not pre-seeded"
            )
            name_to_id[c["product_name"]] = existing.id
        pid = name_to_id[c["product_name"]]
        s.add(
            ProductionCompletion(
                product_id=pid,
                for_date=date(2026, 10, 9),
                completed_qty=float(c["completed_qty"]),
                recorded_at=_dt(2026, 10, 9, 12, 0, tzinfo=_tz.utc),
            )
        )

    s.commit()
    return name_to_id


# Anchor date so the test is calendar-stable and override rows land on
# the same `for_date` we pass in the URL.
_ANCLA = date(2026, 10, 9)


_ROWS_PRINT: list[_PrintSpec] = [
    pytest.param(
        _PrintSpec(
            id="empty_db_renders_empty_pack",
            description="zero products, zero completions → 200 with empty days_pack",
            products=[],
            completions=[],
            expect_in_body=["Plan del"],  # worksheet header (any section title)
        ),
        id="empty_db_renders_empty_pack",
    ),
    pytest.param(
        _PrintSpec(
            id="product_with_positive_qty_no_completion",
            description="1 product, qty_to_produce=10, no completion → row appears with qty_completed=0",
            products=[
                {"name": "P1", "yield_qty": 12, "qty_to_produce": 10, "sale_price_gs": 25000}
            ],
            completions=[],
            expect_in_body=["P1"],
        ),
        id="product_with_positive_qty_no_completion",
    ),
    pytest.param(
        _PrintSpec(
            id="product_zero_qty_with_completion_kept",
            description="qty_to_produce=0 BUT completion exists → row kept (else of skip branch)",
            products=[{"name": "P2", "yield_qty": 12, "qty_to_produce": 0, "sale_price_gs": 25000}],
            completions=[{"product_name": "P2", "completed_qty": 5.0}],
            expect_in_body=["P2"],
        ),
        id="product_zero_qty_with_completion_kept",
    ),
    pytest.param(
        _PrintSpec(
            id="product_zero_qty_no_completion_skipped",
            description="qty_to_produce=0 AND no completion → row SKIPPED (continue branch)",
            products=[{"name": "P3", "yield_qty": 12, "qty_to_produce": 0, "sale_price_gs": 25000}],
            completions=[],
            # P3 has qty=0 and no completion → it should NOT appear in
            # the worksheet. Use a non-product substring that's stable.
            expect_not_in_body=["P3"],
        ),
        id="product_zero_qty_no_completion_skipped",
    ),
    pytest.param(
        _PrintSpec(
            id="product_without_recipe_renders",
            description="product with recipe_id=NULL → recipe is None, no yield_label",
            products=[
                {"name": "P4", "yield_qty": None, "qty_to_produce": 7, "sale_price_gs": 25000}
            ],
            completions=[],
            expect_in_body=["P4"],
        ),
        id="product_without_recipe_renders",
    ),
    pytest.param(
        _PrintSpec(
            id="ad_hoc_completion_added_to_print_rows",
            description="completion for product with qty_to_produce=0 → row kept (else of skip branch)",
            # P5 has no override, so plan_production()'s auto-forecast
            # yields qty=0 (no sales history). The completion row keeps
            # it from being skipped (the `else` branch of
            # `r.qty_to_produce <= 0 and r.product_id not in
            # completions_by_pid: continue`).
            products=[],
            completions=[{"product_name": "P5", "completed_qty": 3.0}],
            expect_in_body=["P5"],
        ),
        id="ad_hoc_completion_added_to_print_rows",
    ),
    pytest.param(
        _PrintSpec(
            id="multi_day_pack_eager_3_days",
            description="days=3 → 3 sections in days_pack",
            products=[],
            completions=[],
            days=3,
            expect_in_body=[
                _ANCLA.isoformat(),
                (_ANCLA + timedelta(days=1)).isoformat(),
                (_ANCLA + timedelta(days=2)).isoformat(),
            ],
        ),
        id="multi_day_pack_eager_3_days",
    ),
    pytest.param(
        _PrintSpec(
            id="worksheet_mode_renders_blank_sheet",
            description="?mode=worksheet → worksheet_mode=True (no filled qty column)",
            products=[
                {"name": "P7", "yield_qty": 12, "qty_to_produce": 10, "sale_price_gs": 25000}
            ],
            completions=[],
            extra_query="mode=worksheet",
            expect_in_body=["P7"],
        ),
        id="worksheet_mode_renders_blank_sheet",
    ),
    pytest.param(
        _PrintSpec(
            id="shift_saved_query_passthrough",
            description="?shift_saved=1 → shift_saved=1 in context (rendered as badge)",
            products=[],
            completions=[],
            extra_query="shift_saved=1",
            expect_status=200,
        ),
        id="shift_saved_query_passthrough",
    ),
]


@pytest.mark.parametrize("row", _ROWS_PRINT, ids=lambda r: r.id)
def test_produccion_print_branches(row: _PrintSpec, authed_client) -> None:
    """Drive `produccion_print` across the scenario rows above.

    Auth is bypassed via `SASKIA_TEST_AUTH_DISABLED=1` (set in
    conftest.py top-level). The seeded `session_factory` and the
    `authed_client` TestClient share the same in-memory SQLite engine
    (monkeypatched via `make_engine_dialect` in conftest.py), so
    seeding through the factory hits the same DB the route reads.
    """
    from app.rms.models import ProductionCompletion, ProductionPlanOverride

    # Reset state so previous tests don't leak rows into our pack.
    with authed_client.app.state.session_factory() as s:
        s.query(ProductionPlanOverride).delete()
        s.query(ProductionCompletion).delete()
        s.commit()

    # Seed per scenario. We do it in two phases so referenced FK
    # products (completions may name products that aren't in
    # spec.products) get created and their IDs are visible to both
    # the main seeder and the completion inserter.
    with authed_client.app.state.session_factory() as s:
        from tests.factories import make_product

        # Phase 1: seed all the FK-donor products (referenced by
        # completions but not already declared in spec.products).
        referenced = {c["product_name"] for c in row.completions}
        declared = {p["name"] for p in row.products}
        for nm in referenced - declared:
            make_product(s, name=nm, sale_price_gs=25000, portion_label="1 unidad")
        s.commit()

        # Phase 2: delegate to _seed_print_spec for the spec-driven
        # products + completions (this is where the per-scenario
        # override / recipe wiring happens).
        _seed_print_spec(s, row)

    # Build the URL. The handler accepts ?days=N (1..14); days < 1
    # violates the ge=1 constraint so we always pass an integer.
    qs = f"for_date={_ANCLA.isoformat()}&days={row.days}"
    if row.extra_query:
        qs += f"&{row.extra_query}"
    r = authed_client.get(f"/produccion/print?{qs}")

    assert r.status_code == row.expect_status, (
        f"[{row.id}] expected status {row.expect_status}, got {r.status_code}. Body: {r.text[:300]}"
    )

    body = r.text
    for needle in row.expect_in_body:
        assert needle in body, (
            f"[{row.id}] expected output to contain {needle!r}, but it was missing. "
            f"--- body head ---\n{body[:600]}\n--- end ---"
        )
    for needle in row.expect_not_in_body:
        assert needle not in body, (
            f"[{row.id}] expected output to NOT contain {needle!r}, but it was present. "
            f"--- body head ---\n{body[:600]}\n--- end ---"
        )


# ─── reclassify scenario row spec ──────────────────────────────────────────


@dataclass
class _ReclassifySpec:
    """One scenario for `reclassify`.

    Each row writes a temp CSV, sets up a minimal Sale table in
    a temp SQLite (matching the reclassify script's actual UPDATE
    target), monkeypatches `scripts.reclassify_sale_channels.make_engine`
    to point at the temp DB, then runs `reclassify` and asserts.
    """

    id: str = ""
    description: str = ""
    # CSV body (text — uses utf-8 encoding).
    csv_body: str = ""
    # Optional pre-seed Sale rows in the temp DB. Each entry is a dict
    # {sold_at_iso, product_id, customer_id, qty, unit_price_gs, channel}.
    seed_sales: list[dict] = field(default_factory=list)
    dry_run: bool = True
    expect_status: type[BaseException] | None = None  # Exception class to expect, or None
    # Stats assertions (only checked when no exception expected).
    expect_csv_rows_total: Optional[int] = None
    expect_csv_rows_skipped_mostrador: Optional[int] = None
    expect_csv_rows_to_reclassify: Optional[int] = None
    expect_rows_updated_min: Optional[int] = None
    expect_rows_unchanged_min: Optional[int] = None
    expect_rows_unchanged_max: Optional[int] = None
    # Optional DB row checks after run. Each entry is a dict
    # {where_sql: "...", expect_channel: "..."}.
    post_db_checks: list[dict] = field(default_factory=list)


# Minimal Sale schema mirroring what reclassify's UPDATE targets. We
# reuse the table layout from `tests/test_reclassify_sale_channels.py`
# so a future SASKIA-204 follow-up test can dedupe if desired.
_SALE_SCHEMA = """
    CREATE TABLE tenant (
        id INTEGER PRIMARY KEY,
        name TEXT,
        slug TEXT UNIQUE,
        primary_color TEXT
    );
    INSERT INTO tenant (id, name, slug, primary_color)
        VALUES (1, 'Test', 'test', '#000000');

    CREATE TABLE product (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        name TEXT,
        sku TEXT,
        unit_price_gs INTEGER,
        is_active INTEGER DEFAULT 1
    );
    INSERT INTO product (id, tenant_id, name, sku, unit_price_gs)
        VALUES (1, 1, 'Test Product', 'TEST-001', 25000);
    INSERT INTO product (id, tenant_id, name, sku, unit_price_gs)
        VALUES (2, 1, 'Second',     'TEST-002', 30000);

    CREATE TABLE customer (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        name TEXT,
        phone TEXT
    );
    INSERT INTO customer (id, tenant_id, name, phone)
        VALUES (1, 1, 'Walk-in', NULL);

    CREATE TABLE sale (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER,
        product_id INTEGER,
        customer_id INTEGER,
        qty REAL,
        unit_price_gs INTEGER,
        channel TEXT,
        sold_at TEXT,
        notes TEXT,
        voided_at TEXT,
        FOREIGN KEY (product_id) REFERENCES product(id),
        FOREIGN KEY (customer_id) REFERENCES customer(id)
    );
"""


def _setup_reclassify_db(db_path: Path, seed_sales: list[dict]) -> None:
    """Create the minimal schema + seed sales in `db_path`."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SALE_SCHEMA)
    for s in seed_sales:
        conn.execute(
            "INSERT INTO sale (tenant_id, product_id, customer_id, qty, "
            "unit_price_gs, channel, sold_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                s["product_id"],
                1,
                s["qty"],
                s["unit_price_gs"],
                s["channel"],
                s["sold_at_iso"],
            ),
        )
    conn.commit()
    conn.close()


_ROWS_RECLASSIFY: list[_ReclassifySpec] = [
    pytest.param(
        _ReclassifySpec(
            id="missing_csv_raises_filenotfound",
            description="csv_path doesn't exist → FileNotFoundError",
            csv_body="",  # not written
            dry_run=True,
            expect_status=FileNotFoundError,
        ),
        id="missing_csv_raises_filenotfound",
    ),
    pytest.param(
        _ReclassifySpec(
            id="empty_csv_zero_stats",
            description="CSV with header only → all counts are 0",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n"),
            seed_sales=[],
            dry_run=True,
            expect_csv_rows_total=0,
            expect_csv_rows_skipped_mostrador=0,
            expect_csv_rows_to_reclassify=0,
        ),
        id="empty_csv_zero_stats",
    ),
    pytest.param(
        _ReclassifySpec(
            id="all_mostrador_skipped",
            description="all rows channel=Mostrador → csv_rows_skipped_mostrador = total",
            csv_body=(
                "Fecha,Canal de Venta,Unidades,Total (₲)\n"
                "2026-10-01,Mostrador,2.0,50000\n"
                "2026-10-02,Mostrador,3.0,75000\n"
            ),
            seed_sales=[],
            dry_run=True,
            expect_csv_rows_total=2,
            expect_csv_rows_skipped_mostrador=2,
            expect_csv_rows_to_reclassify=0,
        ),
        id="all_mostrador_skipped",
    ),
    pytest.param(
        _ReclassifySpec(
            id="single_retail_row_normalized",
            description="1 row channel=Retail → csv_rows_to_reclassify=1, raw 'Retail' canonical 'retail'",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,2.0,50000\n"),
            seed_sales=[],
            dry_run=True,
            expect_csv_rows_total=1,
            expect_csv_rows_skipped_mostrador=0,
            expect_csv_rows_to_reclassify=1,
        ),
        id="single_retail_row_normalized",
    ),
    pytest.param(
        _ReclassifySpec(
            id="mixed_mostrador_retail_other",
            description="4 rows: 2 mostrador + 1 retail + 1 unknown 'FooBar' → 2 skipped, 2 to_reclassify",
            csv_body=(
                "Fecha,Canal de Venta,Unidades,Total (₲)\n"
                "2026-10-01,Mostrador,2.0,50000\n"
                "2026-10-02,Mostrador,3.0,75000\n"
                "2026-10-03,Retail,4.0,100000\n"
                "2026-10-04,FooBar,5.0,125000\n"
            ),
            seed_sales=[],
            dry_run=True,
            expect_csv_rows_total=4,
            expect_csv_rows_skipped_mostrador=2,
            expect_csv_rows_to_reclassify=2,
        ),
        id="mixed_mostrador_retail_other",
    ),
    pytest.param(
        _ReclassifySpec(
            id="unparseable_date_dropped_from_updates",
            description="row with date='not-a-date' → dropped from csv_updates",
            csv_body=(
                "Fecha,Canal de Venta,Unidades,Total (₲)\n"
                "2026-10-01,Retail,2.0,50000\n"
                "not-a-date,Wholesale,3.0,75000\n"
            ),
            seed_sales=[],
            dry_run=True,
            # raw_channel_distribution has 2 entries; csv_updates has
            # only 1 (the parseable-date row). csv_rows_total still 2
            # (raw count is post-parse).
            expect_csv_rows_total=2,
            expect_csv_rows_skipped_mostrador=0,
            expect_csv_rows_to_reclassify=1,
        ),
        id="unparseable_date_dropped_from_updates",
    ),
    pytest.param(
        _ReclassifySpec(
            id="py_format_thousands_separator",
            description="Unidades='1.234.567' (PY format) → parse_decimal strips periods",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,1.234,50000\n"),
            seed_sales=[],
            dry_run=True,
            # parse_decimal('1.234') → only one period, no comma →
            # treated as decimal → Decimal('1.234'). Either way the
            # row normalizes to retail + parseable date, so it's
            # counted in csv_rows_to_reclassify.
            expect_csv_rows_to_reclassify=1,
        ),
        id="py_format_thousands_separator",
    ),
    pytest.param(
        _ReclassifySpec(
            id="us_format_comma_decimal_sep",
            description="Unidades='1,500.50' (US format) → parse_decimal handles both separators",
            csv_body=(
                "Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,1,500.50,50000\n"
            ),
            seed_sales=[],
            dry_run=True,
            # Note: '1,500.50' has BOTH separators → period-thousands
            # branch → strips period → strips comma → replaces comma
            # with period → '1500.50' → 1500.50. The row is valid
            # regardless of decimal interpretation.
            expect_csv_rows_to_reclassify=1,
        ),
        id="us_format_comma_decimal_sep",
    ),
    pytest.param(
        _ReclassifySpec(
            id="dry_run_no_db_writes",
            description="dry_run=True → stats returned, rows_updated stays 0 even with matching sale",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,2.0,50000\n"),
            seed_sales=[
                {
                    "product_id": 1,
                    "qty": 2.0,
                    "unit_price_gs": 25000,
                    "channel": "mostrador",
                    "sold_at_iso": "2026-10-01 00:00:00",
                }
            ],
            dry_run=True,
            expect_rows_updated_min=0,
            expect_rows_unchanged_max=0,  # dry-run never increments this
            post_db_checks=[
                {
                    "where_sql": "SELECT channel FROM sale WHERE id = 1",
                    "expect_channel": "mostrador",  # unchanged
                }
            ],
        ),
        id="dry_run_no_db_writes",
    ),
    pytest.param(
        _ReclassifySpec(
            id="apply_updates_matching_sale_to_retail",
            description="dry_run=False + matching sale → DB row flipped to 'retail'",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,2.0,50000\n"),
            seed_sales=[
                {
                    "product_id": 1,
                    "qty": 2.0,
                    "unit_price_gs": 25000,
                    "channel": "mostrador",
                    "sold_at_iso": "2026-10-01 00:00:00",
                }
            ],
            dry_run=False,
            expect_rows_updated_min=1,
            post_db_checks=[
                {
                    "where_sql": "SELECT channel FROM sale WHERE id = 1",
                    "expect_channel": "retail",
                }
            ],
        ),
        id="apply_updates_matching_sale_to_retail",
    ),
    pytest.param(
        _ReclassifySpec(
            id="apply_no_match_increments_unchanged",
            description="dry_run=False + no matching sale → rows_unchanged += 1, DB unchanged",
            csv_body=("Fecha,Canal de Venta,Unidades,Total (₲)\n2026-10-01,Retail,2.0,50000\n"),
            # Sale row exists but on a DIFFERENT date → UPDATE window
            # misses → rowcount=0 → rows_unchanged += 1.
            seed_sales=[
                {
                    "product_id": 1,
                    "qty": 2.0,
                    "unit_price_gs": 25000,
                    "channel": "mostrador",
                    "sold_at_iso": "2026-09-15 00:00:00",
                }
            ],
            dry_run=False,
            expect_rows_unchanged_min=1,
            post_db_checks=[
                {
                    "where_sql": "SELECT channel FROM sale WHERE id = 1",
                    "expect_channel": "mostrador",  # unchanged
                }
            ],
        ),
        id="apply_no_match_increments_unchanged",
    ),
    pytest.param(
        _ReclassifySpec(
            id="alt_header_channel_column",
            description="CSV with 'channel' header instead of 'Canal de Venta' → still picked up",
            csv_body=("Fecha,channel,Unidades,Total (₲)\n2026-10-01,Wholesale,2.0,50000\n"),
            seed_sales=[],
            dry_run=True,
            expect_csv_rows_total=1,
            expect_csv_rows_skipped_mostrador=0,
            expect_csv_rows_to_reclassify=1,
        ),
        id="alt_header_channel_column",
    ),
]


@pytest.mark.parametrize("row", _ROWS_RECLASSIFY, ids=lambda r: r.id)
def test_reclassify_branches(row: _ReclassifySpec, tmp_path: Path, monkeypatch) -> None:
    """Drive `reclassify` across the scenario rows above.

    Mirrors `tests/test_reclassify_sale_channels.py::TestReclassifyEndToEnd`:
    build a minimal SQLite DB, monkeypatch the reclassify script's
    `make_engine` to point at our DB, run the helper, assert the
    returned stats + the DB state.

    The repo root is added to sys.path (the script's top-level
    `sys.path.insert(0, ...)` runs at import time, but pytest's
    collection sometimes races it).
    """
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from scripts.reclassify_sale_channels import reclassify

    db_path = tmp_path / "reclassify_test.sqlite"
    csv_path = tmp_path / "VENTAS.csv"

    # Write the CSV (or leave unwritten for the missing-file row).
    if csv_path.exists():
        csv_path.unlink()
    if row.expect_status is not FileNotFoundError:
        csv_path.write_text(row.csv_body, encoding="utf-8")
    _setup_reclassify_db(db_path, row.seed_sales)

    # Monkeypatch the script's make_engine to use our temp DB.
    from sqlalchemy import create_engine

    test_engine = create_engine(f"sqlite:///{db_path}")

    import scripts.reclassify_sale_channels as rsc

    monkeypatch.setattr(rsc, "make_engine", lambda: test_engine)

    if row.expect_status is not None:
        with pytest.raises(row.expect_status):
            reclassify(csv_path, dry_run=row.dry_run)
        return

    stats = reclassify(csv_path, dry_run=row.dry_run)

    # Stats assertions
    if row.expect_csv_rows_total is not None:
        assert stats["csv_rows_total"] == row.expect_csv_rows_total, (
            f"[{row.id}] csv_rows_total: expected {row.expect_csv_rows_total}, "
            f"got {stats['csv_rows_total']}. Stats: {stats!r}"
        )
    if row.expect_csv_rows_skipped_mostrador is not None:
        assert stats["csv_rows_skipped_mostrador"] == row.expect_csv_rows_skipped_mostrador, (
            f"[{row.id}] csv_rows_skipped_mostrador: expected "
            f"{row.expect_csv_rows_skipped_mostrador}, got "
            f"{stats['csv_rows_skipped_mostrador']}. Stats: {stats!r}"
        )
    if row.expect_csv_rows_to_reclassify is not None:
        assert stats["csv_rows_to_reclassify"] == row.expect_csv_rows_to_reclassify, (
            f"[{row.id}] csv_rows_to_reclassify: expected "
            f"{row.expect_csv_rows_to_reclassify}, got "
            f"{stats['csv_rows_to_reclassify']}. Stats: {stats!r}"
        )
    if row.expect_rows_updated_min is not None:
        assert stats["rows_updated"] >= row.expect_rows_updated_min, (
            f"[{row.id}] rows_updated: expected >= {row.expect_rows_updated_min}, "
            f"got {stats['rows_updated']}. Stats: {stats!r}"
        )
    if row.expect_rows_unchanged_min is not None:
        assert stats["rows_unchanged"] >= row.expect_rows_unchanged_min, (
            f"[{row.id}] rows_unchanged: expected >= {row.expect_rows_unchanged_min}, "
            f"got {stats['rows_unchanged']}. Stats: {stats!r}"
        )
    if row.expect_rows_unchanged_max is not None:
        assert stats["rows_unchanged"] <= row.expect_rows_unchanged_max, (
            f"[{row.id}] rows_unchanged: expected <= {row.expect_rows_unchanged_max}, "
            f"got {stats['rows_unchanged']}. Stats: {stats!r}"
        )

    # Post-DB checks
    for check in row.post_db_checks:
        conn = sqlite3.connect(str(db_path))
        try:
            row_data = conn.execute(check["where_sql"]).fetchone()
        finally:
            conn.close()
        assert row_data is not None, (
            f"[{row.id}] post-DB query returned no rows: {check['where_sql']!r}"
        )
        actual_channel = row_data[0]
        assert actual_channel == check["expect_channel"], (
            f"[{row.id}] post-DB channel: expected {check['expect_channel']!r}, "
            f"got {actual_channel!r}"
        )


# ─── Row-count doc-lock ────────────────────────────────────────────────────


# Locks the row counts so a future addition/removal forces a CHANGELOG note.
assert len(_ROWS_PRINT) == 9, f"produccion_print scenarios: expected 9 rows, got {len(_ROWS_PRINT)}"
assert len(_ROWS_RECLASSIFY) == 12, (
    f"reclassify scenarios: expected 12 rows, got {len(_ROWS_RECLASSIFY)}"
)
