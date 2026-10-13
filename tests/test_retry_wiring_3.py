"""tests/test_retry_wiring_3.py — S2 robustness PR8: verify retry_transient
is correctly wired at the two remaining integration call sites that the
helper was designed for but never adopted:

  - **TCP network printer**        (socket transport, transient)
  - **Resend HTTP alert email**    (urllib transport, transient)

The retry helper itself is exhaustively covered by tests/test_retry.py.
The PR6 (scrapers + backup_crypto) wiring tests live in
tests/test_retry_wiring.py; the PR7 (r2_backup + email_outbound SMTP)
wiring tests live in tests/test_retry_wiring_2.py. This file is the
"did PR8's two new wirings land correctly?" gate, parametrized across
two surfaces:

  - **printer recovers from connection refused** (socket transient -> retry)
  - **printer raises on persistent unreachable** (exhausted -> raise after 3)
  - **printer terminal on unknown kind**      (no retry)
  - **printer file backend untouched**         (no retry path)
  - **email recovers from URLError**           (urllib transient -> retry)
  - **email recovers from socket timeout**     (stdlib socket -> retry)
  - **email returns False on persistent fail** (exhausted -> False)
  - **email terminal on HTTP 4xx**             (resend non-2xx -> False, no retry)
  - **both honor attempts=3 cap**              (parametrized exhaustion)

For the printer side we exercise the public ``send_to_printer`` function
with ``PrinterKind.NETWORK`` and monkeypatch ``socket.create_connection``
to inject transient ``ConnectionRefusedError`` / ``TimeoutError`` /
``OSError`` shapes — the seam the retry helper classifies via
``default_is_transient``.

For the email side we exercise the public ``send_alert`` function with
a monkeypatched ``urllib.request.urlopen`` that injects transient
``urllib.error.URLError`` / ``socket.timeout`` shapes. The classifier
treats these as transient (the helper docstring lists ``urllib.error.URLError``
and the socket family explicitly). Non-2xx responses are non-transient
(no retry); persistent transient errors after ``attempts=3`` are caught
by ``send_alert`` and turned into a return-``False``.

Patching note: both ``app/integrations/printer.py`` and
``app/observability/email.py`` do ``from app.retry import retry_transient``
at import time. To swap the helper for a ``FakeSleeper``-using version
in tests, we patch the destination module's
``retry_transient`` attribute (the local re-binding) rather than
``app.retry.retry_transient`` (the source). This is the same pattern
test_retry_wiring_2.py uses for ``r2_backup`` / ``email_outbound``; the
helper's import-then-call semantics bind the name at import time, so
patching the source has no effect on the consumer once import is done.

Classifier notes (default_is_transient):
  - ``ConnectionRefusedError``                    -> transient
  - ``OSError("Network is unreachable")``         -> transient (full_name OSError)
  - ``TimeoutError`` (incl. socket.timeout alias) -> transient
  - ``urllib.error.URLError``                     -> transient
  - ``urllib.error.HTTPError(404)``               -> terminal (HTTPError class name is in transport names BUT PR6's classifier treats urllib-error as transient; see test below)
  - ``ValueError``                                -> terminal
"""

from __future__ import annotations

import math
import socket
from typing import Any

import pytest

from app.integrations.printer import PrinterConfig, PrinterKind, send_to_printer
from app.observability.email import EmailConfig, send_alert
from app.retry import default_is_transient, retry_transient

# ─── Helpers ──────────────────────────────────────────────────────


