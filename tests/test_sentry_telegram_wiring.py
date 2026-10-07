"""tests/test_sentry_telegram_wiring.py — C.1 activation (polish lot 2026-10-07).

Asserts that app/rms/main.py:212-237 wires the Sentry→Telegram bridge by
importing ``sentry_before_send`` from ``app.rms.notify`` and passing it to
``sentry_sdk.init`` as ``before_send``.

This is a static-source test (no Sentry SDK, no DSN, no env vars needed):
we read main.py and assert the wiring pattern is present. The runtime
behaviour of the hook itself is locked by tests/test_notify_telegram.py.

Why static and not runtime? Two reasons:
  1. The init block in main.py:212-237 only runs during app startup (the
     FastAPI lifespan handler). Firing it from a test would require
     either booting the whole app (slow, touches DB) or running a fake
     lifespan (fragile, drifts from the real one).
  2. The actual ``sentry_before_send`` function is unit-tested in
     test_notify_telegram.py. This test only asserts the call site is
     wired, which is the regression that actually costs you in prod
     ("oh, the module shipped but nobody connected it to Sentry").
"""

from __future__ import annotations

import re
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parents[1] / "app" / "rms" / "main.py"


def _read_main_py() -> str:
    return MAIN_PY.read_text(encoding="utf-8")


def test_main_imports_sentry_before_send() -> None:
    """app/rms/main.py must import sentry_before_send from app.rms.notify.

    The import must be inside the Sentry init block (gated by SENTRY_DSN),
    so a missing SENTRY_DSN never triggers the import. This keeps the
    lazy-load rule from test_sentry_lazy_import.py intact.
    """
    src = _read_main_py()
    # Look for the import line anywhere in main.py.
    assert re.search(
        r"from\s+app\.rms\.notify\s+import\s+sentry_before_send",
        src,
    ), "main.py must import sentry_before_send from app.rms.notify"


def _extract_sentry_dsn_block(src: str) -> str:
    """Return the text inside the `if sentry_dsn:` block, up to the next
    top-level statement (a line that starts at column 0)."""
    match = re.search(r"^\s*if\s+sentry_dsn:", src, re.MULTILINE)
    assert match, "`if sentry_dsn:` block not found in main.py"
    start = match.start()
    lines = src[start:].splitlines(keepends=True)
    body_lines: list[str] = []
    for line in lines[1:]:  # skip the `if sentry_dsn:` line itself
        if line and not line[0].isspace():
            break
        body_lines.append(line)
    return "".join(body_lines)


def _extract_sentry_init_block(src: str) -> str:
    """Return the argument list of the `sentry_sdk.init(` call.

    Uses a simple parenthesis balance counter so nested parens (e.g.
    ``FastApiIntegration()``) are handled correctly.
    """
    idx = src.find("sentry_sdk.init(")
    assert idx != -1, "sentry_sdk.init(...) call not found in main.py"
    open_paren = src.find("(", idx)
    depth = 0
    for i in range(open_paren, len(src)):
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return src[open_paren : i + 1]
    raise AssertionError("sentry_sdk.init(...) call has unbalanced parens")


def test_sentry_init_uses_before_send_hook() -> None:
    """sentry_sdk.init(...) must receive before_send=sentry_before_send.

    Locks the activation. If a future refactor drops the kwarg, this test
    fails before the bug ships.
    """
    src = _read_main_py()
    init_args = _extract_sentry_init_block(src)
    assert "before_send=sentry_before_send" in init_args, (
        "sentry_sdk.init(...) must pass before_send=sentry_before_send; "
        f"got args: {init_args!r}"
    )


def test_before_send_import_lives_inside_dsn_gate() -> None:
    """The sentry_before_send import must be inside the `if sentry_dsn:` block.

    Otherwise an unset SENTRY_DSN would still trigger the import of
    app.rms.notify, breaking the lazy-load contract that
    test_sentry_lazy_import.py locks.
    """
    src = _read_main_py()
    body = _extract_sentry_dsn_block(src)
    assert "from app.rms.notify import sentry_before_send" in body, (
        "sentry_before_send import must live inside the `if sentry_dsn:` "
        "block so unset DSN stays a true no-op"
    )


