"""tests/test_perf.py — verify app/rms/perf.py (E16).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E16.

Covers:
- paginate() with explicit total
- paginate() with implicit total (from list length)
- Paginate edge cases: page beyond last, page 0
- query_timer measures time + warns on slow ops
- INDEX_HINTS has expected entries
- count_models returns dict of row counts
- apply_postgres_indexes is idempotent
"""
from __future__ import annotations

from app.rms.perf import (
    INDEX_HINTS,
    apply_postgres_indexes,
    count_models,
    paginate,
    query_timer,
)


def test_paginate_with_explicit_total():
    result = paginate([1, 2, 3, 4, 5], page=1, per_page=2, total=10)
    assert result.items == [1, 2]
    assert result.pagination.total == 10
    assert result.pagination.n_pages == 5


def test_paginate_implicit_total():
    result = paginate([1, 2, 3], page=1, per_page=2)
    assert result.items == [1, 2]
    assert result.pagination.total == 3


def test_paginate_page_beyond_last():
    """When page > n_pages, return empty list (not raise)."""
    result = paginate([1, 2, 3, 4, 5], page=99, per_page=2, total=5)
    assert result.items == []
    assert result.pagination.page == 99


def test_paginate_page_zero_clamped_to_1():
    result = paginate([1, 2, 3], page=0, per_page=2)
    assert result.pagination.page == 1


def test_paginate_per_page_zero_clamped_to_50():
    result = paginate(list(range(60)), per_page=0)
    assert len(result.items) == 50


def test_query_timer_measures_time():
    with query_timer("test-op") as info:
        sum(range(1000))
    assert info["operation"] == "test-op"
    assert info["duration_ms"] > 0


def test_query_timer_warns_on_slow(caplog):
    """If duration > threshold, log warning (capture via caplog)."""
    import logging
    import time as _t
    with caplog.at_level(logging.WARNING, logger="saskia.perf"):
        with query_timer("slow-op", threshold_ms=0.0):
            _t.sleep(0.005)
    assert any("Slow query" in r.message for r in caplog.records)


def test_index_hints_include_key_columns():
    """Sale.sold_at, AuditLog.occurred_at must be in INDEX_HINTS."""
    from app.rms.models import AuditLog, Sale
    sale_hints = [(m, c) for (m, c, u) in INDEX_HINTS if m is Sale]
    audit_hints = [(m, c) for (m, c, u) in INDEX_HINTS if m is AuditLog]
    assert any(c == "sold_at" for (m, c) in sale_hints)
    assert any(c == "occurred_at" for (m, c) in audit_hints)


def test_count_models_returns_dict(session_factory):
    s = session_factory()
    try:
        counts = count_models(s)
        assert isinstance(counts, dict)
        assert "ingredient" in counts
        assert "product" in counts
        assert "sale" in counts
    finally:
        s.close()


def test_apply_postgres_indexes_idempotent(session_factory):
    """Calling twice must not raise."""
    s = session_factory()
    try:
        stmts1 = apply_postgres_indexes(s)
        s.commit()
        # Second pass (idempotency)
        stmts2 = apply_postgres_indexes(s)
        assert stmts1 == stmts2  # same statements
    finally:
        s.close()
