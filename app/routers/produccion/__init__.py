"""app/routers/produccion/ — Production worksheet + calendar (package).

Sazon-Improvement v2 (2026-10-06) Phase E: this package was a single
3007-line file until 2026-10-06. The split into focused modules is
in progress (worksheet / operations / templates / print_export /
analytics + _helpers). The shim pattern below keeps every existing
import working unchanged: callers do `from app.routers.produccion
import router` and get the SAME router object the app/main.py mounts.

For now, the entire content lives in _full.py and is re-exported here.
The next commits will extract the focused modules one at a time, each
behind a regression test (see tests/test_produccion_package_split.py).
"""
from __future__ import annotations

# Re-export everything from the legacy monolith. The contract test
# `test_produccion_package_split.py` pins the public URL surface so
# that subsequent extractions can move code freely without breaking
# app/main.py or any other caller.
from app.routers.produccion._full import *  # noqa: F401, F403
from app.routers.produccion._full import router  # explicit re-export for clarity

__all__ = ["router"]
