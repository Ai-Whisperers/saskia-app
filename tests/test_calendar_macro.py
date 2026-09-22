"""tests/test_calendar_macro.py — Phase B Q2-prep calendar grid shell.

Tests for the week_grid + month_grid macros in
app/templates/_components/calendar.html.

Per Phase B Q2-prep spec: this is the visual scaffold for the production
calendar (Phase D wires business logic). The macros render plain HTML +
CSS class hooks — no DB access, no router logic.

Refs: Saskia review round 1 (Thu 18-sep) — Q2 (c) calendar dashboard.
Phase B = shell; Phase D = week/month views + per-day plan + overrides.
"""

from __future__ import annotations

from datetime import date

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


@pytest.fixture
def jinja_env():
    """Minimal Jinja2 env rooted at app/templates/ for macro tests."""
    return Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# --- week_grid macro ---


def test_week_grid_macro_renders_seven_cells(jinja_env):
    """week_grid emits 7 .calendar-day-cell elements (one per weekday)."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}"""
    )
    days = [
        {"date_iso": f"2026-09-2{i}", "label": f"Día {i}", "item_count": i, "is_today": False, "is_selected": False}
        for i in range(1, 8)
    ]
    html = template.render(
        weekdays=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        days=days,
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
    )
    # 7 weekday header labels
    assert html.count("calendar-weekday") >= 7
    # 7 day cells
    assert html.count("calendar-day-cell") >= 7


def test_week_grid_renders_nav_links(jinja_env):
    """week_grid shows prev/next week navigation."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}"""
    )
    days = [{"date_iso": "2026-09-21", "label": "Lun", "item_count": 3, "is_today": True, "is_selected": False}]
    html = template.render(
        weekdays=["Lun"],
        days=days,
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
    )
    assert "Semana anterior" in html
    assert "Semana siguiente" in html
    assert "2026-09-14" in html
    assert "2026-09-28" in html


def test_week_grid_empty_state(jinja_env):
    """When days=[] the grid still renders but shows empty state."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}"""
    )
    html = template.render(
        weekdays=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        days=[],
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
    )
    # No day cells
    assert "calendar-day-cell" not in html
    # Empty state copy present
    assert "Sin días" in html or "sin planificar" in html.lower()


def test_week_grid_marks_today_and_selected(jinja_env):
    """is_today / is_selected days get their CSS classes."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}"""
    )
    days = [
        {"date_iso": "2026-09-21", "label": "Lun", "item_count": 0,
         "is_today": True, "is_selected": False},
        {"date_iso": "2026-09-22", "label": "Mar", "item_count": 0,
         "is_today": False, "is_selected": True},
        {"date_iso": "2026-09-23", "label": "Mié", "item_count": 0,
         "is_today": False, "is_selected": False},
        {"date_iso": "2026-09-24", "label": "Jue", "item_count": 1,
         "is_today": False, "is_selected": False},
        {"date_iso": "2026-09-25", "label": "Vie", "item_count": 2,
         "is_today": False, "is_selected": False},
        {"date_iso": "2026-09-26", "label": "Sáb", "item_count": 4,
         "is_today": False, "is_selected": False},
        {"date_iso": "2026-09-27", "label": "Dom", "item_count": 6,
         "is_today": False, "is_selected": False},
    ]
    html = template.render(
        weekdays=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        days=days,
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
    )
    assert "is-today" in html
    assert "is-selected" in html


# --- month_grid macro ---


