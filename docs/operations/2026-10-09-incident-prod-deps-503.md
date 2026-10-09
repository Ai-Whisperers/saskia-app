# Incident — 2026-10-09 — prod /healthz/deps 503 (wrong Supabase URL)

**Status:** Open. Caught by `scripts/print_deploy_state.py`.
**Severity:** Medium. Prod is up (`/healthz` = 200) and login works (operator confirmed in prior session). The 503 on `/healthz/deps` is informational but it indicates a real config drift.

## What

`https://saskia-vps.paragu-ai.com/healthz/deps` returns HTTP 503 with body:

```json
{"supabase":{"ok":false,"url_host":"rywzheykhdnaklmmsqey.supabase.co",
 "http_status":null,"error_class":"DNSError",
 "reason":"[Errno -2] Name or service not known"}}
```

The `url_host` is the **wrong Supabase project**. Prod should be hitting `aiwhisperers.supabase.co` (the live project). The test/dev Supabase project `rywzheykhdnaklmmsqey.supabase.co` doesn't resolve from the VPS — that's the DNS error.

## Where

`/etc/sazon/.env.prod` on the VPS at `38.9.96.179` (mode `0600`):

```
SUPABASE_URL=https://rywzheykhdnaklmmsqey.supabase.co
```

This was written by `deploy/write_env_file.py` from the BWS secret named `SUPABASE_URL` in the BWS project that the prod deploy reads from. The value is the test/dev project URL, not the prod project URL.

## Why

Either:
1. The BWS project that the prod env reads from has the wrong `SUPABASE_URL` value
2. The `deploy/envs.yaml` `prod` row's `bws_keys` list is reading the `SUPABASE_URL` from the wrong BWS project

Per the deploy plan, **prod and test share one BWS project** (test and prod's Supabase auth is the same `aiwhisperers.supabase.co` project; dev has a separate project). The fact that prod's `SUPABASE_URL` ends in `rywzheykhdnaklmmsqey.supabase.co` (the dev project) means the wrong BWS project is being read.

## Impact

- **Prod is up**: `/healthz` returns 200. Login + the app work.
- **Supabase auth is broken for prod users**: The auth endpoint on the wrong Supabase project will reject logins. Operator confirmed earlier that Saskia's login DOES work, so either:
  - The `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` are the prod project's keys (and only the URL is wrong)
  - OR the auth flow is falling back to local-bcrypt via `using_supabase()` when the URL is unreachable
- **Cloudflare Tunnel**: The DNS lookup fails BEFORE the HTTP request, so this is the cleanest possible failure mode (TCP RST, no API call).

## How to fix

1. **Verify which BWS project the prod env reads from**: `deploy/envs.yaml` `prod.bws_keys` lists the key names. Find the BWS project that holds those names.
2. **Check `SUPABASE_URL` in that project**: should be `https://aiwhisperers.supabase.co`
3. **If wrong**: fix the BWS secret. The next `deploy.sh --env=prod` will pick up the new value.
4. **If BWS is right but env file is stale**: `bash scripts/deploy.sh --env=prod` to refresh the env file.
5. **Verify**: `scripts/print_deploy_state.py` should show `OK 200` for prod `/healthz/deps`.

## How it was caught

The new `scripts/print_deploy_state.py` (added 2026-10-09 in the CI/CD best-practices pass) probes all 3 envs and prints a table. The table showed:

```
env   hostname                   healthz  deps    backup
----  -------------------------  -------  ------  ------
prod  saskia-vps.paragu-ai.com   OK 200   ⚠ 503   OK 200
test  saskia-test.paragu-ai.com  OK 200   OK 200   OK 200
dev   saskia-dev.paragu-ai.com   OK 200   OK 200   OK 200
```

The `⚠ 503` for prod deps was the signal. Without the script, this would have been invisible.

## Lesson

`/healthz` is not enough. `/healthz/deps` is the actual app-level health check. Sazon's existing 3-endpoint healthz design (`/healthz`, `/healthz/deps`, `/healthz/backup`) is correct; the missing piece was an **operator-visible** aggregation. That's what `print_deploy_state.py` provides.
