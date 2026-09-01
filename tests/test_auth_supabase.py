"""tests/test_auth_supabase.py — tests for Supabase auth integration.

Uses a fake Supabase client (a small stub) so tests don't need a real
Supabase project to run.
"""

from __future__ import annotations

from unittest.mock import MagicMock

# --- Fake Supabase client for tests ---


class FakeSupabaseClient:
    """In-memory stub of supabase.Client.

    Mirrors the real client's structure: client.auth.<method>().
    """

    def __init__(self):
        self.users: dict[str, str] = {}  # email → password
        self.valid_jwts: dict[str, dict] = {}  # jwt → claims
        self.refresh_tokens: dict[str, str] = {}  # refresh_token → email
        self.sign_out_called = False
        self.reset_called_with: list[str] = []
        self.auth = FakeAuth(self)
        self.admin = FakeAuth(self)  # admin uses same interface for our purposes

    def add_user(self, email: str, password: str, user_id: str = None):
        """Register a user for testing."""
        from uuid import uuid4

        uid = user_id or str(uuid4())
        self.users[email] = password
        # Pre-issue a JWT for this user
        jwt = f"jwt-{uid}"
        self.valid_jwts[jwt] = {
            "sub": uid,
            "email": email,
            "role": "authenticated",
        }
        # Pre-issue a refresh token
        refresh = f"refresh-{uid}"
        self.refresh_tokens[refresh] = email
        return uid, jwt, refresh

    def _build_response(self, access_token, refresh_token, email):
        """Build a fake response object with .session and .user."""
        response = MagicMock()
        response.session = MagicMock()
        response.session.access_token = access_token
        response.session.refresh_token = refresh_token
        response.user = MagicMock()
        claims = self.valid_jwts.get(access_token, {})
        response.user.id = claims.get("sub")
        response.user.email = claims.get("email", email)
        return response


class FakeAuth:
    """Mirrors supabase.Client.auth — all the methods auth_supabase.py calls."""

    def __init__(self, client: "FakeSupabaseClient"):
        self._client = client

    def sign_in_with_password(self, creds):
        email = creds["email"]
        password = creds["password"]
        if self._client.users.get(email) != password:
            raise Exception("Invalid login credentials")
        # Find the user's JWT + refresh token
        uid, jwt, refresh = None, None, None
        for j, claims in self._client.valid_jwts.items():
            if claims.get("email") == email:
                uid = claims["sub"]
                jwt = j
                # Look up matching refresh token
                rt = f"refresh-{uid}"
                if rt in self._client.refresh_tokens:
                    refresh = rt
                break
        return self._client._build_response(jwt, refresh, email)

    def sign_out(self):
        self._client.sign_out_called = True

    def refresh_session(self, refresh_token):
        if refresh_token not in self._client.refresh_tokens:
            raise Exception("Invalid refresh token")
        email = self._client.refresh_tokens[refresh_token]
        uid = next(
            (c["sub"] for c in self._client.valid_jwts.values() if c["email"] == email),
            None,
        )
        from uuid import uuid4

        new_access = f"jwt-{uuid4()}"
        new_refresh = f"refresh-{uuid4()}"
        self._client.valid_jwts[new_access] = {
            "sub": uid,
            "email": email,
            "role": "authenticated",
        }
        self._client.refresh_tokens[new_refresh] = email
        return self._client._build_response(new_access, new_refresh, email)

    def get_claims(self, jwt):
        if jwt not in self._client.valid_jwts:
            return None
        response = MagicMock()
        response.claims = self._client.valid_jwts[jwt]
        return response

    def reset_password_email(self, email):
        self._client.reset_called_with.append(email)


# --- Fixtures ---


import pytest


