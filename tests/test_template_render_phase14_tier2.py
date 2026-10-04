"""tests/test_template_render_phase14_tier2.py — Phase 14 Tier 2 (2026-10-01).

Coverage strategy doc, Tier 2: "render every template name from a
known fixture set, assert no {{ undefined_var }} exceptions."

This test catches two distinct regression classes that Tier 1 (route
smoke) doesn't cover well:

1. **Jinja syntax errors** — a typo in any template would 500 the
   route that renders it. The route smoke only hits routes with
   correct fixtures; partials / modals / new pages might never get
   visited. This test loads every .html via get_template(), so a
   syntax error surfaces here even on a template nobody has hit yet.

2. **Missing Jinja globals** — when a template calls a function that
   lives in `templates.env.globals` (e.g. `m.gs()`, `fmt.money()`,
   `now_year()`, `crumbs_for(...)`) and a refactor drops the global,
   every page that uses it 500s. This test asserts the globals that
   `template_render.py` registers are still present after import.

What this does NOT catch:
- Per-template data-shape errors (a pedido page rendering without a
  pedido). Those only happen at request time and are covered by
  Tier 1 route smoke + hand-written CRUD tests.
- Visual regressions. Those are covered by the visual-audit batch.

Why we don't render with empty/minimal context:
- A page that `{% extends "base.html" %}` and reads `{{ pedido }}`
  legitimately cannot render without a pedido. Forcing it to render
  with `pedido=undefined` produces false-positive failures that
  drown out the real signal (missing globals + syntax errors).
- The two real regression classes above are detectable from the
  parse step alone; render is unnecessary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Locate Jinja env exactly as the app uses it (single global instance).
from app.services.template_render import templates as jinja_templates

# Collect every template path under app/templates/. rglob so partials
# / _components/ / modals are included — every .html file is fair game.
TEMPLATE_PATHS = sorted(
    Path("app/templates").rglob("*.html"),
    key=lambda p: str(p),
)
TEMPLATE_NAMES = [str(p.relative_to("app/templates")).replace("\\", "/") for p in TEMPLATE_PATHS]


# Globals that app/services/template_render.py registers. If any of
# these disappear, the templates that use them 500 at request time.
# The test asserts each one is still a registered Jinja global, so a
# refactor that drops one (e.g. moves m() to display.py and forgets
# to re-register) fails this test immediately.
EXPECTED_GLOBALS = {
    "now_year": "render() helper (app/services/template_render.py)",
    "asset_version": "render() helper (app/services/template_render.py)",
    "m": "money formatter namespace",
    "fmt": "display formatter namespace",
}


@pytest.mark.parametrize("template_name", TEMPLATE_NAMES, ids=lambda n: n.replace("/", "_"))
def test_template_parses_without_syntax_error(template_name):
    """Every template must parse without Jinja syntax errors.

    `get_template` compiles the template (and any macros) at load
    time. A typo in any .html file surfaces here even if no route
    points to it.
    """
    try:
        jinja_templates.env.get_template(template_name)
    except Exception as exc:
        pytest.fail(f"get_template({template_name!r}) raised: {type(exc).__name__}: {exc}")


def test_template_count_meets_strategy_target():
    """Strategy doc: cover every template. If this drops below 80,
    someone deleted templates without updating this test."""
    assert len(TEMPLATE_NAMES) >= 80, (
        f"only {len(TEMPLATE_NAMES)} templates discovered — was a "
        "directory renamed or pruned? Check app/templates/."
    )


@pytest.mark.parametrize(
    "name,description", list(EXPECTED_GLOBALS.items()), ids=list(EXPECTED_GLOBALS.keys())
)
def test_required_global_is_registered(name, description):
    """A refactor that drops a Jinja global (e.g. `m` from
    `templates.env.globals`) silently breaks every page that uses
    it. This test pins the set of required globals.

    If you INTENTIONALLY drop a global, update EXPECTED_GLOBALS and
    this test. Don't just delete the test — that's how a regression
    becomes invisible.
    """
    assert name in jinja_templates.env.globals, (
        f"Jinja global {name!r} ({description}) is missing from "
        "templates.env.globals. Every page that uses it now 500s. "
        "Either re-register it in app/services/template_render.py "
        f"or update EXPECTED_GLOBALS in {__file__} if intentional."
    )


def test_module_loaded_with_all_exports():
    """Sanity check: importing the module populated the globals dict
    above the default Jinja set. If this fails, the registration
    code in template_render.py didn't run (likely an import error
    at module load time)."""
    g = jinja_templates.env.globals
    assert callable(g["now_year"])
    assert hasattr(g["m"], "gs")
    assert hasattr(g["fmt"], "money")


def test_money_helpers_handle_none_and_negative():
    """Cover the None-fallback and negative-formatting branches in
    m.gs / fmt.qty / fmt.money. Without these, a price=None silently
    renders as "0" instead of "—" (visual regression)."""
    g = jinja_templates.env.globals
    # m.gs() prefixes "Gs. " — visible currency form
    assert g["m"].gs(None) == "—"
    assert "0" in g["m"].gs(0)
    assert g["m"].gs(-1500).startswith("-")
    # fmt.money() / fmt.qty() use the bare-number form
    assert g["fmt"].money(None) == "—"
    assert g["fmt"].qty(None) == "—"
