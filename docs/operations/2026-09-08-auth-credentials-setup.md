# Saskia RMS — Auth Credentials Setup (2026-09-08)

## ✅ DONE from this session

| Action | Result |
|---|---|
| Generated 2 new passwords (20 chars each, cryptographically secure) | sha `32f43630`, sha `171e3c19` |
| Updated BWS `SASKIA_USER_PASSWORD` | old sha `18917c74` (16 chars) → new sha `32f43630` (20 chars) |
| Updated BWS `SASKIA_IVAN_TEST_PASSWORD` | old sha `436a702e` (20 chars) → new sha `171e3c19` (20 chars) |
| Confirmed Supabase project status | **Project is paused** — Admin API returns 540 "Project paused" |

## ⚠️ BLOCKED — operator action required

The new passwords are saved in BWS but **Supabase Auth itself has not been updated** because the project is paused. Login on `https://saskia-rms.paragu-ai.com/login` will continue to fail until you do both steps below.

### STEP 1 — Unpause the Supabase project (2 min, browser)

1. Open https://supabase.com/dashboard/project/sspnqgiiuhrzzfaavysn
2. If you see a yellow "Project Paused" banner, click **"Restore project"**
3. Wait ~60s for the database to come back online

You'll know it's done when the URL stops redirecting you and the dashboard shows the SQL editor / table view.

### STEP 2 — Sync new passwords to Supabase users (one curl block per user)

Run these from any machine with normal DNS access. The values come from BWS — you don't need to type them, the script fetches them via the Bitwarden SDK.

If you have Python + the Bitwarden token at `/opt/data/.hermes/inbox/bws-token.secret`, run:

```bash
cd /opt/data/profiles/ivan/scratch
/opt/data/.venv/bin/python3.11 update_supabase_users.py
```

That script already exists and does:
1. Fetches `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` + `SASKIA_USER_PASSWORD` + `SASKIA_IVAN_TEST_PASSWORD` from BWS (in subprocess, never echoed)
2. Lists existing Supabase users, finds `saskia@paragu-ai.com` and `ivan@paragu-ai.com`
3. Calls `PUT /auth/v1/admin/users/<uid>` with `{"password": "..."}` for each
4. Prints `PUT status=200` (or `PUT_FAIL <code>`) — never the value

If you can't run Python there, run from this same sandbox right now (it has BWS access) and it will use the Cloudflare anycast IP workaround to bypass DNS:

```bash
/opt/data/.venv/bin/python3.11 /opt/data/profiles/ivan/scratch/run_supa_update.py
```

### STEP 3 — Verify login

Open https://saskia-rms.paragu-ai.com/login in your browser. Type:
- Username: `saskia@paragu-ai.com` (or `ivan@paragu-ai.com`)
- Password: (the new one — fetch it from BWS via `bws secret get --output json <UUID>` or run `python3 -c "..."` from the script)

If login succeeds → done.

If login still fails after both steps → paste the error message and I'll diagnose further.

## Credentials at a glance (BWS UUIDs, no values)

| BWS key | UUID prefix | Length | Sha prefix |
|---|---|---|---|
| `SASKIA_USER_PASSWORD` | `7c338291` | 20 | `32f43630` |
| `SASKIA_IVAN_TEST_PASSWORD` | `5c9e6c24` | 20 | `171e3c19` |
| `SASKIA_ADMIN_PASSWORD` | (unchanged, sha `1222fa85`) | 20 | `1222fa85` |
| `SUPABASE_URL` | (live `https://sspnqgiiuhrzzfaavysn.supabase.co`) | 40 | `ba6928fe` |
| `SUPABASE_SERVICE_ROLE_KEY` | (admin API key) | 219 | `da0078bb` |
| `RENDER_API_KEY` | `cf4514fd` | 32 | `033df5cd` |
| `DATABASE_URL` | (live Neon Postgres) | 146 | `52e76e51` |

## ⚠️ Security note

The OLD `SASKIA_USER_PASSWORD` value (`7XaRAnNun8PJZu3H`, sha `18917c74`) was accidentally printed to this session's transcript during a debugging step (I dumped a BWS JSON response to find the project_id for the update call). That value is now considered compromised regardless of whether you keep using it. The new password I generated and saved (`sha=32f43630`) was never printed.

Per credential-redacted-grep protocol I should have read it via a subprocess that only echoes boolean checks, not the JSON blob. Lesson recorded in session memory: never `json.dumps()` a BWS secret response — read individual fields, never the whole payload.

## Files left on disk (cleanup status)

| Path | Status |
|---|---|
| `/tmp/saskia_new_pwd.txt` | DELETED (shredded after save) |
| `/tmp/ivan_new_pwd.txt` | DELETED (shredded after save) |
| `/tmp/_supa`, `/tmp/_key`, `/tmp/_spwd`, `/tmp/_ipwd` | cleaned up between runs |
| `/opt/data/profiles/ivan/scratch/update_supabase_users.py` | reusable runbook script |
| `/opt/data/profiles/ivan/scratch/run_supa_update.py` | wrapper that fetches + runs |
