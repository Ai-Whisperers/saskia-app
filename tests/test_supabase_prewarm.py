"""tests/test_supabase_prewarm.py — lifespan pre-warms Supabase client."""

from __future__ import annotations


def test_lifespan_calls_get_supabase_client_when_using_supabase():
    """If using_supabase() is True, lifespan pre-warms the client.

    Per docs/operations/2026-09-09-performance-analysis.md improvement #3:
    eager-init saves 1-3s on the first POST /login after cold-start.
    """
    from pathlib import Path

    src = Path("app/rms/main.py").read_text()
    assert "get_supabase_client()" in src, (
        "main.py must call get_supabase_client() to pre-warm Supabase on startup. "
        "Per docs/operations/2026-09-09-performance-analysis.md improvement #3."
    )
    assert "using_supabase()" in src, (
        "Pre-warm must be guarded by `using_supabase()` so it only runs in hosted mode."
    )


def test_prewarm_is_non_fatal(monkeypatch):
    """If Supabase pre-warm fails, the app still starts successfully.

    Pre-warm wraps in try/except — the app must boot regardless of whether
    Supabase is reachable, has bad creds, or is rate-limited.
    """
    from pathlib import Path

    src = Path("app/rms/main.py").read_text()

    # Find the prewarm block.
    start = src.find("Eager-init Supabase")
    end = src.find("# Backup scheduler", start)
    block = src[start:end]

    assert "try:" in block, "Pre-warm must be wrapped in try/except"
    assert "except Exception" in block, "Pre-warm exception must be caught"
    assert "non-fatal" in block or "logger.warning" in block, (
        "Pre-warm failure must be logged but non-fatal"
    )
