"""Regression: every router in app/routers/ must have an auth gate.

A new router added without `require_login` (or `current_user_id`) is a
security bug waiting to happen — anyone can hit it without auth.

Allow-list:
- dev.py: env-gated dev smoke routes (DEV_COMBO_SMOKE=1)
- __init__.py: not a router
- routers that ONLY have an internal API (no user-facing pages) can use
  current_user_id manually but MUST reference auth.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

EXEMPT_FILES = {
    "app/routers/__init__.py",
    "app/routers/dev.py",
    # credits.py is a public CC-BY attribution page — intentionally
    # unauthenticated so external attribution is reachable. See:
    # docs/plans/2026-09-27-image-asset-plan.md
    "app/routers/credits.py",
    # photo_credits.py serves the same public attribution page (newer path).
    "app/routers/photo_credits.py",
    # stations.py implements its own pre-auth station-lock flow: decide()
    # inspects request.session and redirects staff to their pinned home
    # before any station page renders. Auth happens through that lock, not
    # a router-level dependency (see app/rms/stations.py).
    "app/routers/stations.py",
}

# Pattern: a route handler must use at least one of these:
AUTH_MARKERS = (
    "require_login",  # app.auth.require_login
    "current_user_id",  # app.auth.current_user_id
    "Depends(require_auth",  # legacy alias
    "Dependencies=[Depends(require_login",  # module-level dep
    "dependencies=[Depends(require_login",
    "get_current_user",
)


def _file_references_auth(path: Path) -> bool:
    src = path.read_text()
    # File references at least one auth marker somewhere
    return any(marker in src for marker in AUTH_MARKERS)


def _file_has_route_decorators(path: Path) -> bool:
    """Detect @router.get/post/put/delete decorators (any HTTP verb)."""
    src = path.read_text()
    return bool(re.search(r"@router\.(get|post|put|delete|patch|head|trace)\b", src))


@pytest.mark.parametrize(
    "router_path",
    sorted(p for p in Path("app/routers").glob("*.py")),
)
def test_router_requires_auth(router_path: Path) -> None:
    """Every router file must reference an auth gate."""
    spath = str(router_path)
    if spath in EXEMPT_FILES:
        pytest.skip(f"{spath} is exempt (not a router / dev-only)")

    if not _file_has_route_decorators(router_path):
        pytest.skip(f"{spath} has no @router.* decorators")

    if not _file_references_auth(router_path):
        pytest.fail(
            f"{spath} defines routes but does NOT reference any auth gate.\n"
            f"  Required: at least one of {AUTH_MARKERS!r}.\n"
            f"  Add `from app.auth import require_login_or_disabled as require_login`\n"
            f"  and decorate your routes with `dependencies=[Depends(require_login)]`\n"
            f"  (module-level) or per-route `dependencies=[Depends(require_login)]`."
        )


def test_dev_is_explicitly_exempt() -> None:
    """Sanity: the exempt set explicitly includes dev.py."""
    assert "app/routers/dev.py" in EXEMPT_FILES
    assert (Path("app/routers") / "dev.py").exists()


def test_no_routers_added_without_marker() -> None:
    """One-shot summary: list any router missing auth markers."""
    missing = []
    for p in Path("app/routers").glob("*.py"):
        spath = str(p)
        if spath in EXEMPT_FILES:
            continue
        if not _file_has_route_decorators(p):
            continue
        if not _file_references_auth(p):
            missing.append(spath)
    if missing:
        # This is also surfaced by the parametrized test above, but
        # print a one-glance summary so CI logs are easy to scan.
        pytest.fail(f"Routers missing auth gate: {missing}")
