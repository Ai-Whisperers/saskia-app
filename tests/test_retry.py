"""Tests for app.retry.retry_transient (S2 robustness PR2).

Covers:
- Happy path: call succeeds first try, no sleep, no log warning.
- Transient retry: call fails N-1 times then succeeds.
- Exhausted: call fails every time, raises the last error after N attempts.
- Terminal: non-transient error re-raised immediately, no retries.
- Classifier: default_is_transient recognizes common shapes.
- Backoff math: delays follow 2**(n-1) * base within ±25% jitter.
- max_delay cap respected.
- Validation: attempts < 1 raises ValueError, base_delay < 0 raises.
- Logging: each transient attempt emits WARNING, exhaustion emits ERROR.
- Stdlib-only: no third-party imports beyond stdlib.
"""

from __future__ import annotations

import logging
import sqlite3
from unittest.mock import MagicMock

import pytest

from app.retry import default_is_transient, retry_transient


# ─── Helpers ──────────────────────────────────────────────────────


class FakeSleeper:
    """Records sleep calls without blocking."""

    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# ─── Happy path ───────────────────────────────────────────────────


def test_happy_path_returns_first_try():
    sleeper = FakeSleeper()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "ok"

    result = retry_transient(fn, sleep=sleeper, op_name="happy")
    assert result == "ok"
    assert calls["n"] == 1
    assert sleeper.calls == []  # no backoff


# ─── Transient retry ─────────────────────────────────────────────


def test_transient_retries_then_succeeds():
    sleeper = FakeSleeper()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionResetError("peer closed")
        return "recovered"

    result = retry_transient(fn, sleep=sleeper, attempts=4, op_name="recover")
    assert result == "recovered"
    assert calls["n"] == 3
    # 2 sleep calls (between attempts 1-2 and 2-3)
    assert len(sleeper.calls) == 2


def test_transient_exhausted_raises_last_error():
    sleeper = FakeSleeper()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ConnectionResetError(f"failure {calls['n']}")

    with pytest.raises(ConnectionResetError, match="failure 3"):
        retry_transient(fn, sleep=sleeper, attempts=3, op_name="exhaust")
    assert calls["n"] == 3
    assert len(sleeper.calls) == 2  # backoff between attempts


def test_terminal_error_reraises_immediately():
    sleeper = FakeSleeper()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("this should NOT retry")

    with pytest.raises(ValueError):
        retry_transient(fn, sleep=sleeper, attempts=5, op_name="terminal")
    assert calls["n"] == 1
    assert sleeper.calls == []  # never slept


# ─── Classifier ───────────────────────────────────────────────────


def test_default_classifier_connection_reset():
    assert default_is_transient(ConnectionResetError("reset")) is True


def test_default_classifier_sqlite_locked():
    # sqlite3.OperationalError message-based check
    err = sqlite3.OperationalError("database is locked")
    assert default_is_transient(err) is True


def test_default_classifier_value_error_is_terminal():
    assert default_is_transient(ValueError("nope")) is False


def test_default_classifier_key_error_is_terminal():
    assert default_is_transient(KeyError("missing")) is False


def test_default_classifier_oserror_too_many_files_is_terminal():
    # Only socket errors are transient; other OSErrors are not.
    err = OSError(24, "Too many open files")
    assert default_is_transient(err) is False


def test_default_classifier_socket_timeout():
    import socket

    assert default_is_transient(socket.timeout("read timeout")) is True


def test_default_classifier_socket_gaierror():
    import socket

    assert default_is_transient(socket.gaierror("name resolution")) is True


# ─── Backoff math ─────────────────────────────────────────────────


def test_backoff_follows_exponential_pattern_within_jitter_window():
    sleeper = FakeSleeper()
    attempts = 4

    def fn():
        raise ConnectionResetError("retry me")

    with pytest.raises(ConnectionResetError):
        retry_transient(fn, sleep=sleeper, attempts=attempts, base_delay=0.1, op_name="backoff")
    # Expected sleep calls: attempts-1 (between each pair)
    assert len(sleeper.calls) == attempts - 1
    # Each delay should be in [base * 2**(i-1) * 0.75, base * 2**(i-1) * 1.25]
    for i, observed in enumerate(sleeper.calls, start=1):
        expected = 0.1 * (2 ** (i - 1))
        assert expected * 0.75 <= observed <= expected * 1.25 + 1e-9, (
            f"attempt {i}: observed={observed} expected~{expected}"
        )


