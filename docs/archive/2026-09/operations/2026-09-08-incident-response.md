# Sazón — Operator incident response playbook

When the user reports "site broken", follow this sequence.

## 1. Quick check (30 seconds)

```bash
# All four health endpoints:
curl -i https://sazon-rms.paragu-ai.com/healthz        # 200 or 503 warming_up
curl -i https://sazon-rms.paragu-ai.com/healthz/db     # 200 = DB OK
curl -i https://sazon-rms.paragu-ai.com/healthz/schema # 200 in_sync, OR 500 drift
curl -i https://sazon-rms.paragu-ai.com/healthz/errors  # 200 with http_500_count
```

Expected responses:
- `/healthz`: 200 (or 503 if mid-deploy — wait 60s and retry)
- `/healthz/db`: 200 with `"dialect":"postgresql"`
- `/healthz/schema`: 200 with `drift=0`, OR 500 with `drift>0` and a `hint` field
- `/healthz/errors`: 200 with `http_500_count.last_1h`, `last_24h`

## 2. Diagnose by symptom

| Symptom | Likely cause | Fix |
|---|---|---|
| `/healthz` 503 longer than 60s | Render free-tier sleep timeout | Trigger manual deploy via API: `python scripts/_trigger_deploy.py` |
| `/healthz/db` 503 | Neon paused (idle >5min) | First query after resume = ~5-20s; wait + retry |
| `/healthz/schema` drift > 0 | Migrations didn't run | Redeploy (init_db now auto-runs) |
| `/healthz/errors` last_1h > 0 | Server bug | Click `/auditoria?action_filter=http.500` |
| `/dashboard` 500 with "column X does not exist" | Migration drift — see above |
| `login` 401 after correct password | Supabase session expired | Clear cookies + re-login; check SUPABASE_* env vars |
| All routes return 502/504 | Render free-tier cold start in progress | Wait 60s; UptimeRobot (id `803916096`) pings every 5min to mitigate |

## 3. Things to check

- **BWS-cached env vars match Render:** Run `scripts/check_render_env.py`
  to confirm lengths + sha prefixes are aligned.
- **Latest deployed commit matches:** `git log -1 --oneline` should match
  Render's "Latest deploy" commit. Render dashboard → sazon-rms → Deploys.
- **UptimeRobot monitor active:** UptimeRobot dashboard →
  weissvanderpol.ivan@gmail.com → Monitors → confirm `sazon-rms /healthz` is up.
- **Audit log row count trending:** `python scripts/audit_prune.py --dry-run` shows how big.
- **Recent errors:** `curl /auditoria?action_filter=http.500&limit=20`.
- **DB size:** `SELECT pg_size_pretty(pg_database_size('neondb'));` via psql or psycopg.

## 4. Recovery actions

### 4a. Schema drift (most common)

```bash
# Option A — push empty commit to trigger re-deploy with auto-migrations:
git commit --allow-empty -m "chore: trigger redeploy for migration"
git push origin main  # via BWS-backed token

# Option B — manually apply migration to live DB:
psql $DATABASE_URL < docs/operations/manual_migrations/012_<name>.sql

# Option C — operator-side SQL script:
python scripts/apply_migration_NNN.py
```

After fix: `/healthz/schema` returns `drift=0` and dashboard loads.

### 4b. Container stuck (cold-start not recovering)

```bash
# Force a fresh build (re-uses same commit):
git commit --allow-empty -m "chore: trigger redeploy for cold-start recovery"
git push origin main
```

Wait 60-90s for `Latest Deploy` status to flip from "in_progress" to "live", then test.

### 4c. Multiple recent http.500s in audit log

```bash
# Get details on the recent errors:
curl "https://sazon-rms.paragu-ai.com/auditoria?action_filter=http.500&start_date=2026-09-08&limit=20"

# Each row has request_id + path + type. Use that request_id to grep Render logs:
# (Render dashboard → Logs, search for the request_id)
```

Then diagnose by `type`:
- `RuntimeError`: code-level bug in route handler, find + fix.
- `IntegrityError`: DB-level conflict (duplicate insert, FK violation).
- `psycopg.OperationalError`: DB unreachable. /healthz/db will also fail.

### 4d. Render plan upgrade (if user can pay $7/mo)

1. Render dashboard → sazon-rms → Settings → Plan
2. Change plan to "Standard"
3. Web service stops cold-starting at 5min idle

Worth it: one operator's monthly cost eliminates the entire "cold
start" failure mode.

## 5. How to escalate

If none of the above works:

1. Re-read `docs/operations/2026-09-08-reliability-review.md` —
   lists known failure modes.
2. Re-read `docs/operations/2026-09-08-live-site-issues-fixes.md` —
   past outage details.
3. Issue: `https://github.com/Ai-Whisperers/saskia/issues/new` —
   describe exact symptom + URL of broken page.
4. Slack: operator + Kiki (developer).

**Don't:** open a new issue every time. Aggregate per-week.
