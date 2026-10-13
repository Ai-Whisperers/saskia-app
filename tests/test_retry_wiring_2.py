"""tests/test_retry_wiring_2.py — S2 robustness PR7: verify retry_transient
is correctly wired at the call sites for **R2/S3** (storage) and
**SMTP** (outbound email).

The retry helper itself is exhaustively covered by tests/test_retry.py;
the PR6 wiring tests live in tests/test_retry_wiring.py. This file
is the "did PR7's two new wirings land correctly?" gate, parametrized
across two surfaces:

  - **R2 recovers from 503**              (boto3 transient 5xx -> retry)
  - **R2 raises on 4xx**                  (boto3 terminal 4xx -> no retry)
  - **email retries on timeout**          (smtplib transient -> retry)
  - **email raises on bad creds**         (smtplib terminal -> no retry)
  - **both honor attempts=3 cap**         (exhausted -> raise after 3)

For the R2 side we exercise the public functions
(``encrypt_and_upload`` / ``download_and_decrypt``) with a fake
``Storage`` whose ``put`` / ``get`` raise a real
``botocore.exceptions.ClientError`` for the configured HTTP status.
For the email side we exercise the public ``send_email_outbound``
function with a monkeypatched ``_open_and_send`` that injects the
SMTP exception we want — the seam where retry_transient wraps the
send call.

Patching note: both ``app/services/r2_backup.py`` and
``app/integrations/email_outbound.py`` do
``from app.retry import retry_transient`` at import time. To swap
the helper for a ``FakeSleeper``-using version in tests, we patch
``app.retry.retry_transient`` (the source) rather than
``r2_backup.retry_transient`` or ``email_outbound.retry_transient``
(the local re-bindings — those don't take effect once import is done).

Note: the helper lives at ``app/retry.py`` (post-#187 — moved out of
``app/rms/retry.py``). Both source modules are wired against the new
location.

Classifier notes:
  - ``botocore.ClientError(status=5xx|429)``  -> transient (retry)
  - ``botocore.ClientError(status=4xx)``       -> terminal (raise)
  - ``smtplib.SMTPConnectError/SMTPServerDisconnected/socket.timeout`` -> transient
  - ``smtplib.SMTPAuthenticationError``       -> terminal (bad creds)
"""

from __future__ import annotations

import math
import smtplib
import socket
from typing import Any

import pytest
from botocore.exceptions import ClientError

from app.integrations.email_outbound import (
    EmailConfigError,
    EmailOutboundConfig,
    _email_is_transient,
    send_email_outbound,
)
from app.retry import default_is_transient, retry_transient
from app.services.r2_backup import (
    _r2_is_transient,
    download_and_decrypt,
    encrypt_and_upload,
)

# ─── Helpers ──────────────────────────────────────────────────────