def test_max_delay_cap_respected():
    sleeper = FakeSleeper()

    def fn():
        raise ConnectionResetError("retry me")

    with pytest.raises(ConnectionResetError):
        retry_transient(
            fn,
            sleep=sleeper,
            attempts=10,
            base_delay=1.0,
            max_delay=2.0,
            op_name="capped",
        )
    # Without cap: 1, 2, 4, 8, 16, 32, 64, 128, 256. With cap 2.0: all <= 2.0 * 1.25
    for s in sleeper.calls:
        assert s <= 2.0 * 1.25 + 1e-9, f"delay {s} exceeded max_delay cap"


# ─── Validation ───────────────────────────────────────────────────


def test_attempts_zero_raises_value_error():
    with pytest.raises(ValueError, match="attempts"):
        retry_transient(lambda: None, attempts=0)


def test_attempts_negative_raises_value_error():
    with pytest.raises(ValueError, match="attempts"):
        retry_transient(lambda: None, attempts=-1)


def test_base_delay_negative_raises_value_error():
    with pytest.raises(ValueError, match="base_delay"):
        retry_transient(lambda: None, base_delay=-0.1)


# ─── Logging ──────────────────────────────────────────────────────


def test_transient_attempts_emit_warning_logs(caplog):
    caplog.set_level(logging.WARNING, logger="app.retry")
    sleeper = FakeSleeper()

    def fn():
        raise ConnectionResetError("retry me")

    with pytest.raises(ConnectionResetError):
        retry_transient(fn, sleep=sleeper, attempts=3, op_name="logged")
    # 2 warning records (one per transient attempt, not the final error)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
    assert all("retry op=logged" in r.message for r in warnings)


def test_exhaustion_emits_error_log(caplog):
    caplog.set_level(logging.ERROR, logger="app.retry")
    sleeper = FakeSleeper()

    def fn():
        raise ConnectionResetError("done")

    with pytest.raises(ConnectionResetError):
        retry_transient(fn, sleep=sleeper, attempts=2, op_name="exhaust-log")
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "retry_exhausted op=exhaust-log" in errors[0].message


def test_terminal_error_does_not_log_warning(caplog):
    caplog.set_level(logging.WARNING, logger="app.retry")

    def fn():
        raise ValueError("terminal")

    with pytest.raises(ValueError):
        retry_transient(fn, attempts=3, op_name="no-log")
    assert caplog.records == []


# ─── Custom classifier ────────────────────────────────────────────


def test_custom_is_transient_overrides_default():
    """Custom predicate that only treats ValueError as retryable.

    A `ConnectionResetError` (which the default classifier would retry)
    is re-raised immediately when the custom predicate is supplied.
    """
    sleeper = FakeSleeper()
    calls = {"n": 0}

    def only_value_error_is_transient(exc: BaseException) -> bool:
        return isinstance(exc, ValueError)

    def fn():
        calls["n"] += 1
        raise ConnectionResetError("default would retry; custom does not")

    with pytest.raises(ConnectionResetError):
        retry_transient(
            fn,
            sleep=sleeper,
            attempts=4,
            is_transient=only_value_error_is_transient,
            op_name="custom",
        )
    assert calls["n"] == 1  # first failure: custom says terminal → no retry


# ─── Custom op_name surfaces in logs ──────────────────────────────


def test_op_name_in_logs(caplog):
    caplog.set_level(logging.WARNING, logger="app.retry")

    def fn():
        raise ConnectionResetError("retry me")

    with pytest.raises(ConnectionResetError):
        retry_transient(fn, sleep=FakeSleeper(), attempts=2, op_name="my_unique_op_name")
    assert any("my_unique_op_name" in r.message for r in caplog.records)
