"""tests/browser/__init__.py — Playwright front-end test layer.

Layered so it adapts when the UI changes:

  helpers.py    — one `pw_page` fixture per test; the ONLY place that knows
                  how to launch the browser. Server + seeded data + login
                  handled once. Swap browser/server strategy here.
  pages.py      — Page Objects. EVERY selector lives here, as class
                  attributes with semantic names. When the UI changes you
                  edit ONE line per selector, not N tests.
  test_*.py     — behavior only: what the user does, what they should see.
                  Zero CSS selectors in test bodies.

Run:  make test-browser   (or pytest tests/browser -m browser)
"""

from __future__ import annotations

CHROME = "/opt/hermes/.playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
