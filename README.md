# Sazón — Bakery Management System

> **the operator** · Restaurant Management System · Fase 1-3 Complete  
> **Local-first** (runs on laptop) + **Hosted** (VPS via Docker Swarm)  
> **Branch**: `chore/root-cleanup-2026-10-09` · **Schema**: v117 · **Routes**: 341 · **Tests**: 7,961

## What this is

Sazón is a full-featured restaurant management system built for **one bakery** (the operator, Asunción, Paraguay). It's not a generic SaaS—every module and design choice addresses a specific real-world need.

### Deployment modes

- **Local**: Runs on the operator's laptop at `127.0.0.1:8765`, SQLite database, no hosting fees
- **Hosted**: Production at `https://sazon-vps.paragu-ai.com` (Docker Swarm + Cloudflare Tunnel)

Both use the same codebase. Local is where you test "fresh DB" scenarios; hosted is where "it's running today."

## Stats & scope (as of 2026-10-05)

| Area | Count | Scale |
|------|-------|-------|
| **Routes** | 341 | Across 51 resource routers |
| **Tests** | 7,961 | 80% coverage gate; refactor wave landed |
| **Templates** | 99 + 11 components | Server-rendered Jinja2 |
| **Models** | 12 | SQLAlchemy 2.x with hand-rolled migrations |
| **RMS modules** | 90 | Domain logic only (no HTTP, no templates) |
| **Migrations** | 117 (36 files) | Hand-rolled, no Alembic |

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│ Local Dev       │    │ Hosted Production│
│ uvicorn         │    │ Docker Swarm     │
│ SQLite          │    │ PostgreSQL       │
│ 127.0.0.1:8765  │    │ Cloudflare Tunnel│
└─────────────────┘    └─────────────────┘
           │                    │
           ▼                    ▼
