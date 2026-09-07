# Rate-limit on auth + write endpoints

**Date:** 2026-09-04
**Author:** operator (Iván) — security review
**Cost guess:** S
**Phase guess:** 1.5
**Source:** security review (2026-09-04 by Kiki)

## What

Apply `5 attempts / 15 min / IP` to `/login` POST only. Exclude `/healthz` (UptimeRobot 5-min probe) and `/healthz/deps`.

## Status

**Became Epic E3.S2 on 2026-09-04.** Shipping in Fase 1.5 hardening batch.
