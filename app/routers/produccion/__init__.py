"""app/routers/produccion/ — Production worksheet + calendar (package).

Sazon-Improvement v2 (2026-10-06) Phase E: this package was a single
3145-line file until 2026-10-06. The split into focused modules is
in progress (worksheet / operations / templates / print_export /
analytics + _helpers). The shim pattern below keeps every existing
import working unchanged: callers do `from app.routers.produccion
import router` and get the SAME router object the app/main.py mounts.

For now, the entire content lives in _full.py and is re-exported here.
The next commits will extract the focused modules one at a time, each
behind a regression test (see tests/test_produccion_package_split.py
and tests/test_produccion_helpers.py).
"""
from __future__ import annotations

# Explicit re-exports (not star-import) so pyright can see them.
# This is the shim — pin the identity in tests, never silently copy.
from app.routers.produccion._full import router
from app.routers.produccion._full import (
    # Router-level constants used in templates
    FORECAST_SOURCE_LABELS,
    SOURCE_BUCKETS,
    CONFIDENCE_BANDS,
    FORECAST_SOURCE_HELP,
    # Pure helpers (re-exported via _full.py until next extraction step)
    source_to_bucket,
    _asuncion_today,
    _batch_surplus,
    _fermentation_reminder,
    _week_monday,
    _day_counts,
    _parse_overrides,
    _confidence_band_for_pct,
    _current_user_display_name,
)

__all__ = [
    "router",
    "FORECAST_SOURCE_LABELS",
    "SOURCE_BUCKETS",
    "CONFIDENCE_BANDS",
    "FORECAST_SOURCE_HELP",
    "source_to_bucket",
    "_asuncion_today",
    "_batch_surplus",
    "_fermentation_reminder",
    "_week_monday",
    "_day_counts",
    "_parse_overrides",
    "_confidence_band_for_pct",
    "_current_user_display_name",
]
