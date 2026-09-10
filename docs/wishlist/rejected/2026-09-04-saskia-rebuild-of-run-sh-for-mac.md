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