class FakeSleeper:
    """Records sleep calls without blocking. Avoids real waits in retries."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _make_boto3_client_error(
    status_code: int, error_code: str = "InternalError"
) -> ClientError:
    """Construct a real ``botocore.exceptions.ClientError`` with the
    given HTTP status. Mirrors what boto3 surfaces when the R2
    endpoint returns a non-2xx response.
    """
    return ClientError(
        error_response={
            "Error": {"Code": error_code, "Message": f"simulated {status_code}"},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        operation_name="PutObject",
    )


def _make_flaky_storage(
    *,
    put_fail: BaseException | None = None,
    put_fail_n: float = 0,
    get_fail: BaseException | None = None,
    get_fail_n: float = 0,
) -> tuple[Any, dict[str, int]]:
    """Build a fake ``Storage`` that fails the first N puts/gets then succeeds.

    ``put_fail_n`` / ``get_fail_n`` = how many times the first calls
    should raise ``put_fail`` / ``get_fail`` before returning successfully.
    Returns ``(storage, counters)`` where ``counters`` is a dict the
    test can read to assert call counts.
    """
    counters: dict[str, int] = {"put": 0, "get": 0}
    data: dict[str, bytes] = {}

    class _Fake:
        def put(self, key: str, value: bytes) -> None:
            counters["put"] += 1
            if put_fail is not None and counters["put"] <= put_fail_n:
                raise put_fail
            data[key] = value

        def get(self, key: str) -> bytes:
            counters["get"] += 1
            if get_fail is not None and counters["get"] <= get_fail_n:
                raise get_fail
            if key not in data:
                raise KeyError(key)
            return data[key]

    return _Fake(), counters


# Sentinel for "fail every call". `math.inf` is portable; comparing
# int<=float is well-defined in Python.
ALWAYS_FAIL: float = math.inf


def _patch_retry_with_sleeper(
    monkeypatch: pytest.MonkeyPatch, sleeper: FakeSleeper, *module_dotted_paths: str
) -> None:
    """Swap the ``retry_transient`` attribute on the given module(s)
    for a version that uses the FakeSleeper. Forwards every kwarg the
    real call sites pass (``attempts``, ``op_name``, ``is_transient``,
    etc.) so we keep the production classifier semantics; only
    ``sleep`` is swapped for the fake.

    Pass FULLY-QUALIFIED attribute paths (e.g.
    ``"app.services.r2_backup.retry_transient"``). monkeypatch.setattr
    splits the last ``.`` as the attribute name and imports the rest;
    without the trailing ``.retry_transient`` it treats the whole
    string as an attribute of the parent module, which fails.

    We patch the destination module (where the call site is) because
    both ``r2_backup.py`` and ``email_outbound.py`` do
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
        # full_dotted is "module.attr"; we want module."attr"
        _module_path, _, attr = full_dotted.rpartition(".")
        assert attr == "retry_transient", (
            f"_patch_retry_with_sleeper only patches .retry_transient, got {full_dotted!r}"
        )
        monkeypatch.setattr(full_dotted, _patched)


# ─── Classifier (covers the gaps default_is_transient doesn't know) ──


def test_default_classifier_does_not_know_boto3_client_error() -> None:
    """Sanity: the default classifier doesn't know about boto3. Our
    custom one does. (If this ever changes, our classifier falls back
    to default, which is fine — but the test pins the gap.)
    """
    err = _make_boto3_client_error(503)
    assert default_is_transient(err) is False
    assert _r2_is_transient(err) is True


def test_default_classifier_does_not_know_smtp_connect_error() -> None:
    """Sanity: the default classifier doesn't know smtplib.* shapes."""
    err = smtplib.SMTPConnectError(421, b"try later")
    assert default_is_transient(err) is False
    assert _email_is_transient(err) is True


# ─── R2 wiring (storage.put / storage.get wrapped in retry) ───────


def test_r2_recovers_from_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Storage.put`` raises ClientError(503) twice, then succeeds.

    ``encrypt_and_upload`` should retry on the transient 5xx and
    succeed on the 3rd attempt. We patch the retry_transient symbol
    at its source module so the FakeSleeper is used in place of
    real ``time.sleep``.
    """
    sleeper = FakeSleeper()
    storage, counters = _make_flaky_storage(
        put_fail=_make_boto3_client_error(503),
        put_fail_n=2,
    )
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.services.r2_backup.retry_transient")

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    plaintext = b"backup snapshot contents"

    ciphertext = encrypt_and_upload(storage, key, "snap.enc", plaintext)
    assert ciphertext  # Fernet ciphertext
    assert counters["put"] == 3, (
        f"expected 3 put calls (2 transient failures + 1 success), got {counters['put']}"
    )
    # 2 sleeps between 3 attempts.
    assert len(sleeper.calls) == 2


def test_r2_raises_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Storage.put`` raises ClientError(400) — the classifier treats
    4xx as terminal, so retry_transient must re-raise immediately.
    No retries, no backoff.
    """
    sleeper = FakeSleeper()
    storage, counters = _make_flaky_storage(
        put_fail=_make_boto3_client_error(400, error_code="InvalidArgument"),
        put_fail_n=ALWAYS_FAIL,
    )
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.services.r2_backup.retry_transient")

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()

    with pytest.raises(ClientError) as exc_info:
        encrypt_and_upload(storage, key, "snap.enc", b"hello")

    # The 400 surfaces — we don't wrap it in StorageError, the caller
    # (run_backup) catches and continues with local-only.
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert counters["put"] == 1, (
        f"4xx must not retry; expected 1 attempt, got {counters['put']}"
    )
    assert sleeper.calls == [], "4xx must not trigger backoff"


