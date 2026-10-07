"""TDD: status-pill classes must use the -- modifier (BEM-style).

Bug (T-2026-10-06e): the templates used `class="status-pill warn"` /
`class="status-pill error"` / `class="status-pill success"`, but the
CSS defines `.status-pill--warn`, `.status-pill--danger`, `.status-pill--ok`
(BEM convention). Result: no background, no color, white-on-white in dark
mode for HACCP chips and accuracy % pills.

TDD: this test asserts that every `class="status-pill` use in production
templates either (a) uses the modifier form `status-pill--*` or (b) is a
known base use (e.g. footer branding in base.html) that needs no modifier.
"""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"

# Files that have status-pill but the bare form is intentional (no color needed)
ALLOWED_BARE = {
    "base.html",  # footer branding chips — uses default color
}


def _check_template(path: Path) -> list[str]:
    """Return list of errors found in this template."""
    text = path.read_text()
    errors: list[str] = []
    # Find every `class="status-pill` (no -- yet) and inspect the next 4 lines
    pattern = re.compile(r'class="status-pill\b', re.MULTILINE)
    for m in pattern.finditer(text):
        # Look at the full <span ...> opening tag (Jinja {% %} can span many
        # lines, so search forward for the closing `>` of the span).
        rest = text[m.start():]
        # Close the <span> — first `>` after a `{% endif %}` or `"` quote.
        # The span can end either with `>` (no attrs after class) or with
        # another attribute then `>`. Find the first `>` after a `"` close
        # quote that follows a Jinja tag end, OR just the literal `>` of
        # the opening tag.
        # Simpler: find the `>` that closes the opening <span ...>
        # The opening span always has `class="...">` so find the `>` after
        # the closing quote of class.
        end = rest.find('">')
        if end == -1:
            # class has no closing — find the `>` directly
            end = rest.find('>')
        else:
            end += 2  # advance past `">`
        snippet = rest[:end]
        # Has a modifier on the same span? Either inline (e.g. class="status-pill status-pill--warn")
        # or via Jinja ({% if %}...status-pill--warn{% endif %})
        if re.search(r'status-pill--\w+', snippet):
            continue  # OK — modifier present
        # Bare class — must be in allowlist
        if path.name in ALLOWED_BARE:
            continue
        line = text[:m.start()].count('\n') + 1
        errors.append(f"{path.name}:{line} — bare 'status-pill' without modifier: {snippet[:80]!r}")
    return errors


def test_status_pill_uses_bem_modifier():
    all_errors: list[str] = []
    for path in TEMPLATES_DIR.glob("*.html"):
        all_errors.extend(_check_template(path))
    assert not all_errors, (
        "Found status-pill without --modifier (will render unstyled = "
        "white-on-white in dark mode):\n" + "\n".join(all_errors)
    )
