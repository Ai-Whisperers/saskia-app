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