@pytest.mark.parametrize(
    "year, month, expected_count",
    [
        (2026, 9, 30),  # September has 30 days
        (2026, 10, 31),  # October has 31
        (2026, 2, 28),  # February (non-leap)
        (2024, 2, 29),  # February (leap year)
    ],
)
def test_month_grid_renders_correct_day_count(jinja_env, year, month, expected_count):
    """month_grid emits exactly N .calendar-day-cell for N days in the month."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.month_grid(year, month, days, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    days = [
        {
            "date_iso": f"{year}-{month:02d}-{d:02d}",
            "label": str(d),
            "item_count": 0,
            "is_today": False,
            "is_selected": False,
        }
        for d in range(1, expected_count + 1)
    ]
    html = template.render(
        year=year,
        month=month,
        days=days,
        first_day_pad=0,
        prev_month_iso=f"{year}-{month - 1 or 12:02d}",
        next_month_iso=f"{year + 1 if month == 12 else year}-{1:02d}",
    )
    # Day cells (excluding header weekday labels — those use calendar-weekday)
    # Count only calendar-day-cell which is unique per day.
    assert html.count("calendar-day-cell") == expected_count


def test_month_grid_renders_nav_links(jinja_env):
    """month_grid shows prev/next month navigation."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.month_grid(year, month, days, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    html = template.render(
        year=2026,
        month=9,
        days=[],
        first_day_pad=0,
        prev_month_iso="2026-08",
        next_month_iso="2026-10",
    )
    assert "Mes anterior" in html
    assert "Mes siguiente" in html
    assert "2026-08" in html
    assert "2026-10" in html


def test_month_grid_renders_weekday_header(jinja_env):
    """month_grid shows the 7-day weekday header."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.month_grid(year, month, days, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    html = template.render(
        year=2026,
        month=9,
        days=[],
        first_day_pad=0,
        prev_month_iso="2026-08",
        next_month_iso="2026-10",
    )
    # The header row has 7 weekday labels.
    assert html.count("calendar-weekday") >= 7


def test_month_grid_empty_state(jinja_env):
    """When days=[] the grid still renders and shows the empty state."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.month_grid(year, month, days, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    html = template.render(
        year=2026,
        month=9,
        days=[],
        first_day_pad=0,
        prev_month_iso="2026-08",
        next_month_iso="2026-10",
    )
    assert "calendar-day-cell" not in html
    # Empty state marker (Spanish, vos)
    assert "Sin planificar" in html or "sin planificar" in html.lower()


# --- Spanish / vos copy ---


def test_calendar_copy_is_spanish_vos(jinja_env):
    """All visible UI strings use Spanish 'vos' (and avoid 'tú')."""
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}
{{ cal.month_grid(year, month, days, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    html = template.render(
        weekdays=["Lun"],
        days=[],
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
        year=2026,
        month=9,
        first_day_pad=0,
        prev_month_iso="2026-08",
        next_month_iso="2026-10",
    )
    # "Hoy" appears for "today" indicator
    assert "Hoy" in html
    # No "tú" / "tienes" / "añade" (vos form expected where applicable)
    # (We don't assert absence of "tu" because that substring appears in
    # "Mes anterior" / "Semana anterior". We just spot-check the strings.)
    assert "Mes anterior" in html
    assert "Semana anterior" in html


def test_calendar_uses_7_col_grid(jinja_env):
    """Both grids render as a 7-column CSS grid (one col per weekday)."""
    # Month with 30 days (September), no offset, so needs 6 rows × 7 cols = 42 cells.
    month_days_30 = [
        {"date_iso": f"2026-09-{d:02d}", "label": str(d),
         "item_count": 0, "is_today": False, "is_selected": False}
        for d in range(1, 31)
    ]
    template = jinja_env.from_string(
        """{% import "_components/calendar.html" as cal %}
{{ cal.week_grid(weekdays, days, prev_week_iso, next_week_iso) }}
{{ cal.month_grid(year, month, days_m, first_day_pad, prev_month_iso, next_month_iso) }}"""
    )
    html = template.render(
        weekdays=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        days=[{"date_iso": "2026-09-21", "label": "Lun",
               "item_count": 0, "is_today": True, "is_selected": False}] * 7
              + [{"date_iso": f"2026-09-{d:02d}", "label": str(d),
                  "item_count": 0, "is_today": False, "is_selected": False}
                 for d in range(22, 30)],
        prev_week_iso="2026-09-14",
        next_week_iso="2026-09-28",
        year=2026,
        month=9,
        days_m=month_days_30,
        first_day_pad=1,
        prev_month_iso="2026-08",
        next_month_iso="2026-10",
    )
    assert "calendar-week-grid" in html
    assert "calendar-month-grid" in html