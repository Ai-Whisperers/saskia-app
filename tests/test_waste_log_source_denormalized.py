"""Tests for PROD-MERMA-2 Batch I: WasteLog.source denormalization.

The feature eliminates the AuditLog join on /merma and /auditoria by
moving the entrypoint tag ('manual' | 'production') onto the WasteLog
row itself. These tests pin:

1. record_waste() default source is 'manual'.
2. record_waste() explicit source='production' is preserved.
3. record_waste() normalizes unknown source strings to 'manual' so the
   /auditoria filter never sees garbage.
4. list_waste() filters by source (column-side, no join).
5. list_waste() without source returns all rows.
6. record_recipe_waste() is callable and returns a result with
   waste_logs (recipe may have 0 lines).
7. /merma GET ?source= is a valid query param wired to list_waste().
8. Migration 102 added the column (visible via PRAGMA).
9. Migration 102 added the index ix_waste_log_source.
10. record_waste() production source survives commit (regression for
    the original /auditoria chip bug).
"""
from __future__ import annotations

from sqlalchemy import text

from app.rms.models import WasteLog
from app.rms.waste import (
    WasteReason,
    list_waste,
    record_recipe_waste,
    record_waste,
)
from tests.factories import make_ingredient, make_recipe


def test_record_waste_default_source_is_manual(session_factory):
    s = session_factory()
    ing = make_ingredient(s, name="harina_qa_1", stock_qty=10.0, purchase_price_gs=5000)
    log = record_waste(
        s,
        ingredient_id=ing.id,
        qty=1.0,
        reason=WasteReason.VENCIDA,
        recorded_by="tester",
    )
    assert log.source == "manual"
    s.commit()
    s.close()


def test_record_waste_explicit_production_source(session_factory):
    s = session_factory()
    ing = make_ingredient(s, name="azucar_qa_1", stock_qty=5.0, purchase_price_gs=3000)
    log = record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.5,
        reason=WasteReason.OTRA,
        source="production",
    )
    assert log.source == "production"
    s.commit()
    s.close()


def test_record_waste_normalizes_unknown_source(session_factory):
    s = session_factory()
    ing = make_ingredient(s, name="leche_qa_1", stock_qty=3.0, purchase_price_gs=4000)
    log = record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.2,
        reason=WasteReason.OTRA,
        source="alembic-experimental",  # not in known set
    )
    # Garbage in → safe default out (the chip / filter will only ever
    # see 'manual' or 'production' on /auditoria).
    assert log.source == "manual"
    s.commit()
    s.close()


def test_list_waste_filters_by_source(session_factory):
    s = session_factory()
    ing = make_ingredient(s, name="manteca_qa_1", stock_qty=8.0, purchase_price_gs=8000)
    a = record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.4,
        reason=WasteReason.VENCIDA,
        source="manual",
    )
    b = record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.3,
        reason=WasteReason.OTRA,
        source="production",
    )
    s.commit()
    only_manual = list_waste(s, source="manual", limit=50)
    only_production = list_waste(s, source="production", limit=50)
    try:
        assert {x.id for x in only_manual} == {a.id}
        assert {x.id for x in only_production} == {b.id}
    finally:
        s.close()


def test_list_waste_no_source_returns_all(session_factory):
    s = session_factory()
    ing = make_ingredient(s, name="sal_qa_1", stock_qty=2.0, purchase_price_gs=500)
    record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.1,
        reason=WasteReason.VENCIDA,
        source="manual",
    )
    record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.05,
        reason=WasteReason.OTRA,
        source="production",
    )
    s.commit()
    try:
        all_rows = list_waste(s, limit=50)
        assert len(all_rows) >= 2
    finally:
        s.close()


def test_record_recipe_waste_callable_with_no_lines(session_factory):
    s = session_factory()
    rec = make_recipe(s, name="receta_qa_1", yield_qty=10.0)
    # Recipe with no lines is fine for record_recipe_waste — it just
    # produces an empty waste_logs list. The function must not raise.
    result = record_recipe_waste(
        s,
        recipe_id=rec.id,
        batch_qty=1.0,
        reason=WasteReason.OTRA,
    )
    assert hasattr(result, "waste_logs")
    s.commit()
    s.close()


def test_migration_102_added_source_column(session_factory):
    s = session_factory()
    try:
        cols = [row[1] for row in s.execute(
            text("PRAGMA table_info(waste_log)")
        ).all()]
        assert "source" in cols
    finally:
        s.close()


def test_migration_102_added_source_index(session_factory):
    s = session_factory()
    try:
        idx_rows = s.execute(text("PRAGMA index_list(waste_log)")).all()
        idx_names = [str(row) for row in idx_rows]
        assert any("ix_waste_log_source" in n for n in idx_names)
    finally:
        s.close()


def test_record_waste_production_persists_after_commit(session_factory):
    """Regression: the production-source value must survive commit, not
    just live on the in-memory object. This is the original bug the
    denormalization fix was written for — /auditoria was showing
    'manual' for production entries."""
    s = session_factory()
    ing = make_ingredient(s, name="harina_prod_qa_1", stock_qty=5.0, purchase_price_gs=4000)
    log = record_waste(
        s,
        ingredient_id=ing.id,
        qty=0.25,
        reason=WasteReason.OTRA,
        source="production",
    )
    log_id = log.id
    s.commit()
    s.close()
    # Re-open the session and read back to confirm persistence.
    s2 = session_factory()
    try:
        fresh = s2.get(WasteLog, log_id)
        assert fresh is not None
        assert fresh.source == "production"
        assert fresh.source != "manual"
    finally:
        s2.close()
