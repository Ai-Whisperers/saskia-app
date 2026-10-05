# Cloudflared + BWS tunnel inventory (audit 2026-09-02)

## Running cloudflared (single instance)
- PID: 2678232
- Started: 2026-08-20 (originally; running fine)
- Binary: /opt/data/bin/cloudflared (v2026.8.2, newer than 2026.1.2)
- Config: /opt/data/cloudflared-config.yml (3-line minimal config)
- Tunnel: 135a9be2-0dd1-494f-92d1-a86119cb6351 (`openclaw-tunnel`)
- Status: Healthy (6+ hours uptime as of 2026-09-02)
- Credentials file: NOT FOUND in any standard location
  - /etc/cloudflared/, /opt/data/.cloudflared/, /home/hermes/.cloudflared/,
    /opt/data/home/.cloudflared/ — all empty
  - The token was never persisted to this VM in a discoverable location
  - The process has the token cached in memory (cloudflared loads it on
    startup and holds it for the lifetime of the process)

## BWS tunnel inventory (Hermes project)
22 CF/tunnel/cloud entries; the tunnel-token+id pairs are:

| Key                  | Value (truncated)   | Notes                     |
|----------------------|---------------------|---------------------------|
| CF_TUNNEL_TOKEN      | e4d2a56c...         | Tunnel 1 token            |
| CF_TUNNEL_ID         | ???                 | Tunnel 1 ID (same value?) |
| CF_TUNNEL_TOKEN_2    | 255dcc30...         | Tunnel 2 token            |
| CF_TUNNEL_ID_2       | ???                 | Tunnel 2 ID                |
| CF_TUNNEL_NAME       | hermes-vps          | Display name              |
| CF_TUNNEL_TOKEN_3    | (not yet saved)     | Should be 135a9be2's token |
| CF_TUNNEL_ID_3       | (not yet saved)     | Should be 135a9be2        |
| CLOUDFLARE_ACCOUNT_ID| 9eb1832f...         | Account                   |
| CF_ACCOUNT_ID        | 9eb1832f...         | Same value (DUPLICATE)    |
| CLOUDFLARE_ZONE_ID   | ???                 | DNS zone                  |
| + 12 CF_R2_* entries | various             | R2 credentials (separate) |

## Actions taken 2026-09-02
- AUDITED BWS via scripts/bws_list_names.py — found 22 CF-related entries
- IDENTIFIED Task1's blocker: /etc/cloudflared/token.env does not exist;
  cloudflared's cred file is missing/not discoverable from this VM.
  Cannot safely save CF_TUNNEL_TOKEN_3 without first locating the token.
- IDENTIFIED Task2 is a no-op: /opt/data/bin/cloudflared is v2026.8.2 (newer
  than the 2026.1.2 threshold in the task). apt-get install cloudflared
  would replace the binary; restarting the service is a confirm-before
  guardrail in the task itself and is unnecessary.
- IDENTIFIED CF_ACCOUNT_ID + CLOUDFLARE_ACCOUNT_ID are duplicates (same value).
  Not deleting per "confirm before deleting any BWS entry" guardrail.

## Recommended next actions (operator decision needed)
1. To complete Task 1: locate the cloudflared credential file. Possible
   sources:
   - Search /opt/data/home and /opt/data for any .json/.pem file
     containing "AccountTag" or "TunnelSecret" (the JSON keys cloudflared uses)
   - Restart cloudflared with --token=<value> (requires operator to have
     the value from elsewhere; the value was not in this VM's standard
     locations when audited)
2. To clean up the duplicate: delete CF_ACCOUNT_ID (keep CLOUDFLARE_ACCOUNT_ID;
   the latter is the more current convention). Confirm before delete.
3. To upgrade cloudflared binary: not necessary; 2026.8.2 > 2026.1.2 already.

## Files
- This file: docs/operations/2026-09-02-cloudflared-audit.md
- Cloudflared config: /opt/data/cloudflared-config.yml
- Cloudflared log: /tmp/cloudflared.log
- BWS audit script: scripts/bws_list_names.py
