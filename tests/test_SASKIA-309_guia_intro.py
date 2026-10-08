"""tests/test_SASKIA-309_guia_intro.py — SASKIA-309 regression lock.

Locks Phase 8.3 of the copy/UX hardening program: the user guide must
have an intro paragraph above the table of contents.

The intro is in `docs/user-guide/README.md` (rendered by `/guia` and
`/guia/{section}` routes — see `app/routers/help.py`).
"""

from __future__ import annotations

from pathlib import Path

GUIDE_DIR = Path(__file__).resolve().parents[1] / "docs" / "user-guide"
README = GUIDE_DIR / "README.md"


def test_guide_readme_exists() -> None:
    assert README.exists(), f"missing: {README}"


def test_guide_readme_has_intro() -> None:
    """The guide intro must appear BEFORE the first table/section."""
    text = README.read_text(encoding="utf-8")
    # The first heading is "# Guía de Sazón"
    assert text.startswith("# Guía de Sazón"), "README should start with `# Guía de Sazón`"
    # Intro = everything between the H1 and the first H2 (## heading)
    h2_pos = text.find("\n## ")
    assert h2_pos > 0, "README missing first ## section heading"
    intro = text[:h2_pos]
    assert len(intro) > 80, (
        f"README intro too short: {len(intro)} chars (intro region: {h2_pos} bytes). "
        "User guide needs an intro above the TOC."
    )


def test_guide_readme_addresses_operator() -> None:
    """The intro must be addressed to the operator (in Spanish voseo),
    not to developers (would be in English)."""
    text = README.read_text(encoding="utf-8")
    # Lock the canonical operator-facing phrase
    assert "Para the operator" in text or "Para vos" in text or "para vos" in text, (
        "README intro must address the operator directly (Spanish voseo)"
    )


def test_guide_readme_has_toc() -> None:
    """Lock that the guide has a table of contents — operators use it
    to find the right section quickly."""
    text = README.read_text(encoding="utf-8")
    assert "## Índice" in text or "## Indice" in text, "README missing table of contents"


def test_guide_routes_exist() -> None:
    """Lock that the routes serving the guide are wired (otherwise the
    doc is unreachable from the app)."""
    help_router = Path(__file__).resolve().parents[1] / "app" / "routers" / "help.py"
    assert help_router.exists(), f"missing router: {help_router}"
    src = help_router.read_text(encoding="utf-8")
    # Both /guia (index) and /guia/{section} must be wired
    assert "guia_index" in src, "missing guia_index route"
    assert "guia_section" in src, "missing guia_section route"


def test_all_sections_have_md_files() -> None:
    """Every section listed in the TOC must have a corresponding .md
    file in the guide directory — otherwise /guia/{section} 404s."""
    text = README.read_text(encoding="utf-8")
    # Pull section filenames from markdown links like [0](00-quickstart.md)
    import re

    md_links = re.findall(r"\]\(([0-9][0-9]-[a-z-]+\.md|[a-z-]+\.md)\)", text)
    missing: list[str] = []
    for fname in set(md_links):
        if not (GUIDE_DIR / fname).exists():
            missing.append(fname)
    assert not missing, f"TOC references {len(missing)} missing .md files:\n" + "\n".join(
        missing[:10]
    )
