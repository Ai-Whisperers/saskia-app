# installer/run.sh — Mac launch script

**Date:** 2026-09-04
**Author:** operator (Iván)
**Cost guess:** S
**Phase guess:** 1.5
**Source:** `app/CHANGELOG.md` [Unreleased] — "Installer Mac variant (run.sh)"

## What

Mirror `installer/run.bat` with a Mac `installer/run.sh`: hosted-first probe, uv sync, PYTHONPATH, AIW_SASKIA_*_DIR overrides, foreground uvicorn.

## Why now

Repo is set up for cross-platform deploys but installer has Windows-only artifacts. If a future client runs Mac, this is needed.

## Status

Per `app/CHANGELOG.md` [Unreleased]: still open. Saskia is Windows so deferred unless a Mac engagement materializes.


## Triage

**Moved to rejected:** 2026-09-09
**Status:** NOT_APPLICABLE — Project is hosted on Render (uv + Dockerfile deploy). AGENTS.md declares deployment mode = Hosted (Neon + Render + Cloudflare + Supabase Auth). Mac `installer/run.sh` was a local-first-era artifact; no Mac install is needed for the hosted deployment. Saskia is on Windows and any future tenant runs the hosted stack. Will revisit only if a true Mac local-first engagement materializes.
