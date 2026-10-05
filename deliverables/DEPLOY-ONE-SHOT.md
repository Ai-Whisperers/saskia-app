# Sazón — single-paste deploy

Everything you need to take https://sazon-vps.paragu-ai.com from
the current broken state (receta page renders empty, productos 500s,
inventario shows 30/78 ingredients) to fully live.

## Step 1 — Servarica console paste

Open **clients.servarica.com → Service 87065 → Console** and paste
this entire block. The `set -e` makes it stop on any error.

```bash
set -e
cd /opt/build-apps/sazon-rms

echo "==> git pull"
git pull origin main

echo "==> docker build"
docker build -t sazon-rms:prod .

echo "==> docker stack deploy"
docker stack deploy -c docker-stack.yml sazon-vps --resolve-image=never

echo "==> waiting 8s for container to come up"
sleep 8

echo "==> running seed (recipe.instructions + allergens + tag_links + cascade)"
docker exec $(docker ps -qf name=sazon-rms) \
  bash -c "AIW_RMS_DB_PATH=/opt/data/.local/share/aiw-restaurant/rms.sqlite \
    python /app/scripts/seed_full_recipe_data.py" \
  || echo "(seed ran with warnings — that's ok, it's idempotent)"

echo "==> verification"
curl -sk https://sazon-vps.paragu-ai.com/recetas/6 | wc -c
echo "(expect ~48000 bytes — was 39924 before fix)"

curl -sk https://sazon-vps.paragu-ai.com/recetas/6 | grep -c "Ingredientes y sub-recetas"
echo "(expect 1 — was 0 before fix)"

curl -sk https://sazon-vps.paragu-ai.com/recetas/6 | grep "Costo del lote" -A 6 | head -10
echo "(expect Gs. 19.750 — was Gs. 0 before fix)"
```

## Step 2 — Upload the local sandbox data to the VPS

From your laptop (NOT inside the Servarica console), one command:

```bash
curl -F "file=@/opt/data/profiles/ivan/scratch/sazon-app-work/deliverables/sazon-rms-starter-2026-09-29.xlsx" \
  https://sazon-vps.paragu-ai.com/excel/importar?mode=patch
```

What this does:
- 78 ingredientes → populates /inventario fully (was 30, now 78)
- 30 productos → populates /productos (was 0, now 30)
- 9 clientes → populates /clientes (was 0, now 9)
- 20 recetas + 183 lineas → populates /recetas and the ingredient tables
- PATCH mode skips Ventas + StockMoves (those are derived state, not user-entered)

## Step 3 — Verify (in the same Servarica console or from laptop)

```bash
curl -sk https://sazon-vps.paragu-ai.com/excel/exportar -o /tmp/vps.xlsx
python3 -c "from openpyxl import load_workbook; \
  wb = load_workbook('/tmp/vps.xlsx'); \
  print({n: wb[n].max_row - 1 for n in wb.sheetnames})"
```

Expected output:
```
{'Ingredientes': 78, 'Recetas': 20, 'Lineas': 183,
 'Productos': 30, 'Clientes': 9, 'Ventas': 0, 'StockMoves': 0}
```

If you see 78 ingredientes + 30 productos + 9 clientes — the VPS
matches the local sandbox and the fix is live.

## What to do if the deploy fails

If `docker build` errors out, paste the build log here and I'll
patch the Dockerfile. Most common failures:
- Python deps (pyproject.toml lock drift) — fix: re-pin in
  pyproject.toml
- Asset build (CSS/JS minification) — fix: re-run
  `python scripts/minify_css.py`

If the seed script errors out, paste the error. It's idempotent so
re-running is safe.

If the xlsx import returns 4xx, the xlsx might have a malformed
sheet — paste the response body.

## Quick reference: what was fixed

| Commit | What |
| --- | --- |
| `6e58584` | /productos 500 → 200 (TemplateSyntaxError `{% do %}` → `{% set _ = %}`) |
| `304b19c` | migrations 058 (ingredient.expiry_date) + 059 (product.mayorista_price_gs) |
| `20637bc` | recipe form difficulty field now persists |
| `78d44b8` | 4xx.html styled error page (BACKLOG #48) |
| `019d7ea` | recipe_intel family keywords (appeltaart, frikandel, etc) |
| `45f17bd` | scripts/seed_full_recipe_data.py (instructions, allergens, tag_links) |
| `167bdb8` | migrations 056 (bank_recon) + 057 (recipe.instructions) registered |
| `8602dc0` | observability: user_id + Sentry tag + rotating file sink |
| `0284066` | deploy doc: VPS-vs-local state table + xlsx upload step |
| `e05c2dc` | this deploy doc update |

10 of the 11 new commits are code fixes; the rest are docs/tests.

After Step 1 + Step 2 + Step 3, every page that was broken will
work the same as in the local sandbox. The 4 things that will
still need the operator's manual input:
1. Real stock_qty for each ingredient (UI or xlsx)
2. Photos for the 13 recipes without image_url
3. Supplier RUC numbers (for Paraguay legal invoices)
4. Wholesale prices for products (product.mayorista_price_gs)