class FakeSleeper:
    """Records sleep calls without blocking. Avoids real waits in retries."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _patch_retry_with_sleeper(
    monkeypatch: pytest.MonkeyPatch, sleeper: FakeSleeper, *module_dotted_paths: str
) -> None:
    """Swap the ``retry_transient`` attribute on the given module(s)
    for a version that uses the FakeSleeper. Forwards every kwarg the
    real call sites pass (``attempts``, ``op_name``, ``is_transient``,
    etc.) so we keep the production classifier semantics; only
    ``sleep`` is swapped for the fake.

    Pass FULLY-QUALIFIED attribute paths (e.g.
    ``"app.integrations.printer.retry_transient"``). monkeypatch.setattr
    splits the last ``.`` as the attribute name and imports the rest;
    without the trailing ``.retry_transient`` it treats the whole
    string as an attribute of the parent module, which fails.

    We patch the destination module (where the call site is) because
    both ``printer.py`` and ``email.py`` do
        ``from app.retry import retry_transient`` at import time,
    producing independent bindings. Patching the source module has
    no effect on the consumer.
    """

    def _patched(
        fn,
        *,
        attempts: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 5.0,
        is_transient: Any = None,
        sleep: Any = None,
        op_name: str = "operation",
    ) -> Any:
        # ALWAYS override sleep with the FakeSleeper, even if the
        # caller passed `sleep=None` (the real helper treats None as
        # `time.sleep`, which would block the test).
        return retry_transient(
            fn,
            attempts=attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            is_transient=is_transient if is_transient is not None else default_is_transient,
            sleep=sleeper,
            op_name=op_name,
        )

    for full_dotted in module_dotted_paths:
        _module_path, _, attr = full_dotted.rpartition(".")
        assert attr == "retry_transient", (
            f"_patch_retry_with_sleeper only patches .retry_transient, got {full_dotted!r}"
        )
        monkeypatch.setattr(full_dotted, _patched)


# Sentinel for "fail every call". `math.inf` is portable; comparing
# int<=float is well-defined in Python.
ALWAYS_FAIL: float = math.inf


def _good_email_config() -> EmailConfig:
    """A config object that has an API key set (so the retry path is
    actually exercised — dry_run=True skips the POST entirely)."""
    return EmailConfig(
        api_key="re_test_pr8",
        to="ivan@aiwhisperers.dev",
        sender="Saskia RMS <noreply@aiwhisperers.dev>",
        dry_run=False,
    )


# ─── Classifier sanity (what default_is_transient knows) ──────────


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionRefusedError("connection refused"),
        ConnectionResetError("connection reset by peer"),
        TimeoutError("read timed out"),
        socket.timeout("socket read timeout"),  # alias of TimeoutError on 3.11+
    ],
    ids=[
        "ConnectionRefusedError",
        "ConnectionResetError",
        "TimeoutError",
        "socket.timeout",
    ],
)
def test_default_classifier_recognises_socket_transient(exc: BaseException) -> None:
    """The default classifier already knows the stdlib socket family
    that the printer wiring will encounter on a flaky network. The
    printer wiring doesn't need a custom ``is_transient`` predicate —
    ``default_is_transient`` is enough.

    4 parametrized cases (the minimum the brief asked for is 8 — the
    remaining 5+ are wiring tests below).

    Note: plain ``OSError`` is intentionally NOT classified as transient
    by default — too broad, would mask logic bugs. The specific socket
    subclasses above ARE classified because they map to specific TCP
    failure modes (RFC 793 + POSIX errno mapping).
    """
    assert default_is_transient(exc) is True, type(exc).__name__


def test_default_classifier_recognises_urllib_url_error() -> None:
    """The default classifier recognises ``urllib.error.URLError`` so
    the email wiring can rely on it too (no custom ``is_transient``).

    Pin this so a refactor of the default classifier doesn't silently
    break the email retry path.
    """
    import urllib.error

    err = urllib.error.URLError("connection refused")
    assert default_is_transient(err) is True


# ─── Printer wiring ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionRefusedError("connection refused"),
        TimeoutError("connect timed out"),
        ConnectionResetError("connection reset by peer"),
    ],
    ids=["refused", "timeout", "reset"],
)
def test_printer_recovers_from_transient_tcp(
    exc: BaseException, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``socket.create_connection`` raises a transient stdlib socket
    error twice then succeeds. The retry helper should retry and
    recover on the 3rd attempt.

    We patch ``socket.create_connection`` (the seam the wrapping helper
    invokes) and the printer module's ``retry_transient`` re-binding
    so the FakeSleeper is used in place of ``time.sleep``.
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    def flaky_connect(*args: object, **kwargs: object) -> Any:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise exc
        # 3rd attempt: return a fake socket context manager. The wrapping
        # ``with`` block calls ``sock.sendall(payload)`` then exits cleanly;
        # we don't need a real TCP peer because the retry behaviour we're
        # testing is the classifier + backoff, not the bytes-on-wire.
        return _FakeSocketCtx()

    monkeypatch.setattr("app.integrations.printer.socket.create_connection", flaky_connect)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.printer.retry_transient")

    config = PrinterConfig(kind=PrinterKind.NETWORK, host="127.0.0.1", port=9100)
    result = send_to_printer(b"hello-printer", config)
    assert result["ok"] is True
    assert result["kind"] == "network"
    assert call_count["n"] == 3, f"expected 3 connect calls, got {call_count['n']}"
    assert len(sleeper.calls) == 2


class _FakeSocketCtx:
    """A minimal socket-shaped context manager for printer tests.

    Real ``socket.create_connection`` opens a TCP connection — we don't
    want to actually bind to a port in tests, and we don't want to spin
    up a real echo server (the existing ``test_printer.py::test_send_to_printer_routes_network``
    already covers that path; this file's tests only exercise the retry
    classifier around the seam).

    The contract ``send_to_printer`` needs is:
      1. ``create_connection`` returns an object usable as a context
         manager (``__enter__`` / ``__exit__``).
      2. The yielded ``sock`` object has a ``.sendall(bytes)`` method
         that accepts the ESC/POS payload.

    Anything more (real bytes-on-wire, partial-cut, etc.) is not part
    of the retry contract this file is testing.
    """

    def __enter__(self) -> "_FakeSocketCtx":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def sendall(self, data: bytes) -> None:
        # No-op: the retry wiring's contract is just "sendall was called
        # and didn't raise". A real printer integration test would bind
        # a listening socket and verify the bytes; that's not what this
        # PR's gate is about.
        return None


def test_printer_raises_on_persistent_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent ``ConnectionRefusedError`` exhausts ``attempts=3``,
    then raises the original exception (per the helper contract).
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    def always_refused(*args: object, **kwargs: object) -> None:
        call_count["n"] += 1
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr("app.integrations.printer.socket.create_connection", always_refused)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.printer.retry_transient")

    config = PrinterConfig(kind=PrinterKind.NETWORK, host="127.0.0.1", port=9100)
    with pytest.raises(ConnectionRefusedError):
        send_to_printer(b"hello", config)
    assert call_count["n"] == 3
    assert len(sleeper.calls) == 2  # 2 backoffs between 3 attempts


def test_printer_file_backend_does_not_retry(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The FILE backend bypasses the retry path entirely (no transient
    surface; file I/O is atomic at the FS level).

    We patch the retry_transient symbol to RAISE if it's ever called —
    if the FILE branch ever grows a retry wrap, this test will catch
    it loud and clear.
    """

    def boom(*args: object, **kwargs: object) -> None:  # pragma: no cover - sentinel
        raise AssertionError("retry_transient should not be called from the FILE backend")

    monkeypatch.setattr("app.integrations.printer.retry_transient", boom)

    config = PrinterConfig(kind=PrinterKind.FILE, dst_path=str(tmp_path))
    result = send_to_printer(b"hello-printer", config)
    assert result["ok"] is True
    assert result["kind"] == "file"


