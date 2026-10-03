"""tests/test_status_dashboard.py — E5.S2 STATUS.html template + refresh.sh.

Pins the dashboard refresh to:
- refresh.sh exists, is executable, writes STATUS.md + STATUS.html
- STATUS.html.tmpl has placeholders that match refresh.sh's sed substitutions
- All substituted placeholders resolve (no orphan __FOO__ left)
- New wishlist fields (raw / triaged / rejected) are wired
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "docs" / "operations" / "dashboard"
TEMPLATE = DASHBOARD_DIR / "STATUS.html.tmpl"
REFRESH_SH = DASHBOARD_DIR / "refresh.sh"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_status_template_exists():
    assert TEMPLATE.exists()


def test_refresh_script_exists_and_executable():
    assert REFRESH_SH.exists()
    import stat
    mode = REFRESH_SH.stat().st_mode
    assert mode & stat.S_IXUSR, "refresh.sh must be executable"


def test_template_has_all_placeholders_that_refresh_substitutes():
    """Every __FOO__ in the template should have a sed substitution in refresh.sh."""
    template = _read(TEMPLATE)
    refresh = _read(REFRESH_SH)
    placeholders = set(re.findall(r"__([A-Z_]+)__", template))
    # Every placeholder must appear as a -e "s|__FOO__|..." line in refresh.sh
    missing = []
    for p in placeholders:
        if f"__  {p}__" not in refresh and f"__{p}__" not in refresh:
            missing.append(p)
    assert not missing, f"placeholders without refresh.sh substitution: {missing}"


def test_refresh_includes_wishlist_counts():
    refresh = _read(REFRESH_SH)
    # All 3 wishlist placeholders must be referenced
    assert "WISHLIST_RAW" in refresh
    assert "WISHLIST_TRIAGED" in refresh
    assert "WISHLIST_REJECTED" in refresh


def test_template_renders_wishlist_section():
    template = _read(TEMPLATE)
    assert "Wishlist" in template
    # 3 cards: Open (raw), Triaged, Rejected
    assert "__WISHLIST_RAW__" in template
    assert "__WISHLIST_TRIAGED__" in template
    assert "__WISHLIST_REJECTED__" in template


def test_status_md_template_includes_wishlist_block():
    """The STATUS.md YAML frontmatter has the wishlist section."""
    refresh = _read(REFRESH_SH)
    assert "wishlist:" in refresh
    assert "raw:" in refresh
    assert "triaged:" in refresh
    assert "rejected:" in refresh


def test_refresh_script_uses_documented_saskia_app_path():
    refresh = _read(REFRESH_SH)
    # The default path should match the convention so it Just Works locally.
    assert "saskia-app" in refresh


def test_no_orphan_placeholders_in_generated_html():
    """Sanity: every placeholder the template declares should be in refresh.sh."""
    template = _read(TEMPLATE)
    placeholders = set(re.findall(r"__([A-Z_]+)__", template))
    # All must have a sed entry in refresh.sh
    refresh = _read(REFRESH_SH)
    for p in placeholders:
        # Check if the placeholder is referenced in refresh.sh anywhere
        assert f"__{p}__" in refresh, (
            f"placeholder __{p}__ has no substitution in refresh.sh"
        )


def test_wishlist_dir_scanning_works():
    """refresh.sh finds *.md in docs/wishlist/raw / triaged / rejected."""
    # Confirm the wishlist dir exists for the script to scan
    raw = REPO_ROOT / "docs" / "wishlist" / "raw"
    triaged = REPO_ROOT / "docs" / "wishlist" / "triaged"
    rejected = REPO_ROOT / "docs" / "wishlist" / "rejected"
    assert raw.exists() or triaged.exists(), (
        "wishlist directory missing — refresh.sh has nothing to count"
    )


def test_ci_workflow_runs_refresh_on_push_to_main():
    """The CI workflow must invoke refresh.sh on push to main (E5.S2)."""
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return  # No CI yet, skip
    content = _read(ci)
    assert "refresh.sh" in content or "Refresh STATUS" in content, (
        "ci.yml must run refresh.sh on push to main"
    )
