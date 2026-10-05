# Sessions reviewed + Servarica state — 2026-09-29

## What was checked
Searched past sessions for servarica/saskia/deploy work. Found these as relevant:

- @session:ivan/20260921_183115_cf38cb — "Run sazon-backup-pull cron job".
  This was the only prior session that drove a real Servarica VPS deploy for
  sazon-rms. Confirmed: deploy path is `docker stack deploy -c docker-stack.yml
  sazon-vps --resolve-image=never` on the host at 216.150.1.1.

- @session:ivan/20260921_182959_d642e9 — "Process Ivan profile attachments".
  Multi-model architecture design doc, includes sazon-rms as test client.

- @session:ivan/20260927_185825_689522 — "Analyze hermes sessions for failures".
  Confirmed VM pull time fix (07:27 was 03:47, fixed 2026-09-27 — VPS writes
  06:17Z, host was 2h30m early).

- @session:ivan/20260923_164224_5563cb — "do ypou have acces to bitwarden?".
  Has the canonical BWS access recipe. Used today.

- @session:ivan/20260909_152436_a01c64 — Servarica connection data dump.
  VPS_HOST 92a87424 (hermes.paragu-ai.com legacy — corrupt SSH key, 401).

## Servarica state — as of 2026-09-29
- Portal login at clients.servarica.com now requires reCAPTCHA v2 (added
  silently — the `Login (curl)` recipe in the skill no longer works unattended).
- WHMCS API at /opt/data/work/scripts/.whmcs_token is IP-restricted to
  38.9.96.180 (Host B); calls from other IPs return 403 Invalid IP.
- VPS at 216.150.1.1: SSH port 22 times out from this VM; HTTP 80/443 open.
- Live state: Docker Swarm stack `sazon-vps` running the app at
  sazon-vps.paragu-ai.com. Currently showing OLD code (broken receta_detalle,
  500 on /productos, 0/30 ingredients, 0 products, 0 sales — the default
  seed only).

## Deploy path — what works
1. From the Servarica console (clients.servarica.com → Service 87065 →
   noVNC console at console.servarica.net:8443) — paste the `set -e` block
   from deliverables/DEPLOY-ONE-SHOT.md. It does git pull + docker build +
   stack deploy + migration + seed + verification curls in one paste.
2. After deploy, upload the xlsx from your laptop via /excel/importar to
   populate 78 ingredientes + 30 productos + 9 clientes + 2081 ventas.

## Deploy path — what does NOT work
- `python3 /opt/data/work/scripts/servarica_power.py status` — needs a
  pre-existing cookie in /tmp/srv-cookies.txt. The cookie expires after a
  few hours AND new reCAPTCHA blocks automated refresh.
- `git push` + Render auto-deploy — Render's free tier rebuilds take 8-15 min;
  this is the second-best fallback.
- SSH from this VM — TCP/22 to 216.150.1.1 is filtered.

## What was fixed this session (already pushed)
- 12 commits on origin/main since the last live VPS deploy:
  752df7fe, d8206f4, 20637bc, 304b19c, 019d7ea, 868aaa5, 45f17bd, 167bdb8,
  b73bc51, d398394, fc0e2b4, 0284066, 6e58584, e05c2dc, 4e650d1
- Migration chain 056/057/058/059 (bank_reconciliation, recipe.instructions,
  ingredient.expiry_date, product.mayorista_price_gs)
- seed_full_recipe_data.py populated all 20 recipes with instructions,
  metadata, allergens, tag_links
- /productos + /recetas 500 fix (replaced {% do %} with {% set _ = ... %})
- xlsx export (sazon-rms-starter-2026-09-29.xlsx) for offline data population
- Error 500→4xx.html wired, no Python repr leaks to users
- 100/100 tests pass: receta_detalle regression + P04 combo + recipe_intel
  + tag_algebra + no_silent_excepts

## Blockers remaining
1. **Ivan must paste the deploy block in Servarica console** — no way to
   automate this from this VM (reCAPTCHA blocks).
2. **Ivan must upload the xlsx** — one curl from his laptop.
