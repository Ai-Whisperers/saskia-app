# Sazón — Auth Status on VPS

## Current state (parallel run, 2026-09-23)
- VPS: https://sazon-vps.paragu-ai.com — RUNNING with **SASKIA_TEST_AUTH_DISABLED=1**
  - All routes work without login
  - Used for parallel-run validation against Render
- Render: https://sazon-rms.paragu-ai.com — RUNNING with normal Supabase auth

## Security alert 🚨
Ivan shared the Supabase user password (`HzvIsJkm7HDLGYRBQk30`) in chat on
2026-09-23. This password should be considered **compromised**:
1. Change it in Supabase dashboard immediately
2. Rotate the SUPABASE_SERVICE_KEY and SUPABASE_ANON_KEY (they may be
   in the same Supabase project)
3. Check Supabase auth logs for suspicious logins since 2026-09-22 16:01 UTC

## To restore real Supabase auth on VPS
1. Read SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY from Render env vars
2. Update /opt/build-apps/sazon-rms/docker-stack.yml on VPS:
   - Remove the `SASKIA_TEST_AUTH_DISABLED=1` line
   - Replace the placeholder values in SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY
3. Redeploy:
   ```
   ssh paragu-ai
   cd /opt/build-apps/sazon-rms
   docker stack deploy -c docker-stack.yml sazon-vps --resolve-image=never
   docker service update --force sazon-vps_web
   ```

## To switch DNS to VPS (when ready)
1. In Cloudflare dashboard, change sazon-rms.paragu-ai.com:
   - From: 216.24.57.18 (Render)
   - To:   38.9.96.179 (VPS)
2. Wait for DNS propagation (~5 min)
3. Verify in browser: https://sazon-rms.paragu-ai.com
4. Delete Render service in Render dashboard

## What needs real auth to test
- Login/logout flow
- Audit log entries (record_audit uses user_id)
- Multi-user permission checks (we're single-user for now)
