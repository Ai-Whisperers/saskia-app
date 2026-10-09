"""tests/test_dashboard_stock_led.py — Stock-confidence LED on /inicio.

Prelaunch roadmap 2026-09-17 item: aggregate ingredient health into a
single green/amber/red signal rendered on the HOY band.

Severity rules:
- danger: any ingredient with negative stock (data integrity issue)
- warn:   1+ ingredients below min_stock_qty (but none negative)
- success: all tracked ingredients at or above min (or none tracked)

The signal appears as a 5th <ui-kpi-card> in the HOY band with
severity + value + href=/reorder.
"""

# allow-hardcoded-dates: stock math doesn't depend on the calendar.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.rms.models import Ingredient


def _make_ing(s, name, stock, min_stock):
    ing = Ingredient(name=name, stock_qty=stock, min_stock_qty=min_stock, unit="g")
    s.add(ing)
    s.flush()
    return ing


def _make_ing_bypass_check(s, name, stock, min_stock):
    """Insert via raw SQL — bypasses the BACKLOG #3 stock_qty >= 0 trigger.

    Used to seed the negative-stock scenario for the LED danger test.
    The DB constraint makes negative stock unreachable through the ORM;
    raw SQL can still produce it (and the dashboard LED should still
    warn — that's the whole point of the test).

    Implementation: SQLite BEFORE INSERT trigger fires on raw SQL too,
    so we DROP it, insert, then recreate. Postgres uses a model-level
    CheckConstraint that can't be temporarily dropped; there we use
    ``SET CONSTRAINTS ALL DEFERRED`` (which doesn't apply to NOT NULL
    constraints on SQLite), so we accept that Postgres can't be tested
    in the danger scenario — only SQLite, where the LED logic still
    has merit for any future edge case (data corruption, manual SQL
    fix-up, rollback of a future migration).
    """
    from sqlalchemy import text as sa_text

    bind = s.get_bind()
    if bind.dialect.name == "sqlite":
        # Temporarily drop the BEFORE INSERT trigger.
        s.execute(sa_text("DROP TRIGGER IF EXISTS ingredient_stock_qty_positive_insert"))
    try:
        result = s.execute(
            sa_text(
                "INSERT INTO ingredient (name, unit, stock_qty, min_stock_qty, "
                "purchase_price_gs, role, lead_time_days, lot_required, "
                "may_contain_gluten, purchase_streak_count) "
                "VALUES (:n, 'g', :sq, :ms, NULL, NULL, 3, 0, 0, 0)"
            ),
            {"n": name, "sq": stock, "ms": min_stock},
        )
        s.flush()
        pk = result.lastrowid
        ing = s.get(Ingredient, pk)
    finally:
        if bind.dialect.name == "sqlite":
            # Recreate the trigger (idempotent thanks to IF NOT EXISTS).
            s.execute(
                sa_text(
                    "CREATE TRIGGER IF NOT EXISTS ingredient_stock_qty_positive_insert "
                    "BEFORE INSERT ON ingredient "
                    "FOR EACH ROW WHEN NEW.stock_qty < 0 "
                    "BEGIN SELECT RAISE(ABORT, 'ingredient.stock_qty must be >= 0'); END"
                )
            )
            s.commit()  # commit so the recreate is durable
    return ing


def test_led_success_when_all_above_min(client, session_factory):
    """No negative, no below-min → success / 'todo OK'."""
    with session_factory() as s:
        _make_ing(s, "harina-led-ok1", 5000, 1000)
        _make_ing(s, "azúcar-led-ok1", 3000, 500)
        s.commit()
    r = client.get("/inicio")
    assert r.status_code == 200
    assert 'severity="success"' in r.text
    assert "todo OK" in r.text


def test_led_warn_when_one_below_min(client, session_factory):
    """1 ingredient below min → warn / '1 bajo mínimo'."""
    with session_factory() as s:
        _make_ing(s, "harina-led-warn1", 500, 1000)  # below
        _make_ing(s, "azúcar-led-warn1", 3000, 500)
        s.commit()
    r = client.get("/inicio")
    assert r.status_code == 200
    assert 'severity="warn"' in r.text
    assert "1 bajo mínimo" in r.text


def test_led_danger_when_negative_stock(client, session_factory):
    """Negative stock overrides below-min → danger.

    Negative stock is normally prevented by migration 084's DB-level
    constraint. We seed via raw SQL to simulate "data corruption"
    scenarios — the LED should still warn so the operator notices.
    """
    with session_factory() as s:
        _make_ing_bypass_check(s, "harina-led-neg1", -100, 1000)
        _make_ing(s, "azúcar-led-neg1", 3000, 500)
        s.commit()
    r = client.get("/inicio")
    assert r.status_code == 200
    assert "en negativo" in r.text


def test_led_success_when_no_min_tracked(client, session_factory):
    """No ingredients with min_stock_qty set → success."""
    with session_factory() as s:
        _make_ing(s, "harina-led-nomin1", 100, 0)  # min=0 means not tracked
        s.commit()
    r = client.get("/inicio")
    assert r.status_code == 200
    assert 'severity="success"' in r.text


def test_led_card_links_to_reorder(client, session_factory):
    """The LED card must be clickable to /reorder.

    Seeded via raw SQL bypass — the danger case (negative stock) is
    normally prevented by migration 084, but the dashboard LED should
    still surface a /reorder link so the operator can act.
    """
    with session_factory() as s:
        _make_ing_bypass_check(s, "harina-led-link1", -50, 1000)
        s.commit()
    r = client.get("/inicio")
    assert r.status_code == 200
    assert 'href="/reorder"' in r.text
