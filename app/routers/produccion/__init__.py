"""app/routers/produccion/ — Production worksheet + calendar (package).

Sazon-Improvement v2 (2026-10-06) Phase E: this package was a single
3145-line file until 2026-10-06. The split into focused modules is
in progress. As of this commit:
  - _helpers.py: pure functions + constants (extracted)
  - _full.py: legacy monolith (still has the route handlers; helpers now
              imported FROM _helpers.py, not defined here)
  - __init__.py: re-exports the public surface for backward-compat

The contract tests in tests/test_produccion_package_split.py and
tests/test_produccion_helpers.py pin the public API so subsequent
extractions can move code freely without breaking app/main.py or
any other caller.
"""
from __future__ import annotations

# Explicit re-exports (not star-import) so pyright can see them.
# The shim points at _helpers for the extracted symbols, and at
# _full.py for everything else (routes, complex helpers, etc.).
from app.routers.produccion._helpers import (
    CONFIDENCE_BANDS,
    DEFAULT_BAKE_START_HOUR,
    FORECAST_SOURCE_HELP,
    FORECAST_SOURCE_LABELS,
    SOURCE_BUCKETS,
    _asuncion_today,
    _batch_surplus,
    _confidence_band_for_pct,
    _current_user_display_name,
    _day_counts,
    _fermentation_reminder,
    _parse_overrides,
    _week_monday,
    source_to_bucket,
)
from app.routers.produccion._full import router

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
