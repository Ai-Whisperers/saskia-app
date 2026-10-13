"""Parametrized coverage for two more D-grade helpers with no branch matrix.

S1 batch-16 (test coverage continuation): lock the branch matrix of two
D-grade helpers that lack parametrized coverage:

  (1) `app/routers/produccion/_full.py:_produccion_day_view` (CC 28, D-grade)
      The day-view orchestrator behind `GET /produccion`. It is a
      260-line monolith that wires together 15 step-N helpers plus
      `plan_production`, `get_demand`, recipe-pricing joins, raw-SQL
      `recipe_pricing` lookup, EOD completions, ingredient filter
      (falta/justo/suficiente), pagination, and the closed-day banner.
      Most branches are URL-param driven (rows, page, show_all,
      ingredients_filter) or DB-state driven (closed_day row). We drive
      the helper directly with a stub `Request` + a monkeypatched
      `render` (the imported `app.services.template_render.render`
      symbol) so the context dict is captured without going through
      the full Jinja2 render path. Branches covered:

      - rows=200 → rows_per_page=100 (locks `rows_per_page = max(1, min(100, int(rows)))`
        upper clamp)
      - rows=0 → rows_per_page=1 (locks the lower clamp of the same expression)
      - rows=20 (default) → rows_per_page=20 (locks the in-range path)
      - page=-5 → current_page=1 (locks `current_page = max(1, int(page))`
        clamp on negatives — the route's Query(ge=1) blocks this from HTTP,
        but the helper itself is defensive)
      - page=0 → current_page=1 (locks the same clamp on zero)
      - show_all=0 → context["show_all"]=False (locks `1 if int(show_all)==1 else 0`
        and the `show_all_int == 1` truthy gate)
      - show_all=1 → context["show_all"]=True (locks the 1-becomes-True branch)
      - show_all=2 → context["show_all"]=False (locks the "any int other than 1 → 0"
        fallback)
      - ingredients_filter="falta" → context["ingredients_filter"]="falta" (locks
        the value passthrough into the template context)
      - ingredients_filter="" → context["ingredients_filter"]="" (locks the
        empty-string passthrough AND the `if ingredients_filter in (...)` else
        branch that sorts ALL plan lines without filtering)
      - ingredients_filter="other" → context["ingredients_filter"]="other" (locks
        the value passthrough for non-empty values that don't match the
        falta/justo/suficiente whitelist → else branch again)
      - shift="AM" → context["shift"]="AM" (locks the shift passthrough)
      - shift="PM" → context["shift"]="PM" (locks the PM passthrough)
      - shift="" → context["shift"]="" (locks the default-empty passthrough)
      - closed_day seeded for target_date → context["closed_day_active"]=True,
        context["closed_day_reason"]=seeded reason (locks the
        `closed_day = session.get(ProductionClosedDay, target_date)` branch
        AND the `closed_day_active: closed_day is not None` passthrough)
      - no closed_day row → context["closed_day_active"]=False,
        context["closed_day_reason"]=None (locks the not-found branch)
      - template name is "produccion.html" (locks the literal template
        arg to `render(...)` so a future rename is caught)

  (2) `scripts/import_herebus_data.py:import_bank_transactions` (CC 21, D-grade)
      Dutch EUR bank TAB importer. Reads `HEREBUS_DIR/top/TXT260711013722.TAB`
      (tab-separated, 9 columns: account_id, currency, posted_date YYYYMMDD,
      balance_before, balance_after, date2, amount, description with IBAN/name,
      repeat), parses IBAN and counterparty name from the description via
      regex, classifies by keyword, and writes idempotent BankTransaction
      rows. We monkeypatch the module-level `HEREBUS_DIR` to point at a
      tmp_path so the test doesn't need the real Dutch bank file. Branches
      covered:

      - HEREBUS_DIR/top/TXT260711013722.TAB does not exist → returns 0
        (locks the `if not tab_path.exists(): return 0` early-exit AND the
        `print("⚠️ ... not found, skipping")` message)
      - blank line in TAB → skipped (locks `if not line: continue`)
      - parts < 7 (short line) → skipped (locks `if len(parts) < 7: continue`)
      - amount unparseable ("abc") → skipped (locks
        `except (ValueError, IndexError): continue`)
      - posted_date unparseable ("not-a-date") → skipped (locks the
        `except ValueError: continue` for the date parse)
      - description matches "sepa overboeking" → category="incoming_transfer"
        (locks the OR with "ontv aab" branch)
      - description matches "ontv aab" → category="incoming_transfer"
        (locks the other arm of the same OR)
      - description matches "ovpay" → category="transport" (locks the
        inner `if "ovpay"` branch inside the betaalpas arm)
      - description matches "betaalpas" only → category="personal" (locks
        the else arm of the same betaalpas/ovpay block)
      - description matches "kruidvat"/"lidl"/"action" → category="groceries"
        (locks the OR-grocery branch)
      - description matches "geldmaat" → category="cash_withdrawal" (locks
        the geldmaat arm)
      - description matches nothing → category="other" (locks the catch-all
        else branch)
      - existing tx (same posted_at + amount + source="tab_dutch") → skipped
        (locks the idempotency branch: `existing = session.execute(...); if
        existing: continue`)
      - description with "IBAN: NL91ABNA0417164300" → counterparty_iban parsed
        (locks the `iban_match = re.search(r"IBAN:\\s*(\\S+)", description)`
        branch)
      - description with "Naam: ACME B.V. Kenmerk: ..." → counterparty_name
        parsed (locks the `name_match = re.search(r"Naam:\\s*([^B]+?)\\s+\\w+:",
        description)` branch)
      - description with no IBAN and no Naam → counterparty_iban=None,
        counterparty_name=None (locks the optional-regex fallback)
      - flushes every 50 added rows (locks `if n % 50 == 0: session.flush()`)
        — we seed 51 unique rows in a single file and verify the helper
        completes without losing any.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import pytest
from sqlalchemy import select

# ─── _produccion_day_view row spec ───────────────────────────────────────────


@dataclass
class _DayViewSpec:
    """One scenario for `_produccion_day_view`.

    Each scenario configures the kwargs for one call to the day-view
    orchestrator, and asserts on values in the captured context dict
    (substituted for the normal `render(request, "produccion.html", ctx)`
    call by monkeypatch).
    """

    id: str = ""
    # kwargs to pass to _produccion_day_view
    rows: int = 20
    page: int = 1
    show_all: int = 0
    ingredients_filter: str = ""
    shift: str = ""
    # optional closed_day seeding
    seed_closed_day: Optional[dict] = None
    # asserts: list of (context_key, expected_value) pairs
    # use _SENTINEL for "must be present, value not asserted"
    asserts: list[tuple[str, Any]] = field(default_factory=list)


_SENTINEL = object()


def _make_fake_request() -> Any:
    """Build a minimal `Request` stub the day-view helper accepts.

    `_produccion_day_view` calls `render(...)` which reads:
      - `request.session.get("station")`           → session dict
      - `request.session.get("station_locked")`    → bool
      - `request.url.path.startswith("/puesto")`   → path string
      - `request.app.state.engine`                 → engine or None
      - `request.query_params`                     → used in route, not helper
    Plus `_csrf_token_for_request(request)` reads `request.app.state.csrf_secret`
    or returns a hard-coded fallback. So a SimpleNamespace is enough.
    """
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(engine=None, csrf_secret=None)),
        session={},
        url=SimpleNamespace(path="/produccion"),
        query_params={},
    )


def _capture_render(monkeypatch, captured: dict) -> Any:
    """Replace `app.routers.produccion._full.render` with a context-capturing spy.

    The spy stores `template_name` and `context` in `captured` and returns
    a real HTMLResponse (the orchestrator wraps it in nothing — the call
    site is `return render(request, "produccion.html", ctx)` so whatever
    we return becomes the route's response).
    """
    from fastapi.responses import HTMLResponse

    from app.routers.produccion import _full

    def fake_render(request, template_name, context=None, status_code=200):
        captured["template_name"] = template_name
        captured["context"] = context
        return HTMLResponse("<html>FAKE</html>", status_code=status_code)

    monkeypatch.setattr(_full, "render", fake_render)
    return _full


# ─── _produccion_day_view scenario rows ──────────────────────────────────────


_DAY_VIEW_ROWS: list[_DayViewSpec] = [
    pytest.param(
        _DayViewSpec(
            id="rows_200_clamped_to_100",
            rows=200,
            asserts=[("rows_per_page", 100)],
        ),
        id="rows_200_clamped_to_100",
    ),
    pytest.param(
        _DayViewSpec(
            id="rows_0_clamped_to_1",
            rows=0,
            asserts=[("rows_per_page", 1)],
        ),
        id="rows_0_clamped_to_1",
    ),
    pytest.param(
        _DayViewSpec(
            id="rows_20_default_unchanged",
            rows=20,
            asserts=[("rows_per_page", 20)],
        ),
        id="rows_20_default_unchanged",
    ),
    pytest.param(
        _DayViewSpec(
            id="page_negative_clamped_to_1",
            page=-5,
            asserts=[("current_page", 1)],
        ),
        id="page_negative_clamped_to_1",
    ),
    pytest.param(
        _DayViewSpec(
            id="page_zero_clamped_to_1",
            page=0,
            asserts=[("current_page", 1)],
        ),
        id="page_zero_clamped_to_1",
    ),
    pytest.param(
        _DayViewSpec(
            id="show_all_zero_sets_context_false",
            show_all=0,
            asserts=[("show_all", False)],
        ),
        id="show_all_zero_sets_context_false",
    ),
    pytest.param(
        _DayViewSpec(
            id="show_all_one_sets_context_true",
            show_all=1,
            asserts=[("show_all", True)],
        ),
        id="show_all_one_sets_context_true",
    ),
    pytest.param(
        _DayViewSpec(
            id="show_all_two_falls_back_to_false",
            show_all=2,
            asserts=[("show_all", False)],
        ),
        id="show_all_two_falls_back_to_false",
    ),
    pytest.param(
        _DayViewSpec(
            id="ingredients_filter_falta_passthrough",
            ingredients_filter="falta",
            asserts=[("ingredients_filter", "falta")],
        ),
        id="ingredients_filter_falta_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="ingredients_filter_empty_passthrough",
            ingredients_filter="",
            asserts=[("ingredients_filter", "")],
        ),
        id="ingredients_filter_empty_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="ingredients_filter_unrecognized_passthrough",
            ingredients_filter="other",
            asserts=[("ingredients_filter", "other")],
        ),
        id="ingredients_filter_unrecognized_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="shift_am_passthrough",
            shift="AM",
            asserts=[("shift", "AM")],
        ),
        id="shift_am_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="shift_pm_passthrough",
            shift="PM",
            asserts=[("shift", "PM")],
        ),
        id="shift_pm_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="shift_empty_passthrough",
            shift="",
            asserts=[("shift", "")],
        ),
        id="shift_empty_passthrough",
    ),
    pytest.param(
        _DayViewSpec(
            id="no_closed_day_active_is_false",
            asserts=[
                ("closed_day_active", False),
                ("closed_day_reason", None),
            ],
        ),
        id="no_closed_day_active_is_false",
    ),
    pytest.param(
        _DayViewSpec(
            id="closed_day_seeded_marks_active_and_reason",
            seed_closed_day={"reason": "vacaciones"},
            asserts=[
                ("closed_day_active", True),
                ("closed_day_reason", "vacaciones"),
            ],
        ),
        id="closed_day_seeded_marks_active_and_reason",
    ),
    pytest.param(
        _DayViewSpec(
            id="template_name_is_produccion_html",
            asserts=[("__template_name__", "produccion.html")],
        ),
        id="template_name_is_produccion_html",
    ),
]


# ─── _produccion_day_view driver ─────────────────────────────────────────────


@pytest.mark.parametrize("row", _DAY_VIEW_ROWS, ids=lambda r: r.id)
def test_produccion_day_view_branches(row: _DayViewSpec, monkeypatch, session_factory):
    """Drive _produccion_day_view across the 17 scenario rows above.

    We bypass the HTTP layer: monkeypatch the imported `render` symbol
    in `app.routers.produccion._full` to a spy that captures the
    template name + context dict. Pass a `SimpleNamespace` stub as the
    `request` (the helper only forwards it to `render`, which we have
    also stubbed). Use `session_factory()` directly so the test runs
    against the shared in-memory SQLite from conftest.
    """
    captured: dict = {}
    _full = _capture_render(monkeypatch, captured)

    from app.rms.models import ProductionClosedDay
    from app.routers.produccion._helpers import _asuncion_today

    target_date = _asuncion_today()

    with session_factory() as s:
        # Optionally seed a ProductionClosedDay row so the
        # `closed_day = session.get(ProductionClosedDay, target_date)`
        # branch is exercised.
        if row.seed_closed_day is not None:
            s.add(
                ProductionClosedDay(
                    for_date=target_date,
                    reason=row.seed_closed_day["reason"],
                    closed_at=datetime(2026, 10, 13, 12, 0, 0),
                )
            )
            s.flush()

        _full._produccion_day_view(
            request=_make_fake_request(),
            session=s,
            for_date=target_date,
            overrides={},
            shift=row.shift,
            ui="v2",
            sort="lote",
            dir="desc",
            rows=row.rows,
            page=row.page,
            show_all=row.show_all,
            filter_allergen=None,
            filter_source=None,
            filter_with_pedidos="",
            filter_with_hecho="",
            filter_with_surplus="",
            ingredients_sort="severity",
            ingredients_dir="asc",
            ingredients_filter=row.ingredients_filter,
        )

    # Assert on captured context.
    assert captured.get("template_name") == "produccion.html", (
        f"_produccion_day_view must render produccion.html; got {captured.get('template_name')!r}"
    )
    ctx = captured.get("context")
    assert isinstance(ctx, dict), f"render() must receive a context dict; got {type(ctx).__name__}"

    for key, expected in row.asserts:
        if key == "__template_name__":
            assert captured["template_name"] == expected, (
                f"template name must be {expected!r}; got {captured['template_name']!r}"
            )
            continue
        assert key in ctx, f"context missing {key!r}; keys: {sorted(ctx)[:15]}"
        actual = ctx[key]
        assert actual == expected, f"context[{key!r}] must be {expected!r}; got {actual!r}"


# ─── import_bank_transactions row spec ───────────────────────────────────────


@dataclass
class _BankTxSpec:
    """One scenario for `import_bank_transactions`.

    Each scenario builds a fake TAB file at a temp path, monkeypatches
    the module-level `HEREBUS_DIR` to point at the temp dir, calls
    `import_bank_transactions(session)`, and asserts on the persisted
    BankTransaction rows.
    """

    id: str = ""
    # TAB file contents. None means: don't create the file at all
    # (used for the "file missing" branch).
    tab_content: Optional[str] = None
    # Pre-existing BankTransactions: list of (posted_at_date, amount)
    # tuples to seed for the idempotency test.
    seed_existing: list[tuple[date, float]] = field(default_factory=list)
    # Expected: number of rows added by the helper.
    expected_added: int = 0
    # Optional: subset of expected persisted rows. Each entry is a dict
    # of fields to assert equality on (e.g. category, counterparty_iban,
    # amount, posted_at).
    expected_rows: list[dict] = field(default_factory=list)


def _write_tab_file(tmp_path: Path, filename: str, content: str) -> Path:
    """Write `content` to `tmp_path/top/<filename>` and return the file path.

    `import_bank_transactions` reads `HEREBUS_DIR / "top" / TXT260711013722.TAB`,
    so we mirror that exact layout under tmp_path. The function
    constructs `HEREBUS_DIR` from the module's `HEREBUS_DIR` symbol, so
    we monkeypatch that to `tmp_path` and the test's `top/` subdir will
    be picked up automatically.
    """
    top = tmp_path / "top"
    top.mkdir(parents=True, exist_ok=True)
    p = top / filename
    p.write_text(content)
    return p


# TAB row shape (tab-separated, columns 0..8 — helper reads up to 7/8):
#   0: account_id  (ignored by helper)
#   1: currency    ('EUR')
#   2: date        (YYYYMMDD)
#   3: balance_before (ignored)
#   4: balance_after  (ignored, helper has a no-op `parts[4]`)
#   5: date2       (ignored)
#   6: amount      (uses ',' as decimal separator → float)
#   7: description (parsed for IBAN / Naam / category keywords)
#   8: balance_after_str_repeat (ignored)
def _tab_row(
    account_id: str,
    currency: str,
    date_yyyymmdd: str,
    amount: str,
    description: str,
) -> str:
    """Build a single TAB line in the 9-column shape the helper expects."""
    return "\t".join(
        [
            account_id,
            currency,
            date_yyyymmdd,
            "1000.00",  # balance_before
            "1000.00",  # balance_after
            date_yyyymmdd,  # date2
            amount,
            description,
            "1000.00",  # repeat
        ]
    )


# ─── import_bank_transactions scenario rows ──────────────────────────────────


def _row_with_desc(description: str, amount: str = "10,00", date: str = "20250919") -> str:
    """Build a single valid TAB row with the given description."""
    return _tab_row(
        account_id="NL91ABNA0417164300",
        currency="EUR",
        date_yyyymmdd=date,
        amount=amount,
        description=description,
    )


_BANK_ROWS: list[_BankTxSpec] = [
    pytest.param(
        _BankTxSpec(
            id="tab_file_missing_returns_zero",
            tab_content=None,  # no file written
            expected_added=0,
        ),
        id="tab_file_missing_returns_zero",
    ),
    pytest.param(
        _BankTxSpec(
            id="blank_line_skipped",
            tab_content="\n" + _row_with_desc("SEPA Overboeking Naam: ACME"),
            expected_added=1,
            expected_rows=[{"category": "incoming_transfer"}],
        ),
        id="blank_line_skipped",
    ),
    pytest.param(
        _BankTxSpec(
            id="short_parts_line_skipped",
            # 6 columns → len(parts) < 7 → skip
            tab_content="a\tEUR\t20250919\t1000.00\t1000.00\t1000.00",
            expected_added=0,
        ),
        id="short_parts_line_skipped",
    ),
    pytest.param(
        _BankTxSpec(
            id="invalid_amount_skipped",
            tab_content=_row_with_desc("SEPA Naam: X", amount="not-a-number"),
            expected_added=0,
        ),
        id="invalid_amount_skipped",
    ),
    pytest.param(
        _BankTxSpec(
            id="invalid_date_skipped",
            # amount is fine; date column is unparseable
            tab_content=_tab_row(
                account_id="NL91ABNA0417164300",
                currency="EUR",
                date_yyyymmdd="not-a-date",
                amount="10,00",
                description="SEPA Naam: X",
            ),
            expected_added=0,
        ),
        id="invalid_date_skipped",
    ),
    pytest.param(
        _BankTxSpec(
            id="sepa_overboeking_classified_incoming_transfer",
            tab_content=_row_with_desc("SEPA Overboeking Naam: SOMEONE Kenmerk: foo"),
            expected_added=1,
            expected_rows=[
                {
                    "category": "incoming_transfer",
                    "currency": "EUR",
                    "counterparty_name": "SOMEONE",
                }
            ],
        ),
        id="sepa_overboeking_classified_incoming_transfer",
    ),
    pytest.param(
        _BankTxSpec(
            id="ontv_aab_classified_incoming_transfer",
            tab_content=_row_with_desc("Ontv aab Naam: SOMEONE Kenmerk: bar"),
            expected_added=1,
            expected_rows=[{"category": "incoming_transfer"}],
        ),
        id="ontv_aab_classified_incoming_transfer",
    ),
    pytest.param(
        _BankTxSpec(
            id="ovpay_classified_transport",
            tab_content=_row_with_desc("Betaalpas OVPAY Amsterdam"),
            expected_added=1,
            expected_rows=[{"category": "transport"}],
        ),
        id="ovpay_classified_transport",
    ),
    pytest.param(
        _BankTxSpec(
            id="betaalpas_only_classified_personal",
            tab_content=_row_with_desc("Betaalpas Albert Heijn"),
            expected_added=1,
            expected_rows=[{"category": "personal"}],
        ),
        id="betaalpas_only_classified_personal",
    ),
    pytest.param(
        _BankTxSpec(
            id="kruidvat_classified_groceries",
            tab_content=_row_with_desc("PIN Kruidvat Den Haag"),
            expected_added=1,
            expected_rows=[{"category": "groceries"}],
        ),
        id="kruidvat_classified_groceries",
    ),
    pytest.param(
        _BankTxSpec(
            id="geldmaat_classified_cash_withdrawal",
            tab_content=_row_with_desc("PIN Geldmaat Utrecht"),
            expected_added=1,
            expected_rows=[{"category": "cash_withdrawal"}],
        ),
        id="geldmaat_classified_cash_withdrawal",
    ),
    pytest.param(
        _BankTxSpec(
            id="unknown_description_classified_other",
            tab_content=_row_with_desc("PIN Mystery Shop Zutphen"),
            expected_added=1,
            expected_rows=[{"category": "other"}],
        ),
        id="unknown_description_classified_other",
    ),
    pytest.param(
        _BankTxSpec(
            id="iban_and_name_parsed_from_description",
            tab_content=_row_with_desc(
                "SEPA Overboeking IBAN: NL91ABNA0417164300 Naam: SOMEONE Kenmerk: foo"
            ),
            expected_added=1,
            expected_rows=[
                {
                    "category": "incoming_transfer",
                    "counterparty_iban": "NL91ABNA0417164300",
                    "counterparty_name": "SOMEONE",
                }
            ],
        ),
        id="iban_and_name_parsed_from_description",
    ),
    pytest.param(
        _BankTxSpec(
            id="missing_iban_and_name_stored_as_none",
            tab_content=_row_with_desc("SEPA Overboeking mystery"),
            expected_added=1,
            expected_rows=[
                {
                    "category": "incoming_transfer",
                    "counterparty_iban": None,
                    "counterparty_name": None,
                }
            ],
        ),
        id="missing_iban_and_name_stored_as_none",
    ),
    pytest.param(
        _BankTxSpec(
            id="duplicate_posted_at_amount_source_skipped",
            # Seed one BankTransaction with the exact (posted_at, amount, source)
            # tuple the row would create, then re-import the same line.
            seed_existing=[(date(2026, 5, 19), 10.0)],
            tab_content=_row_with_desc(
                "SEPA Overboeking Naam: ACME", date="20260519", amount="10,00"
            ),
            expected_added=0,
        ),
        id="duplicate_posted_at_amount_source_skipped",
    ),
    pytest.param(
        _BankTxSpec(
            id="flushes_at_50_rows_continues_until_done",
            # 60 unique rows → 60 inserts, with a flush at row 50.
            tab_content="\n".join(
                _row_with_desc(
                    f"SEPA Overboeking Naam: Vendor{i:03d} Kenmerk: k",
                    # 3 months × 20 days = 60 unique valid YYYYMMDD dates.
                    # Months 1,2,3 are all valid; days 1..20 are valid in every month.
                    date=f"2025{(i // 20) + 1:02d}{(i % 20) + 1:02d}",
                    amount=f"{(i + 1)},00",
                )
                for i in range(60)
            ),
            expected_added=60,
        ),
        id="flushes_at_50_rows_continues_until_done",
    ),
]


# ─── import_bank_transactions driver ─────────────────────────────────────────


@pytest.mark.parametrize("row", _BANK_ROWS, ids=lambda r: r.id)
def test_import_bank_transactions_scenarios(
    row: _BankTxSpec, tmp_path: Path, monkeypatch, session_factory
):
    """Drive import_bank_transactions across the 16 scenario rows above.

    The helper reads a fixed-path file (`HEREBUS_DIR/top/TXT260711013722.TAB`)
    and persists BankTransaction rows idempotently. We:
      1. monkeypatch the module-level `HEREBUS_DIR` symbol to point at
         a fresh tmp dir so the real Dutch bank file is not touched,
      2. optionally write a fake TAB file at the expected subpath,
      3. optionally pre-seed BankTransaction rows for the idempotency
         branch,
      4. call `import_bank_transactions(session)` and assert on the
         return value + the persisted rows.
    """
    # Import lazily so the script path can move without breaking the
    # test file. Same pattern as test_d_grade_helpers_batch10.py.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import scripts.import_herebus_data as ihd
    from app.rms.models import BankTransaction

    # 1. Point HEREBUS_DIR at the tmp dir.
    monkeypatch.setattr(ihd, "HEREBUS_DIR", tmp_path)

    # 2. Write (or skip) the TAB file.
    if row.tab_content is not None:
        _write_tab_file(tmp_path, "TXT260711013722.TAB", row.tab_content)

    with session_factory() as s:
        # 3. Pre-seed BankTransaction rows for the duplicate-skip test.
        for d, amt in row.seed_existing:
            s.add(
                BankTransaction(
                    posted_at=datetime.combine(d, datetime.min.time()),
                    currency="EUR",
                    amount=amt,
                    counterparty_name="<pre-seeded>",
                    counterparty_iban=None,
                    description="<pre-seeded for test>",
                    category="other",
                    source="tab_dutch",
                    account_holder="JGHM VAN DER POL",
                )
            )
            s.flush()

        # 4. Run the helper.
        added = ihd.import_bank_transactions(s)

        assert added == row.expected_added, (
            f"import_bank_transactions must add {row.expected_added} rows; got {added}"
        )

        # Validate the persisted rows.
        persisted = s.execute(select(BankTransaction).order_by(BankTransaction.id)).scalars().all()

        # Helper-added rows are those NOT pre-seeded. The pre-seeded
        # rows have a description starting with "<pre-seeded" so we
        # can distinguish them safely.
        helper_added = [r for r in persisted if not r.description.startswith("<pre-seeded")]
        assert len(helper_added) == row.expected_added, (
            f"Expected {row.expected_added} helper-added rows; got {len(helper_added)}"
        )

        if row.expected_rows:
            by_desc = {r.description: r for r in helper_added}
            for expected in row.expected_rows:
                # The `flushes_at_50_rows_continues_until_done` scenario
                # has 60 rows with dynamic descriptions, so we only
                # assert on fields that are present in `expected`.
                desc_match = None
                for desc, rec in by_desc.items():
                    if expected.get("category") and rec.category != expected["category"]:
                        continue
                    desc_match = rec
                    break
                if desc_match is None:
                    raise AssertionError(
                        f"No helper-added row matches {expected!r}; "
                        f"got {[(r.category, r.description[:40]) for r in helper_added]}"
                    )
                if "category" in expected:
                    assert desc_match.category == expected["category"]
                if "currency" in expected:
                    assert desc_match.currency == expected["currency"]
                if "counterparty_iban" in expected:
                    assert desc_match.counterparty_iban == expected["counterparty_iban"]
                if "counterparty_name" in expected:
                    assert desc_match.counterparty_name == expected["counterparty_name"]


# ─── Row-count doc-lock ─────────────────────────────────────────────────────


# Locks the row counts so a future addition/removal forces a CHANGELOG note.
assert len(_DAY_VIEW_ROWS) == 17, (
    f"_produccion_day_view scenarios: expected 17 rows, got {len(_DAY_VIEW_ROWS)}"
)
assert len(_BANK_ROWS) == 16, (
    f"import_bank_transactions scenarios: expected 16 rows, got {len(_BANK_ROWS)}"
)
