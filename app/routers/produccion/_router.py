"""app/routers/produccion/_router.py — Single shared APIRouter for the package.

Sazon-Improvement v2 (2026-10-06) Phase E: every submodule
(worksheet, operations, templates, print_export, analytics) imports
this single router object so routes registered on it all attach to
the same FastAPI router. `__init__.py` re-exports it as `router` so
app/main.py mounts it as before.

Why a separate file? If each submodule defined its own `APIRouter`,
the package would have to use `include_router` to compose them,
which changes how routes are listed (and breaks the
test_produccion_package_split URL-surface assertions that grep
the single router's `routes` attribute). Sharing one instance
keeps the contract intact.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_login_or_disabled as require_login

router = APIRouter(prefix="/produccion", dependencies=[Depends(require_login)])


__all__ = ["router"]
