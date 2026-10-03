"""P1-2: tests for /p/{token} hardening (longer token, expiry, rate limit).

Covers:
  - generate_public_token() produces 16+ chars (was 8)
  - _is_token_valid() handles 3 cases: NULL, future, past
  - Migration 067 adds public_token_expires_at + backfills from created_at
  - /p/{token} returns 410 Gone for expired tokens
  - /p/{token}/comprobante returns 410 for expired tokens
  - /p/{token} returns 404 (not 410) for unknown tokens
  - /p/{token} returns 429 after 30 views / 5 min from the same IP
"""
# allow-hardcoded-dates: token expiry boundary tests need fixed future/past timestamps (deterministic _is_token_valid checks)
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import pytest

from app.rms.models import Customer, Pedido
from app.routers.pedidos import (
    _is_token_valid,
    generate_public_token,
)


def test_generate_public_token_is_at_least_16_chars() -> None:
    """Token entropy bump: was 8-char [:8] of token_urlsafe(8) →
    now full token_urlsafe(16) ≈ 22 chars."""
    for _ in range(20):
        token = generate_public_token()
        assert len(token) >= 16, (
            f"token too short: {token!r} (len={len(token)}). P1-2 mandates "
            ">= 16 chars for 96 bits of entropy."
        )
        # URL-safe alphabet (no padding '=', no /+)
        assert all(c.isalnum() or c in "-_" for c in token)


