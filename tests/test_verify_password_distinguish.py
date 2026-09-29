"""tests/test_verify_password_distinguish.py — distinguish corrupt hash from bad password.

Phase 1B ticket #7: verify_password returns False on every error, making it
impossible to tell "user typo" from "corrupted DB hash". Per the audit
(SASKIA_ARCHITECTURE_REFACTOR_PLAN_2026-09-24.md F8), this masks real
production incidents.

Fix: add `verify_password_or_raise(plain, hashed)` that propagates
ValueError/TypeError so callers that care (admin tools, login error
forensics) can distinguish bad-password from corruption. The original
`verify_password` keeps its contract (returns False on any error)
to avoid breaking existing call sites.
"""
from __future__ import annotations

import pytest

# ─── Existing contract preservation ──────────────────────────────────────────


def test_verify_password_still_returns_false_on_garbage_hash():
    """Backwards compat: verify_password with non-bcrypt hash → False, no raise."""
    from app.auth import verify_password

    # Garbage that isn't a valid bcrypt hash
    result = verify_password("anything", "not-a-bcrypt-hash-at-all")
    assert result is False


def test_verify_password_still_returns_false_on_empty_hash():
    """Backwards compat: verify_password with empty hash → False, no raise."""
    from app.auth import verify_password

    result = verify_password("anything", "")
    assert result is False


def test_verify_password_returns_true_on_correct_password():
    """Sanity: happy path still works."""
    from app.auth import hash_password, verify_password

    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


# ─── New contract: verify_password_or_raise ─────────────────────────────────


def test_verify_password_or_raise_propagates_corruption():
    """Garbage hash → raises ValueError (corruption), not returns False."""
    from app.auth import verify_password_or_raise

    with pytest.raises((ValueError, TypeError)):
        verify_password_or_raise("anything", "not-a-bcrypt-hash-at-all")


def test_verify_password_or_raise_propagates_empty_hash():
    """Empty hash → raises ValueError."""
    from app.auth import verify_password_or_raise

    with pytest.raises((ValueError, TypeError)):
        verify_password_or_raise("anything", "")


def test_verify_password_or_raise_returns_true_on_correct_password():
    """Happy path: returns True (not raises)."""
    from app.auth import hash_password, verify_password_or_raise

    h = hash_password("secret123")
    assert verify_password_or_raise("secret123", h) is True


def test_verify_password_or_raise_returns_false_on_wrong_password():
    """Wrong password: returns False (not raises) — distinct from corruption."""
    from app.auth import hash_password, verify_password_or_raise

    h = hash_password("secret123")
    assert verify_password_or_raise("wrong", h) is False
