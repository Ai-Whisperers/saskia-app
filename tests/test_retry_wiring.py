"""tests/test_retry_wiring.py — S2 robustness PR6: verify retry_transient
is correctly wired at the call sites for HTTP (scrapers) and crypto
(backup_crypto).

The retry helper itself is exhaustively covered by tests/test_retry.py.
This file is the "did the wiring land correctly?" gate, parametrized
across the two surfaces:

  - **scraper recovers from 429**         (httpx transient -> retry)
  - **scraper raises on 4xx**             (httpx terminal -> no retry)
  - **backup retries on DB locked**       (sqlite3 transient -> retry)
  - **backup raises on integrity error**  (sqlite3 terminal -> no retry)
  - **both honor attempts=3 cap**         (exhausted -> raise)

For the scraper side we exercise the public function with a fake
``httpx.Client.get`` that raises ``httpx.HTTPStatusError`` on the
first N attempts then returns a minimal-valid Superseis page. For the
backup side we monkeypatch ``derive_key`` inside ``app.services.backup_crypto``
to inject the error -- the wiring wraps ``encrypt_backup`` so the inner
``derive_key`` call is the natural seam for "the DB is locked" / "the
DDL change failed mid-flight" simulations.

Classifier notes (default_is_transient):
  - ``httpx.HTTPStatusError(status_code=429)``   -> transient
  - ``httpx.HTTPStatusError(status_code=404)``   -> terminal (not in 429/5xx)
  - ``sqlite3.OperationalError("database is locked")`` -> transient
  - ``sqlite3.IntegrityError``                    -> terminal (PRAGMA check fails)
  - ``ValueError``                                -> terminal
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import httpx
import pytest

from app.integrations.scrapers import scrape_superseis
from app.rms.retry import default_is_transient, retry_transient
from app.services.backup_crypto import encrypt_backup

# ─── Helpers ──────────────────────────────────────────────────────


class FakeSleeper:
    """Records sleep calls without blocking. Avoids real waits in retries."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _make_httpx_error(status_code: int) -> httpx.HTTPStatusError:
    """Construct an ``httpx.HTTPStatusError`` with a real response.

    httpx requires both ``request`` and ``response`` to construct the
    exception; we use MagicMock(spec=...) so the helper stays hermetic
    (no real network, no real Request/Response construction).
    """
    request = MagicMock(spec=httpx.Request)
    request.method = "GET"
    request.url = "http://example.com/search"
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.request = request
    return httpx.HTTPStatusError(f"{status_code} error", request=request, response=response)


def _superseis_ok_html() -> str:
    """Minimal valid Superseis-ish HTML for ``_parse_superseis``.

    The parser only needs ``product-thumb`` divs with ``data-product-price``
    + ``data-product-name`` attributes; we keep it small.
    """
    return (
        "<html><body>"
        '<div class="product-thumb" data-product-price="\u20b2 3.600">'
        '  <a href="/product/123-harina" data-product-name="Harina 1 kg"></a>'
        "</div>"
        "</body></html>"
    )


# ─── Classifier (PR2 helper extended in PR6) ──────────────────────


def test_default_classifier_httpx_429_is_transient() -> None:
    """429 is rate-limit; we should retry."""
    err = _make_httpx_error(429)
    assert default_is_transient(err) is True


def test_default_classifier_httpx_5xx_is_transient() -> None:
    """5xx is server-side, transient."""
    for code in (500, 502, 503, 504):
        assert default_is_transient(_make_httpx_error(code)) is True, code


@pytest.mark.parametrize("code", [400, 401, 403, 404, 410])
def test_default_classifier_httpx_4xx_other_is_terminal(code: int) -> None:
    """Non-429 4xx is a client error; retrying won't help."""
    assert default_is_transient(_make_httpx_error(code)) is False, code


def test_default_classifier_httpx_connect_error_is_transient() -> None:
    """Transport-level failures (no status) are transient."""
    err = httpx.ConnectError("connection refused")
    assert default_is_transient(err) is True


# ─── Scraper wiring ───────────────────────────────────────────────


