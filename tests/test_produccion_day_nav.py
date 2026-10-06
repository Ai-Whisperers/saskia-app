"""Tests for PRODUCCION-V3 Phase 1 — day navigation.

The audit (H2, M2, M7, M18, M20) flagged that /produccion had no
intuitive way to jump between days. We add a sticky day-nav control
with prev / date-picker / today / next + keyboard shortcuts.

The nav renders even on an empty plan (it sits ABOVE the plan table,
not inside it), so we do NOT need to seed plan rows for these tests
— just verify the nav itself is well-formed.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest


def _day_nav_in_html(body: str) -> str | None:
    """Return the inner HTML of the <nav class="day-nav" ...> block,
    or None if not found. Used by all 4 tests below."""
    m = re.search(
        r'<nav[^>]*class="[^"]*\bday-nav\b[^"]*"[^>]*data-day-nav[^>]*>(.*?)</nav>',
        body,
        re.DOTALL,
    )
    return m.group(0) if m else None


def test_day_nav_renders_prev_today_next(authed_client, session_factory):
    """GET /produccion?for_date=2026-10-05 body contains the day-nav HTML."""
    today = datetime.now(UTC).date().isoformat()
    r = authed_client.get(f"/produccion?for_date={today}")
    assert r.status_code == 200, r.text[:200]
    nav = _day_nav_in_html(r.text)
    assert nav is not None, "day-nav <nav data-day-nav> must be present in /produccion body"
    # Must contain a "Hoy" button (Spanish for today)
    assert "Hoy" in nav, f'day-nav must include a "Hoy" button; got: {nav[:300]}'
    # Must contain prev/next arrows
    assert "‹" in nav and "›" in nav, "day-nav must include ‹ (prev) and › (next) arrows"
    # Must contain a date input
    assert re.search(r'<input[^>]*type="date"', nav), (
        "day-nav must include an <input type='date'> for the date picker"
    )


def test_prev_link_computes_yesterday(authed_client, session_factory):
    """The prev link in the day-nav points to for_date=today-1."""
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}")
    nav = _day_nav_in_html(r.text)
    assert nav is not None
    # Find the prev link (it has the "Día anterior" aria-label OR the ‹ glyph)
    m = re.search(
        r'<a[^>]*href="\?for_date=(\d{4}-\d{2}-\d{2})[^"]*"[^>]*aria-label="[^"]*anterior[^"]*"',
        nav,
    ) or re.search(
        r'href="\?for_date=(\d{4}-\d{2}-\d{2})[^"]*"[^>]*>‹',
        nav,
    )
    assert m, f"prev link not found in day-nav; nav was: {nav[:500]}"
    assert m.group(1) == yesterday.isoformat(), (
        f"prev link must point to {yesterday.isoformat()}; got {m.group(1)}"
    )


def test_today_link_always_returns_today(authed_client, session_factory):
    """The 'Hoy' button in the day-nav always points to for_date=today,
    regardless of the current for_date query param."""
    today = datetime.now(UTC).date()
    # Use a date that's NOT today so we can verify the link differs
    other = today - timedelta(days=3)
    r = authed_client.get(f"/produccion?for_date={other.isoformat()}")
    nav = _day_nav_in_html(r.text)
    assert nav is not None
    # Find the "Hoy" button — it should be an <a> with text Hoy
    m = re.search(
        r'<a[^>]*href="\?for_date=(\d{4}-\d{2}-\d{2})[^"]*"[^>]*>\s*Hoy\s*</a>',
        nav,
    )
    assert m, f"'Hoy' link not found in day-nav; nav was: {nav[:500]}"
    assert m.group(1) == today.isoformat(), (
        f"'Hoy' link must always be {today.isoformat()}; got {m.group(1)}"
    )


def test_date_picker_input_value_matches_for_date(authed_client, session_factory):
    """The <input type='date'> in the day-nav has value={{ for_date }}."""
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}")
    nav = _day_nav_in_html(r.text)
    assert nav is not None
    m = re.search(
        r'<input[^>]*type="date"[^>]*name="for_date"[^>]*value="(\d{4}-\d{2}-\d{2})"',
        nav,
    ) or re.search(
        r'<input[^>]*name="for_date"[^>]*value="(\d{4}-\d{2}-\d{2})"[^>]*type="date"',
        nav,
    )
    assert m, f"date input with name='for_date' and value not found; nav was: {nav[:500]}"
    assert m.group(1) == today.isoformat()
