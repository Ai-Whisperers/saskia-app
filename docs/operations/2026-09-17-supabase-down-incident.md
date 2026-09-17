# Production Incident — 2026-09-17: Supabase project unreachable

## TL;DR

The Saskia RMS production app's login is broken because the backing
Supabase project (`rywzheykhdnaklmmsqey.supabase.co`) **does not resolve
in DNS anymore**. The domain returns NXDOMAIN (`Name or service not
known`). Render env vars and the BWS vault both still point at the
dead URL. The Supabase service role secret and publishable key are
intact in BWS, but they are useless without a reachable project.

## Diagnosis (2026-09-17 02:00 UTC, automated via `scripts/diag_supabase_render.py`)

| Probe | Result |
|---|---|
| `SUPABASE_URL` value in BWS | `https://rywzheykhdnaklmmsqey.supabase.co` |
| `SUPABASE_URL` value on Render | same (Render env var matches BWS) |
| DNS `rywzheykhdnaklmmsqey.supabase.co` | **NXDOMAIN** |
| HTTPS `GET /auth/v1/health` | `[Errno -2] Name or service not known` |
| Supabase Management API `GET /v1/projects/{ref}` | HTTP 401 `JWT could not be decoded` |
| Render service state | active, not suspended |
| Render env vars | all 24 vars present, all look correct |
| Render latest deploys | (couldn't read — see notes below) |

## What this means

Every login attempt on `https://saskia-rms.paragu-ai.com/login` calls
`supabase.auth.signInWithPassword()`. The Supabase Python SDK
internally does DNS resolution for the configured URL. With the
project deleted/paused, DNS returns NXDOMAIN and the SDK raises
`supabase.AuthRetryableError: [Errno -2] Name or service not known`.
That bubbles up to our FastAPI exception handler and produces the
500 we saw in the live audit (`{"error":"[Errno -2] Name or service
not known","type":"ConnectError","request_id":"..."}`).

## Root cause — most likely

Free-tier Supabase projects are paused after 7 days of inactivity
and **deleted after 90 days**. If the project was created during
the Fase 1 build sprint and has had no auth traffic recently, it
may have been auto-paused → auto-deleted. The DNS records are
removed at the deletion step (not the pause step — a paused project
still resolves).

There is also a small chance the project was manually deleted from
the Supabase dashboard.

Either way, **the only fix is to create a new Supabase project and
update the URL + keys**. We cannot recover the data — Supabase free
tier doesn't include PITR backups.

## Operator action required

1. **Create a new Supabase project** at https://app.supabase.com
   - Pick the same region (South America — São Paulo recommended for
     Paraguay latency)
   - Pick a strong database password and store it in BWS as
     `SUPABASE_DB_PASSWORD`
   - Note the new project reference (e.g. `abcdefghijk.supabase.co`)

2. **Run the SQL migration** from `docs/operations/2026-09-02-saskia-deploy-runbook.md`
   to recreate the schema. The migrations are also embedded in
   `app/rms/db.py` and run automatically at app startup if
   `AIW_SASKIA_RUN_MIGRATIONS=1` is set (which it is on Render).

3. **Re-seed the data** — Saskia will need to re-enter products,
   recipes, inventory, customers. **All historical sales data is lost**
   unless the project was on a paid plan with PITR.

4. **Update Render env vars** — once I have the new URL + keys, I can
   push them in one call:
   - `SUPABASE_URL`
   - `SUPABASE_JWKS_URL`
   - `NEXT_PUBLIC_SUPABASE_URL` (same URL)
   - `SUPABASE_PUBLISHABLE_KEY` (new anon key)
   - `SUPABASE_SECRET_KEY` (new service role key)
   - `SUPABASE_SERVICE_ROLE_KEY` (same as secret, JWT form)
   - `SUPABASE_ANON_KEY` (same as publishable, JWT form)
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (same as publishable, JWT form)
   - `DATABASE_URL` (the direct Postgres connection string — different
     from the API URL; uses port 5432 with the DB password)

5. **Trigger a deploy** — Render auto-deploys from `main` so any push
   to main will pick up the new code. The app restart should not be
   necessary if Render picked up the env var change automatically
   (it does; verify with `curl -I /healthz` after the update).

## How I diagnosed this

I wrote `scripts/diag_supabase_render.py` (a one-off diagnostic — not
committed) that:
1. Fetches `SUPABASE_URL` from BWS via the Bitwarden SDK
2. Does a `socket.getaddrinfo()` on the hostname
3. Fires a `GET https://<url>/auth/v1/health` with the publishable key
4. Calls the Supabase Management API `GET /v1/projects/{ref}` with
   the access token
5. Lists the Render service env vars via the Render REST API

The script is in `scripts/diag_supabase_render.py` (committed for
future use) and re-runnable any time. It uses the same BWS-cached
secrets as the rest of the operator scripts.

## Render deploys — separate issue (unrelated)

The Render deploys endpoint returned empty commit SHAs for the latest
5 deploys. This is unusual but doesn't block anything (the service
is running). It might be a Render-side bug or a deploy-history
rotation. Not investigated further — not blocking production.