def test_r2_get_recovers_from_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror of the put case for the download path. ``Storage.get``
    raises ClientError(503) twice then succeeds; download_and_decrypt
    retries and recovers.
    """
    sleeper = FakeSleeper()
    storage, counters = _make_flaky_storage(
        get_fail=_make_boto3_client_error(503),
        get_fail_n=2,
    )
    # Pre-seed one ciphertext.
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    ciphertext = Fernet(key).encrypt(b"hello world")
    storage.put("snap.enc", ciphertext)  # NOTE: this skips retry (direct call).

    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.services.r2_backup.retry_transient")

    plaintext = download_and_decrypt(storage, key, "snap.enc")
    assert plaintext == b"hello world"
    # 3 get calls (2 transient failures + 1 success).
    assert counters["get"] == 3
    assert len(sleeper.calls) == 2


# ─── Email wiring (SMTP send wrapped in retry) ────────────────────


def _good_email_config() -> EmailOutboundConfig:
    """A config object that passes ``validate()`` (used by every
    email test that wants to get past the config check)."""
    return EmailOutboundConfig(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="alerts@example.com",
        smtp_password="hunter2",
        use_tls=True,
    )


def test_email_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_open_and_send`` raises ``smtplib.SMTPConnectError`` twice
    (simulating a transient network blip) then succeeds. The retry
    helper should recover on the 3rd attempt.
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    def flaky_send(cfg: Any, msg: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise smtplib.SMTPConnectError(421, b"try later")
        # 3rd attempt: pretend it succeeded.

    import app.integrations.email_outbound as email_mod

    monkeypatch.setattr(email_mod, "_open_and_send", flaky_send)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.email_outbound.retry_transient")

    result = send_email_outbound(
        to="ivan@aiwhisperers.dev",
        subject="test retry",
        body="hello",
        cfg=_good_email_config(),
    )
    assert result is True
    assert call_count["n"] == 3, (
        f"expected 3 send calls (2 transient + 1 success), got {call_count['n']}"
    )
    assert len(sleeper.calls) == 2


def test_email_retries_on_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second transient path: ``socket.timeout`` instead of
    ``SMTPConnectError``. The classifier treats both as transient,
    so the wiring should still retry.
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    def flaky_send(cfg: Any, msg: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] < 2:
            raise socket.timeout("read timeout")
        # 2nd attempt succeeds.

    import app.integrations.email_outbound as email_mod

    monkeypatch.setattr(email_mod, "_open_and_send", flaky_send)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.email_outbound.retry_transient")

    result = send_email_outbound(
        to="ivan@aiwhisperers.dev",
        subject="socket timeout retry",
        body="hello",
        cfg=_good_email_config(),
    )
    assert result is True
    assert call_count["n"] == 2


def test_email_raises_on_bad_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_open_and_send`` raises ``smtplib.SMTPAuthenticationError``
    (535 = auth failed). The classifier treats this as TERMINAL — the
    helper must NOT retry. ``send_email_outbound`` returns ``False``
    on terminal failure (caller decides what to do).
    """
    sleeper = FakeSleeper()
    call_count = {"n": 0}

    def failing_send(cfg: Any, msg: Any) -> None:
        call_count["n"] += 1
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")

    import app.integrations.email_outbound as email_mod

    monkeypatch.setattr(email_mod, "_open_and_send", failing_send)
    _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.email_outbound.retry_transient")

    result = send_email_outbound(
        to="ivan@aiwhisperers.dev",
        subject="bad creds",
        body="hello",
        cfg=_good_email_config(),
    )
    # Terminal → False, not raise (the caller treats False as "won't
    # ever succeed, fall back to spool / Sentry").
    assert result is False
    assert call_count["n"] == 1, (
        f"bad creds must not retry; expected 1 attempt, got {call_count['n']}"
    )
    assert sleeper.calls == [], "bad creds must not trigger backoff"


