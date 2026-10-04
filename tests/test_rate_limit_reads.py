"""tests/test_rate_limit_reads.py — BACKLOG #10 (Phase 14).

Tests the read-rate limiter applied to /api/search and /reportes/*.

What's covered:
1. /api/search returns 200 the first N times and 429 after N+1
   (N = 60 for search; we exercise the threshold with a smaller
   number by passing max_per_minute directly to is_read_rate_limited)
2. /reportes/* returns 200 (router-level dep wired)
3. /healthz/db is NOT rate-limited even after many calls
4. AIW_SASKIA_AUTH_DISABLED=1 bypasses the limiter
5. record_read_heavy is idempotent / cheap on failure
6. The X-Forwarded-For header is honored for IP-based counting
7. FAIL OPEN: if the DB is unavailable, returns allowed=True

These tests use is_read_rate_limited directly (unit-level) so they
don't require a full uvicorn + DB bootstrap. End-to-end smoke is
covered by the rate-limit guards in the routes themselves.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.rms.models import AuditLog
from app.rms.rate_limit import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_WINDOW_SECONDS,
    is_disabled,
    is_read_rate_limited,
    read_rate_limit_dependency,
    record_read_heavy,
)


def _fake_request(ip: str = "192.0.2.10", xff: str | None = None) -> SimpleNamespace:
    """Build a minimal Request-like object with the headers we need."""
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(
        headers=headers,
        client=SimpleNamespace(host=ip),
    )


def _populate_audit(session, ip: str, action_prefix: str, n: int, when: datetime) -> None:
    """Insert N audit rows for `ip` matching `action LIKE '<prefix>%'`."""
    for i in range(n):
        session.add(
            AuditLog(
                occurred_at=when - timedelta(seconds=i),
                action=f"{action_prefix}.seed_{i}",
                ip=ip,
                detail={},
            )
        )
    session.commit()


def test_default_constants() -> None:
    assert DEFAULT_READ_LIMIT == 60
    assert DEFAULT_READ_WINDOW_SECONDS == 60


def test_disabled_bypass_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "1")
    assert is_disabled() is True


def test_disabled_bypass_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("AIW_SASKIA_AUTH_DISABLED", raising=False)
    assert is_disabled() is False


def test_first_read_allowed_on_clean_db(session_factory) -> None:
    """A new IP with no audit history must be allowed."""
    with session_factory() as s:
        request = _fake_request(ip="203.0.113.1")
        when = datetime.now(timezone.utc)
        decision = is_read_rate_limited(
            s,
            request,
            max_per_minute=5,
            window_seconds=60,
            now=when,
        )
        assert decision.allowed is True
        assert decision.current_count == 0
        assert decision.limit == 5
        assert decision.retry_after_seconds == 0


def test_blocks_after_threshold(session_factory) -> None:
    """After max_per_minute read.heavy rows in the window, return blocked."""
    ip = "203.0.113.7"
    when = datetime.now(timezone.utc)
    with session_factory() as s:
        _populate_audit(s, ip, "read.heavy.api.search.products", n=5, when=when)
        request = _fake_request(ip=ip)
        decision = is_read_rate_limited(
            s,
            request,
            max_per_minute=5,
            window_seconds=60,
            now=when,
        )
        assert decision.allowed is False
        assert decision.current_count == 5
        assert decision.retry_after_seconds == 60


def test_uses_xff_first_hop_ip(session_factory) -> None:
    """When X-Forwarded-For is set, count by first hop, not request.client."""
    real_ip = "198.51.100.5"
    spoofed_ip = "198.51.100.99"
    xff = f"{spoofed_ip}, 10.0.0.1"
    when = datetime.now(timezone.utc)
    with session_factory() as s:
        # Populate the spoofed IP, not the real one
        _populate_audit(s, spoofed_ip, "read.heavy.test", n=5, when=when)
        request = _fake_request(ip=real_ip, xff=xff)
        decision = is_read_rate_limited(
            s,
            request,
            max_per_minute=5,
            window_seconds=60,
            now=when,
        )
        assert decision.allowed is False, "should have used spoofed IP from XFF"


def test_window_does_not_count_old_reads(session_factory) -> None:
    """Reads older than window_seconds should not count."""
    ip = "203.0.113.20"
    now = datetime.now(timezone.utc)
    # 5 reads 5 minutes ago, well outside the 60-second window
    long_ago = now - timedelta(seconds=600)
    with session_factory() as s:
        _populate_audit(s, ip, "read.heavy", n=5, when=long_ago)
        request = _fake_request(ip=ip)
        decision = is_read_rate_limited(
            s,
            request,
            max_per_minute=5,
            window_seconds=60,
            now=now,
        )
        assert decision.allowed is True


def test_fail_open_on_db_error() -> None:
    """If the DB raises, return allowed=True (do not brick the route)."""
    bogus_session = MagicMock()
    bogus_session.query.side_effect = RuntimeError("DB unavailable")
    request = _fake_request(ip="203.0.113.30")
    decision = is_read_rate_limited(
        bogus_session,
        request,
        max_per_minute=5,
        window_seconds=60,
    )
    assert decision.allowed is True
    assert decision.limit == 5


def test_record_read_heavy_writes_audit_row(session_factory) -> None:
    """record_read_heavy should append one row tagged read.heavy.<tag>."""
    with session_factory() as s:
        request = _fake_request(ip="203.0.113.40")
        record_read_heavy(s, request, route_tag="unit.test")
        row = s.query(AuditLog).filter(AuditLog.action == "read.heavy.unit.test").one()
        assert row.ip == "203.0.113.40"


def test_record_read_heavy_swallows_db_failures() -> None:
    """DB errors during record_read_heavy must not raise into the caller."""
    bogus_session = MagicMock()
    bogus_session.add.side_effect = RuntimeError("DB unavailable")
    request = _fake_request(ip="203.0.113.50")
    # Must not raise:
    record_read_heavy(bogus_session, request, route_tag="unit.broken")


def test_dependency_returns_none_when_disabled(monkeypatch, session_factory) -> None:
    """The FastAPI dependency is a no-op when AIW_SASKIA_AUTH_DISABLED=1."""
    monkeypatch.setenv("AIW_SASKIA_AUTH_DISABLED", "1")
    dep = read_rate_limit_dependency(5, route_tag="dep.test")
    request = _fake_request(ip="203.0.113.60")
    with session_factory() as s:
        # The dep returns None in this case; FastAPI passes None through.
        result = dep(request=request, session=s)
        assert result is None


def test_dependency_records_when_allowed(monkeypatch, session_factory) -> None:
    """The dep appends an audit row when allowed (so future counts have data)."""
    monkeypatch.delenv("AIW_SASKIA_AUTH_DISABLED", raising=False)
    dep = read_rate_limit_dependency(5, route_tag="dep.record.test")
    request = _fake_request(ip="203.0.113.70")
    with session_factory() as s:
        result = dep(request=request, session=s)
        assert result is None
        row = s.query(AuditLog).filter(AuditLog.action == "read.heavy.dep.record.test").first()
        assert row is not None


def test_dependency_raises_http_429_when_blocked(monkeypatch, session_factory) -> None:
    """The dep raises HTTPException(429) when the limit is exceeded."""
    from fastapi import HTTPException

    monkeypatch.delenv("AIW_SASKIA_AUTH_DISABLED", raising=False)
    ip = "203.0.113.80"
    when = datetime.now(timezone.utc)
    dep = read_rate_limit_dependency(5, route_tag="dep.429")
    request = _fake_request(ip=ip)
    with session_factory() as s:
        _populate_audit(s, ip, "read.heavy.dep.429", n=5, when=when)
        with pytest.raises(HTTPException) as exc_info:
            dep(request=request, session=s)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_healthz_db_not_rate_limited() -> None:
    """/healthz/db is exempt from rate limiting (UptimeRobot polls every 5 min).

    Smoke-level check: the health router does NOT include
    `read_rate_limit_dependency` in its routes. Verified by structural
    inspection here so a future refactor that adds the dep to /healthz
    fails this test (operator + cron would break).
    """
    from app.routers.health import router as health_router

    routes = [r.path for r in health_router.routes]
    # Confirm healthz routes exist
    assert "/healthz/db" in routes
    assert "/healthz" in routes
    # Confirm they don't carry the read-rate-limit dep
    for r in health_router.routes:
        if r.path in ("/healthz", "/healthz/db"):
            for dep in getattr(r, "dependencies", []) or []:
                # The dep object has a `dependency` attribute pointing to the
                # underlying function. Our dep is `read_rate_limit_dependency`.
                assert "read_rate_limit_dependency" not in str(dep.dependency), (
                    f"{r.path} carries read_rate_limit_dependency -- UptimeRobot polling will 429!"
                )


def test_routes_wired_with_dependency() -> None:
    """The 4 /api/search routes + /reportes/* all carry the read limiter."""
    from app.routers import (
        customers as customers_mod,
    )
    from app.routers import (
        insights_derived as insights_derived_mod,
    )
    from app.routers import (
        inventory as inventory_mod,
    )
    from app.routers import (
        products as products_mod,
    )
    from app.routers import (
        recipes as recipes_mod,
    )
    from app.routers import (
        reportes as reportes_mod,
    )

    # /api/search routes (4 of them)
    search_paths = {
        "/productos/api/search": products_mod.router,
        "/inventario/api/search": inventory_mod.router,
        "/clientes/api/search": customers_mod.router,
        "/recetas/api/search": recipes_mod.router,
    }
    for path, mod in search_paths.items():
        found = False
        for r in mod.routes:
            if r.path == path:
                found = True
                deps = [str(d.dependency) for d in (getattr(r, "dependencies", []) or [])]
                assert any("read_rate_limit_dependency" in d for d in deps), (
                    f"{path} missing read_rate_limit_dependency"
                )
        assert found, f"{path} route not found"

    # /reportes/* uses router-level deps (one dep on the APIRouter itself)
    for mod in (reportes_mod, insights_derived_mod):
        router_deps = [str(d.dependency) for d in (mod.router.dependencies or [])]
        assert any("read_rate_limit_dependency" in d for d in router_deps), (
            f"{mod.__name__} /reportes router missing read_rate_limit_dependency"
        )
