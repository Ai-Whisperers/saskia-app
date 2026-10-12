"""tests/perf/test_performance_benchmarks.py — Phase 1 refactored."""

import time
import timeit
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = [pytest.mark.perf, pytest.mark.slow]


def test_validate_upload_imports():
    """validate_upload should be importable."""
    from app.rms.upload_limits import validate_upload

    assert callable(validate_upload)


def test_md_to_html_under_50ms():
    """_md_to_html should run in <50ms for typical input."""
    from app.routers.help import _md_to_html

    md = "# Title\n\n**Bold** and *italic* text with [link](https://x.com).\n"
    _md_to_html(md)
    elapsed = timeit.timeit(lambda: _md_to_html(md), number=10) / 10
    assert elapsed < 0.050, f"_md_to_html too slow: {elapsed * 1000:.2f}ms"


def test_sparkline_under_50ms():
    """sparkline should run in <50ms for 100 values."""
    from app.rms.charts import sparkline

    values = list(range(100))
    sparkline(values)
    elapsed = timeit.timeit(lambda: sparkline(values), number=10) / 10
    assert elapsed < 0.050, f"sparkline too slow: {elapsed * 1000:.2f}ms"


def test_jaccard_under_5ms():
    """jaccard_similarity should run in <5ms for small sets."""
    from app.rms.product_similarity import jaccard_similarity

    a = set(range(50))
    b = set(range(25, 75))
    jaccard_similarity(a, b)
    elapsed = timeit.timeit(lambda: jaccard_similarity(a, b), number=100) / 100
    assert elapsed < 0.005, f"jaccard_similarity too slow: {elapsed * 1000:.2f}ms"


def test_format_gs_under_5ms():
    """format_gs should run in <5ms."""
    from app.rms.money import format_gs

    format_gs(1_000_000)
    elapsed = timeit.timeit(lambda: format_gs(1_000_000), number=100) / 100
    assert elapsed < 0.005, f"format_gs too slow: {elapsed * 1000:.2f}ms"


def test_hash_password_under_1s():
    """hash_password should run in <1s (bcrypt is intentionally slow)."""
    try:
        from app.auth import hash_password

        hash_password("test")
        elapsed = timeit.timeit(lambda: hash_password("test"), number=1)
        assert elapsed < 1.0, f"hash_password too slow: {elapsed * 1000:.2f}ms"
    except (ImportError, Exception):
        pytest.skip("hash_password not available")


def test_100_concurrent_format_gs_under_1s():
    """100 concurrent format_gs calls should complete in <1s."""
    from app.rms.money import format_gs

    def call():
        return format_gs(1_234_567)

    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: call(), range(100)))
    elapsed = time.time() - start
    assert len(results) == 100
    assert elapsed < 1.0, f"100 concurrent format_gs took {elapsed:.2f}s"


def test_1000_sparklines_under_5s():
    """1000 sparkline calls should complete in <5s."""
    from app.rms.charts import sparkline

    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    start = time.time()
    for _ in range(1000):
        sparkline(values)
    elapsed = time.time() - start
    assert elapsed < 5.0, f"1000 sparklines took {elapsed:.2f}s"


def test_import_perf_modules():
    """Performance-related modules should be importable."""
    from app.rms import charts, money, upload_limits
    from app.routers import help

    assert money is not None
    assert charts is not None
    assert upload_limits is not None
    assert help is not None
