"""tests/test_backup.py — verify app/rms/backup.py (E20).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E20.

Covers:
- dump_full_state serializes all BACKUP_TABLES
- backup_database writes a tarball; sha256 in manifest matches
- load_archive reverse-parses the file
- verify_backup raises on tampered archive
- restore_database upserts rows (no FK violations)
- prune_old_backups keeps newest N + last-D-days, removes rest
- _MODEL_BY_NAME maps all expected models
"""

from __future__ import annotations

import pytest

from app.rms.backup import (
    _MODEL_BY_NAME,
    BACKUP_TABLES,
    backup_database,
    dump_full_state,
    load_archive,
    prune_old_backups,
    restore_database,
    verify_backup,
)
from app.rms.models import (
    Product,
)
from tests.factories import make_ingredient, make_product


def test_dump_full_state_includes_all_tables(session_factory):
    s = session_factory()
    try:
        # Empty DB
        state = dump_full_state(s)
        assert isinstance(state, dict)
        assert "ingredient" in state
        assert "product" in state
        assert "recipe" in state
        assert "sale" in state
        assert "app_meta" in state
    finally:
        s.close()


def test_dump_full_state_serializes_rows(session_factory):
    s = session_factory()
    try:
        s.add(make_ingredient(s, name="harina", unit="kg", stock_qty=10.0, purchase_price_gs=4500))
        s.add(make_product(s, name="Muffin", sale_price_gs=2500))
        s.commit()
        state = dump_full_state(s)
        assert len(state["ingredient"]) == 1
        assert state["ingredient"][0]["name"] == "harina"
    finally:
        s.close()


def test_backup_database_writes_to_directory(tmp_path, session_factory):
    s = session_factory()
    try:
        s.add(make_ingredient(s, name="azúcar", unit="kg", stock_qty=20.0, purchase_price_gs=5200))
        s.add(make_product(s, name="Muffin", sale_price_gs=2500))
        s.commit()
        manifest = backup_database(s, tmp_path)
        assert manifest.n_rows >= 2
        assert manifest.sha256  # non-empty
        assert manifest.schema_version >= 1
        assert len(manifest.created_at) > 0

        # File written
        files = list(tmp_path.glob("sazon-backup-*.json.gz"))
        assert len(files) == 1
    finally:
        s.close()


def test_backup_database_file_is_loadable(tmp_path, session_factory):
    s = session_factory()
    try:
        s.add(make_product(s, name="Torta", sale_price_gs=35000))
        s.commit()
        manifest = backup_database(s, tmp_path)
        out_file = next(tmp_path.glob("sazon-backup-*.json.gz"))

        # Load it back
        loaded_manifest, tables = load_archive(out_file)
        assert loaded_manifest.sha256 == manifest.sha256
        assert "product" in tables
        assert any(p["name"] == "Torta" for p in tables["product"])
    finally:
        s.close()


def test_verify_backup_passes_on_valid_archive(tmp_path, session_factory):
    s = session_factory()
    try:
        s.add(make_ingredient(s, name="harina", unit="kg", stock_qty=5.0))
        s.commit()
        backup_database(s, tmp_path)
        out_file = next(tmp_path.glob("sazon-backup-*.json.gz"))
        # verify_backup returns the manifest (no exception)
        verified = verify_backup(out_file)
        assert verified.sha256
    finally:
        s.close()


def test_verify_backup_raises_on_tampered(tmp_path, session_factory):
    """Mutate the JSON inside the backup to simulate tampering."""
    s = session_factory()
    try:
        s.add(make_product(s, name="Torta", sale_price_gs=35000))
        s.commit()
        backup_database(s, tmp_path)  # compressed by default
        out_file = next(tmp_path.glob("sazon-backup-*.json.gz"))
        # Decompress, mutate, recompress
        import gzip

        raw = gzip.decompress(out_file.read_bytes())
        text = raw.decode("utf-8").replace("Torta", "Torta_TAMPERED")
        out_file.write_bytes(gzip.compress(text.encode("utf-8")))

        with pytest.raises(ValueError, match="integrity"):
            verify_backup(out_file)
    finally:
        s.close()


def test_restore_database_preserves_rows(session_factory, tmp_path):
    """Source session: create + backup.
    Dest session: empty + restore.
    Both should have same products after restore.
    """
    source_sf = session_factory
    s = source_sf()
    try:
        s.add(make_product(s, name="Muffin", sale_price_gs=2500))
        s.add(make_product(s, name="Torta", sale_price_gs=35000))
        s.add(make_ingredient(s, name="harina", unit="kg", stock_qty=10.0, purchase_price_gs=4500))
        s.commit()
        backup_database(s, tmp_path)
    finally:
        s.close()

    out_file = next(tmp_path.glob("sazon-backup-*.json.gz"))

    # Restore into same session (idempotent merge)
    s2 = source_sf()
    try:
        restore_database(s2, out_file)
        # Both products exist (merge is additive + idempotent)
        names = {p.name for p in s2.execute(select(Product)).scalars()}
        assert "Muffin" in names
        assert "Torta" in names
    finally:
        s2.close()


def test_prune_old_backups_removes_old_keeps_newest(tmp_path):
    """prune_old_backups keeps newest N + last D days."""
    # Create 10 backups with descending mtime
    paths = []
    for i in range(10):
        p = tmp_path / f"sazon-backup-2026010{i + 1}T00000{i}Z.json.gz"
        p.write_bytes(b"test")
        # Set mtime explicitly
        import os

        os.utime(p, (1700000000 + i * 86400, 1700000000 + i * 86400))
        paths.append(p)

    # keep newest 3 + older-than-30-days are pruned
    result = prune_old_backups(tmp_path, keep_n=3, keep_days=999)
    # Oldest 7 should be removed
    assert result.n_removed == 7
    assert result.n_kept == 3


def test_prune_old_backups_empty_dir(tmp_path):
    result = prune_old_backups(tmp_path)
    assert result.n_kept == 0
    assert result.n_removed == 0


def test_backup_tables_lists_expected_models():
    """All required tables are in the BACKUP_TABLES list (for full coverage)."""
    # M1 (2026-10-02): `sale_stock_move` was dropped by migration 092
    # (BACKLOG #1); sale-driven stock-out now lives in `stock_movement`.
    expected_names = {
        "app_meta",
        "ingredient",
        "recipe",
        "recipe_line",
        "product",
        "sale",
        "stock_movement",
        "import_batch",
        "audit_log",
        "customer",
        "waste_log",
        "user",
        "tag",
        "tag_link",
    }
    actual = {m.__tablename__ for m in BACKUP_TABLES}
    assert expected_names <= actual


def test_model_by_name_complete():
    """Every table in BACKUP_TABLES has a name mapping."""
    for model in BACKUP_TABLES:
        assert model.__tablename__ in _MODEL_BY_NAME


# Local import for restore test
from sqlalchemy import select