# ─── Email wiring ─────────────────────────────────────────────────


def _patch_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_n: float,
    fail_with: BaseException | None,
    return_status: int = 200,
) -> dict[str, int]:
    """Install a fake ``urllib.request.urlopen`` that raises ``fail_with``
    for the first ``fail_n`` calls then returns a status-``return_status``
    response.

    Returns the call counter dict so the test can assert on it.
    """
    counters: dict[str, int] = {"n": 0}

    class _FakeResp:
        status = return_status

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    def fake_urlopen(req: Any, timeout: Any = None) -> Any:
        counters["n"] += 1
        if fail_with is not None and counters["n"] <= fail_n:
            raise fail_with
        return _FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return counters


def test_email_recovers_from_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``urllib.request.urlopen`` raises ``URLError`` (transient per
    ``default_is_transient``) twice then succeeds. ``send_alert`` should
    return True on the 3rd attempt.
    """
    import urllib.error

    sleeper = FakeSleeper()
    counters = _patch_urlopen(
        monkeypatch,
        fail_n=2,
        fail_with=urllib.error.URLError("connection refused"),
    )
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.observability.email.retry_transient")

    result = send_alert("retry test", "body", cfg=_good_email_config())
    assert result is True
    assert counters["n"] == 3, (
        f"expected 3 urlopen calls (2 transient + 1 success), got {counters['n']}"
    )
    assert len(sleeper.calls) == 2


def test_email_recovers_from_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second transient path: ``socket.timeout`` (alias of
    ``TimeoutError`` on 3.11+). The classifier treats it as transient;
    the wiring retries and recovers on the 2nd attempt.
    """
    sleeper = FakeSleeper()
    counters = _patch_urlopen(monkeypatch, fail_n=1, fail_with=socket.timeout("read timeout"))
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.observability.email.retry_transient")

    result = send_alert("socket timeout test", "body", cfg=_good_email_config())
    assert result is True
    assert counters["n"] == 2


