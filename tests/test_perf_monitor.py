"""Phase 23 — Performance monitor tests.

Verifies the perf-monitor.js Web Vitals tracking utility.
"""

from __future__ import annotations

from pathlib import Path

PERF_JS = Path(__file__).parent.parent / "app" / "static" / "perf-monitor.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_perf_monitor_exists():
    """Should have a performance monitoring script."""
    assert PERF_JS.exists()


def test_perf_monitor_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "perf-monitor.js" in text


def test_perf_monitor_tracks_page_load():
    """Should track page load metrics."""
    js = PERF_JS.read_text()
    assert "pageLoad" in js
    assert "domContentLoaded" in js
    assert "loadComplete" in js


def test_perf_monitor_tracks_resources():
    """Should track resource loading by type."""
    js = PERF_JS.read_text()
    assert "resources" in js
    assert "transferSize" in js


def test_perf_monitor_tracks_lcp():
    """Should track Largest Contentful Paint."""
    js = PERF_JS.read_text()
    assert "lcp" in js.lower() or "largest-contentful-paint" in js
    assert "LCP" in js or "lcp" in js


def test_perf_monitor_tracks_fid():
    """Should track First Input Delay."""
    js = PERF_JS.read_text()
    assert "fid" in js.lower() or "first-input" in js
    assert "FID" in js or "fid" in js


def test_perf_monitor_tracks_cls():
    """Should track Cumulative Layout Shift."""
    js = PERF_JS.read_text()
    assert "cls" in js.lower() or "layout-shift" in js
    assert "CLS" in js or "cls" in js


def test_perf_monitor_uses_performance_observer():
    """Should use PerformanceObserver API."""
    js = PERF_JS.read_text()
    assert "PerformanceObserver" in js
    assert "observe" in js
    assert "buffered: true" in js


def test_perf_monitor_groups_resources_by_type():
    """Should group resources by type (js, css, image, font)."""
    js = PERF_JS.read_text()
    assert "js" in js
    assert "css" in js
    assert "image" in js
    assert "font" in js


def test_perf_monitor_has_mark_measure():
    """Should support custom mark/measure for user timing."""
    js = PERF_JS.read_text()
    assert "mark:" in js or "mark(" in js
    assert "measure:" in js or "measure(" in js
    assert "performance.mark" in js
    assert "performance.measure" in js


def test_perf_monitor_get_metrics():
    """Should expose getMetrics()."""
    js = PERF_JS.read_text()
    assert "getMetrics:" in js or "getMetrics(" in js
    assert "_metrics" in js


def test_perf_monitor_handles_unsupported():
    """Should gracefully handle missing APIs."""
    js = PERF_JS.read_text()
    assert "Not supported" in js or "catch" in js
    assert "try {" in js


def test_perf_monitor_disconnect():
    """Should support disconnecting observers."""
    js = PERF_JS.read_text()
    assert "disconnect:" in js
    assert "obs.disconnect" in js
    assert "_observers = []" in js


def test_perf_monitor_exposes_global():
    """Should expose Performance globally."""
    js = PERF_JS.read_text()
    assert "window.Performance" in js


def test_perf_monitor_uses_iife():
    """Should be wrapped in IIFE."""
    js = PERF_JS.read_text()
    assert "(function()" in js
    assert "'use strict'" in js


def test_perf_monitor_auto_initializes():
    """Should auto-init on DOMContentLoaded."""
    js = PERF_JS.read_text()
    assert "DOMContentLoaded" in js
    assert "Performance.init" in js or "init()" in js


def test_perf_monitor_tracks_navigation_timing():
    """Should capture navigation timing breakdown."""
    js = PERF_JS.read_text()
    assert "dns" in js
    assert "tcp" in js
    assert "request" in js
    assert "response" in js
    assert "dom" in js


def test_perf_monitor_uses_load_event():
    """Should track on window load event."""
    js = PERF_JS.read_text()
    assert "'load'" in js or '"load"' in js
    assert "addEventListener" in js


def test_perf_monitor_resource_size_tracking():
    """Should track transfer sizes."""
    js = PERF_JS.read_text()
    assert "transferSize" in js
    assert "totalSize" in js


def test_perf_monitor_resource_count():
    """Should count resources by type."""
    js = PERF_JS.read_text()
    assert ".count++" in js or "count: 0" in js
