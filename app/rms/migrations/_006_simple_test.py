def _migration_006_simple_test(conn):
    """Simple test migration for pkgutil discovery.

    This is a test migration to verify pkgutil discovery works.
    It adds a simple test column to AppMeta table.
    """
    # Add a simple test column
    conn.execute("""
    ALTER TABLE AppMeta ADD COLUMN IF NOT EXISTS test_migration_6 INTEGER DEFAULT 0
    """)

    # Update schema version manually
    conn.execute("""
    UPDATE AppMeta SET value = 6 WHERE key = 'schema_version'
    """)

    # Verify the update
    result = conn.execute("""
    SELECT value FROM AppMeta WHERE key = 'schema_version'
    """).fetchone()
    assert result[0] == 6, f"Schema version not updated: {result[0]}"
