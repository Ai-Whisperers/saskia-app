"""Phase 29 — Live time tracker tests.

Verifies the LiveTime utility that auto-updates relative times.
"""
from __future__ import annotations

from pathlib import Path


LIVE_TIME_JS = Path(__file__).parent.parent / "app" / "static" / "live-time.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_live_time_js_exists():
    """Should have a dedicated live time script."""
    assert LIVE_TIME_JS.exists()


def test_live_time_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "live-time.js" in text


def test_live_time_exposes_global():
    """Should expose LiveTime globally."""
    js = LIVE_TIME_JS.read_text()
    assert "window.LiveTime" in js


def test_live_time_uses_iife():
    """Should be wrapped in IIFE."""
    js = LIVE_TIME_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_live_time_checks_dateformat():
    """Should verify DateFormat is available."""
    js = LIVE_TIME_JS.read_text()
    assert "window.DateFormat" in js


def test_live_time_uses_data_attribute():
    """Should use data-relative-time attribute."""
    js = LIVE_TIME_JS.read_text()
    assert "data-relative-time" in js
    assert "querySelectorAll" in js


def test_live_time_supports_multiple_formats():
    """Should support short/dateTime/smart/time/relative formats."""
    js = LIVE_TIME_JS.read_text()
    assert "data-format" in js
    assert "case 'short'" in js
    assert "case 'dateTime'" in js
    assert "case 'smart'" in js
    assert "case 'time'" in js


def test_live_time_default_format():
    """Should default to 'relative' format."""
    js = LIVE_TIME_JS.read_text()
    assert "'relative'" in js


def test_live_time_has_interval():
    """Should have a configurable update interval."""
    js = LIVE_TIME_JS.read_text()
    assert "interval:" in js
    assert "60000" in js


def test_live_time_uses_setinterval():
    """Should use setInterval for periodic updates."""
    js = LIVE_TIME_JS.read_text()
    assert "setInterval" in js


def test_live_time_sets_title():
    """Should set title attribute with full date for hover."""
    js = LIVE_TIME_JS.read_text()
    assert "setAttribute('title'" in js
    assert "dateTime" in js


def test_live_time_uses_set():
    """Should use Set for element tracking."""
    js = LIVE_TIME_JS.read_text()
    assert "new Set()" in js


def test_live_time_removes_detached():
    """Should remove detached elements from tracking."""
    js = LIVE_TIME_JS.read_text()
    assert "document.body.contains" in js


def test_live_time_uses_mutation_observer():
    """Should observe DOM changes for new elements."""
    js = LIVE_TIME_JS.read_text()
    assert "MutationObserver" in js


def test_live_time_has_init():
    """Should have init method."""
    js = LIVE_TIME_JS.read_text()
    assert "init()" in js
    assert "this.refresh" in js
    assert "this.start" in js


def test_live_time_dom_ready_check():
    """Should wait for DOM ready if needed."""
    js = LIVE_TIME_JS.read_text()
    assert "readyState" in js
    assert "DOMContentLoaded" in js


def test_live_time_preserves_children():
    """Should preserve icon children when updating."""
    js = LIVE_TIME_JS.read_text()
    assert "children.length === 0" in js
    assert "childNodes" in js
    assert "TEXT_NODE" in js


def test_live_time_handles_subtree():
    """Should observe subtree for new elements."""
    js = LIVE_TIME_JS.read_text()
    assert "subtree: true" in js
    assert "childList: true" in js


def test_live_time_uses_text_content():
    """Should update textContent for leaf elements."""
    js = LIVE_TIME_JS.read_text()
    assert "textContent" in js


def test_live_time_method_update():
    """Should have public update method."""
    js = LIVE_TIME_JS.read_text()
    assert "update()" in js


def test_live_time_method_refresh():
    """Should have public refresh method."""
    js = LIVE_TIME_JS.read_text()
    assert "refresh()" in js


def test_live_time_method_start():
    """Should have public start method."""
    js = LIVE_TIME_JS.read_text()
    assert "start()" in js


def test_live_time_warns_if_no_dateformat():
    """Should warn if DateFormat not loaded."""
    js = LIVE_TIME_JS.read_text()
    assert "console.warn" in js
    assert "DateFormat" in js


def test_live_time_check_null_timestamp():
    """Should handle missing timestamp gracefully."""
    js = LIVE_TIME_JS.read_text()
    assert "if (!timestamp) return" in js or "if (!timestamp)" in js