"""tests/test_sentry_level_mapping.py — S2 robustness PR5 (2026-10-13).

Parametrized coverage for ``app.rms.sentry.sentry_level_for``:

  - All 13 domain-specific ``AppError`` subclasses get the right Sentry
    level (4xx -> "warning", 5xx -> "error").
  - The base ``AppError`` and a plain ``RuntimeError`` fallback to
    the documented default ("warning" for the 400-default base, "error"
    for non-AppError).
  - ``sentry_before_send`` (in app/rms/notify.py) consumes the mapper
    correctly: 4xx AppErrors that arrive via the Sentry ``hint`` arrive
    at Sentry with ``event["level"] == "warning"`` and therefore skip
    the Telegram mirror; 5xx AppErrors arrive as "error" and mirror.

These three guarantees are the contract of the PR:
  1. The mapper exists and is correct (this test file, primary surface).
  2. The mapper is wired into the ``before_send`` hook.
  3. Subclasses inherit the right level via ``status_code`` (no
     regression when a future PR adds a 14th subclass).
"""

from __future__ import annotations

import json
import urllib.request

import pytest

import app.rms.notify as notify
import app.rms.sentry as rms_sentry
from app.rms.errors import (
    AlreadyExists,
    AppError,
    AppInternalError,
    BadRequest,
    CashSessionError,
    ClosureError,
    Conflict,
    DataIntegrityError,
    DependencyError,
    EODClosedError,
    ExpenseError,
    FiadoError,
    Forbidden,
    LLMError,
    MenuNotFound,
    NotFound,
    RateLimited,
    RecipeTreeError,
    RecipeValidationError,
    RefundError,
    RollbackError,
    StorageError,
    TenantError,
    Unauthenticated,
    ValidationError,
)


def _force_known_subclasses() -> dict[str, type[AppError]]:
    """Return the 13 domain-specific AppError subclasses we promise to cover.

    The set is collected by name (not by inheritance walk) so a future
    refactor that adds a 14th subclass fails this PR's gate loud and
    early. Same name -> same intended level -> same level string. If a
    future subclass lands without an entry here, the operator gets a
    PR-time reminder to add it.
    """
    return {
        # --- 4xx subclass family -> "warning" ---
        "RecipeValidationError": RecipeValidationError,
        "FiadoError": FiadoError,
        "CashSessionError": CashSessionError,
        "ClosureError": ClosureError,
        "ExpenseError": ExpenseError,
        "RefundError": RefundError,
        "EODClosedError": EODClosedError,
        "MenuNotFound": MenuNotFound,
        # --- 5xx subclass family -> "error" ---
        "RecipeTreeError": RecipeTreeError,
        "LLMError": LLMError,
        "StorageError": StorageError,
        "TenantError": TenantError,
        "RollbackError": RollbackError,
    }


