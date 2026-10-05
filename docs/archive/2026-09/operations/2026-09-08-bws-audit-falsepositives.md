# 2026-09-08 BWS audit false-positives catalog

During the BWS reliability audit on 2026-09-08, several entries
were flagged as suspicious. Most turned out to be **legitimate
placeholder values, version-stamped keys, or different-key-name
duplicates** — not actual security concerns.

This document catalogs each "false positive" so future audits
don't waste cycles re-investigating.

## Categorically false positives — DO NOT RE-FLAG

These are intentional placeholders or version-stamped keys, NOT
real security issues:

| BWS key | Sha | Notes |
|---|---|---|
| `NOTION_API_KEY` | `1eae5c32` | All four "fake" tokens share this sha — actual placeholder. Operator has no Notion business plan. |
| `RESEND_API_KEY` | `1eae5c32` | Same sha as above; placeholder until operator subscribes to Resend. |
| `SENDGRID_API_KEY` | `1eae5c32` | Same. |
| `STRIPE_SECRET_KEY` | `1eae5c32` | Same. |
| `TWILIO_ACCOUNT_SID` | `1eae5c32` | Same. |
| `TWILIO_AUTH_TOKEN` | `1eae5c32` | Same. |
| `BREVO_MCP_API_KEY` | `be10a9ba` | Different sha; distinct placeholder for the MCP service. |
| `SUPABASE_DB_URL` | n/a | Value = literal `"ROTATE-ME-2026-08-13"`. Known placeholder. No consumer of this var. |

Each of these has `[DEAD sha=... DATE]` prefix in their BWS note
as of 2026-09-08T16:00.

## Corrected entries that need RE-checking each audit

These are NOT false positives — they were intentionally set, but
their BWS note historically referenced the WRONG Supabase project
(`sspnqgiiuhrzzfaavysn` — paragu-ai-builder). After the 2026-09-08
correction, they point at Saskia's project (`rywzheykhdnaklmmsqey`).
The note MUST be updated each time the underlying Supabase project
changes:

| BWS key | Sha | Notes |
|---|---|---|
| `SUPABASE_URL` | `b9508847` | Now points at `rywzheykhdnaklmmsqey.supabase.co` (saskia's, not paragu-ai-builder's). |
| `SUPABASE_SECRET_KEY` | `ca879f13` | Service-role key, owner = `rywzheykhdnaklmmsqey`. |
| `SUPABASE_PUBLISHABLE_KEY` | `32f6ba59` | Anon public, owner = `rywzheykhdnaklmmsqey`. |
| `SUPABASE_ANON_KEY` | `12302f88` | Anon JWT, owner = `rywzheykhdnaklmmsqey`. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `12302f88` | (same key, client-side bundle mirror). |
| `NEXT_PUBLIC_SUPABASE_URL` | `b9508847` | (mirror for client bundle). |
| `SUPABASE_SERVICE_ROLE_KEY` | `84364324` | Operationally tied to previous Supabase project but operator uses Anon for sign-in. |
| `SUPABASE_JWKS_URL` | `fd22ad7b` | (Jkks for token verification). |

If any of these were re-flagged in a future audit, first check
`docs/operations/2026-09-08-auth-credentials-setup.md` to confirm
whether they were corrected, then verify via
`scripts/check_render_env.py` that they're still aligned with
`rywzheykhdnaklmmsqey`.

## Legitimate dead creds that we never fixed

These were on the "fix list" but kept as-is because the operator
didn't authorize replacement:

- **`CF_API_TOKEN`** — `c3a7f61e-12a8-4c13-99d7-b4be016ca093`. 401.
  Operator uses `R2_API_TOKEN_CFUT` and `CF_DNS_EDIT_TOKEN` for
  actual operations. Re-flag `[DEAD c3a7f61e]`.
- **`NEON_API_KEY`** — currently flagged ERR 400. Used for the
  Management API (not the DB connection, which uses DATABASE_URL).
  Operator uses Neon web UI for management.

These are stuck-dead-but-acceptable because they don't impact
production. Don't try to "fix" them by removing or rotating —
the operator has the context for whether they're actually needed.

## How to do this audit efficiently in the future

When the operator asks "audit BWS again":

1. Open the BWS secrets cache tsv.
2. Run `scripts/bws_liveness_audit.py` (or similar).
3. Skip any entries with `[DEAD sha=... DATE]` in their notes.
4. For entries still suspicious after that, check this doc.
5. Only spend time investigating things not in either category.
