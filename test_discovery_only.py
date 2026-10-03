def test_pkgutil_discovery_only():
    """Test that pkgutil discovery works independently of merge logic."""
    try:
        from app.rms.migrations import MIGRATIONS as discovered_migrations
        assert len(discovered_migrations) >= 2, f"Expected at least 2 discovered migrations, got {len(discovered_migrations)}"
        assert 44 in discovered_migrations, "Migration 44 should be discoverable"
        print(f"✅ Pkgutil discovery works: {len(discovered_migrations)} migrations found")
    except Exception as e:
        print(f"❌ Pkgutil discovery failed: {e}")
        raise