@pytest.fixture
def fake_supabase(monkeypatch):
    """Return a FakeSupabaseClient and patch get_supabase_client to return it."""
    fake = FakeSupabaseClient()
    fake.add_user("saskia@example.com", "correct-horse-battery-staple")

    import app.auth_supabase as au

    monkeypatch.setattr(au, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(au, "get_supabase_admin", lambda: fake)
    # Enable supabase auth for these tests
    monkeypatch.setattr(au, "SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setattr(au, "SUPABASE_ANON_KEY", "fake-anon")
    monkeypatch.setattr(au, "SUPABASE_SERVICE_ROLE_KEY", "fake-secret")
    monkeypatch.setattr(au, "is_supabase_auth_enabled", lambda: True)

    return fake


# --- Tests ---


def test_sign_in_with_password_success(fake_supabase):
    """Valid email + password returns session dict."""
    from app.auth_supabase import sign_in_with_password

    result = sign_in_with_password("saskia@example.com", "correct-horse-battery-staple")
    assert result is not None
    assert "access_token" in result
    assert "refresh_token" in result
    assert result["email"] == "saskia@example.com"
    assert result["user_id"] is not None


def test_sign_in_with_password_wrong_password(fake_supabase):
    """Wrong password → None (not exception)."""
    from app.auth_supabase import sign_in_with_password

    result = sign_in_with_password("saskia@example.com", "wrong")
    assert result is None


def test_sign_in_with_password_unknown_user(fake_supabase):
    """Unknown email → None."""
    from app.auth_supabase import sign_in_with_password

    result = sign_in_with_password("nobody@example.com", "anything")
    assert result is None


def test_verify_jwt_valid(fake_supabase):
    """Valid JWT returns SupabaseUser with id/email."""
    from app.auth_supabase import verify_jwt

    _, jwt, _ = fake_supabase.add_user("a@b.com", "pw")
    user = verify_jwt(jwt)
    assert user is not None
    assert user.is_authenticated()
    assert user.email == "a@b.com"


def test_verify_jwt_invalid_returns_none(fake_supabase):
    """Invalid JWT returns None."""
    from app.auth_supabase import verify_jwt

    assert verify_jwt("garbage-jwt") is None
    assert verify_jwt("") is None


def test_store_and_get_session(fake_supabase):
    """store_session + get_session_user roundtrip."""
    from app.auth_supabase import (
        SESSION_KEY_ACCESS,
        get_session_user,
        store_session,
    )

    fake_request = MagicMock()
    fake_request.session = {}

    # Issue a real JWT for a user
    _, jwt, refresh = fake_supabase.add_user("test@example.com", "pw")

    store_session(
        fake_request,
        access_token=jwt,
        refresh_token=refresh,
        user_id="fake-uuid",
        email="test@example.com",
    )

    # Verify the session cookie was populated
    assert SESSION_KEY_ACCESS in fake_request.session

    # Now read it back
    user = get_session_user(fake_request)
    assert user is not None
    assert user.email == "test@example.com"


def test_clear_session(fake_supabase):
    """clear_session removes all session keys."""
    from app.auth_supabase import (
        SESSION_KEY_ACCESS,
        SESSION_KEY_REFRESH,
        SESSION_KEY_USER_EMAIL,
        SESSION_KEY_USER_ID,
        clear_session,
    )

    fake_request = MagicMock()
    fake_request.session = {
        SESSION_KEY_ACCESS: "x",
        SESSION_KEY_REFRESH: "y",
        SESSION_KEY_USER_ID: "z",
        SESSION_KEY_USER_EMAIL: "w",
        "unrelated_key": "kept",
    }

    clear_session(fake_request)
    assert SESSION_KEY_ACCESS not in fake_request.session
    assert SESSION_KEY_REFRESH not in fake_request.session
    assert SESSION_KEY_USER_ID not in fake_request.session
    assert SESSION_KEY_USER_EMAIL not in fake_request.session
    assert "unrelated_key" in fake_request.session


def test_get_session_user_refreshes_expired_token(fake_supabase):
    """If JWT expired but refresh token valid, refreshes and returns user."""
    from app.auth_supabase import (
        SESSION_KEY_ACCESS,
        SESSION_KEY_REFRESH,
        get_session_user,
    )

    fake_request = MagicMock()
    fake_request.session = {}
    uid, jwt, refresh = fake_supabase.add_user("user@x.com", "pw")

    # Simulate: JWT is now invalid (deleted from valid_jwts), but refresh still works
    fake_supabase.valid_jwts.pop(jwt, None)

    fake_request.session[SESSION_KEY_ACCESS] = jwt  # expired
    fake_request.session[SESSION_KEY_REFRESH] = refresh  # valid

    user = get_session_user(fake_request)
    assert user is not None
    assert user.email == "user@x.com"
    # Access token should have been rotated
    assert fake_request.session[SESSION_KEY_ACCESS] != jwt


def test_get_session_user_no_session_returns_none(fake_supabase):
    """Empty session → None."""
    from app.auth_supabase import get_session_user

    fake_request = MagicMock()
    fake_request.session = {}
    assert get_session_user(fake_request) is None


def test_trigger_password_reset_silent_on_unknown(fake_supabase):
    """reset_password_email is called even for unknown emails (no leak)."""
    from app.auth_supabase import trigger_password_reset

    trigger_password_reset("nobody@example.com")
    assert "nobody@example.com" in fake_supabase.reset_called_with


def test_is_supabase_auth_enabled(monkeypatch):
    """is_supabase_auth_enabled requires all three env vars."""
    import app.auth_supabase as au

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(au, "SUPABASE_URL", None)
    monkeypatch.setattr(au, "SUPABASE_ANON_KEY", None)
    monkeypatch.setattr(au, "SUPABASE_SERVICE_ROLE_KEY", None)
    assert au.is_supabase_auth_enabled() is False

    monkeypatch.setattr(au, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(au, "SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(au, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    assert au.is_supabase_auth_enabled() is True
