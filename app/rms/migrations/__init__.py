"""app/rms/migrations/__init__.py — migrations directory for pkgutil discovery.

Phase 2A ticket #25: Replace hardcoded MIGRATIONS dict with pkgutil discovery.

Each migration file should export a function `_migration_NNN_description(conn)`
where NNN is the version number. The __init__.py will collect all migration
functions via pkgutil.walk_packages and build the MIGRATIONS dict automatically.

When imported, this module registers all migrations found via pkgutil.
"""

import importlib
import pkgutil
from pathlib import Path  # noqa: F401 — re-exported via __all__
from typing import Any, Callable

# MIGRATIONS dict populated automatically via pkgutil discovery
MIGRATIONS: dict[int, Callable[[Any], None]] = {}


def _discover_migrations() -> dict[int, Callable[[Any], None]]:
    """Auto-discover migration functions via pkgutil.

    Looks for functions named `_migration_NNN_description` in all modules
    in this package, where NNN is the version number.

    Returns:
        Dict mapping version numbers to migration functions
    """
    migrations = {}

    # Walk all modules in this package
    for _, name, _ in pkgutil.walk_packages(__path__, __name__ + "."):
        try:
            module = importlib.import_module(name)
        except ImportError:
            # Skip modules that can't be imported (missing dependencies)
            continue

        # Find all migration functions in the module
        for attr_name in dir(module):
            if attr_name.startswith("_migration_"):
                # Extract version number: _migration_044_description -> 44
                try:
                    version_str = attr_name.split("_")[2]  # skip "_migration_"
                    version = int(version_str)
                except (IndexError, ValueError):
                    # Skip malformed names
                    continue

                func = getattr(module, attr_name)
                if callable(func):
                    migrations[version] = func

    # Sort by version number
    return dict(sorted(migrations.items()))


# Auto-discover migrations on import
MIGRATIONS.update(_discover_migrations())


def get_migration(version: int) -> Callable[[Any], None]:
    """Get a specific migration function by version.

    Args:
        version: The migration version number

    Returns:
        The migration function

    Raises:
        RuntimeError: If migration version is not found
    """
    if version not in MIGRATIONS:
        raise RuntimeError(
            f"No migration registered for schema version {version}; "
            f"available: {sorted(MIGRATIONS.keys())}"
        )
    return MIGRATIONS[version]
