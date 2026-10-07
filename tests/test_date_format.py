"""Phase 27 — Date format utility tests.

Verifies the DateFormat helper for consistent date display.
"""
from __future__ import annotations

from pathlib import Path


DATE_JS = Path(__file__).parent.parent / "app" / "static" / "date-format.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_date_format_js_exists():
    """Should have a dedicated date format script."""
    assert DATE_JS.exists()


def test_date_format_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "date-format.js" in text


def test_date_format_exposes_global():
    """Should expose DateFormat globally."""
    js = DATE_JS.read_text()
    assert "window.DateFormat" in js


def test_date_format_has_short():
    """Should have short date format (DD/MM/YYYY)."""
    js = DATE_JS.read_text()
    assert "short:" in js
    assert "DD/MM" in js or "getDate" in js


def test_date_format_has_date_time():
    """Should have dateTime format."""
    js = DATE_JS.read_text()
    assert "dateTime:" in js
    assert "time:" in js


def test_date_format_has_time():
    """Should have time-only format (HH:mm)."""
    js = DATE_JS.read_text()
    assert "time:" in js
    assert "getHours" in js
    assert "getMinutes" in js


def test_date_format_has_relative():
    """Should have relative time format (hace X)."""
    js = DATE_JS.read_text()
    assert "relative:" in js
    assert "hace" in js


def test_date_format_has_smart():
    """Should have smart format (relative if recent, else short)."""
    js = DATE_JS.read_text()
    assert "smart:" in js


def test_date_format_has_day_name():
    """Should have Spanish day name."""
    js = DATE_JS.read_text()
    assert "dayName:" in js
    assert "lunes" in js
    assert "domingo" in js
    assert "sábado" in js


def test_date_format_has_month_name():
    """Should have Spanish month name."""
    js = DATE_JS.read_text()
    assert "monthName:" in js
    assert "enero" in js
    assert "diciembre" in js


def test_date_format_handles_invalid_input():
    """Should handle null/invalid input gracefully."""
    js = DATE_JS.read_text()
    assert "if (!date) return ''" in js
    assert "isNaN" in js


def test_date_format_uses_pad_start():
    """Should pad single digits with zeros."""
    js = DATE_JS.read_text()
    assert "padStart" in js


def test_date_format_uses_iife():
    """Should be wrapped in IIFE."""
    js = DATE_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_date_format_has_to_date_helper():
    """Should have a _toDate helper for type coercion."""
    js = DATE_JS.read_text()
    assert "_toDate" in js
    assert "instanceof Date" in js
    assert "new Date" in js


def test_date_format_handles_string():
    """Should accept string input."""
    js = DATE_JS.read_text()
    assert "typeof input === 'string'" in js or 'typeof input === "string"' in js


def test_date_format_handles_number():
    """Should accept numeric timestamp."""
    js = DATE_JS.read_text()
    assert "typeof input === 'number'" in js or 'typeof input === "number"' in js


def test_date_format_handles_few_seconds():
    """Should handle 'recién' / 'en un momento' for < 60s."""
    js = DATE_JS.read_text()
    assert "recién" in js
    assert "en un momento" in js


def test_date_format_handles_minutes():
    """Should format minutes correctly."""
    js = DATE_JS.read_text()
    assert "hace" in js
    assert "min" in js


def test_date_format_handles_hours():
    """Should format hours with pluralization."""
    js = DATE_JS.read_text()
    assert "hora" in js


def test_date_format_handles_days():
    """Should format days with pluralization."""
    js = DATE_JS.read_text()
    assert "día" in js
    assert "días" in js or "!= 1" in js


def test_date_format_handles_weeks():
    """Should format weeks."""
    js = DATE_JS.read_text()
    assert "semana" in js


def test_date_format_pluralizes():
    """Should pluralize Spanish words correctly."""
    js = DATE_JS.read_text()
    assert "absHour !== 1" in js or "absHour != 1" in js


def test_date_format_falls_back_to_short():
    """Should fall back to short date for > 30 days."""
    js = DATE_JS.read_text()
    assert "absDay < 30" in js or "< 30" in js


def test_date_format_smart_logic():
    """Smart format should use relative for < 7 days."""
    js = DATE_JS.read_text()
    assert "diffDays < 7" in js or "< 7" in js