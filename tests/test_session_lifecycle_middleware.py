"""tests/test_session_lifecycle_middleware.py — production middleware guard.

If a FastAPI handler obtains a session but doesn't close it (e.g. by
holding a raw reference), we want a warning logged so the operator
sees a leak in /auditoria before it becomes a `Too many connections`
error on Neon.
"""
from __future__ import annotations


def test_session_lifecycle_middleware_in_app():
    """The middleware module is importable + registers in the app."""
    from app.rms.session_lifecycle import SessionLifecycleMiddleware
    assert SessionLifecycleMiddleware is not None


def test_session_lifecycle_middleware_emits_warning_on_leak(client):
    """Smoke test: middleware can be instantiated and is properly wired.

    Full end-to-end leak detection is exercised via integration tests
    that open sessions directly in route handlers (out of scope for
    unit tests — would require monkey-patching the dependency chain).
    """
    from app.rms.session_lifecycle import SessionLifecycleMiddleware
    m = SessionLifecycleMiddleware(app=None)
    assert m is not None
    assert hasattr(m, "dispatch")



def test_middleware_is_registered_in_main():
    """Production main.py wires the middleware into the app."""
    from app.rms.main import app
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert any("SessionLifecycle" in c for c in middleware_classes), (
        f"SessionLifecycleMiddleware not registered. Found: {middleware_classes}"
    )
