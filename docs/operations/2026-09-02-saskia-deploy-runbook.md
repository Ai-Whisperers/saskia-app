# Saskia RMS — Hosted Deploy Runbook (Path C, "she just logs in")

**Date:** 2026-09-02
**Companion to:** `docs/operations/2026-09-02-saskia-team-tasks.md`
**Audience:** operator (Ivan) — paste these commands sequentially
**Goal:** in ~50 min of operator time + ~30 min of agent verification, the hosted app is live at `https://saskia-rms.paragu-ai.com` and Saskia can log in.

---

## Pre-flight (5 min, do these BEFORE the steps below)

```
[ ] Read docs/operations/2026-09-02-saskia-decision-hosted-pivot.md
[ ] Confirm you have admin access to: neon.tech, supabase.com, render.com, dash.cloudflare.com, paragu-ai.com DNS
[ ] Confirm you have the GH_TOKEN with contents:write to Ai-Whisperers/saskia-app (the one used in the prior sessions)
[ ] Have a terminal with `uv` installed (already on Ivan's box)
```

---

## Step 1 — Neon project (5 min)

**Action in browser:** https://console.neon.tech → Sign in (Google SSO) → New Project.

| Field | Value |
|---|---|
| Project name | `saskia-rms` |
| Region | US East (Ohio) — closest free-tier region to Paraguay |
| Postgres version | 16 (default) |
| Compute | Auto-scaling (default; free tier 0.5GB) |

Click **Create Project**. Wait ~30s for provisioning.

**Action in browser:** Click "Connection string" dropdown → "Connection details" → copy the **pooled** connection string.

It looks like: `postgresql://neondb_owner:<password>@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`

**Save to BWS (Pattern 5 — credential never appears in terminal output):**

```bash
# Use the BWS SDK to save the DATABASE_URL without echoing it.
# Replace <DATABASE_URL> with the value you copied (paste only into your local editor, not the command).
python3 - <<'PYEOF'
import sys, uuid
sys.path.insert(0, '/opt/data/.venv/lib/python3.11/site-packages')
from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType
t = open('/opt/data/.hermes/inbox/bws-token.secret').read().strip()
c = BitwardenClient(ClientSettings(
    api_url='https://api.bitwarden.com',
    identity_url='https://identity.bitwarden.com',
    user_agent='saskia-deploy/1',
    device_type=DeviceType.SERVER,
c.auth().login_access_token(t, None)

# TODO: operator pastes DATABASE_URL here (one line, between quotes).
# The script will save it to BWS and never echo the value.
db_url = "<PASTE_DATABASE_URL_HERE>"

# Create the secret
result = c.secrets().create(
    organization_id=uuid.UUID(open('/opt/data/.hermes/inbox/org-id.txt').read().strip()),
    name='SASKIA_NEON_DATABASE_URL',
    value=db_url,
    note='Saskia RMS hosted DB. Free tier 0.5GB, US East. 2026-09-02.',
)
print(f"saved: {result.id}")
PYEOF
```

**Expected output:** A line like `saved: <uuid>`. **DO NOT paste this UUID anywhere chatty** — it's a BWS secret identifier.

**Acceptance:** BWS has the secret; the value never appeared in this terminal.

---

## Step 2 — Supabase project (5 min)

**Action in browser:** https://supabase.com/dashboard → Sign in → New Project.

| Field | Value |
|---|---|
| Name | `saskia-auth` |
| Database password | (generate one, save to BWS as `SASKIA_SUPABASE_DB_PWD`) |
| Region | Same as Neon (US East) for low latency |
| Plan | Free |

Click **Create new project**. Wait ~2 min for provisioning.

**Action in browser:** Settings (⚙) → API. Copy three values:

- **Project URL** → save to BWS as `SASKIA_SUPABASE_URL`
- **anon public key** → save to BWS as `SASKIA_SUPABASE_ANON_KEY`
- **service_role secret** (click "Reveal" first) → save to BWS as `SASKIA_SUPABASE_SERVICE_ROLE_KEY`

Use the same BWS SDK pattern as Step 1 (one script, three `create()` calls).

**Then:** Authentication → Users → **Add user → Create new user**:

| Field | Value |
|---|---|
| Email | `saskia@paragu-ai.com` |
| Password | Click "Generate password" → copy → save to BWS as `SASKIA_USER_PASSWORD` |
| Auto Confirm User | ✅ Yes (so she can log in immediately without email confirmation) |

**Acceptance:** 4 BWS entries created (`SASKIA_SUPABASE_URL`, `SASKIA_SUPABASE_ANON_KEY`, `SASKIA_SUPABASE_SERVICE_ROLE_KEY`, `SASKIA_USER_PASSWORD`).

---

## Step 3 — Cloudflare Tunnel (10 min)

