"""tests/test_dockerfile_includes_docs.py — catch the /guia 404 regression.

Background: app/routers/help.py reads /app/docs/user-guide/*.md at
runtime. The Dockerfile must COPY ./docs so the deployed image has
those files — otherwise /guia 404s in production while passing tests.

The contributing session that introduced help.py shipped this code but
forgot to update the Dockerfile. The deployed Render container then
returned 404 for every /guia* path even though OpenAPI listed them
as registered. This test pins the Dockerfile so it can't regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _dockerfile_text() -> str:
    """Read the project's Dockerfile."""
    return DOCKERFILE.read_text(encoding="utf-8")


def test_dockerfile_copies_docs_directory():
    """`docs/` must be COPY'd into the image — /guia reads from it at runtime."""
    text = _dockerfile_text()
    # Look for a `COPY docs ./docs` line (or similar that copies docs/)
    # Allow: COPY docs ./docs, COPY docs /app/docs, COPY ./docs ./docs
    assert any(
        line.strip().startswith("COPY")
        and "docs" in line
        and "/docs" in line.split("COPY", 1)[1]  # target ends with /docs*
        for line in text.splitlines()
        if line.strip().startswith("COPY")
    ), (
        "Dockerfile must include a COPY line for docs/ (target ends with /docs).\n"
        "Without it, /guia 404s in production even though the route is mounted.\n"
        "Example: `COPY docs ./docs`"
    )


def test_help_route_uses_project_rooted_docs():
    """Sanity: the runtime lookup path is /app/docs/user-guide."""
    from app.routers.help import GUIDE_DIR

    expected = Path(__file__).resolve().parents[1] / "docs" / "user-guide"
    assert GUIDE_DIR == expected, (
        f"GUIDE_DIR is {GUIDE_DIR}, expected {expected}.\n"
        "If you change it, also update the Dockerfile COPY line."
    )


@pytest.mark.parametrize(
    "section",
    [
        "00-quickstart",
        "01-dashboard",
        "02-ventas",
    ],
)
def test_user_guide_sections_exist_locally(section):
    """The markdown source files we need to ship into the image must exist."""
    md = Path(__file__).resolve().parents[1] / "docs" / "user-guide" / f"{section}.md"
    assert md.exists(), f"Missing source file {md} — Dockerfile will fail to COPY it"
    assert md.read_text(encoding="utf-8").strip(), f"{md} is empty"


def test_readme_exists_in_user_guide():
    """The guide index route /guia reads README.md by literal name."""
    readme = Path(__file__).resolve().parents[1] / "docs" / "user-guide" / "README.md"
    assert readme.exists(), (
        f"Missing {readme}. app/routers/help.py reads 'README' by name; "
        "if you rename it, also update help.py:215."
    )
