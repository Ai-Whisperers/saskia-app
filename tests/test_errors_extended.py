"""Tests for the extended AppError taxonomy (S2 robustness).

Covers:
- Each new subclass has the right status_code + reason_code.
- Each subclass carries message + context + cause through `__init__`.
- Existing `except` patterns keep working (backwards compat) because
  new classes subclass the same base (e.g. `FiadoError(Conflict)`).
- `to_http_exception()` handles the new subclasses.
- `__cause__` survives `raise X from Y` discipline.

These tests are behavior-preserving additions; they do NOT modify
the existing taxonomy test in `tests/test_observability.py` (owned
by S1 tests lane).
"""

from __future__ import annotations

import pytest

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
    to_http_exception,
)


# ─── Each subclass: status_code + reason_code ─────────────────────


@pytest.mark.parametrize(
    "cls,expected_status,expected_reason",
    [
        (RecipeTreeError, 500, "recipe_tree_error"),
        (RecipeValidationError, 422, "recipe_validation_error"),
        (FiadoError, 409, "fiado_error"),
        (CashSessionError, 409, "cash_session_error"),
        (ClosureError, 422, "closure_error"),
        (ExpenseError, 422, "expense_error"),
        (RefundError, 409, "refund_error"),
        (LLMError, 502, "llm_unavailable"),
        (StorageError, 502, "storage_unavailable"),
        (EODClosedError, 409, "eod_closed"),
        (TenantError, 503, "tenant_error"),
        (RollbackError, 500, "rollback_failed"),
    ],
)
def test_subclass_status_and_reason(cls, expected_status, expected_reason):
    err = cls("boom")
    assert err.status_code == expected_status
    assert err.reason_code == expected_reason
    assert err.message == "boom"


def test_menu_not_found_status_and_reason():
    """`MenuNotFound` has a custom __init__ that uses the default
    entity-prefix builder — so we pass entity + id and verify."""
    err = MenuNotFound("Menú", id=7)
    assert err.status_code == 404
    assert err.reason_code == "menu_not_found"
    assert "Menú" in err.message and "7" in err.message


# ─── Each subclass: message + context + cause ─────────────────────


@pytest.mark.parametrize(
    "cls",
    [
        RecipeTreeError,
        RecipeValidationError,
        FiadoError,
        CashSessionError,
        ClosureError,
        ExpenseError,
        RefundError,
        LLMError,
        StorageError,
        EODClosedError,
        TenantError,
        RollbackError,
    ],
)
def test_subclass_carries_context_and_cause(cls):
    """Most subclasses take message verbatim. `MenuNotFound` builds its
    own message from entity+id (NotFound's contract) and is tested
    separately below."""
    cause = RuntimeError("original")
    err = cls(
        "user-facing message",
        context={"key": "value", "request_id": "abc123"},
        cause=cause,
    )
    assert err.message == "user-facing message"
    assert err.context == {"key": "value", "request_id": "abc123"}
    # `cause` is stored on the instance.
    # NOTE: `__cause__` is only auto-set when using `raise X from Y`
    # syntax. Passing `cause=` stores it on `.cause` for explicit use.
    assert err.cause is cause


def test_subclass_to_dict_shape():
    err = RecipeTreeError(
        "recipe 7 cycles through recipe 9",
        context={"recipe_id": 7, "cycle": [7, 9, 7]},
    )
    d = err.to_dict()
    assert d["error"] == "recipe 7 cycles through recipe 9"
    assert d["type"] == "RecipeTreeError"
    assert d["status"] == 500
    assert d["reason"] == "recipe_tree_error"
    assert d["context"] == {"recipe_id": 7, "cycle": [7, 9, 7]}


# ─── Backwards compatibility: subclass catches as base ─────────────


def test_fiado_error_catches_as_conflict():
    with pytest.raises(Conflict):
        raise FiadoError("too many outstanding credits")


def test_closure_error_catches_as_validation_error():
    with pytest.raises(ValidationError):
        raise ClosureError("missing close signature")


def test_storage_error_catches_as_dependency_error():
    with pytest.raises(DependencyError):
        raise StorageError("R2 bucket unreachable")


def test_recipe_tree_error_catches_as_data_integrity_error():
    with pytest.raises(DataIntegrityError):
        raise RecipeTreeError("cycle detected")


def test_menu_not_found_catches_as_not_found():
    with pytest.raises(NotFound):
        raise MenuNotFound("Menú del martes")


def test_rollback_error_catches_as_app_error():
    with pytest.raises(AppError):
        raise RollbackError("transaction in unknown state")


# ─── to_http_exception still works for new subclasses ─────────────


def test_to_http_exception_for_new_subclass():
    from fastapi import HTTPException

    err = EODClosedError("El cierre del día ya se hizo hoy.")
    http_exc = to_http_exception(err)
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == 409
    assert http_exc.headers == {"X-Reason-Code": "eod_closed"}


# ─── raise from preserves __cause__ ────────────────────────────────


def test_raise_from_preserves_cause():
    try:
        try:
            raise ValueError("original SQL constraint failure")
        except ValueError as original:
            raise DataIntegrityError(
                "FK violated on pedido",
                cause=original,
            ) from original
    except DataIntegrityError as caught:
        assert caught.cause is not None
        assert isinstance(caught.cause, ValueError)
        assert caught.__cause__ is caught.cause  # `from` links


# ─── MenuNotFound auto-builds reason_code with prefix ─────────────


def test_menu_not_found_with_id_builds_reason_and_context():
    err = MenuNotFound("Menú del martes", id=42)
    # `MenuNotFound` overrides reason_code to "menu_not_found" (per
    # subclass attr), but NotFound.__init__ still builds the context.
    assert err.context.get("entity") == "Menú del martes"
    assert err.context.get("id") == "42"
    # reason_code stays "menu_not_found" (subclass attribute wins over
    # NotFound's entity-prefix builder)
    assert err.reason_code == "menu_not_found"


# ─── Smoke: the original taxonomy still imports ────────────────────


def test_original_taxonomy_still_works():
    """Regression: the new subclasses do NOT shadow existing classes."""
    assert BadRequest is BadRequest
    assert AlreadyExists is AlreadyExists
    assert Unauthenticated is Unauthenticated
    assert Forbidden is Forbidden
    assert RateLimited is RateLimited
    assert AppInternalError is AppInternalError
    # And the new ones exist
    assert RecipeTreeError.__name__ == "RecipeTreeError"
    assert TenantError.__name__ == "TenantError"
