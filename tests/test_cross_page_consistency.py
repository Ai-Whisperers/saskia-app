"""tests/test_cross_page_consistency.py — T8 (Phase C).

Saskia review: "Debe coincidir con los registros de las demás páginas".

Three guarantees:
1. Money renders via the m.gs / m.gs_full macros everywhere (no raw
   comma-thousands `{:,.0f}` formatting left in templates).
2. Dates render dd/mm/yyyy on user-facing pages (ISO only allowed in
   form input values).
3. Daily totals reconcile: sum of daily summaries == direct Sale-table
   total for the same seeded window.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.rms.models import Product, Sale

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "templates"


# --- 1. Money macro discipline ---


def test_no_raw_money_formatting_in_templates():
    """No '{:,.0f}' format strings outside the macros file (comma
    thousands separator is wrong for Paraguay; macros use periods)."""
    offenders: list[str] = []
    for tpl in TEMPLATES_DIR.rglob("*.html"):
        if tpl.name == "macros.html":
            continue
        content = tpl.read_text(encoding="utf-8")
        if "{:,.0f}" in content:
            offenders.append(str(tpl.relative_to(TEMPLATES_DIR)))
    assert not offenders, f"Raw money formatting found in: {offenders}"


# --- 2. Date format discipline ---


def test_no_us_date_format_in_templates():
    """No %m/%d/%Y (US order) anywhere; ISO %Y-%m-%d allowed only inside
    input value= attributes (forms), not in display markup."""
    offenders: list[str] = []
    for tpl in TEMPLATES_DIR.rglob("*.html"):
        content = tpl.read_text(encoding="utf-8")
        if "%m/%d/%Y" in content:
            offenders.append(f"{tpl.relative_to(TEMPLATES_DIR)} (US order)")
        strftime_pat = re.compile("strftime" + chr(92) + chr(40) + chr(34) + "([^" + chr(34) + "]*)" + chr(34) + chr(92) + chr(41))
        for m in strftime_pat.finditer(content):
            fmt = m.group(1)
            if "%Y-%m-%d" in fmt:
                line_start = content.rfind(chr(10), 0, m.start()) + 1
                line_end = content.find(chr(10), m.start())
                line = content[line_start:line_end if line_end != -1 else len(content)]
                if "value=" not in line:
                    offenders.append(
                        f"{tpl.relative_to(TEMPLATES_DIR)}: ISO display '{fmt}'"
                    )
    assert not offenders, f"Date-format inconsistencies: {offenders}"


# --- 3. Totals reconciliation ---


@pytest.fixture
def seeded_sales(session_factory):
    """One product, 5 days of sales (2/day at Gs. 2500). Returns product id."""
    with session_factory() as s:
        prod = Product(name="Reconcile muffin", sale_price_gs=2500)
        s.add(prod)
        s.commit()
        pid = prod.id
        now = datetime.now(timezone.utc)
        for d in range(5):
            for _ in range(2):
                s.add(Sale(
                    product_id=pid, qty=1.0,
                    sold_at=now - timedelta(days=d), unit_price_gs=2500,
                ))
        s.commit()
        return pid


def test_daily_totals_reconcile(session_factory, seeded_sales):
    """Sum of daily_summary revenue over the 5 seeded days == the direct
    Sale-table total. If report math drifts from the raw ledger, this
    catches it (Saskia: 'debe coincidir con los registros')."""
    from app.rms.accounting import daily_summary

    grand = 0
    for d in range(5):
        day = datetime.now(timezone.utc) - timedelta(days=d)
        summ = daily_summary(session_factory(), day=day)
        grand += summ.revenue_gross_gs
    expected = 5 * 2 * 2500
    assert grand == expected, f"daily summaries sum to {grand}, expected {expected}"

    with session_factory() as s:
        total = s.execute(select(func.sum(Sale.unit_price_gs * Sale.qty))).scalar()
        assert total == grand, f"Sale table total {total} != daily summary total {grand}"
