# 2026-09-08 Render env-var catalog

Last verified via Render API on 2026-09-08 (BWS-fetched auth).
Total env vars on Render: **22**.

This document is the source of truth for what each var does. Update
it whenever you change Render env vars.

## Categories

### A. Set directly by Render (not in BWS)

These are values the operator added via Render dashboard or API:

| Var | Current value (length+sha only) | Purpose |
|---|---|---|
| `BIND_HOST` | `0.0.0.0` | Render uses this; we don't override |
| `PORT` | `8000` | uvicorn bind port |
| `PYTHONUNBUFFERED` | `1` | Disable stdout buffering for log streaming |
| `DATABASE_URL` | `postgresql://n...` | Neon pooled connection, 67 chars |
| `SESSION_SECRET` | (in Render, not BWS) | Cookie HMAC; lost on env-var edit, must be set in Render UI |
| `FERNET_KEY` | `687d...` (43 chars) | Backup encryption |
| `AIW_RMS_LOG_DIR` | `/tmp/sazon-logs` | loguru output path |

### B. From BWS, set via Render API

| Var | Source BWS key | Current sha | Purpose |
|---|---|---|---|
| `AIW_RMS_RUN_MIGRATIONS` | n/a (env-only) | `1` | Auto-migrate on startup |
| `AIW_RMS_FORCE_SECURE_COOKIES` | n/a (env-only) | `1` | CSRF Secure flag (HTTPS only) |
| `AIW_SASKIA_LOG_FORMAT` | n/a (env-only) | `prod` | "prod" → JSON logs; "dev" → human |
| `SUPABASE_URL` | SUPABASE_URL | `b9508847` | Saskia's project: `rywzheykhdnaklmmsqey` |
| `SUPABASE_ANON_KEY` | SUPABASE_ANON_KEY | `12302f88` | Client-side anon JWT |
| `SUPABASE_PUBLISHABLE_KEY` | SUPABASE_PUBLISHABLE_KEY | `32f6ba59` | New-style anon public (publishable_key=) |
| `SUPABASE_SECRET_KEY` | SUPABASE_SECRET_KEY | `ca879f13` | Service-role key (sb_secret_...) |
| `SUPABASE_SERVICE_ROLE_KEY` | SUPABASE_SERVICE_ROLE_KEY | `84364324` | Old-style service-role JWT |
| `SUPABASE_JWKS_URL` | SUPABASE_JWKS_URL | `fd22ad7b` | JWT-key endpoint for Supabase |
| `NEXT_PUBLIC_SUPABASE_URL` | NEXT_PUBLIC_SUPABASE_URL | `b9508847` | Same as SUPABASE_URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | NEXT_PUBLIC_SUPABASE_ANON_KEY | `12302f88` | Same as SUPABASE_ANON_KEY |
| `CF_R2_ACCESS_KEY_ID` | CF_R2_ACCESS_KEY_ID | (32-char hex) | R2 backup credential |
| `CF_R2_SECRET_ACCESS_KEY` | CF_R2_SECRET_ACCESS_KEY | (43-char hex) | R2 backup credential |
| `CF_TUNNEL_TOKEN` | CF_TUNNEL_TOKEN | (eyJ-prefix JWT) | Cloudflare tunnel auth |
| `CF_TUNNEL_NAME` | CF_TUNNEL_NAME | `hermes-vps` | Tunnel name |
| `R2_BUCKET` | R2_BUCKET | `sazon-rms-backups` | R2 target bucket |
| `R2_ENDPOINT` | R2_ENDPOINT | `https://9eb1...` | R2 S3 endpoint URL |
| `SASKIA_ADMIN_PASSWORD` | SASKIA_ADMIN_PASSWORD | (13 chars) | bcrypt hash for admin login |

## How to update Render env vars

Manual UI update:
1. Render dashboard → sazon-rms → Environment → Add/Edit
2. After save, Render auto-redeploys. Verify with
   `curl /healthz/deps` (returns 200 with env fingerprint).

Programmatic update via API (preferred for BWS-managed vars):
1. Fetch the API key from BWS:
   ```
   python scripts/_bws_fetch.py --key RENDER_API_KEY
   ```
2. PUT to `https://api.render.com/v1/services/srv-.../env-vars/<VAR>`:
   ```
   PUT /v1/services/srv-dac8g2u7bikc73f3psf0/env-vars/<VAR>
   Content-Type: application/json
   {"value": "..."}
   Authorization: Bearer <KEY>
   ```
3. Render auto-redeploys.

## How to detect a stale var

```bash
# Compare Render env (machine-readable sha + length) vs BWS:
curl -sH "X-Healthz-Source: operator" \
     https://sazon-rms.paragu-ai.com/healthz/deps | python3 -m json.tool
```

Compare the lengths/sha prefixes with BWS-fetched values. Drift
= someone updated one and forgot the other.

## Common operations

### Add a new env var from BWS

```bash
# 1. Confirm new value in BWS (operator-side)
# 2. Push to Render via script:
python scripts/set_render_env.py --var NEW_VAR --value NEW_VALUE
# 3. Add to this catalog doc.
```

### Rotate a secret (e.g. Supabase key)

```bash
# 1. Generate new value in BWS
# 2. Push new value to Render (one var at a time)
# 3. Live site picks up next deploy (auto-redeploy)
# 4. Verify /healthz/deps shows new sha prefix
# 5. Update this doc
```