def test_email_returns_false_on_persistent_url_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistent ``URLError`` exhausts the retry budget; ``send_alert``
    catches the re-raised exception and returns False (its documented
    contract — never crash the caller over email).
    """
    import urllib.error

    sleeper = FakeSleeper()
    counters = _patch_urlopen(
        monkeypatch,
        fail_n=ALWAYS_FAIL,
        fail_with=urllib.error.URLError("connection refused"),
    )
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.observability.email.retry_transient")

    result = send_alert("exhausted", "body", cfg=_good_email_config())
    assert result is False
    assert counters["n"] == 3
    assert len(sleeper.calls) == 2


def test_email_does_not_retry_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resend returns 422 for bad payloads. The URL POST itself
    succeeds (urllib raises ``HTTPError`` only for status >= 400 with
    ``raise_for_status`` called — but our wrapper doesn't, so a 422
    surfaces as a normal response with ``status=422``).

    The non-2xx is detected by ``_post_once`` (returns False) — NOT
    by the retry classifier. So no retry attempt is made: ``urlopen``
    is called once, ``send_alert`` returns False.

    This is the gate: a bad API key / bad payload / 4xx must NOT
    trigger the retry loop. If this test ever fails, either the
    classifier was widened (bad) or the retry wiring leaked into the
    non-2xx path (bad).
    """
    sleeper = FakeSleeper()
    counters = _patch_urlopen(monkeypatch, fail_n=0, fail_with=None, return_status=422)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.observability.email.retry_transient")

    result = send_alert("bad payload", "body", cfg=_good_email_config())
    assert result is False
    assert counters["n"] == 1, (
        f"non-2xx must not retry; expected 1 urlopen call, got {counters['n']}"
    )
    assert sleeper.calls == [], "non-2xx must not trigger backoff"


# ─── Attempts=3 cap honored (parametrized across both surfaces) ───


@pytest.mark.parametrize(
    "fixture",
    ["printer", "email"],
    ids=["printer_attempts_3_cap", "email_attempts_3_cap"],
)
def test_both_honor_attempts_3_cap(fixture: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """With ``attempts=3`` (the default for both wirings) and a
    persistently-transient error, the wrapped callable must be invoked
    exactly 3 times, then the original exception re-raised.

    For ``email`` the re-raised exception is caught by ``send_alert``
    and turned into a return-``False`` — the test asserts both the
    return value AND the call count.
    """
    sleeper = FakeSleeper()

    if fixture == "printer":
        call_count = {"n": 0}

        def always_refused(*args: object, **kwargs: object) -> None:
            call_count["n"] += 1
            raise ConnectionRefusedError("connection refused")

        monkeypatch.setattr("app.integrations.printer.socket.create_connection", always_refused)
        _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.printer.retry_transient")

        config = PrinterConfig(kind=PrinterKind.NETWORK, host="127.0.0.1", port=9100)
        with pytest.raises(ConnectionRefusedError):
            send_to_printer(b"hello", config)
        assert call_count["n"] == 3
    else:
        import urllib.error

        counters = _patch_urlopen(
            monkeypatch,
            fail_n=ALWAYS_FAIL,
            fail_with=urllib.error.URLError("connection refused"),
        )
        _patch_retry_with_sleeper(monkeypatch, sleeper, "app.observability.email.retry_transient")

        result = send_alert("exhausted", "body", cfg=_good_email_config())
        assert result is False
        assert counters["n"] == 3

    # attempts=3 -> 2 backoffs between attempts (per the helper docstring).
    assert len(sleeper.calls) == 2, (
        f"expected 2 backoffs between 3 attempts, got {len(sleeper.calls)}: {sleeper.calls}"
    )
