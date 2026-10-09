"""Tests for /produccion B.3 — Fermentation reminder.

Recipes with bulk fermentation (masa madre, poolish, levain builds)
need many hours before baking. The cook currently has to mentally
compute "if pan masa madre takes 14h and tomorrow's bake starts at
06:00, I need to start it at 16:00 today" — and they sometimes forget.

B.3 adds a per-row reminder so the cook sees exactly when to start
the ferment so the batch is ready for the typical 06:00 bake start.

Saved ~150k Gs/mes (1 salvaged batch that wasn't forgotten overnight).
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "app" / "templates" / "produccion.html"
# Sazon-Improvement v2 (2026-10-06) Phase E: _fermentation_reminder now
# lives in app/routers/produccion/_helpers.py (extracted from _full.py).
# The worksheet handler that calls it is in _full.py. We read BOTH so
# the test finds the helper AND its caller in the day-view context.
ROUTER = Path(__file__).parent.parent / "app" / "routers" / "produccion" / "_helpers.py"
ROUTER_CALLERS = Path(__file__).parent.parent / "app" / "routers" / "produccion" / "_full.py"
MODEL = Path(__file__).parent.parent / "app" / "rms" / "models_legacy.py"
MIGRATION = (
    Path(__file__).parent.parent
    / "app"
    / "rms"
    / "migrations"
    / "_101_recipe_fermentation_minutes.py"
)

TEMPLATE_SRC = TEMPLATE.read_text(encoding="utf-8")
ROUTER_SRC = ROUTER.read_text(encoding="utf-8") + ROUTER_CALLERS.read_text(encoding="utf-8")
MODEL_SRC = MODEL.read_text(encoding="utf-8")
MIGRATION_SRC = MIGRATION.read_text(encoding="utf-8")


# ────────────────────── model + migration (B.3) ──────────────────────


def test_recipe_model_has_fermentation_minutes():
    """B.3 — Recipe must have a fermentation_minutes column."""
    # The model declares it
    assert "fermentation_minutes" in MODEL_SRC, (
        "B.3 — Recipe model must declare fermentation_minutes"
    )
    # It's an Integer column, nullable
    assert "Mapped[Optional[int]]" in MODEL_SRC and "fermentation_minutes" in MODEL_SRC, (
        "B.3 — fermentation_minutes must be Mapped[Optional[int]] "
        "(NULL for recipes that don't ferment)"
    )


def test_migration_101_exists():
    """B.3 — Migration 101 must add the column."""
    assert MIGRATION.exists(), "B.3 — migration _101_recipe_fermentation_minutes.py must exist"


def test_migration_101_idempotent():
    """B.3 — Migration must use try/except so re-running is safe."""
    assert "try:" in MIGRATION_SRC, "B.3 — migration must guard ALTER TABLE with try/except"
    assert "ALTER TABLE recipe ADD COLUMN fermentation_minutes" in MIGRATION_SRC, (
        "B.3 — migration must ALTER TABLE recipe to add the column"
    )


def test_migration_registered_in_db():
    """B.3 — The migration must be imported + registered in app/rms/db.py."""
    db_path = Path(__file__).parent.parent / "app" / "rms" / "db.py"
    db_src = db_path.read_text(encoding="utf-8")
    assert "_migration_101_recipe_fermentation_minutes" in db_src, (
        "B.3 — db.py must import _migration_101_recipe_fermentation_minutes"
    )
    assert "101: _migration_101_recipe_fermentation_minutes" in db_src, (
        "B.3 — db.py MIGRATIONS dict must register 101"
    )


def test_schema_version_bumped_to_101():
    """B.3 — CURRENT_SCHEMA_VERSION must be 101 (or higher) so migration runs."""
    config_path = Path(__file__).parent.parent / "app" / "rms" / "config.py"
    config_src = config_path.read_text(encoding="utf-8")
    # We just need the version to be ≥ 101; subsequent features may bump it.
    import re

    match = re.search(r"CURRENT_SCHEMA_VERSION\s*=\s*(\d+)", config_src)
    assert match, "B.3 — CURRENT_SCHEMA_VERSION must be defined in config.py"
    version = int(match.group(1))
    assert version >= 101, (
        f"B.3 — CURRENT_SCHEMA_VERSION must be ≥ 101 (got {version}) so the migration actually runs"
    )


# ────────────────────── helper unit tests (B.3) ──────────────────────


def test_router_has_fermentation_reminder_helper():
    """B.3 — _fermentation_reminder must be defined."""
    assert "def _fermentation_reminder" in ROUTER_SRC, (
        "B.3 — _fermentation_reminder helper must be defined"
    )


def test_router_helper_returns_none_for_no_ferment():
    """B.3 — None / 0 minutes returns None (no reminder needed)."""
    idx = ROUTER_SRC.find("def _fermentation_reminder")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2000]
    assert "fermentation_minutes <= 0" in block or "not fermentation_minutes" in block, (
        "B.3 — helper must return None when fermentation_minutes is null or 0"
    )


def test_router_helper_returns_6_keys():
    """B.3 — Helper must return minutes, hours, start_at, start_label, ready_label, days_before."""
    idx = ROUTER_SRC.find("def _fermentation_reminder")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2000]
    for key in (
        '"fermentation_minutes"',
        '"fermentation_hours"',
        '"start_at"',
        '"start_label"',
        '"ready_label"',
        '"days_before"',
    ):
        assert key in block, f"B.3 — helper must return {key}"


def test_router_helper_uses_asuncion_tz():
    """B.3 — The reminder must use America/Asuncion TZ (not UTC)."""
    idx = ROUTER_SRC.find("def _fermentation_reminder")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2000]
    assert "America/Asuncion" in block, (
        "B.3 — helper must use America/Asuncion TZ so the start time matches the cook's wall clock"
    )


def test_router_helper_anchors_to_bake_start_hour():
    """B.3 — The reminder is calculated backward from bake_start_hour."""
    idx = ROUTER_SRC.find("def _fermentation_reminder")
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 2000]
    assert "bake_start_hour" in block, (
        "B.3 — helper must accept a bake_start_hour parameter (default 06:00)"
    )
    assert "timedelta(minutes=fermentation_minutes)" in block, (
        "B.3 — helper must subtract fermentation_minutes from bake_start"
    )


# ────────────────────── context wiring (B.3) ──────────────────────


def test_router_day_view_sets_fermentation_reminder():
    """B.3 — plan_rows_view entries include fermentation_reminder."""
    assert "fermentation_reminder" in ROUTER_SRC, (
        "B.3 — context must set fermentation_reminder per row"
    )
    # Must call the helper, not duplicate logic
    idx = ROUTER_SRC.find('"fermentation_reminder":')
    assert idx > 0
    block = ROUTER_SRC[idx : idx + 800]
    assert "_fermentation_reminder" in block


# ────────────────────── template UI (B.3) ──────────────────────


def test_template_renders_fermentation_pill():
    """B.3 — The row must show a fermentation-pill when reminder exists."""
    assert "fermentation-pill" in TEMPLATE_SRC, (
        "B.3 — template must render a fermentation-pill element"
    )


def test_template_pill_uses_emoji():
    """B.3 — The pill uses 🍞 as a recognisable bread symbol."""
    assert "🍞 Fermentar" in TEMPLATE_SRC, (
        "B.3 — pill must start with 🍞 Fermentar so the cook knows it's bread"
    )


def test_template_pill_includes_data_attributes():
    """B.3 — The pill carries data-* attributes for JS / future extensions."""
    assert "data-fermentation-minutes" in TEMPLATE_SRC, (
        "B.3 — pill must carry data-fermentation-minutes"
    )
    assert "data-fermentation-start" in TEMPLATE_SRC, (
        "B.3 — pill must carry data-fermentation-start (ISO datetime)"
    )


def test_template_pill_title_includes_ready_label():
    """B.3 — The title tooltip must explain when the ferment will be ready."""
    idx = TEMPLATE_SRC.find("data-fermentation-minutes=")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 1500]
    assert "ready_label" in block, (
        "B.3 — pill title must mention ready_label so the cook sees the deadline"
    )


def test_template_pill_handles_cross_midnight_ferments():
    """B.3 — Cross-midnight ferments must show 'ayer' so the cook doesn't confuse AM/PM."""
    idx = TEMPLATE_SRC.find("data-fermentation-minutes=")
    assert idx > 0
    block = TEMPLATE_SRC[idx : idx + 1500]
    assert "days_before > 0" in block and "ayer" in block, (
        "B.3 — pill must show 'ayer HH:MM' when the ferment starts the previous day"
    )


def test_template_fermentation_pill_print_styles():
    """B.3 — Fermentation pill must remain visible (with adjusted colors) on print."""
    assert ".fermentation-pill" in TEMPLATE_SRC, "B.3 — CSS rules for .fermentation-pill must exist"
    # Check there's a print-media rule
    assert "@media print" in TEMPLATE_SRC