def test_scraper_recovers_from_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx.Client.get raises 429 twice, then returns a valid page.

    The retry helper should retry on the transient 429 and succeed on
    the 3rd attempt. We patch ``_client`` inside ``app.integrations.scrapers``
    so the real ``_client()`` context manager still works (calls
    ``__enter__`` / ``__exit__``) but yields a fake client whose ``.get``
    is the controlled one.
    """
    sleeper = FakeSleeper()
    real_client = MagicMock(spec=httpx.Client)
    real_response = MagicMock()
    real_response.text = _superseis_ok_html()
    real_response.raise_for_status = MagicMock(return_value=None)

    call_count = {"n": 0}

    def fake_get(*args: object, **kwargs: object) -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise _make_httpx_error(429)
        return real_response

    real_client.get = fake_get

    fake_client_instance = MagicMock()
    fake_client_instance.__enter__ = lambda self: real_client
    fake_client_instance.__exit__ = lambda self, *args: None

    monkeypatch.setattr("app.integrations.scrapers._client", lambda: fake_client_instance)

    # Patch retry_transient inside the scrapers module to use the fake
    # sleeper and the default classifier (which already knows 429 is
    # transient). This is the seam the wiring introduces.
    monkeypatch.setattr(
        "app.integrations.scrapers.retry_transient",
        lambda fn, *, attempts=3, op_name="operation": retry_transient(
            fn, sleep=sleeper, attempts=attempts, op_name=op_name
        ),
    )

    result = scrape_superseis("harina")

    assert result.ok, f"expected success, got error={result.error!r}"
    assert len(result.matches) >= 1, "expected parsed product"
    assert call_count["n"] == 3, f"expected 3 attempts, got {call_count['n']}"
    # 2 sleeps between the 3 attempts
    assert len(sleeper.calls) == 2


def test_scraper_raises_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """httpx.Client.get raises 404.

    The classifier treats 4xx-other as terminal; ``retry_transient`` must
    re-raise immediately without retries. The outer ``except httpx.HTTPError``
    in ``scrape_superseis`` then turns it into a ``ScrapeResult(error=...)``.
    """
    sleeper = FakeSleeper()
    real_client = MagicMock(spec=httpx.Client)
    call_count = {"n": 0}

    def fake_get(*args: object, **kwargs: object) -> MagicMock:
        call_count["n"] += 1
        raise _make_httpx_error(404)

    real_client.get = fake_get

    fake_client_instance = MagicMock()
    fake_client_instance.__enter__ = lambda self: real_client
    fake_client_instance.__exit__ = lambda self, *args: None

    monkeypatch.setattr("app.integrations.scrapers._client", lambda: fake_client_instance)
    monkeypatch.setattr(
        "app.integrations.scrapers.retry_transient",
        lambda fn, *, attempts=3, op_name="operation": retry_transient(
            fn, sleep=sleeper, attempts=attempts, op_name=op_name
        ),
    )

    result = scrape_superseis("harina")

    assert result.ok is False
    assert "fetch failed" in (result.error or "")
    assert call_count["n"] == 1, f"4xx must not retry; expected 1 attempt, got {call_count['n']}"
    assert sleeper.calls == [], "4xx must not trigger backoff"


# ─── Backup wiring ────────────────────────────────────────────────


def test_backup_retries_on_db_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    """``derive_key`` raises ``sqlite3.OperationalError("database is locked")``
    twice, then succeeds. ``encrypt_backup`` (which calls ``derive_key`` inside
    the retry-wrapped closure) should retry and succeed on the 3rd attempt.
    """
    sleeper = FakeSleeper()
    real_derive_key = None
    # Import inside the test so the monkeypatch on the module attribute
    # resolves to the same object the wrapped helper calls.
    from app.services import backup_crypto

    real_derive_key = backup_crypto.derive_key
    call_count = {"n": 0}

    def flaky_derive_key(dni: str, salt: bytes) -> bytes:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return real_derive_key(dni, salt)

    monkeypatch.setattr(backup_crypto, "derive_key", flaky_derive_key)
    monkeypatch.setattr(
        backup_crypto,
        "retry_transient",
        lambda fn, *, attempts=3, op_name="operation": retry_transient(
            fn, sleep=sleeper, attempts=attempts, op_name=op_name
        ),
    )

    blob = encrypt_backup(b"hello world", dni="1234567")

    assert isinstance(blob, bytes) and len(blob) > 0
    assert call_count["n"] == 3, (
        f"expected 3 derive_key calls (2 failures + 1 success), got {call_count['n']}"
    )
    assert len(sleeper.calls) == 2  # 2 backoffs between 3 attempts


def test_backup_raises_on_integrity_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``derive_key`` raises ``sqlite3.IntegrityError`` (NOT classified as
    transient). ``encrypt_backup`` must re-raise immediately; no retries,
    no backoff.
    """
    sleeper = FakeSleeper()
    from app.services import backup_crypto

    call_count = {"n": 0}

    def failing_derive_key(dni: str, salt: bytes) -> bytes:
        call_count["n"] += 1
        raise sqlite3.IntegrityError("UNIQUE constraint failed: salt.salt_id")

    monkeypatch.setattr(backup_crypto, "derive_key", failing_derive_key)
    monkeypatch.setattr(
        backup_crypto,
        "retry_transient",
        lambda fn, *, attempts=3, op_name="operation": retry_transient(
            fn, sleep=sleeper, attempts=attempts, op_name=op_name
        ),
    )

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint"):
        encrypt_backup(b"hello world", dni="1234567")

    assert call_count["n"] == 1, (
        f"IntegrityError is terminal; expected 1 attempt, got {call_count['n']}"
    )
    assert sleeper.calls == [], "terminal errors must not trigger backoff"