def test_email_raises_on_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing smtp_host surfaces as :class:`EmailConfigError` BEFORE
    the SMTP connection is attempted. The retry helper never runs; we
    get an immediate ``EmailConfigError`` raise from ``send_email_outbound``.
    """
    bad_cfg = EmailOutboundConfig(
        smtp_host="",  # missing
        smtp_port=587,
        smtp_user="alerts@example.com",
        smtp_password="hunter2",
    )

    with pytest.raises(EmailConfigError, match="smtp_host"):
        send_email_outbound(
            to="ivan@aiwhisperers.dev",
            subject="missing config",
            body="hello",
            cfg=bad_cfg,
        )


# ─── Attempts=3 cap honored (parametrized across both surfaces) ───


@pytest.mark.parametrize(
    "fixture",
    ["r2_put", "r2_get", "email"],
    ids=["r2_put_attempts_3_cap", "r2_get_attempts_3_cap", "email_attempts_3_cap"],
)
def test_both_honor_attempts_3_cap(
    fixture: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``attempts=3`` and a persistently-transient error, the
    wrapped function must be called exactly 3 times, then raise.
    """
    sleeper = FakeSleeper()

    if fixture == "r2_put":
        # Always-failing put (always ClientError(503) = transient).
        storage, counters = _make_flaky_storage(
            put_fail=_make_boto3_client_error(503),
            put_fail_n=ALWAYS_FAIL,
        )
        _patch_retry_with_sleeper(monkeypatch, sleeper, "app.services.r2_backup.retry_transient")

        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        with pytest.raises(ClientError) as exc_info:
            encrypt_and_upload(storage, key, "snap.enc", b"hello")
        # The helper raised the underlying boto3 error (not a wrapped
        # StorageError) — preserves the S2 contract of "retry_transient
        # re-raises the original exc on exhaustion".
        assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 503
        assert counters["put"] == 3
    elif fixture == "r2_get":
        # Always-failing get.
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        storage, counters = _make_flaky_storage(
            get_fail=_make_boto3_client_error(503),
            get_fail_n=ALWAYS_FAIL,
        )
        # Pre-seed ciphertext (direct put; no retry).
        ciphertext = Fernet(key).encrypt(b"hello")
        storage.put("snap.enc", ciphertext)

        _patch_retry_with_sleeper(monkeypatch, sleeper, "app.services.r2_backup.retry_transient")

        with pytest.raises(ClientError):
            download_and_decrypt(storage, key, "snap.enc")
        assert counters["get"] == 3
    else:
        # Always-failing email send.
        import app.integrations.email_outbound as email_mod

        call_count = {"n": 0}

        def always_timeout(cfg: Any, msg: Any) -> None:
            call_count["n"] += 1
            raise smtplib.SMTPConnectError(421, b"try later")

        monkeypatch.setattr(email_mod, "_open_and_send", always_timeout)
        _patch_retry_with_sleeper(monkeypatch, sleeper, "app.integrations.email_outbound.retry_transient")

        # send_email_outbound re-raises on exhausted (per its docstring),
        # so we expect the SMTPConnectError to propagate.
        with pytest.raises(smtplib.SMTPConnectError):
            send_email_outbound(
                to="ivan@aiwhisperers.dev",
                subject="exhausted",
                body="hello",
                cfg=_good_email_config(),
            )
        assert call_count["n"] == 3

    # attempts=3 -> 2 backoffs between attempts (per the helper docstring).
    assert len(sleeper.calls) == 2, (
        f"expected 2 backoffs between 3 attempts, got {len(sleeper.calls)}: {sleeper.calls}"
    )
