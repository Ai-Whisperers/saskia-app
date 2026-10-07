# Legacy Render.com Scripts (2026-10-07)

This directory contains the Render.com deployment configuration and scripts that are now deprecated.

## What was moved

- `render.yaml` - Render.com deployment configuration (deprecated 2026-09-24)
- Original scripts that were Render-specific and have been migrated or removed:
  - `diag_supabase_render.py` → replaced with `scripts/diag_supabase.py`
  - `set_render_env.py` → removed (Render-only, no remaining value)

## Why these were archived

Sazón is now deployed on the VPS (paragu-ai) using Docker Swarm instead of Render.com. The Render deployment is no longer the source of truth and has been deprecated due to:

1. Migration path incompatibility (Render used Neon Postgres, VPS uses SQLite)
2. Incomplete migrations on the Render deployment
3. Switch to VPS provides better performance and cost control

## Active deployment

- **Primary**: VPS at https://sazon-vps.paragu-ai.com
- **Config**: `deploy-to-vps.sh` + `docker-stack.yml`
- **Backup scripts**: `scripts/diag_supabase.py` (replaces the Render-specific version)

## Restore command

To restore these files from the archive:

```bash
git mv archive/legacy/2026-10-07-render-com-scripts/render.yaml .
```

## Bringing Render back (if needed)

If you need to restore the Render deployment, you'll need to:

1. Migrate the VPS SQLite database to Neon Postgres
2. Apply migrations 28-32 that were never applied to the Render deployment
3. Update the DATABASE_URL in the Render dashboard
4. Set all the required environment variables

Note: This is a complex process and not recommended for production use.