# ─── Attempts cap honored ─────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture",
    ["scraper", "backup"],
    ids=["scraper_attempts_3_cap", "backup_attempts_3_cap"],
)
def test_both_honor_attempts_3_cap(fixture: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """With ``attempts=3`` and a persistently-transient error, the wrapped
    function must be called exactly 3 times, then raise.
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    if fixture == "scraper":
        real_client = MagicMock(spec=httpx.Client)

        def fake_get(*args: object, **kwargs: object) -> MagicMock:
            call_count["n"] += 1
            raise _make_httpx_error(503)

        real_client.get = fake_get
        fake_client_instance = MagicMock()
        fake_client_instance.__enter__ = lambda self: real_client
        fake_client_instance.__exit__ = lambda self, *args: None

        monkeypatch.setattr("app.integrations.scrapers._client", lambda: fake_client_instance)
        monkeypatch.setattr(
            "app.integrations.scrapers.retry_transient",
            lambda fn, *, attempts=3, op_name="operation": retry_transient(
                fn, sleep=sleeper, attempts=attempts, op_name=op_name
            ),
        )

        # The scraper catches ``httpx.HTTPError`` externally and turns
        # exhausted retries into a ``ScrapeResult(error=...)`` rather than
        # propagating. Verify the wrapper stopped at 3 and the result is
        # the expected error path.
        result = scrape_superseis("harina")
        assert result.ok is False
        assert "503" in (result.error or "") or "fetch failed" in (result.error or "")
        assert call_count["n"] == 3
    else:
        from app.services import backup_crypto

        def always_locked(dni: str, salt: bytes) -> bytes:
            call_count["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(backup_crypto, "derive_key", always_locked)
        monkeypatch.setattr(
            backup_crypto,
            "retry_transient",
            lambda fn, *, attempts=3, op_name="operation": retry_transient(
                fn, sleep=sleeper, attempts=attempts, op_name=op_name
            ),
        )

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            encrypt_backup(b"hello world", dni="1234567")
        assert call_count["n"] == 3

    # attempts=3 -> 2 backoffs between attempts (per the helper docstring).
    assert len(sleeper.calls) == 2, (
        f"expected 2 backoffs between 3 attempts, got {len(sleeper.calls)}: {sleeper.calls}"
    )
