# R2 backup retention policy

**Date:** 2026-09-04
**Author:** operator (Iván) — discovered during config audit
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `app/services/r2_backup.py` encrypts; retention is unspecified

## What

Decide and document a retention rule for `r2_backup.py`: keep last 30 daily + last 12 monthly + last 7 yearly. Add a sweep script for expired backups.

## Why now

She's been live since 2026-09-04. Each day adds a backup file. Capture the rule before we forget.

## Repro / context

- Local backup dir already has `KEEP_LOCAL_BACKUPS_DAYS = 30` (config.py).
- R2 retention is the missing twin.
## Triage

**Moved to rejected:** 2026-09-09
**Status:** DEFERRED — script built (`scripts/backup_cron.py`), operator-side cron install pending. Not a code task.
