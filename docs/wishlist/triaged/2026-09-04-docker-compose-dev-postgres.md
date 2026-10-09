# docker-compose.dev.yml (PG + app) for local dev

**Date:** 2026-09-04
**Author:** Kiki — discovered while planning E2.S2
**Cost guess:** S
**Phase guess:** 1.5
**Source:** critical-path plan E2.S2

## What

A `docker-compose.dev.yml` that spins up Postgres + the app on `127.0.0.1:8765`.

## Why now

The 5 production hotfixes (2026-09-04) all happened because we couldn't reproduce the hosted data shape locally. A `docker-compose up` would have caught 4 of 5.


## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `docker-compose.dev.yml` (Postgres 16-alpine + app on 127.0.0.1:8765). Verified by `tests/test_dev_tooling.test_docker_compose_exists`. Pre-existing prior to test_dev_tooling audit (commit 928f08d aligns contract).
