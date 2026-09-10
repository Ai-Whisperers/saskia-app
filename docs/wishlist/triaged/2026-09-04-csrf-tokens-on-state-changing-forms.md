# CSRF token on all POST forms

**Date:** 2026-09-04
**Author:** operator (Iván) — security review
**Cost guess:** S
**Phase guess:** 1.5
**Source:** security review (2026-09-04 by Kiki)

## What

Add a CSRF token to every state-changing form. Missing or invalid token → 403. Token: `hmac(session_secret, session_id)[:32]`.

## Status

**Became Epic E3.S3 on 2026-09-04.** Bundled with `SameSite=Lax` cookie + CSP middleware.
## Triage

**Moved to triaged:** 2026-09-09
**Status:** SHIPPED — `app/rms/csrf.py` (HMAC-signed double-submit cookie + `/login` exemption). E3.S3.
