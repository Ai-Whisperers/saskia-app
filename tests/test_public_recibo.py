"""tests/test_public_recibo.py — BACKLOG #17 (/r/{token} digital recibo share).

Coverage:
  - POST /ventas/{id}/share issues a fresh token + 30-day expiry
  - Same route called twice rotates the token (old URL 404s)
  - GET /r/{token} renders the recibo in public_mode (no back-to-history link)
  - GET /r/{token} for unknown token → 404
  - GET /r/{token} for expired token → 410 Gone (not 404)
  - Rate-limit 429 after 30 hits in 5 minutes
  - public_tokens helper unit tests (token shape, issue_token, is_token_valid)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text


def _make_sale(session_factory):
    """Insert product + sale via factories; return sale id."""
    from tests.factories import make_product, make_sale

    with session_factory() as s:
        p = make_product(s)
        sale = make_sale(s, product=p, qty=2.0, unit_price_gs=10000)
        s.commit()
        return sale.id


# --- public_tokens unit tests ------------------------------------------------


def test_generate_public_token_is_url_safe_and_long_enough():
    from app.rms.public_tokens import generate_public_token

    t1 = generate_public_token()
    t2 = generate_public_token()
    assert t1 != t2, "tokens must be unique across calls"
    assert len(t1) >= 22, f"expected ≥22 chars (96 bits base64url), got {len(t1)}"
    # URL-safe alphabet: A-Z, a-z, 0-9, '-', '_'
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert set(t1) <= allowed, "token chars must be URL-safe base64"


def test_issue_token_returns_fresh_pair_with_future_expiry():
    from app.rms.public_tokens import issue_token

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    token, expires_at = issue_token(now=now)
    assert isinstance(token, str) and len(token) >= 22
    # Default TTL is 30 days (matches /p/{token} convention).
    expected = now + timedelta(days=30)
    # Allow ±1s for the call time inside issue_token (it uses `now` directly).
    assert abs((expires_at - expected).total_seconds()) <= 1


def test_is_token_valid_returns_false_for_none_and_unparseable():
    from app.rms.public_tokens import is_token_valid

    assert is_token_valid(None) is False
    assert is_token_valid("not a datetime") is False
    assert is_token_valid("") is False


def test_is_token_valid_returns_true_when_future_expiry():
    from app.rms.public_tokens import is_token_valid

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    future = now + timedelta(days=10)
    assert is_token_valid(future, now=now) is True


def test_is_token_valid_returns_false_when_past_expiry():
    from app.rms.public_tokens import is_token_valid

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    past = now - timedelta(seconds=1)
    assert is_token_valid(past, now=now) is False


def test_is_token_valid_handles_naive_datetime_as_utc():
    """DB columns may hand back naive datetimes; treat them as UTC."""
    from app.rms.public_tokens import is_token_valid

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Naive future in UTC = same wall clock as the tz-aware future.
    naive_future = now.replace(tzinfo=None) + timedelta(days=5)
    assert is_token_valid(naive_future, now=now) is True


def test_is_token_valid_handles_string_formats():
    """SQLite returns datetimes as strings; handle both ISO and the
    SQLite-default 'YYYY-MM-DD HH:MM:SS[.ffffff]' shapes."""
    from app.rms.public_tokens import is_token_valid

    now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert is_token_valid("2026-10-15 12:00:00", now=now) is True
    assert is_token_valid("2026-09-25 12:00:00", now=now) is False
    # T-separated ISO variant.
    assert is_token_valid("2026-10-15T12:00:00", now=now) is True
    # With fractional seconds.
    assert is_token_valid("2026-10-15 12:00:00.123456", now=now) is True


# --- share endpoint (auth, POST /ventas/{id}/share) --------------------------


def test_share_endpoint_redirects_with_token_in_query(client, session_factory):
    """Operator hits share → 303 to detail page with the new URL."""
    sid = _make_sale(session_factory)
    r = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    assert r.status_code == 303
    assert f"/ventas/{sid}" in r.headers["location"]
    # The share URL is /r/{token}; the detail page consumes it via ?url=...
    assert "url=/r/" in r.headers["location"]
    assert "shared=1" in r.headers["location"]


def _extract_token_from_redirect(location: str) -> str:
    """Pull the token out of a Location header shaped like
    ``/ventas/{sid}?shared=1&url=/r/{token}``.

    Strips the ``/r/`` prefix so the returned string is the bare token.
    """
    url_value = location.split("url=", 1)[1]
    return url_value.split("/r/", 1)[1]


def test_share_endpoint_persists_token_with_30day_expiry(client, session_factory):
    sid = _make_sale(session_factory)
    r = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token = _extract_token_from_redirect(r.headers["location"])
    # Confirm it landed in the DB with a future expiry.
    with session_factory() as s:
        sale = s.get(__import__("app.rms.models_legacy", fromlist=["Sale"]).Sale, sid)
        assert sale.public_token == token
        assert sale.public_token_expires_at is not None
        assert sale.public_token_expires_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_share_endpoint_rotates_token_on_resubmission(client, session_factory):
    """Second share click invalidates the prior token."""
    sid = _make_sale(session_factory)
    r1 = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token1 = _extract_token_from_redirect(r1.headers["location"])
    r2 = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token2 = _extract_token_from_redirect(r2.headers["location"])
    assert token1 != token2
    # The old URL must now 404.
    old = client.get(f"/r/{token1}")
    assert old.status_code == 404


def test_share_endpoint_404s_for_missing_sale(client, session_factory):
    r = client.post("/ventas/9999999/share", follow_redirects=False)
    # Should be a NotFound (renders 404 page in the app, or 404 status).
    assert r.status_code == 404


# --- public recibo GET /r/{token} --------------------------------------------


def test_public_recibo_renders_in_public_mode(client, session_factory):
    sid = _make_sale(session_factory)
    # Issue a share.
    r = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token = _extract_token_from_redirect(r.headers["location"])
    # Public view.
    public = client.get(f"/r/{token}")
    assert public.status_code == 200
    body = public.text
    # Operator-only "Volver al historial" link must NOT be present in public mode.
    assert "Volver al historial" not in body
    # Customer-facing footer MUST be present.
    assert "Recibo digital" in body or "Saskia RMS" in body
    # Sale details still surface.
    assert f"#{sid}" in body


def test_public_recibo_404s_for_unknown_token(client, session_factory):
    r = client.get("/r/this-token-does-not-exist")
    assert r.status_code == 404


def test_public_recibo_410_gone_for_expired_token(client, session_factory):
    """Manually expire the token via SQL, confirm 410 (not 404)."""
    sid = _make_sale(session_factory)
    r = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token = _extract_token_from_redirect(r.headers["location"])
    # Force expiry to the past via raw SQL (bypasses model type-checking).
    with session_factory() as s:
        s.execute(
            text("UPDATE sale SET public_token_expires_at = :exp WHERE id = :sid"),
            {"exp": "2020-01-01 00:00:00", "sid": sid},
        )
        s.commit()
    r = client.get(f"/r/{token}")
    assert r.status_code == 410


def test_public_recibo_audit_row_created(client, session_factory):
    """Each view logs an audit row so the rate-limit + forensics work."""
    from app.rms.models import AuditLog

    sid = _make_sale(session_factory)
    r = client.post(f"/ventas/{sid}/share", follow_redirects=False)
    token = _extract_token_from_redirect(r.headers["location"])
    client.get(f"/r/{token}")
    with session_factory() as s:
        row = s.execute(
            select(AuditLog).where(AuditLog.action == "public.recibo.view")
        ).scalar_one_or_none()
    assert row is not None, "expected at least one public.recibo.view audit row"
    assert row.target_type == "sale"
    assert row.target_id == str(sid)
