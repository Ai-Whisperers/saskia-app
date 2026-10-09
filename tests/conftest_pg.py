"""tests/conftest_pg.py — real Postgres fixtures via testcontainers.

Closes Phase 0 epic E2.S2. Five production hotfixes on 2026-09-04
would have been caught by a real-PG roundtrip test. Until now, only
SQLite (in-memory or file-based) was exercised, so psycopg3 dialect
quirks, JSONB column behavior, and Postgres-specific DDL never got
regression coverage.

Usage:
- Mark a test or module with @pytest.mark.pg.
- pytest -m pg boots a Postgres container once per session and
  provides `pg_engine` + `pg_session_factory` fixtures.
- pytest -m 'not pg' (the default) skips these tests entirely —
  local dev without Docker keeps working.

CI: the workflow at .github/workflows/ci.yml runs pytest -m pg after
the main suite. Without Docker, the run produces 0 collected tests
(skipped, not failed) so this never blocks PRs.

Local caveat: requires Docker. If you have the docker CLI but no
daemon (e.g., WSL2 without dockerd), the tests will skip with a clear
message rather than crash.
"""

from __future__ import annotations

import pytest

# Skip everything in this module if testcontainers isn't importable.
# This guards against environments where the dep wasn't installed
# (e.g., a fresh `uv sync` without --extra dev).
#
# testcontainers>=4.8 moved PostgresContainer from testcontainers.postgres
# (deprecated) to testcontainers.community.postgres. We pin the new path.
try:
    from testcontainers.community.postgres import (
        PostgresContainer,  # type: ignore[import-not-found]
    )
except ImportError as exc:  # pragma: no cover — defensive only
    _IMPORT_ERROR: ImportError | None = exc
    PostgresContainer = None  # type: ignore[assignment]
else:
    _IMPORT_ERROR = None


_DOCKER_REACHABLE: bool | None = None


def _docker_daemon_reachable() -> bool:
    """Cheap probe: `docker info` exits 0 only if the daemon responds.

    Avoids the 10s+ timeout testcontainers imposes when it tries to
    hit a dead daemon. We import lazily so tests that don't need PG
    never pay this cost.

    Result is cached module-level so the probe runs at most once per
    pytest session — without this, every `pg_*` fixture call would
    re-pay the subprocess cost and the session-level skip would still
    cascade per test.
    """
    global _DOCKER_REACHABLE
    if _DOCKER_REACHABLE is not None:
        return _DOCKER_REACHABLE

    import shutil
    import subprocess

    if shutil.which("docker") is None:
        _DOCKER_REACHABLE = False
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        _DOCKER_REACHABLE = result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        _DOCKER_REACHABLE = False
    return _DOCKER_REACHABLE


# Session-scoped container — boots ONCE per pytest invocation.
# Module-level pytest.fixture skips collection if the marker isn't used.
_PG_URL: str | None = None


def _start_pg_container() -> str | None:
    """Boot a Postgres container and return the SQLAlchemy URL.

    Returns None if Docker isn't available (test will skip).
    """
    global _PG_URL
    if _PG_URL is not None:
        return _PG_URL

    if _IMPORT_ERROR is not None or PostgresContainer is None:
        return None
    if not _docker_daemon_reachable():
        return None

    # image + version chosen to match Neon's major version (PG 16).
    # Smaller images (alpine) save CI bandwidth.
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    # SQLAlchemy 2.0 needs the postgresql+psycopg:// driver prefix.
    raw_url = container.get_connection_url()
    _PG_URL = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

    # Stash container for cleanup.
    _PG_URL_CONTAINER = container
    pytest._pg_container = container  # type: ignore[attr-defined]
    return _PG_URL


@pytest.fixture(scope="session")
def pg_engine():
    """Real Postgres engine with our schema applied.

    Skips if testcontainers / Docker / PostgresContainer not available.
    The container is reused for the entire pytest session — much faster
    than per-test boots.
    """
    url = _start_pg_container()
    if url is None:
        pytest.skip(
            "Postgres container not available — needs testcontainers + Docker. "
            "Run `pytest -m 'not pg'` to skip, or enable Docker for local runs."
        )

    from app.rms.db import init_db, make_engine

    engine = make_engine(url, for_tests=True)
    init_db(engine)
    yield engine
    engine.dispose()
    # Stop the container at session teardown.
    container = getattr(pytest, "_pg_container", None)
    if container is not None:
        container.stop()


@pytest.fixture
def pg_session_factory(pg_engine):
    """sessionmaker bound to pg_engine, mirroring tests/conftest.py:session_factory."""
    from app.rms.db import make_session_factory

    return make_session_factory(pg_engine)


@pytest.fixture
def pg_session(pg_session_factory):
    """Single Session for tests that don't need transaction control."""
    with pg_session_factory() as s:
        yield s