**Assumes:** Ivan's AIW-org cloudflared (PID 2678232) is still running. If not, restart it: `systemctl --user start cloudflared`.

**Action in browser:** https://one.dash.cloudflare.com → Zero Trust → Networks → Tunnels → **Create a tunnel**.

| Field | Value |
|---|---|
| Tunnel name | `saskia-rms` |
| Tunnel type | Cloudflared |

Skip "Install and run a connector" — we'll add this as a 2nd ingress on Ivan's existing tunnel.

**Action in browser:** Public Hostname → **Add a public hostname**:

| Field | Value |
|---|---|
| Subdomain | `saskia-rms` |
| Domain | `paragu-ai.com` |
| Service type | HTTP |
| URL | `http://localhost:8000` (where Render will serve; we use a CF-side proxy through Ivan's existing tunnel) |

**Save the tunnel token** (shown after creation) → save to BWS as `SASKIA_CF_TUNNEL_TOKEN`.

**Action on Ivan's box** (the box where cloudflared PID 2678232 runs):

```bash
# Edit /opt/data/cloudflared-config.yml to add the saskia ingress rule
# The new entry should be added BEFORE the catch-all 404 rule.
cat >> /opt/data/cloudflared-config.yml.new <<'EOF'
  - hostname: saskia-rms.paragu-ai.com
    service: http://localhost:8000
EOF

# Or, if you want a separate tunnel config for cleaner isolation,
# create /opt/data/cloudflared-saskia.yml and run as a second process.
```

**For now, the simplest is:** edit the existing config to add the new hostname → reload cloudflared (`cloudflared tunnel run <config>`).

**Acceptance:** `curl https://saskia-rms.paragu-ai.com/` returns... something (will be 502 Bad Gateway until Render is up in Step 5; that's expected).

---

## Step 4 — Generate FERNET_KEY + SESSION_SECRET (1 min)

```bash
# FERNET_KEY — used to encrypt R2 backups. Generate once, store in BWS, never lose.
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Save the output to BWS as SASKIA_R2_FERNET_KEY (Pattern 5)

# SESSION_SECRET — signs session cookies. Generate via Render (it has a "generateValue" option),
# or paste your own (e.g., `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`).
```

**Acceptance:** `SASKIA_R2_FERNET_KEY` in BWS; `SESSION_SECRET` will be set by Render (Step 5).

---

## Step 5 — Render deploy (10 min)

**Action in browser:** https://dashboard.render.com → New → **Blueprint**.

| Field | Value |
|---|---|
| Connect a repository | `Ai-Whisperers/saskia-app` |
| Branch | `main` |
| Blueprint name | `saskia-rms` |

Render auto-detects `render.yaml` and proposes the `saskia-rms` web service.

**Click "Apply".** Render starts provisioning. While it builds (5-10 min), **add the env vars** below.

**Environment Variables** (Environment tab → Add Environment Variable):

| Key | Value | Sync |
|---|---|---|
| `DATABASE_URL` | `<paste from SASKIA_NEON_DATABASE_URL>` | false (paste once) |
| `SUPABASE_URL` | `<paste from SASKIA_SUPABASE_URL>` | false |
| `SUPABASE_ANON_KEY` | `<paste from SASKIA_SUPABASE_ANON_KEY>` | false |
| `SUPABASE_SERVICE_ROLE_KEY` | `<paste from SASKIA_SUPABASE_SERVICE_ROLE_KEY>` | false |
| `SESSION_SECRET` | (use Render's "Generate" button) | generateValue |
| `HTTPS_ONLY` | `true` | value |
| `BIND_HOST` | `0.0.0.0` | value |
| `PORT` | `8000` | value |
| `PYTHONUNBUFFERED` | `1` | value |
| `AIW_SASKIA_LOG_DIR` | `/tmp/saskia-logs` | value |
| `R2_BUCKET` | `saskia-rms-backups` | value |
| `R2_ENDPOINT` | `<paste from existing R2 endpoint>` | false |
| `R2_ACCESS_KEY` | `<paste from existing R2 access key>` | false |
| `R2_SECRET_KEY` | `<paste from existing R2 secret>` | false |
| `R2_ENCRYPTION_KEY_PATH` | `/tmp/saskia-logs/fernet.key` | value |
| `SENTRY_DSN` | (skip — add later if you want Sentry) | false |
| `AIW_SASKIA_FERNET_KEY` | `<paste from SASKIA_R2_FERNET_KEY>` | false |

**Click "Save Changes"** → Render triggers a new deploy.

**Acceptance:** Render dashboard shows service as **Live** (green). The deploy takes ~5 min.

---

## Step 6 — Schema migration + first smoke test (~15 min)

**Wait for Render deploy to go green** (Live status). Then:

```bash
# From Ivan's box (where this runbook is being executed):
# Set DATABASE_URL to the Neon connection string (load from BWS via Pattern 5)
eval "$(python3 - <<'PYEOF'
import sys, uuid
sys.path.insert(0, '/opt/data/.venv/lib/python3.11/site-packages')
from bitwarden_sdk import BitwardenClient, ClientSettings, DeviceType
t = open('/opt/data/.hermes/inbox/bws-token.secret').read().strip()
c = BitwardenClient(ClientSettings(
    api_url='https://api.bitwarden.com',
    identity_url='https://identity.bitwarden.com',
    user_agent='saskia-deploy/2',
    device_type=DeviceType.SERVER,
))
c.auth().login_access_token(t, None)
val = c.secrets().get(uuid.UUID('<paste SASKIA_NEON_DATABASE_URL BWS UUID here>')).to_dict()['data']['value']
print(f"export DATABASE_URL='{val}'")
PYEOF
)"

# Apply the schema (creates all 8 tables + initial app_meta row)
cd /opt/data/profiles/ivan/scratch/saskia-build-full/saskia-app
uv run python -c "from app.rms.db_dialect import make_engine, get_metadata; e=make_engine(); get_metadata().create_all(e); print('schema applied')"

# Expected output: "schema applied"
```

**Smoke test the live URL:**

```bash
# Health check (no auth needed)
curl -s -o /dev/null -w "%{http_code}\n" https://saskia-rms.paragu-ai.com/healthz
# Expected: 200

# Login page (no auth needed)
curl -s -o /dev/null -w "%{http_code}\n" https://saskia-rms.paragu-ai.com/login
# Expected: 200

# Protected route (should 303 redirect to /login without cookie)
curl -s -o /dev/null -w "%{http_code}\n" https://saskia-rms.paragu-ai.com/inventario
# Expected: 303
```

**Browser smoke test:**

1. Open `https://saskia-rms.paragu-ai.com` in a browser
2. Verify the login page appears (Spanish, with username/password fields)
3. Log in with `saskia@paragu-ai.com` + the password from BWS (`SASKIA_USER_PASSWORD`)
4. Verify dashboard renders (will be empty since no data yet — that's fine)

**Acceptance:** Login works, dashboard renders, no 500 errors in Render logs.

---

## Step 7 — UptimeRobot monitor (2 min)

**Action in browser:** https://uptimerobot.com → Add New Monitor:

| Field | Value |
|---|---|
| Monitor Type | HTTP(s) |
| Friendly Name | `saskia-rms-hosted` |
| URL | `https://saskia-rms.paragu-ai.com/healthz` |
| Monitoring Interval | 5 minutes (mitigates Render free tier spin-down) |
| Alert Contacts | Ivan's email (add later if you want SMS/WhatsApp alerts) |

**Acceptance:** Monitor shows as "Up" within 5 min.

---

## Step 8 — Send Saskia the WhatsApp messages (5 min)

From `docs/operations/2026-09-02-saskia-agent-messages.md`:

1. Send **Message 1** (initial setup) using the Evolution API script in that doc. URL is `https://saskia-rms.paragu-ai.com`. Username is `saskia@paragu-ai.com`. Password is the one from BWS.

2. Wait for her "I logged in" reply (~minutes to hours).

3. Send **Message 2** (first-login walkthrough).

4. Wait 24h. Send **Message 3** (daily use).

5. Wait 7d. Send **Message 4** (week-1 check-in) — this is the start of Round 1 review.

**Acceptance:** Saskia has logged in and registered ≥1 product + ≥1 sale.

---

## What the agent (me) is doing in parallel

While you execute these steps, I'll:

1. ✅ Push the patched `installer/run.bat` to the repo (this turn)
2. ✅ Update `installer/README.md` to point hosted first (this turn)
3. ⏳ Stage the schema migration script with the right DATABASE_URL detection (in queue)
4. ⏳ Stage the R2 backup integration tests for hosted (in queue)
5. ⏳ Stage Round 1 review template + check-in scripts (in queue)

I won't start the Postgres/Render-side work until you paste me the DATABASE_URL + Supabase keys (Pattern 5). Once you have them, you can paste them via the helper script — I can run that script with the values loaded from your local paste.

---

## When you hit a wall

If any step returns unexpected output, **STOP and paste the error here.** Do not skip steps or guess. Each step's expected output is listed; if yours differs, that's a signal something upstream went wrong.

The 3 most likely failure modes:

1. **Neon connection refused from Ivan's box** → check if Neon's IP allowlist needs to be disabled (free tier is open by default)
2. **Supabase "Invalid API key"** → you pasted the wrong key (anon vs service_role)
3. **Render deploy fails with "no such file or directory"** → the Dockerfile COPY path changed; check Render build logs

---

*Generated 2026-09-02. Companion to docs/operations/2026-09-02-saskia-team-tasks.md. Operator time: ~50 min. Agent time: ~30 min (after operator provides creds).*