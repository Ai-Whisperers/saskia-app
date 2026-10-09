"""Phase 11 — storage_keyword DB table (migration 049).

infer_storage() reads keywords from the DB when a session is provided,
falls back to the legacy hardcoded dict otherwise.
"""

from sqlalchemy import select

from app.rms.ingredient_intel import infer_storage
from app.rms.models import StorageKeyword


def test_migration_049_seeded_keywords(session_factory):
    """Table exists and is seeded with the legacy keyword set."""
    with session_factory() as s:
        rows = s.execute(select(StorageKeyword)).scalars().all()
        keywords = {(r.storage_code, r.keyword) for r in rows}
        assert ("refrigerated", "leche") in keywords
        assert ("refrigerated", "queso crema") in keywords
        assert ("frozen", "congelad") in keywords
        # All seeded rows active
        assert all(r.is_active for r in rows)


def test_infer_storage_uses_db_keywords(session_factory):
    """DB keyword match wins; custom operator keywords take effect."""
    with session_factory() as s:
        # Legacy behaviour preserved via seeded rows
        assert infer_storage("Leche enterna", session=s) == "refrigerated"
        assert infer_storage("Frutillas congeladas", session=s) == "frozen"
        assert infer_storage("Harina 000", session=s) == "ambient"

        # Operator adds a custom keyword — infer_storage picks it up
        s.add(StorageKeyword(storage_code="frozen", keyword="polo norte", sort_order=5))
        s.commit()
        assert infer_storage("Mix polo norte premium", session=s) == "frozen"


def test_infer_storage_inactive_keyword_ignored(session_factory):
    """Deactivated keywords no longer match."""
    with session_factory() as s:
        row = s.execute(
            select(StorageKeyword).where(StorageKeyword.keyword == "leche")
        ).scalar_one()
        row.is_active = False
        s.commit()
        assert infer_storage("Leche enterna", session=s) == "ambient"


def test_infer_storage_fallback_without_session():
    """No session → legacy hardcoded dict still works."""
    assert infer_storage("Leche enterna") == "refrigerated"
    assert infer_storage("Frutillas congeladas") == "frozen"
    assert infer_storage("Harina 000") == "ambient"
