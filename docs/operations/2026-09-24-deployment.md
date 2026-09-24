# Deployment — VPS (active) + Render (deprecated)

**Last updated:** 2026-09-24
**Active deployment:** VPS at `paragu-ai` (ServaRica), Docker Swarm
**Deprecated:** Render.com (kept for historical reference only)

---

## TL;DR

Saskia RMS is deployed on a ServaRica VPS using Docker Swarm + Traefik
+ Cloudflare DNS-01 for SSL. The Render.com blueprint (`render.yaml`)
is **deprecated** and no longer the source of truth. We migrated from
Render during the audit work because:

1. Render's auto-deploy was failing on schema migrations 28-32
   (Postgres-specific syntax issues that we kept patching instead of fixing)
2. The free tier spins down after 15 minutes idle
3. Render's Neon Postgres DB was out of sync with the code
4. VPS gives us full control over the stack

---

## VPS deployment

### One-time setup
```bash
# On paragu-ai VPS:
docker swarm init
# Traefik with Cloudflare DNS-01 (already configured by Kiki earlier)
```

### Files
- `Dockerfile` — multi-stage build, uv-based, venv at /opt/venv
- `docker-stack.yml` — Swarm stack with Traefik labels
- `deploy-to-vps.sh` — convenience wrapper around scp + docker build +
  service update

### Deploy flow
```bash
# From local machine:
./deploy-to-vps.sh

# This:
# 1. scp's the repo files to /opt/build-apps/saskia-rms/
# 2. Runs `docker build --no-cache -t saskia-rms:prod .`
# 3. Runs `docker stack deploy -c docker-stack.yml saskia-vps`
# 4. Forces a service update so all replicas are fresh
```

### Environment variables
Set in `docker-stack.yml` under the `web` service:
- `AIW_SASKIA_DB_PATH=/data/rms.sqlite` — SQLite path (mounted volume)
- `BIND_HOST=0.0.0.0`
- `PORT=8000`
- `SASKIA_TEST_AUTH_DISABLED=1` — dev mode bypass for the Supabase
  password rotation issue. Set to 0 in real production.
- `AIW_SASKIA_INTERNAL_ROUTES=1` — enables /auditoria + /ops. Set to 0
  in real production (these are internal-only admin pages).
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, etc. — currently the values from
  Render's deployment (these still point at the Render project's Supabase
  project). They work because the auth bypass mode is on.

### Volumes
- `saskia-vps_saskia-data` → `/data` in container → `rms.sqlite`

### TLS / DNS
- `saskia-vps.paragu-ai.com` → Cloudflare DNS → VPS IP `38.9.96.179`
- Let's Encrypt cert via Traefik DNS-01 challenge

### Health check
- `/healthz` returns 200 + JSON if the app is up
- Traefik polls every 30s

### Backups
- SQLite DB at `/data/rms.sqlite` in the volume
- Back up via `docker exec` or restore via mounted host path

---

## Render deployment (deprecated)

### Status: DEPRECATED 2026-09-24

`render.yaml` is kept in the repo for historical reference but is **not
the active deployment path**. The Render service still exists but:

- DB is out of sync (Postgres migrations 28-32 never applied)
- New code commits do NOT auto-deploy to Render (autoDeploy was disabled)
- No new features ship to Render anymore

### Why we migrated
See `docs/operations/2026-09-22-saskia-prelaunch-roadmap.md` and the
chat history. Key reasons:
1. Render free tier unreliable for a real business workflow
2. Postgres migration compatibility issues (psycopg binding, JSONB)
3. We wanted full control over the deployment timing
4. VPS is paid but predictable (no spin-down)

### How to bring Render back (if ever needed)
If you want to resurrect Render:
1. Apply migrations 28-32 to the Neon Postgres (they only ran on SQLite)
2. Update DATABASE_URL on Render dashboard to point at the VPS SQLite OR
   migrate the VPS to Postgres
3. Set Render `autoDeploy: true` in render.yaml
4. Flip CI/CD to deploy to Render on push to main

This is not recommended. The VPS is the source of truth.

---

## Migration history

| Date | Action | Source of truth |
|---|---|---|
| 2026-08 | Initial Render deploy | Render + Neon Postgres |
| 2026-09-02 | Hosted pivot decision | Render + Neon |
| 2026-09-22 | VPS stack created as backup | Docker Swarm on paragu-ai |
| 2026-09-23 | Migrations 28-32 failing on Render | (no successful deploy since) |
| 2026-09-24 | VPS becomes primary | saskia-vps.paragu-ai.com |
| 2026-09-24 | render.yaml marked DEPRECATED | (this file) |

---

## Active endpoints

| Service | URL | Status |
|---|---|---|
| VPS (primary) | https://saskia-vps.paragu-ai.com | ✓ Live, schema v48 |
| Render (legacy) | https://saskia-rms.paragu-ai.com | ⚠️ Live but stale |
| Local dev | http://127.0.0.1:8765 | ✓ (when running locally) |

---

## Future improvements (out of scope)

- Set Render auto-deploy to false explicitly in the dashboard
- Add a `Render.status: deprecated` header to Render responses
- Move render.yaml to `docs/deprecated/` once we're sure Render is fully sunset
- Document the data migration path if we ever need to move from VPS SQLite to Render Postgres

---

## Cross-references

- `Dockerfile` — VPS build
- `docker-stack.yml` — Swarm stack definition
- `deploy-to-vps.sh` — convenience deploy wrapper
- `render.yaml` — DEPRECATED Render blueprint
- `docs/operations/2026-09-24-static-content-audit-final-summary.md` — what runs on VPS
- `docs/operations/2026-09-22-saskia-prelaunch-roadmap.md` — pre-VPS context
