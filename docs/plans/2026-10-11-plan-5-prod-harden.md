# Plan 5 — Production hardening pass (4h, MEDIUM)

> **Master plan:** `docs/plans/2026-10-11-round-5-6-master-plan.md`

## Scope
Several issues from the round-1-4 audit are NOT code bugs but
operational gaps. Ship as a "Sprint 2.2" batch.

## Tasks

### 5.1 — BWS 429 retry on deploy-test (1h)

**Symptom:** `docs/operations/2026-10-10-deploy-race-audit.md`
documents that `deploy-test` occasionally hits a transient BWS
429 when deploy-dev and deploy-test run in parallel.

**Fix:** add a 3-attempt exponential backoff in the BWS
secret-fetching code.

**Files:**
- `scripts/bws_get_secret.sh` (shell wrapper)
- Any `app/rms/backup.py` BWS calls

**Pattern:**

```bash
for attempt in 1 2 3; do
  response=$(bws secret get "$SECRET_NAME" 2>&1)
  if [[ $? -eq 0 ]]; then
    echo "$response"
    exit 0
  fi
  if [[ $response == *"429"* ]]; then
    sleep $((attempt * 5))
    continue
  fi
  echo "$response" >&2
  exit 1
done
```

### 5.2 — Feature flag for caja error rendering (30min)

**Symptom:** The round-5 `caja.html` fix (rendering `{{ error }}`)
is a small behavior change. Operators might want to disable it.

**Fix:** add a `caja_error_banner` feature flag in `settings_kv`
so the change can be rolled back without redeploy.

**Files:**
- `app/rms/settings_registry.py` (add flag to the 42-key registry)
- `app/templates/caja.html` (wrap the error block in
  `{% if settings.caja_error_banner %}`)

### 5.3 — Audit row for fiado `/cargar` (DONE round 5)

**Action:** verify it's covered by `test_fiado_cargar_writes_audit_row`.

### 5.4 — Schema version doc refresh (30min)

**Symptom:** `docs/user-guide/README.md` was bumped to schema 117
in round 5. Other docs may still reference older versions.

**Action:**

```bash
grep -rn "schema v[0-9]\|schema [0-9]\{2,3\}" docs/ \
  --include="*.md" | grep -v "117\|archived"
# Find any doc that says schema < 117 and bump it.
```

### 5.5 — Daily backup verification test (1h)

**Symptom:** `app/rms/backup.py` was fixed for migration
compatibility in round 5. But there's no test for the full
backup → restore → integrity_check roundtrip.

**File:** `tests/test_backup_live_db.py`

**Pattern:**

```python
def test_backup_live_db_roundtrip(session_factory, tmp_path):
    """Full backup → restore → integrity_check on a live-shape DB."""
    db_path = session_factory().get_bind().url.database
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"

    # Backup
    import shutil
    shutil.copy(db_path, backup_path)

    # Restore
    shutil.copy(backup_path, restored_path)

    # Integrity check
    import sqlite3
    conn = sqlite3.connect(restored_path)
    result = conn.execute("PRAGMA integrity_check").fetchone()
    conn.close()
    assert result[0] == "ok"
```

### 5.6 — Deploy race audit follow-up (1h)

**Symptom:** `docs/operations/2026-10-10-deploy-race-audit.md`
was created in round 4. Verify all 4 race-condition fixes are
documented and the audit doc is up to date.

**Action:** read the audit doc, verify each fix is referenced
in the commit log, update if any are missing.

## Acceptance
- BWS 429 retry is wired
- Caja error rendering is feature-flagged
- Docs are consistent on schema 117
- Backup roundtrip test passes

## Ship-blocked-by
None (independent of test work).

## Risk
Low. All are additive changes.
