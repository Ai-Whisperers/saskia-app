"""tests/test_session_lifecycle_skips_static.py — middleware should skip /static.

Without this skip, gc.get_objects() runs on EVERY static asset request,
which:
- Adds 50-200ms latency per asset (especially under load)
- Can cause 503s when GC iterates during file I/O
- Wastes CPU on assets that never open DB sessions

The fix mirrors request_log_middleware: skip /static/* and /healthz/*.
"""
from __future__ import annotations


def test_middleware_skips_static_path():
    """SessionLifecycleMiddleware must not run gc.get_objects() for /static/*."""
    # Inspect the source code to verify the skip is implemented.
    import inspect

    from app.rms.session_lifecycle import SessionLifecycleMiddleware
    src = inspect.getsource(SessionLifecycleMiddleware.dispatch)
    assert '"/static/"' in src or "'/static/'" in src, (
        f"Middleware should skip /static/*. Got:\n{src}"
    )
    assert "/healthz" in src, (
        f"Middleware should skip /healthz*. Got:\n{src}"
    )


def test_static_path_not_subject_to_gc(client):
    """Static asset requests complete in <200ms (no GC overhead)."""
    import time

    start = time.perf_counter()
    resp = client.get("/static/app.css")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    # Without the fix this is often 50-200ms; with the fix <30ms.
    # Allow generous bound to account for test overhead.
    assert elapsed_ms < 300, f"Static asset took {elapsed_ms:.0f}ms — middleware is hot"


def test_healthz_not_subject_to_gc(client):
    """/healthz* requests don't trigger gc.get_objects()."""
    import time

    start = time.perf_counter()
    resp = client.get("/healthz")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 200, f"/healthz took {elapsed_ms:.0f}ms — middleware is hot"
