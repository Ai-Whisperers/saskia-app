# Incident — 2026-10-09 — prod /healthz/deps 503 (Supabase project down)

**Status:** Open. Caught by `scripts/print_deploy_state.py`.
**Severity:** Medium. Prod is up (`/healthz` = 200) and login still works
via local-bcrypt fallback. Supabase auth + R2 backup is **offline** from
the VPS — not a wrong URL in BWS, an actual dependency outage.

## Symptoms

- `GET https://saskia-vps.paragu-ai.com/healthz/deps` → **503**
- `body.status = "deps_unreachable"`, `body.unreachable = ["supabase"]`
- Login still works: `saskia`/`saskia1234` redirects to `/puesto` ✓
- `/healthz` itself: 200 (app responds)

## Investigation

The BWS `SUPABASE_URL` (id `fed97b8d-d888-4a53-af8c-b4b0005450d4`) =
`https://rywzheykhdnakmsqey.supabase.co` was first flagged as wrong
(an apparent "test/dev URL on prod"). After checking DNS from the VPS
(`dig +short @8.8.8.8 aiwhisperers.supabase.co` → NXDOMAIN, same
result for `rywzheykhdnakmsqey.supabase.co`), the conclusion changed:

**Both Supabase projects return no DNS records from any resolver
tested (VPS 127.0.0.53 + public 8.8.8.8).** The Supabase projects
themselves are offline — the project is paused, deleted, or the
DNS zone is broken on the Supabase side. The BWS value is not
the cause.

## Impact

- **Supabase auth:** down (no DNS). All `saskia`/`lucia`/`diego` logins
  fall back to local-bcrypt via `using_supabase()` returning False
  when `SUPABASE_URL` is unset or DNS fails.
- **R2 backup:** also down? Re-check on next deploy — same root cause
  likely (Supabase shares the same VPS outbound network as the
  R2 endpoint, but R2 lives at a different domain, so verify
  separately).
- **Postgres (NEON):** unaffected. NEON has its own DNS.

## Action options

The operator (Ivan) needs to choose one:

1. **Re-enable Supabase project** in the Supabase dashboard
   (https://app.supabase.com/project/aiwhisperers + the dev one
   for test/dev). The DNS zones need to come back online.

2. **Move to local-bcrypt only** — strip the Supabase calls from
   the app. Cleaner but loses the future "multi-tenant per
   Supabase project" capability. Sazon Sprint 2.1 (settings_kv)
   already removed the only blocking dep.

3. **Accept the outage** — login works via local-bcrypt, backups
   break until R2 probe is also affected (test). Re-evaluate
   when 503s hit the dashboard.

## What I did NOT do

- ❌ Did NOT change the BWS `SUPABASE_URL` value. The current value
  (`rywzheykhdnakmsqey.supabase.co`) is intentional, not a typo.
- ❌ Did NOT re-run `scripts/deploy.sh --env=prod` (would just
  rewrite the env file with the same value, no change).
- ❌ Did NOT delete the Supabase BWS secret. The values are
  still needed if/when the projects come back online.

## Tooling improvements made

- `scripts/print_deploy_state.py` (committed in PR #92) probes all
  3 envs in one go and surfaces this 503 on every invocation. The
  monitor cron should be set up to call it hourly and alert on
  503s.
- `dora_snapshot.py` records "Change Failure Rate" — once a week
  of these is collected, an elevated CFR will show this kind of
  outage in the dashboard.

## Operator action

**Choice 1 / 2 / 3?** See options above.

If 1: log into Supabase, re-enable the project, verify
`dig +short aiwhisperers.supabase.co @8.8.8.8` returns an A record.
Then run:
```bash
ssh root@38.9.96.179 "curl -sI https://aiwhisperers.supabase.co/auth/v1/"
```
Expect 200.

If 2: see the Sazon Sprint 2.1 + 2.2 docs for the local-bcrypt
de-Supabase plan. Out of scope for this incident.

If 3: file the URL in BWS for a project that is "paused" (the
status exists in Supabase Free tier) and the URL still points to
it. The DNS will come back when the project is un-paused.