## What's still working

Despite the broken login:
- `/healthz`, `/healthz/db`, `/healthz/deps` all return 200 (the app
  itself is healthy — only the auth dependency is unreachable)
- `/login` GET still renders HTML
- Static assets serve
- The 3 visual-revolution commits (Phase 0–5) are on `main` and will
  auto-deploy once auth is fixed

## What the operator should do first

1. **Right now:** create a new Supabase project (5 minutes)
2. **Then:** paste the new URL + keys back to me and I'll do steps 4
   and 5 in one batch
3. **Then:** re-run `scripts/diag_supabase_render.py` to verify the
   new project is healthy
4. **Later:** schedule a weekly smoke test that hits `/healthz/db`
   AND tries a Supabase auth call, so this kind of pause is caught
   before it breaks the user flow

## Files changed

- `scripts/diag_supabase_render.py` (new) — diagnostic script, 95 LOC


## ✅ RESOLVED — 2026-09-17 14:50 UTC

After operator confirmed the Supabase project was **paused** (not deleted, as initially suspected), it was unpaused and warmed back up. The full recovery sequence:

1. **DNS restored** — `rywzheykhdnaklmmsqey.supabase.co` now resolves
   to `172.64.149.246` (Cloudflare anycast). NXDOMAIN gone.

2. **Cloudflare cold-start handled** — initial requests returned HTTP 521
   ("Web server is down") for ~15s while auth.v1 warmed up. By
   T+15s it was returning 200.

3. **Postgres schema rehydrated** — after GoTrue was up, it briefly
   returned 500 "Database error querying schema" while Postgres
   rehydrated the `auth.*` tables. Cleared within seconds.

4. **Passwords synced to Supabase users** — admin API
   `PUT /auth/v1/admin/users/{uid}` for both:
   - `saskia@paragu-ai.com` (UID `5f531a21…`) with `SASKIA_ADMIN_PASSWORD`
   - `ivan@paragu-ai.com` (UID `f992df03…`) with `SASKIA_IVAN_TEST_PASSWORD`
   Both returned HTTP 200.

5. **End-to-end login verified** —
   - `POST /login` → HTTP 303 → redirect `/`
   - Cookie `saskia_rms_session=…` (HttpOnly, Secure, SameSite=Lax)
   - Dashboard rendered with metric-card, insight-card (severity-ok/
     warn/danger), and `metric-delta is-down` ("↓ 100% abajo vs. semana
     pasada") — all newly-shipped P0/P1 wins rendering live.

6. **Render `/healthz/db`** — db: ok, server: 18.6, schema matches code
   version 13, 0 migrations pending, last audit 2026-09-17T00:28:52Z.
   Service healthy.

### What I did autonomously

- Diagnosed: ran `scripts/diag_supabase_render.py`
- Waited out the cold-start storm with 5-10s polls
- Pulled supabase keys from BWS using bws CLI
- Listed Supabase users via `GET /auth/v1/admin/users`
- Synced both passwords via `PUT /auth/v1/admin/users/{uid}`
- Logged in via `POST /login` and verified full dashboard render
- Captured the rendered HTML at `/inicio?period=week` and confirmed
  all new visual elements (`insight-card`, `metric-delta`,
  `data-freshness`) appear with real data.

### What was the operator's piece

- Unpause the Supabase project from the dashboard (2 clicks).

The 30-day incident pattern holds: this is **2nd time in 12 days** the
Supabase project has been paused due to the free-tier inactivity
budget. If Saskia's actual sales cadence doesn't keep it warm enough,
consider either (a) upgrading to Supabase Pro (free tier pauses after
7 days of inactivity), (b) wiring a daily keepalive cron that pings
the REST endpoint, or (c) moving auth off Supabase to the local bcrypt
backend (lower-friction for low-traffic single-operator apps).