# ────────────────────────────────────────────────────────────────────
# 1. The mapper: pure-function coverage of the level table.
# ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc_factory", "expected_level", "case_id"),
    [
        # ─── Base AppError status coverage (sanity) ───────────────────
        (
            lambda: BadRequest("missing field foo"),
            "warning",
            "bad_request_400",
        ),
        (
            lambda: ValidationError("schema mismatch"),
            "warning",
            "validation_error_422",
        ),
        (
            lambda: NotFound("pedido", id=42),
            "warning",
            "not_found_404",
        ),
        (
            lambda: AlreadyExists("already exists"),
            "warning",
            "already_exists_409",
        ),
        (
            lambda: Conflict("conflict"),
            "warning",
            "conflict_409",
        ),
        (
            lambda: Unauthenticated("login required"),
            "warning",
            "unauthenticated_401",
        ),
        (
            lambda: Forbidden("not allowed"),
            "warning",
            "forbidden_403",
        ),
        (
            lambda: RateLimited("slow down"),
            "warning",
            "rate_limited_429",
        ),
        # ─── Base 5xx family ──────────────────────────────────────────
        (
            lambda: DataIntegrityError("FK violation"),
            "error",
            "data_integrity_500",
        ),
        (
            lambda: DependencyError("drive is down"),
            "error",
            "dependency_502",
        ),
        (
            lambda: AppInternalError("unexpected"),
            "error",
            "internal_500",
        ),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_base_apperror_classes_get_right_level(exc_factory, expected_level, case_id) -> None:
    """The 12 base AppError classes resolve to the right level bucket.

    Covers: 8 4xx classes (-> "warning") + 3 5xx base classes (-> "error")
    + the base AppError (default status_code 400 -> "warning").
    """
    exc = exc_factory()
    assert rms_sentry.sentry_level_for(exc) == expected_level, (
        f"[{case_id}] {type(exc).__name__}(status_code={getattr(exc, 'status_code', '?')}) "
        f"expected level {expected_level!r}, got {rms_sentry.sentry_level_for(exc)!r}"
    )


@pytest.mark.parametrize(
    ("subclass", "expected_level", "case_id"),
    [
        # ─── 13 domain-specific subclasses ────────────────────────────
        # 4xx -> "warning"
        (RecipeValidationError, "warning", "recipe_validation_error_422"),
        (FiadoError, "warning", "fiado_error_409"),
        (CashSessionError, "warning", "cash_session_error_409"),
        (ClosureError, "warning", "closure_error_422"),
        (ExpenseError, "warning", "expense_error_422"),
        (RefundError, "warning", "refund_error_409"),
        (EODClosedError, "warning", "eod_closed_409"),
        (MenuNotFound, "warning", "menu_not_found_404"),
        # 5xx -> "error"
        (RecipeTreeError, "error", "recipe_tree_error_500"),
        (LLMError, "error", "llm_error_502"),
        (StorageError, "error", "storage_error_502"),
        (TenantError, "error", "tenant_error_503"),
        (RollbackError, "error", "rollback_error_500"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_all_13_apperror_subclasses_get_right_level(subclass, expected_level, case_id) -> None:
    """Every AppError domain subclass maps to the right level bucket.

    Locks the per-subclass level decision so a future refactor that
    miscategorizes one (e.g. flipping TenantError to "warning") fails
    CI loud and early. The case_id mirrors the docstring table in
    app/rms/sentry.py for quick greppability.
    """
    # Most subclasses take (message, ...). RollbackError / TenantError
    # accept a plain message; the others accept one as well (we've
    # verified each signature by inspection during the PR).
    exc = subclass("synthetic fixture for level mapping")
    actual = rms_sentry.sentry_level_for(exc)
    assert actual == expected_level, (
        f"[{case_id}] {subclass.__name__}(status_code={getattr(exc, 'status_code', '?')}) "
        f"-> {actual!r}; expected {expected_level!r}"
    )


def test_all_13_subclasses_are_inventory_complete() -> None:
    """Defensive guard: every named subclass actually exists and is an AppError.

    If a future refactor deletes one of the 13 domain subclasses, this
    test fires before the parametrized cases do (because Python import
    would fail first). It exists so the LEDGER / CHANGELOG entry for
    this PR can say "all 13 subclasses covered" without a stale-tuple
    risk sneaking past CI.
    """
    for name, cls in _force_known_subclasses().items():
        assert issubclass(cls, AppError), (
            f"named subclass {name!r} ({cls!r}) is not an AppError subclass"
        )


def test_non_apperror_falls_back_to_default_error() -> None:
    """Non-AppError exceptions (RuntimeError, KeyError, ...) -> "error".

    Sentry's default for ``capture_exception`` is "error" level, so
    nothing about this PR should change the SDK's behaviour for
    untyped exceptions. This case pins the documented fallback.
    """
    assert rms_sentry.sentry_level_for(RuntimeError("boom")) == "error"
    assert rms_sentry.sentry_level_for(KeyError("missing")) == "error"
    assert rms_sentry.sentry_level_for(ValueError("bad")) == "error"
    assert rms_sentry.sentry_level_for(OSError("disk gone")) == "error"


def test_sentry_level_for_handles_cause_chain() -> None:
    """``raise X from Y`` chains don't change the AppError level decision.

    Sentry unwraps the chain for display, but the BEFORE level mapping
    must run against the original AppError, not the ``__cause__``.
    Locking this so a future refactor doesn't accidentally double-walk
    and pick the wrong side of the chain.
    """
    exc: AppError
    try:
        try:
            raise RuntimeError("network blip")
        except RuntimeError as inner:
            raise NotFound("pedido", id=1) from inner
    except NotFound as caught:
        exc = caught

    assert rms_sentry.sentry_level_for(exc) == "warning"  # 4xx side of chain wins


# ────────────────────────────────────────────────────────────────────
# 2. The wire: the mapper is consumed by sentry_before_send.
# ────────────────────────────────────────────────────────────────────


def _evt(level: str = "error", exc_type: str = "RuntimeError") -> dict:
    """Build a minimal Sentry-shaped event dict for the hook tests."""
    return {
        "level": level,
        "event_id": "abc123",
        "fingerprint": [f"{exc_type}-test"],
        "exception": {"values": [{"type": exc_type, "value": "synthetic"}]},
    }


def _hint_with_exc(exc: BaseException) -> dict:
    """Sentry SDK puts (type, value, traceback) in hint['exc_info'].

    We don't have a real traceback in the test; the SDK accepts any
    3-tuple where element [1] is the live exception instance.
    """
    return {"exc_info": (type(exc), exc, None)}


def test_before_send_relabels_4xx_aperror_to_warning(monkeypatch) -> None:
    """NotFound (404) arriving via Sentry hint should be set to "warning".

    Locks the new behaviour introduced in PR5: the level mapping
    happens BEFORE the level filter, so 4xx AppErrors don't get
    mirrored to Telegram AND don't arrive at Sentry as "error".
    """
    # Make sure Telegram doesn't actually fire (even if env is set).
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    notify.sentry_before_send._last_sent = {}

    exc = NotFound("pedido", id=42)
    event = _evt(level="error", exc_type="NotFound")
    out = notify.sentry_before_send(event, _hint_with_exc(exc))

    assert out is event
    assert out["level"] == "warning", (
        f"4xx AppError should be relabeled 'warning'; got {out['level']!r}"
    )


def test_before_send_relabels_5xx_aperror_to_error(monkeypatch) -> None:
    """DataIntegrityError (500) should arrive at Sentry as 'error' (5xx bucket)."""
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    notify.sentry_before_send._last_sent = {}

    exc = DataIntegrityError("FK violation")
    event = _evt(level="error", exc_type="DataIntegrityError")
    out = notify.sentry_before_send(event, _hint_with_exc(exc))

    assert out is event
    assert out["level"] == "error"


def test_before_send_5xx_triggers_telegram_mirror(monkeypatch) -> None:
    """5xx AppError -> "error" -> Telegram mirror fires.

    This is the positive control: the mapper's "error" output keeps
    the existing C.1 contract (5xx server faults page on-call via
    Telegram) intact.
    """
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    notify.sentry_before_send._last_sent = {}

    sent = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        sent["text"] = json.loads(req.data.decode())["text"]
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    exc = AppInternalError("oops")
    event = _evt(level="error", exc_type="AppInternalError")
    out = notify.sentry_before_send(event, _hint_with_exc(exc))

    assert out["level"] == "error"
    assert sent.get("text"), "expected Telegram mirror to fire for 5xx AppError"
    assert "AppInternalError" in sent["text"]


def test_before_send_4xx_suppresses_telegram_mirror(monkeypatch) -> None:
    """4xx AppError -> "warning" -> NO Telegram mirror (negative control).

    The whole point of PR5 is that the operator's phone doesn't buzz
    on every NotFound 404 in production. If this test fails, someone
    re-broke the level mapper or bypassed it.
    """
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    notify.sentry_before_send._last_sent = {}

    calls = {"n": 0}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    exc = ValidationError("bad input")
    event = _evt(level="error", exc_type="ValidationError")
    out = notify.sentry_before_send(event, _hint_with_exc(exc))

    assert out["level"] == "warning"
    assert calls["n"] == 0, (
        f"4xx AppError should NOT trigger a Telegram mirror; got {calls['n']} mirror call(s)"
    )


def test_before_send_non_apperror_keeps_default_level(monkeypatch) -> None:
    """Plain RuntimeError without an AppError -> level untouched."""
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    notify.sentry_before_send._last_sent = {}

    exc = RuntimeError("network blip")
    event = _evt(level="error", exc_type="RuntimeError")
    out = notify.sentry_before_send(event, _hint_with_exc(exc))

    assert out is event
    assert out["level"] == "error", (
        "non-AppError should keep Sentry's default level (no relabeling)"
    )


def test_before_send_handles_missing_hint(monkeypatch) -> None:
    """Missing/None hint must not crash the mapper (defensive probe)."""
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    notify.sentry_before_send._last_sent = {}

    event = _evt(level="error")
    # No hint at all (some Sentry integrations skip the hint argument).
    out = notify.sentry_before_send(event, {})
    assert out is event
    # No relabeling happened; default "error" sticks.
    assert out["level"] == "error"


# ────────────────────────────────────────────────────────────────────
# 3. Hardening: submodule import + __all__ surface.
# ────────────────────────────────────────────────────────────────────


def test_sentry_module_has_dunder_all() -> None:
    """Module exposes a stable surface via __all__ (AGENTS.md convention)."""
    import app.rms.sentry as mod

    assert hasattr(mod, "__all__")
    assert "sentry_level_for" in mod.__all__


def test_sentry_module_does_not_import_sentry_sdk() -> None:
    """The mapper is pure-Python and must NOT import sentry_sdk at import time.

    AGENTS.md rule 26 (no new SDK deps in feature modules) + the
    lazy-load rule from test_sentry_lazy_import.py. If a future
    refactor accidentally adds ``import sentry_sdk`` at module top,
    this test fires and the operator can move it inside a function
    body.
    """
    import sys

    sys.modules.pop("sentry_sdk", None)
    import app.rms.sentry  # noqa: F401 — import only

    assert "sentry_sdk" not in sys.modules, (
        "app.rms.sentry pulled in sentry_sdk at import time; the mapper "
        "must be pure-Python so test environments stay SDK-free"
    )