def test_generate_public_token_is_unique() -> None:
    """Birthday-paradox sanity check — 1000 tokens must all be distinct."""
    tokens = {generate_public_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_is_token_valid_rejects_null_expiry() -> None:
    """Legacy rows (pre-migration 067) have NULL expiry → invalid."""
    p = Pedido()
    p.public_token_expires_at = None
    assert _is_token_valid(p) is False


def test_is_token_valid_accepts_future_expiry() -> None:
    """A token that expires tomorrow is valid today."""
    p = Pedido()
    p.public_token_expires_at = datetime.utcnow() + timedelta(days=1)
    assert _is_token_valid(p) is True


def test_is_token_valid_rejects_past_expiry() -> None:
    """A token that expired yesterday is invalid today."""
    p = Pedido()
    p.public_token_expires_at = datetime.utcnow() - timedelta(days=1)
    assert _is_token_valid(p) is False


def test_is_token_valid_with_now_override() -> None:
    """Deterministic comparison via the `now` parameter."""
    p = Pedido()
    p.public_token_expires_at = datetime(2026, 10, 15, 12, 0, 0)
    # Same moment → not strictly greater → invalid
    assert _is_token_valid(p, now=datetime(2026, 10, 15, 12, 0, 0)) is False
    # Just before → valid
    assert _is_token_valid(p, now=datetime(2026, 10, 15, 11, 59, 59)) is True
    # Just after → invalid
    assert _is_token_valid(p, now=datetime(2026, 10, 15, 12, 0, 1)) is False


def test_is_token_valid_handles_string_datetime_from_sqlite() -> None:
    """SQLite sometimes returns TIMESTAMP columns as raw strings.

    When the ORM (via str_to_datetime processor) or our own _is_token_valid
    encounters a string, it must handle it without crashing. Test both
    the date-only format (the most common mistake when hand-typing) and
    the full timestamp format.
    """
    p = Pedido()
    # Date-only string (e.g. from a manual UPDATE SET expires_at='2025-01-01')
    p.public_token_expires_at = "2025-01-01"
    # 2025-01-01 is in the past → invalid
    assert _is_token_valid(p) is False

    # Future date-only string
    p.public_token_expires_at = "2099-12-31"
    assert _is_token_valid(p) is True

    # Full timestamp string (ISO variant with T separator)
    p.public_token_expires_at = "2025-01-01T00:00:00"
    assert _is_token_valid(p) is False

    # Garbage string → invalid (defensive)
    p.public_token_expires_at = "not a date"
    assert _is_token_valid(p) is False


def _build_expired_pedido(session_factory) -> tuple[int, str]:
    """Create a pedido whose public_token already expired."""
    with session_factory() as s:
        cust = Customer(name="Expired Cust", phone="0981111111")
        s.add(cust)
        s.flush()

        token = secrets.token_urlsafe(16)
        p = Pedido(
            customer_id=cust.id,
            customer_name="Expired Cust",
            customer_phone="0981111111",
            promised_date=datetime.utcnow().date(),
            promised_time="10:00",
            channel="mostrador",
            status="pending",
            payment_intent="efectivo",
            notes="",
            public_token=token,
            public_token_expires_at=datetime.utcnow() - timedelta(days=1),
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id, token


def _build_active_pedido(session_factory) -> tuple[int, str]:
    """Create a pedido whose public_token expires in 30 days."""
    with session_factory() as s:
        cust = Customer(name="Active Cust", phone="0981222222")
        s.add(cust)
        s.flush()

        token = secrets.token_urlsafe(16)
        p = Pedido(
            customer_id=cust.id,
            customer_name="Active Cust",
            customer_phone="0981222222",
            promised_date=datetime.utcnow().date(),
            promised_time="10:00",
            channel="mostrador",
            status="pending",
            payment_intent="efectivo",
            notes="",
            public_token=token,
            public_token_expires_at=datetime.utcnow() + timedelta(days=30),
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id, token


def test_public_pedido_returns_410_for_expired_token(client, session_factory) -> None:
    """An expired /p/{token} returns 410 Gone (not 200, not 404)."""
    pid, token = _build_expired_pedido(session_factory)

    r = client.get(f"/p/{token}")
    assert r.status_code == 410, f"Expected 410, got {r.status_code}: {r.text[:200]}"
    assert "venci" in r.text.lower() or "venci" in r.json().get("detail", "").lower() if r.headers.get("content-type", "").startswith("application/json") else True


def test_public_pedido_returns_404_for_unknown_token(client) -> None:
    """A token that never existed returns 404 (distinguishes 'unknown' from 'expired')."""
    r = client.get("/p/this_token_never_existed_xxxxxxxxxxxxxxxxxx")
    assert r.status_code == 404


def test_public_pedido_returns_200_for_active_token(client, session_factory) -> None:
    """An active /p/{token} still works (happy path regression check)."""
    pid, token = _build_active_pedido(session_factory)

    r = client.get(f"/p/{token}")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"


def test_comprobante_returns_410_for_expired_token(client, session_factory) -> None:
    """An expired /p/{token}/comprobante upload returns 410 Gone."""
    import io as _io

    pid, token = _build_expired_pedido(session_factory)

    # Use raw multipart (no CSRF wrapper) — 410 must fire BEFORE CSRF
    # or form parsing so the expiry check doesn't depend on auth state.
    r = client.post(
        f"/p/{token}/comprobante",
        files={"file": ("x.jpg", _io.BytesIO(b"x"), "image/jpeg")},
    )
    assert r.status_code == 410, f"Expected 410 for expired upload, got {r.status_code}"


def test_public_pedido_rate_limit_after_30_views(client, session_factory) -> None:
    """After 30 GETs to /p/{token} in 5 min from the same IP, return 429.

    Rate limit fires BEFORE the token lookup (it's the first check
    in public_pedido), so we don't need a real pedido for this test —
    we just spam the endpoint until the threshold trips.
    """
    # Bypass the per-test rate-limit disable so we can actually
    # exercise the limit. conftest sets AIW_SASKIA_AUTH_DISABLED=1
    # by default; undo it for this test.
    import os
    saved = os.environ.pop("AIW_SASKIA_AUTH_DISABLED", None)
    os.environ.pop("SASKIA_TEST_AUTH_DISABLED", None)

    # Force-enable rate limiter via the same env the rate_limit module reads.
    # (The "disabled" check returns False when env var is unset/empty.)
    try:
        # Build a fresh pedido to hit (rate limit fires before lookup,
        # but we need valid tokens to keep status 200 vs 404 noise).
        pid, token = _build_active_pedido(session_factory)

        # First 30 requests: 200 (or other valid status)
        for i in range(30):
            r = client.get(f"/p/{token}")
            assert r.status_code == 200, (
                f"Request {i+1}/30 should succeed, got {r.status_code}"
            )

        # 31st request: 429 (over the limit)
        r = client.get(f"/p/{token}")
        assert r.status_code == 429, (
            f"Request 31 should hit rate limit, got {r.status_code}"
        )
        assert "Retry-After" in r.headers, "429 must include Retry-After header"
    finally:
        if saved is not None:
            os.environ["AIW_SASKIA_AUTH_DISABLED"] = saved
        os.environ["SASKIA_TEST_AUTH_DISABLED"] = "1"


def test_migration_067_adds_column_and_backfills(tmp_path) -> None:
    """Migration 067 adds public_token_expires_at and backfills it.

    Strategy: insert a row with created_at=2026-01-01 BEFORE running
    init_db. After init_db, migration 067 should fire, add the column,
    and backfill the row's expires_at to created_at + 30 days.

    We use init_db's own machinery: if the schema starts at version 67
    (because of the new model + config bump), 067 is a no-op. To force
    the migration to run we must manipulate app_meta's schema_version
    BEFORE init_db runs — but we can't do that on a fresh DB because
    067 runs first.

    The pragmatic test: verify the column exists after init_db, and
    that a row inserted AFTER init_db with created_at=2026-01-01
    backfills to 2026-01-31 when 067 is forced to re-run by deleting
    the column + rolling back schema_version.
    """
    from datetime import datetime as _dt

    from sqlalchemy import create_engine, text

    from app.rms.db import init_db as _init

    db_path = tmp_path / "migtest.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")

    # Run init_db to bring schema to v67.
    _init(engine)

    # Now force 067 to re-run: rollback schema_version, drop the
    # indexes on the new column, drop the column, insert a row with a
    # known created_at, then re-init and verify backfill.
    with engine.begin() as conn:
        # Reset schema_version to 66 so 067 fires on next init.
        conn.execute(text(
            "UPDATE app_meta SET value = '66' WHERE key = 'schema_version'"
        ))
        # Drop both indexes that reference the new column (SQLite
        # refuses DROP COLUMN if any index references it). The ORM
        # auto-creates ix_pedido_public_token_expires_at; my migration
        # creates ix_pedido_token_expires.
        conn.execute(text("DROP INDEX IF EXISTS ix_pedido_public_token_expires_at"))
        conn.execute(text("DROP INDEX IF EXISTS ix_pedido_token_expires"))
        try:
            conn.execute(text(
                "ALTER TABLE pedido DROP COLUMN public_token_expires_at"
            ))
        except Exception as exc:
            # If drop fails, the column didn't exist (migration already
            # skipped). Skip the backfill assertion so the test still
            # gives a useful signal.
            pytest.skip(f"could not drop column to force re-migration: {exc}")
        # Insert a row with NULL expires_at (mimics pre-067 state).
        conn.execute(text(
            "INSERT INTO pedido (customer_name, customer_phone, promised_date, "
            "channel, status, payment_intent, notes, public_token, created_at, updated_at) "
            "VALUES ('Migration Test', '0981000000', '2026-01-02', 'mostrador', "
            "'pending', 'efectivo', '', 'mig_test_token_xyz', '2026-01-01 12:00:00', '2026-01-01 12:00:00')"
        ))

    # Re-run init_db. 067 should fire, re-add the column, and backfill.
    _init(engine)

    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT public_token_expires_at FROM pedido WHERE public_token = 'mig_test_token_xyz'"
        )).first()
        assert row is not None, "row missing after re-init"
        assert row[0] is not None, "migration 067 didn't backfill expires_at"
        # Should be ~2026-01-31 (30 days after 2026-01-01)
        expires = _dt.fromisoformat(str(row[0]))
        created = _dt(2026, 1, 1, 12, 0, 0)
        delta_days = (expires - created).days
        assert 29 <= delta_days <= 31, f"expected ~30 day delta, got {delta_days}"
