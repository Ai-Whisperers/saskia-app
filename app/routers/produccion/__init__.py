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

# Import _full so all the existing @router.get / @router.post decorators
# in that module register their routes on the shared router object.
# This is the "shim + extract" pattern: routes that haven't been split
# out yet still live in _full.py and attach to the shared router via
# the `from _router import router` line at the top of _full.py.
import app.routers.produccion._full
import app.routers.produccion.analytics
import app.routers.produccion.forecast
import app.routers.produccion.operations
import app.routers.produccion.prep_recipes
import app.routers.produccion.print_export
import app.routers.produccion.templates_ops

# Explicit re-exports (not star-import) so pyright can see them.
# The shim points at _helpers for the extracted symbols, and at
# _full.py for everything else (routes, complex helpers, etc.).
from app.routers.produccion._helpers import (
    CONFIDENCE_BANDS,
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

# Re-export the shared router from the package's canonical location
# so submodules (worksheet, operations, ...) can do
# `from app.routers.produccion import router` and register their routes.
from app.routers.produccion._router import router

__all__ = [
    "CONFIDENCE_BANDS",
    "FORECAST_SOURCE_HELP",
    "FORECAST_SOURCE_LABELS",
    "SOURCE_BUCKETS",
    "_asuncion_today",
    "_batch_surplus",
    "_confidence_band_for_pct",
    "_current_user_display_name",
    "_day_counts",
    "_fermentation_reminder",
    "_parse_overrides",
    "_week_monday",
    "router",
    "source_to_bucket",
]