┌──────────────────────────────────────────────┐
│                 FastAPI 0.115                 │
│            sync handlers, Jinja2              │
│             SQLAlchemy 2.x sync               │
└──────────────────────────────────────────────┘
```

### Tech stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Web** | FastAPI | Form handling + Jinja templates; async adds no win |
| **ORM** | SQLAlchemy 2.x | `Mapped[...]` syntax, post-1.4 style |
| **DB** | SQLite/Postgres | Same schema, both supported |
| **Auth** | Session cookies + Supabase | Local + hosted auth patterns |
| **Migrations** | Hand-rolled in `app/rms/db.py` | Not Alembic (versioned migration functions) |
| **Tests** | pytest + hypothesis | 80% coverage, property-based for money/units |
| **Lint** | ruff | CI gate; strict standards |

### Where to add X

| You want to | Put it in |
|-------------|-----------|
| New page | `app/routers/<thing>.py` + `app/templates/<thing>.html` |
| New SQL model | `app/rms/models/<group>.py` + migration in `app/rms/db.py` |
| Business rule | `app/rms/<module>.py` (if no DB) or `session: Session` function |
| External integration | `app/integrations/<vendor>.py` (scrapers, barcode, printer) |
| Nav entry | `NAV_GROUPS` in `app/rms/nav.py` (never hardcode in templates) |
| Operator setting | `SETTINGS` list in `app/rms/settings.py` |

## Navigation groups

The app is organized into 6 functional groups:

### Operación (Daily operations)
- **/** Inicio (Dashboard with today/week/month sales, alerts)
- **/ventas** Ventas (POS sales + void)
- **/pedidos** Pedidos (customer orders + fulfillment)
- **/produccion** Production planning + execution
- **/eod** Cierre del día (end-of-day closing)

### Catálogo (Inventory & products)
- **/productos** Productos (CRUD + pricing)
- **/recetas** Recetas (recipe management + cost calculation)
- **/inventario** Inventario (stock tracking + variants)
- **/merma** Merma (waste tracking)

### Compras (Purchasing & suppliers)
- **/reorder** Reponer (reorder management + supplier lock/unlock)
- **/shopping-list** Lista de compras (shopping lists from production plans)
- **/suppliers** Proveedores (supplier CRUD + price volatility)
- **/wishlist** Equipamiento (equipment wish list)

### Ventas y clientes (Sales & customers)
- **/clientes** Clientes (CRM + duplicate detection)
- **/suscripciones** Suscripciones (subscriptions + invoicing)

### Finanzas (Financial reports)
- **/reportes** Reportes (sales, inventory, financial PDFs)
- **/analisis** Análisis (insights + data intelligence)
- **/dashboard** KPIs mensuales (financial dashboard)
- **/pricing** Precios por canal (channel pricing)
- **/vs-mercado** Precios vs mercado (competitive pricing)
- **/bank** Banco (bank reconciliation)
- **/riesgos** Riesgos (risk management)

### Sistema (System administration)
- **/settings** Configuración (business settings)
- **/users** Usuarios (user management)
- **/excel** Excel (import/export)
- **/auditoria** Auditoría (audit log + analytics)
- **/guia** Guía (help system)

## Development

### Quick start

```bash
git clone https://github.com/Ai-Whisperers/sazon-app.git
cd sazon-app
make install          # uv sync --all-extras
make migrate          # apply schema migrations
make seed             # populate demo data
make serve            # run on http://127.0.0.1:8765
```

`make help` shows all available shortcuts.

### Testing

```bash
make test              # full suite (~70s)
make test-coverage     # with HTML report
make check             # ruff + tests (CI gate)
```

Target: 80%+ coverage. New code must come with tests.

### Contribution workflow

1. Branch off `main`: `eng/E6-realistic-seed`, `fix/audit-log`, etc.
2. All changes to `app/`, `scripts/`, `tests/`, or `.github/` **must update `app/CHANGELOG.md`** (CI enforces this)
3. Run `make check` locally
4. Open PR to `main`

### Database

- Schema is hand-rolled; **do not use Alembic**. Migrations in `app/rms/db.py` as `_migration_NNN_*`
- Bump `CURRENT_SCHEMA_VERSION` in `app/rms/config.py` after migration
- Run `make migrate` after pulling to apply pending migrations

## Key engineering rules

### Money (never break these)
- **All money use `Decimal`, never `float`**
- All persistence through `app/rms/money.py:to_int_gs()`
- DB columns are INTEGER (no decimal currencies in Paraguay)

### Time
- All datetime math uses `ASUNCION_TZ` (UTC-4)
- DB stores naive UTC; display converts to Asunción local
- `datetime.now()` without timezone = bug

### Stock
- Stock moves are atomic with sale creation
- Negative stock allowed (UI shows red alert)
- Void reverses stock moves fully, including sub-recipes

### Authentication
Two modes, set by `AUTH_MODE`:
- **Local** (default): Signed cookie sessions; `demo`/`admin` passwords
- **Supabase** (prod): Delegates to Supabase Auth

### Middleware
- CSRF on all state-changing routes
- Security headers
- Request context logging
- Gzip compression

## Deployment

### Local
No deployment needed. Run `make serve`.

### Hosted
```bash
make deploy            # push + deploy to VPS
make ci-smoke          # quick health check
```

See `docs/operations/2026-09-24-deployment.md` for full topology.

## Companion resources

- **[app/rms/AGENTS.md](app/rms/AGENTS.md)** — Engineering hard rules and patterns
- **[CHANGELOG.md](CHANGELOG.md)** — App-level changelog (separate from repo)
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Development workflow and conventions
- **[docs/operations/](docs/operations/)** — Architecture, deployment, operations docs
- **[docs/user-guide/](docs/user-guide/)** — User-facing manual with screenshots
- **[docs/plans/](docs/plans/)** — Development plans and roadmap

## Recent updates (2026-09-10 - 2026-10-05)

- **Phase 3 CI cleanup**: Ruff from 1910→0 errors, currency drift elimination, bug fixes
- **Production v2**: Demand forecasting, production planning, audit log enhancements
- **Static content audit**: 24 PNG screenshots, user guide completion
- **Redesign hardening**: Visual polish, new components, accessibility improvements

---

**Status**: Active development (Fase 1-3 complete, Fase 4 planning)  
**Contact**: AI Whisperers · ivan@ai-whisperers.dev  
**License**: MIT · Visibility: PUBLIC (no PII; build-only)