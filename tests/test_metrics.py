"""Tests for app/rms/metrics — Prometheus exposition format."""

from __future__ import annotations

import pytest

from app.rms.metrics import (
    _BUCKETS_S,
    _normalize_path,
    record_request,
    render,
    set_app_info,
    set_db_up,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Wipe metrics between tests so each test starts fresh."""
    import app.rms.metrics as m

    with m._lock:
        m._count_total.clear()
        m._hist.clear()
        m._db_up = 1
        m._app_info = {}
    yield


def test_empty_render_has_headers():
    out = render()
    assert "# HELP rms_requests_total" in out
    assert "# TYPE rms_requests_total counter" in out
    assert "# TYPE rms_request_duration_seconds histogram" in out
    assert "rms_db_up 1" in out  # default up


def test_record_increments_counter():
    record_request("/ventas", "GET", 200, 0.05)
    record_request("/ventas", "GET", 200, 0.07)
    record_request("/ventas", "GET", 500, 0.30)

    out = render()
    assert 'rms_requests_total{path="/ventas",method="GET",status="200"} 2' in out
    assert 'rms_requests_total{path="/ventas",method="GET",status="500"} 1' in out


def test_record_populates_histogram_buckets():
    """A 60ms request should fall into the 50ms and 100ms buckets, but not 25ms."""
    record_request("/api/test", "GET", 200, 0.060)
    out = render()

    # Find the bucket lines for /api/test
    bucket_lines = [
        line for line in out.split("\n")
        if "rms_request_duration_seconds_bucket" in line and 'path="/api/test"' in line
    ]
    # 11 buckets (10 finite + 1 +Inf)
    assert len(bucket_lines) == len(_BUCKETS_S) + 1

    # 50ms bucket (≤ 50ms) — 0 because 60ms > 50ms
    bucket_50 = [line for line in bucket_lines if 'le="0.05"' in line]
    assert bucket_50[0].endswith(" 0.0") or bucket_50[0].endswith(" 0")

    # 100ms bucket (≤ 100ms) — 1 because 60ms ≤ 100ms
    bucket_100 = [line for line in bucket_lines if 'le="0.1"' in line]
    assert bucket_100[0].endswith(" 1.0") or bucket_100[0].endswith(" 1")

    # +Inf bucket — always 1
    bucket_inf = [line for line in bucket_lines if 'le="+Inf"' in line]
    assert bucket_inf[0].endswith(" 1.0") or bucket_inf[0].endswith(" 1")


def test_histogram_sum_and_count():
    record_request("/x", "GET", 200, 0.1)
    record_request("/x", "GET", 200, 0.2)
    out = render()
    # Sum should be 0.3 (within rounding)
    sum_line = [line for line in out.split("\n") if "rms_request_duration_seconds_sum" in line and 'path="/x"' in line]
    assert len(sum_line) == 1
    assert sum_line[0].endswith(" 0.300000") or sum_line[0].endswith(" 0.3")
    # Count should be 2
    count_line = [line for line in out.split("\n") if "rms_request_duration_seconds_count" in line and 'path="/x"' in line]
    assert count_line[0].endswith(" 2")


def test_db_up_gauge():
    set_db_up(True)
    assert "rms_db_up 1" in render()
    set_db_up(False)
    assert "rms_db_up 0" in render()


def test_app_info_emitted_when_set():
    set_app_info(version="1.0", schema_version=84)
    out = render()
    assert 'rms_app_info{' in out
    assert 'schema_version="84"' in out
    assert 'version="1.0"' in out
    assert out.count('rms_app_info{') == 1
    # The line must end with " 1" (Prometheus info-gauge convention)
    info_line = [line for line in out.split("\n") if line.startswith("rms_app_info{")]
    assert info_line[0].endswith(" 1")


def test_no_app_info_omitted():
    """If set_app_info wasn't called, no rms_app_info line appears."""
    out = render()
    assert "rms_app_info" not in out


def test_normalize_path_collapses_ids():
    assert _normalize_path("/ventas/123") == "/ventas/:id"
    assert _normalize_path("/ventas/abc") == "/ventas/abc"
    assert _normalize_path("/recetas/42/lineas/9") == "/recetas/:id/lineas/:id"
    # Static paths unchanged
    assert _normalize_path("/") == "/"


def test_metric_thread_safety_smoke():
    """50 concurrent increments all land."""
    import threading

    def hammer():
        for _ in range(50):
            record_request("/x", "GET", 200, 0.001)

    threads = [threading.Thread(target=hammer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    out = render()
    # Counter should reflect all 500 increments
    assert 'rms_requests_total{path="/x",method="GET",status="200"} 500' in out


def test_escape_in_path():
    """Backslash, quote, and newline must be escaped in labels."""
    record_request("/weird/\\path\"quote\"", "GET", 200, 0.01)
    out = render()
    # Both backslash and quote should be doubled in the label value
    assert 'path="/weird/\\\\path\\"quote\\""' in out
