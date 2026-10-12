"""tests/test_write_env_file_duplicate_key.py — locked-in test for SASKIA-212.

On 2026-10-12, BWS had two entries for `CF_R2_SECRET_ACCESS_KEY`:
- id 1fa51e13, value 0b07e5cc... (DEAD, created 2026-08-25)
- id 6e12fcbc, value a68b285f... (LIVE, revised 2026-10-12)

The previous `bws_get()` did `for s in secrets: if s["key"] == key: return s["value"]`
which returned the FIRST match. Since 1fa51e13 was created first, the dead value
shadowed the rotated one and the VPS env file silently kept using the revoked
secret. `saskia-rms-backups` R2 uploads failed with 403.

Fix: collect all matches, sort by `revisionDate` (or `creationDate`) descending,
warn on stderr if duplicates exist, and return the most-recently-revised value.

These tests are FAIL-CLOSED — reverting the fix (going back to first-match-wins)
must break the duplicate-key test.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load write_env_file.py as a real importable module.
# Trick: copy the file to a temp location so importlib treats it as a normal .py
# (handles __file__ and module globals correctly).
_DEPLOY_DIR = Path(__file__).resolve().parents[1] / "deploy"
_SRC = _DEPLOY_DIR / "write_env_file.py"


def _load_module():
    """Load write_env_file.py via importlib so we can patch it."""
    # Stub yaml (used only inside load_envs, which we don't call).
    sys.modules["yaml"] = MagicMock(safe_load=lambda f: {})
    tmpdir = tempfile.mkdtemp()
    tmp_path = Path(tmpdir) / "write_env_file.py"
    shutil.copy2(_SRC, tmp_path)
    spec = importlib.util.spec_from_file_location("wef_test", tmp_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wef = _load_module()

# Patch the deploy script to use a writable BWS token file (instead of
# /etc/sazon/bws-token, which only exists on the VPS). Also stub the
# BWS binary check (we always mock subprocess.run, so the bws binary
# never needs to exist).
_TMP_TOKEN = Path(tempfile.mkdtemp()) / "bws-token"
_TMP_TOKEN.write_text("fake-bws-token-for-test")
wef.BWS_TOKEN_FILE = _TMP_TOKEN
# BWS_BIN must be a path that exists (bws_get calls .exists() on it before
# calling subprocess.run). We point it at a real tmpfile we just created.
_BWS_BIN_PATH = _TMP_TOKEN.parent / "bws"
_BWS_BIN_PATH.touch()
wef.BWS_BIN = str(_BWS_BIN_PATH)


def _fake_bws_proc(secrets: list[dict]) -> MagicMock:
    """Build a fake CompletedProcess with the given secrets as bws list output."""
    proc = MagicMock()
    proc.returncode = 0
    proc.stdout = json.dumps(secrets)
    proc.stderr = ""
    return proc


def test_bws_get_returns_value_for_unique_key():
    """Sanity: a single matching entry returns its value."""
    secrets = [
        {
            "id": "1fa51e13-a959-4c67-b9af-b4b100f65c28",
            "key": "FERNET_KEY",
            "value": "unique-fernet-value",
            "revisionDate": "2026-08-25T14:56:58.149218800Z",
            "creationDate": "2026-08-25T14:56:58.149218800Z",
        }
    ]

    with patch.object(wef.subprocess, "run", return_value=_fake_bws_proc(secrets)):
        val = wef.bws_get("FERNET_KEY")
    assert val == "unique-fernet-value"


def test_bws_get_raises_keyerror_when_missing():
    """Missing key raises KeyError (caller converts to exit 2)."""
    secrets = [
        {
            "id": "abc",
            "key": "OTHER",
            "value": "x",
            "revisionDate": "2026-08-25T14:56:58Z",
            "creationDate": "2026-08-25T14:56:58Z",
        }
    ]

    with patch.object(wef.subprocess, "run", return_value=_fake_bws_proc(secrets)):
        with pytest.raises(KeyError):
            wef.bws_get("MISSING_KEY")


def test_bws_get_picks_most_recently_revised_when_duplicates_exist(capsys):
    """The locked-in regression: with two entries, return the LIVE one.

    SASKIA-212 (2026-10-12): the old 1fa51e13 (created 2026-08-25, never revised)
    was the first match, so the dead value shadowed the rotated 6e12fcbc.
    """
    secrets = [
        {
            "id": "1fa51e13-a959-4c67-b9af-b4b100f65c28",
            "key": "CF_R2_SECRET_ACCESS_KEY",
            "value": "0b07e5cc-DEAD-OLD-VALUE",
            "revisionDate": "2026-08-25T19:44:49.309920200Z",
            "creationDate": "2026-08-25T14:56:58.149218800Z",
        },
        {
            "id": "6e12fcbc-6d00-4e40-90ac-b4b8011ed05a",
            "key": "CF_R2_SECRET_ACCESS_KEY",
            "value": "a68b285f-LIVE-ROTATED-VALUE",
            "revisionDate": "2026-10-12T15:42:59.195493200Z",
            "creationDate": "2026-09-01T17:24:15.434637200Z",
        },
    ]

    with patch.object(wef.subprocess, "run", return_value=_fake_bws_proc(secrets)):
        val = wef.bws_get("CF_R2_SECRET_ACCESS_KEY")

    assert val == "a68b285f-LIVE-ROTATED-VALUE", (
        "Duplicate-key resolution failed: bws_get returned the dead value. "
        "This is the SASKIA-212 regression — first-match-wins is no longer correct."
    )

    # Warning should have been emitted on stderr.
    captured = capsys.readouterr()
    assert "WARN" in captured.err
    assert "2 entries" in captured.err
    assert "6e12fcbc" in captured.err  # the chosen id


def test_bws_get_uses_creationdate_when_revisiondate_missing():
    """Edge case: some BWS entries may lack revisionDate. Fall back to creationDate."""
    secrets = [
        {
            "id": "old-id",
            "key": "DUP_KEY",
            "value": "old-value",
            "creationDate": "2026-01-01T00:00:00Z",
            # No revisionDate.
        },
        {
            "id": "new-id",
            "key": "DUP_KEY",
            "value": "new-value",
            "creationDate": "2026-12-31T00:00:00Z",
        },
    ]

    with patch.object(wef.subprocess, "run", return_value=_fake_bws_proc(secrets)):
        val = wef.bws_get("DUP_KEY")

    assert val == "new-value"


def test_bws_get_works_when_creation_and_revision_both_missing():
    """Edge case: empty metadata — don't crash, return first match."""
    secrets = [
        {"id": "x", "key": "WEIRD_KEY", "value": "weird-value"},
    ]

    with patch.object(wef.subprocess, "run", return_value=_fake_bws_proc(secrets)):
        val = wef.bws_get("WEIRD_KEY")

    assert val == "weird-value"
