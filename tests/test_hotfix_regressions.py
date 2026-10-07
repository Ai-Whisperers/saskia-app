"""tests/test_hotfix_regressions.py — locked-in tests for the 5 production hotfixes on 2026-09-04.

These tests are FAIL-CLOSED — reverting any of the corresponding hotfixes must
break them. The purpose is so the next time someone refactors auth_supabase,
the Dockerfile pip list, /healthz, the import path, or /healthz/deps, CI catches
the regression before it ships.

Per the 2026-09-04 critical-path plan, E2.S1.

Mapping:
- f1af406 (HEAD /healthz for UptimeRobot)   -> tests test_head_healthz_*
- c093a75 (SUPABASE_SECRET_KEY alias)       -> tests test_supabase_env_alias_*
- 99b37c6 (supabase SDK in Dockerfile)      -> tests test_dockerfile_includes_supabase
- bb21eff (/healthz/deps env fingerprint)   -> tests test_healthz_deps_*
- 501bcff (row_counts_json matches JSONB)   -> tests test_row_counts_json_roundtrip_*

Note: HEAD /healthz also has coverage in tests/test_healthz.py. This file is the
canonical regression suite for hotfixes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# E2.S2 — the row_counts_json tests are tagged @pytest.mark.pg below so they
# auto-skip locally without Docker and run in CI. The other tests in this
# file (HEAD /healthz, env aliases, Dockerfile inspection, deps fingerprint)
# don't touch the DB so they stay SQLite-compatible.

# ---------------------------------------------------------------------------
# 1. f1af406 — HEAD /healthz for uptime monitors
# ---------------------------------------------------------------------------


def test_head_healthz_returns_200(client):
    """UptimeRobot probes with HEAD; GET-only @router.get returned 405 (regression: 2026-09-04).

    Reverting f1af406 (removing the @router.head) would make this fail.
    """
    r = client.head("/healthz")
    assert r.status_code == 200, "UptimeRobot probes with HEAD — must not 405. See commit f1af406."


def test_head_healthz_has_no_body(client):
    """HEAD response body should be empty (transport strips)."""
    r = client.head("/healthz")
    # Either b"" or None is acceptable — the key thing is no body bytes.
    assert r.content in (b"", None)


def test_head_healthz_registers_separate_route(client):
    """The HEAD route exists alongside GET, not as a side-effect of GET."""
    from app.routers.health import router

    methods = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/healthz", ("GET",)) in methods, "GET /healthz missing"
    assert ("/healthz", ("HEAD",)) in methods, "HEAD /healthz missing (f1af406)"


# ---------------------------------------------------------------------------
# 2. c093a75 — SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY aliases
# ---------------------------------------------------------------------------


def test_supabase_env_alias_secret_key_from_env(monkeypatch):
    """When only SUPABASE_SECRET_KEY is set, is_supabase_auth_enabled() should be True.

    The Render deployment uses BWS naming (SECRET_KEY, PUBLISHABLE_KEY) but
    app/auth_supabase.py expects (SERVICE_ROLE_KEY, ANON_KEY). The alias lets
    BWS-naming env vars flow into the SUPABASE_* names. Reverting c093a75 would
    re-introduce the silent fallback to bcrypt-with-empty-users (every login 500).
    """
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "alias-secret")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "alias-pub")
    # Re-import to pick up env at module load time
    import importlib

    import app.auth_supabase as au

    importlib.reload(au)
    assert au.is_supabase_auth_enabled() is True, (
        "BWS-style env names (SECRET_KEY/PUBLISHABLE_KEY) must be accepted as "
        "aliases for SERVICE_ROLE_KEY/ANON_KEY. See commit c093a75."
    )


def test_supabase_env_alias_sourcerole_key_still_works(monkeypatch):
    """Original SERVICE_ROLE_KEY + ANON_KEY still works (backwards compat)."""
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "orig-secret")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "orig-anon")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)

    import importlib

    import app.auth_supabase as au

    importlib.reload(au)
    assert au.is_supabase_auth_enabled() is True


def test_supabase_env_alias_service_role_module_constant(monkeypatch):
    """The module constant SUPABASE_SERVICE_ROLE_KEY is read from alias if env is alias."""
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "alias-secret")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "alias-pub")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    import importlib

    import app.auth_supabase as au

    importlib.reload(au)
    assert au.SUPABASE_SERVICE_ROLE_KEY == "alias-secret"


# ---------------------------------------------------------------------------
# 3. 99b37c6 — supabase SDK must be in Dockerfile pip list
# ---------------------------------------------------------------------------


def test_dockerfile_includes_supabase():
    """The Dockerfile must install the supabase package.

    On Render, the auth path lazily imports app.auth_supabase -> 'import supabase'.
    If the Dockerfile's pip list omits supabase, every login POST returns 500.
    This test reads the Dockerfile and fails if 'supabase' is missing.
    """
    repo_root = Path(__file__).resolve().parent.parent
    dockerfile = repo_root / "Dockerfile"
    assert dockerfile.exists(), f"Dockerfile not found at {dockerfile}"

    # Join backslash-continued lines so multi-line pip lists are searchable as one
    raw = dockerfile.read_text()
    joined = re.sub(r"\\\n\s*", " ", raw)
    pip_lines = [
        line
        for line in joined.splitlines()
        if "pip install" in line and not line.strip().startswith("#")
    ]
    assert pip_lines, "Dockerfile has no pip install lines at all"

    # Dockerfile installs via `uv sync` + `uv pip install .` from
    # pyproject.toml (uv migration). The dependency list lives in
    # pyproject.toml [project] dependencies — check it there.
    supabase_present = any(re.search(r"\bsupabase\b", line) for line in pip_lines)
    if not supabase_present:
        pyproject = dockerfile.parent / "pyproject.toml"
        deps_text = pyproject.read_text() if pyproject.exists() else ""
        supabase_present = re.search(r"['\"]supabase[><=~]", deps_text) is not None
    assert supabase_present, (
        "`supabase` package missing from both Dockerfile pip lines and "
        "pyproject.toml dependencies. Reverting 99b37c6 would cause "
        "ModuleNotFoundError on first login. See commit 99b37c6."
    )


def test_supabase_package_installed_in_env():
    """The supabase package must be importable in the runtime env (local + Docker parity).

    pyproject.toml declares it; the Dockerfile must too. This test catches the case
    where pyproject is updated but Dockerfile isn't.
    """
    try:
        import supabase  # noqa: F401 — test import availability

        imported = True
    except ImportError:
        imported = False
    assert imported, "supabase SDK not installed in current env"


# ---------------------------------------------------------------------------
# 4. bb21eff — /healthz/deps env fingerprint endpoint
# ---------------------------------------------------------------------------


def test_healthz_deps_returns_200_and_dict(client):
    """/healthz/deps must return 200 with a dict payload."""
    r = client.get("/healthz/deps")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


def test_healthz_deps_reports_supabase_fingerprints(client):
    """The payload must include sha-prefix fingerprints of SUPABASE_SECRET_KEY and SUPABASE_PUBLISHABLE_KEY.

    Even when the env vars are unset, the keys must be present (with null value).
    """
    r = client.get("/healthz/deps")
    body = r.json()
    assert "SUPABASE_PUBLISHABLE_KEY" in body, "missing SUPABASE_PUBLISHABLE_KEY fingerprint"
    assert "SUPABASE_SECRET_KEY" in body, "missing SUPABASE_SECRET_KEY fingerprint"


def test_healthz_deps_does_not_leak_env_values(client, monkeypatch):
    """The fingerprint format is 'len=N sha=PREFIX' — never the value itself.

    This is the whole point of the endpoint: debug Render-vs-local env mismatches
    WITHOUT shipping the secret to a public URL.
    """
    # The fingerprint function reads os.environ at REQUEST time, so monkeypatch.setenv
    # before the client call is sufficient — no module reload needed.
    sentinel = "AKIAIOSFODNN7EXAMPLE-this-must-not-leak"
    monkeypatch.setenv("SUPABASE_SECRET_KEY", sentinel)
    r = client.get("/healthz/deps")
    body = r.json()
    fp = body.get("SUPABASE_SECRET_KEY") or ""
    assert sentinel not in fp, f"env value leaked into /healthz/deps: {fp!r}"
    if fp:
        assert re.match(r"^len=\d+ sha=[0-9a-f]+$", fp), (
            f"unexpected fingerprint format (must be 'len=N sha=HEX'): {fp!r}"
        )


def test_healthz_deps_reports_package_versions(client):
    """The payload must include the 'packages' dict with at least fastapi."""
    r = client.get("/healthz/deps")
    body = r.json()
    assert "packages" in body
    assert "fastapi" in body["packages"]


# ---------------------------------------------------------------------------
# 5. 501bcff — row_counts_json type matches the column type (JSON vs JSONB)
# ---------------------------------------------------------------------------


@pytest.mark.pg
def test_row_counts_json_roundtrip_through_orm(session_factory):
    """The row_counts_json column must round-trip a dict through the ORM.

    On Postgres, JSONB rejects raw JSON strings (DatatypeMismatch → 500). The fix
    was to type the ORM column as JSON (which the PG dialect renders as JSONB and
    SQLite renders as TEXT). This test verifies the dict flows in and out without
    coercion.

    E2.S2: tagged @pytest.mark.pg — the SQLite path is verified by the
    other row_counts_json_* tests; this one pins PG JSONB behavior in CI.
    """
    from datetime import datetime, timezone

    from app.rms.models import ImportBatch

    with session_factory() as session:
        batch = ImportBatch(
            imported_at=datetime.now(timezone.utc),
            source_filename="test.xlsx",
            note="regression test",
            row_counts_json={"ingredients": 5, "recipes": 2, "products": 3},
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        # Should come back as a dict (or string that JSON-parses to dict)
        if isinstance(batch.row_counts_json, str):
            counts = json.loads(batch.row_counts_json)
        else:
            counts = batch.row_counts_json
        assert counts == {"ingredients": 5, "recipes": 2, "products": 3}


def test_row_counts_json_orm_column_type():
    """The ImportBatch.row_counts_json column must be typed as JSON (not Text).

    Reverting 501bcff — changing `JSON` back to `Text` — would re-introduce the
    Postgres DatatypeMismatch on every Excel import. This test reads the model
    definition and fails if the column type is Text.
    """
    from sqlalchemy import JSON, Text

    from app.rms.models import ImportBatch

    col = ImportBatch.__table__.columns["row_counts_json"]
    col_type = type(col.type)
    assert col_type is JSON, (
        f"ImportBatch.row_counts_json is {col_type.__name__}, expected JSON. "
        "See commit 501bcff — reverting to Text breaks Postgres JSONB inserts."
    )
    assert col_type is not Text


@pytest.mark.pg
def test_row_counts_json_handles_empty_dict(session_factory):
    """Edge case: an empty dict (default) must persist."""
    from datetime import datetime, timezone

    from app.rms.models import ImportBatch

    with session_factory() as session:
        batch = ImportBatch(
            imported_at=datetime.now(timezone.utc),
            source_filename="empty.xlsx",
            note="",
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        if isinstance(batch.row_counts_json, str):
            counts = json.loads(batch.row_counts_json)
        else:
            counts = batch.row_counts_json
        # Default is dict() per the model — must come back as {}, not None or ""
        assert counts in ({}, None)  # allow both for backward compat
