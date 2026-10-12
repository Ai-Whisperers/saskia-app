# SASKIA-212: write_env_file.py duplicate-key resolution

**Date:** 2026-10-12
**Owner:** Iván
**Status:** shipped
**Estimate:** 30m

## What

Fix `deploy/write_env_file.py` so the `bws_get()` function returns the
**most-recently-revised** BWS entry when multiple entries share the same
key name, instead of "first match wins". On duplicate, emit a `WARN:`
line on stderr identifying the chosen id and the duplicate count, so the
operator can clean up BWS.

## Why

On 2026-10-12, BWS had two entries for `CF_R2_SECRET_ACCESS_KEY`:

| id | value | created | revised |
|---|---|---|---|
| `1fa51e13` (DEAD) | `0b07e5cc...` | 2026-08-25 | (never) |
| `6e12fcbc` (LIVE) | `a68b285f...` | 2026-09-01 | 2026-10-12 |

The previous `bws_get()` did `for s in secrets: if s["key"] == key: return s["value"]`
— first match wins. The DEAD entry was first (alphabetical / creation-order),
so the VPS env file silently kept using the revoked secret and
`saskia-rms-backups` R2 uploads failed with 403. The dead entry has been
deleted from BWS as part of this ticket.

This pattern will recur every time you rotate a key:
"add new → forget to delete old". The fix makes the deploy script
defensive against the operator forgetting the cleanup step.

## Tasks

- [x] Patch `bws_get()` to collect all matches, sort by `revisionDate`
  (with `creationDate` fallback) descending, return the most-recent.
- [x] Emit `WARN: BWS has N entries for key 'X'; using most-recently-revised
  (id=..., revised=...). Clean up duplicates in BWS to silence this warning.`
  on stderr when duplicates exist.
- [x] Delete the dead `1fa51e13` entry from BWS.
- [x] Add `tests/test_write_env_file_duplicate_key.py` with 5 RED-GREEN tests:
  - unique-key (sanity)
  - missing-key (raises KeyError)
  - **duplicate-key picks the LIVE one (the regression test)**
  - creationDate fallback when revisionDate is missing
  - empty metadata doesn't crash
- [x] Add CHANGELOG entry.

## Acceptance

- `uv run pytest tests/test_write_env_file_duplicate_key.py -v` → 5/5 GREEN.
- The locked-in test `test_bws_get_picks_most_recently_revised_when_duplicates_exist`
  FAILS if the fix is reverted (verified: with the old `for s in secrets: return s["value"]`
  loop, the test fails with the exact "first match wins" assertion).
- Re-running `deploy.sh` on the VPS produces an env file with the live
  `a68b285f...` R2 secret (verified by BWS inventory: only one
  `CF_R2_SECRET_ACCESS_KEY` entry remains as of 2026-10-12 16:04 UTC).

## Test evidence

```
tests/test_write_env_file_duplicate_key.py::test_bws_get_returns_value_for_unique_key PASSED
tests/test_write_env_file_duplicate_key.py::test_bws_get_raises_keyerror_when_missing PASSED
tests/test_write_env_file_duplicate_key.py::test_bws_get_picks_most_recently_revised_when_duplicates_exist PASSED
tests/test_write_env_file_duplicate_key.py::test_bws_get_uses_creationdate_when_revisiondate_missing PASSED
tests/test_write_env_file_duplicate_key.py::test_bws_get_works_when_creation_and_revision_both_missing PASSED
============================== 5 passed in 5.87s ===============================
```

## Operational follow-up

The next `deploy.sh` run on the VPS will rewrite `/etc/sazon/.env.prod`
with the live `a68b285f...` value. The SHA-256 idempotency check in
`write_env_file.py` ensures this rewrite only happens when the BWS
value actually differs from what's on disk — so it fires once on the
next deploy, then stays quiet.
