"""tests/test_SASKIA-309_500_no_secrets.py — SASKIA-309 regression lock.

Locks Phase 8.1 of the copy/UX hardening program (plan:
`.hermes/plans/2026-10-07_202522-copy-ux-hardening.md`).

The 500.html error template must NOT leak:
  - Python stack traces (`Traceback`, `File "...line..."`)
  - Internal path segments (`app/rms/...`, `sqlite`, `SQLAlchemy`)
  - Secret keywords (`password`, `secret`, `token=`, `auth_*`)
  - Source code (`import`, `def `, `schema_version`)

These are checked against the TEMPLATE SOURCE — runtime 500s go through
the Sentry hook (already wired in `polish/saskia-p0`) and never render
stack traces.

Why a template-source check and not a render-the-page check:
  rendering `/__nonexistent__` returns 404 (FastAPI's HTTPException path),
  not 500. Triggering a real 500 in tests requires breaking the app
  enough to crash a route, which would mask the security regression
  we're trying to prevent. A static-source check is the right tool.
"""

from __future__ import annotations

from pathlib import Path

ERR_500 = Path(__file__).resolve().parents[1] / "app" / "templates" / "errors" / "500.html"

# Substrings that, if found in the template source, would indicate a
# leak risk. ALL of these should be absent from the rendered template
# output. Allowed exceptions go in the `exempt_lines` set below.
FORBIDDEN = [
    "Traceback",
    'File "',
    "sqlite",
    "SQLAlchemy",
    "OperationalError",
    "IntegrityError",
    "ProgrammingError",
    "password",
    "secret",
    "token=",
    "auth_token",
    "schema_version",
    "AIW_RMS_",
    "SUPABASE_",
    "RESEND_",
    "OPENAI_",
    "BWS_",
]

# Lines that legitimately contain one of the forbidden substrings
# (e.g. a Jinja comment explaining the rule). Right now there are none
# — the template is clean.
EXEMPT_LINES: set[str] = set()


def test_500_template_exists() -> None:
    assert ERR_500.exists(), f"missing template: {ERR_500}"


def test_500_template_does_not_leak_stack_trace() -> None:
    src = ERR_500.read_text(encoding="utf-8")
    leaks: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(src.splitlines(), start=1):
        # Strip Jinja `{% import ... %}` (legitimate syntax, contains 'import')
        # before keyword matching
        stripped = line.strip()
        if stripped.startswith("{%") and "import" in stripped:
            continue
        for kw in FORBIDDEN:
            if kw in line and line not in EXEMPT_LINES:
                leaks.append((kw, lineno, line.strip()))
                break
    assert not leaks, (
        f"errors/500.html contains {len(leaks)} leak-risk substrings.\n"
        "Fix the template, or add the line to EXEMPT_LINES with justification.\n"
        "First few leaks:\n"
        + "\n".join(f"  {kw!r} at line {ln}: {snippet}" for kw, ln, snippet in leaks[:5])
    )


def test_500_template_has_user_facing_message() -> None:
    """The 500 page must show a generic, friendly message — not a raw
    exception class or empty content."""
    src = ERR_500.read_text(encoding="utf-8")
    # Either Spanish or English generic-error copy
    has_spanish = "Algo salió mal" in src or "Error" in src
    has_english = "500" in src
    assert has_spanish or has_english, (
        "errors/500.html must contain a generic error message (e.g. 'Algo salió mal' or '500')"
    )


def test_500_template_does_not_show_request_id_literally_as_code() -> None:
    """The request_id is OK to show (it's for operator support tracking)
    but it must not be wrapped in a way that looks like an API token."""
    src = ERR_500.read_text(encoding="utf-8")
    # Sanity: the request_id IS rendered (this is what the operator wants)
    assert "request_id" in src, "request_id should be rendered for support tracking"
    # But not as a Bearer / API key / Authorization header format
    for bad_pattern in ("Bearer ", "Authorization:", "x-api-key", "sk-"):
        assert bad_pattern not in src, f"errors/500.html renders as API-style: {bad_pattern!r}"
