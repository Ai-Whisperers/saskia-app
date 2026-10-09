# app/ — Sazón Fase 1-3 Core

> **Restaurant management app core** for the operator · Built per `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`  
> **Local**: `127.0.0.1:8765` · **Hosted**: `https://sazon-vps.paragu-ai.com`  
> **Scope**: 287 routes, 99 templates, 90 RMS modules, 102 migrations, 475 tests

## What this is

The production-ready code for the operator's bakery management system. This is **not** a skeleton—it's a complete system with:

- POS (Ventas) with void, refunds, sharing
- Order management (Pedidos) with fulfillment tracking
- Production planning and execution
- Inventory management with variants and packaging
- Recipe system with cost calculation
- Customer CRM and subscriptions
- Financial reports and analytics
- Supplier management with price tracking
- Waste logging (Merma)
- Audit logging and compliance features

## Architecture

```
app/
├── rms/                    # Domain logic (no HTTP, no templates)
│   ├── main.py            # FastAPI entry point
│   ├── config.py          # constants, ASUNCION_TZ, schema version
│   ├── db.py              # engine, migrations, session factory
│   ├── models/            # SQLAlchemy 2.x models (15 files)
│   ├── money.py           # Decimal helpers, Gs. formatting
│   ├── units.py           # Unit enum with coerce()
│   ├── services/          # cross-cutting services
│   └── ... (~90 modules)
├── routers/               # FastAPI routers (36 files, 287 routes)
├── templates/            # Jinja2 templates (99 HTML + 11 components)
├── static/               # CSS, JS, images, SVG assets
├── auth.py               # Authentication layers
└── integrations/         # External integrations
```

### Tech stack

| Layer | Package | Purpose |
|-------|---------|---------|
| **Web framework** | FastAPI 0.115 | REST API, form handling, Jinja templating |
| **ORM** | SQLAlchemy 2.x | Postgres/SQLite with Mapped[...] syntax |
| **Templates** | Jinja2 | Server-rendered HTML with Paraguayan Spanish |
| **CSS** | Custom | Design system, no framework dependencies |
| **Auth** | itsdangerous | Session cookies; Supabase integration |
| **Migrations** | Hand-rolled | Versioned migration functions in `db.py` |
| **Tests** | pytest + hypothesis | 80% coverage gate, property-based |
| **Lint** | ruff | Code quality, CI gate |

## Development

### Quick start

```bash
git clone https://github.com/Ai-Whisperers/sazon-app.git
cd sazon-app
make install               # uv sync --all-extras
make migrate               # apply schema migrations (v102)
make seed                  # populate demo data
make serve                 # run on http://127.0.0.1:8765
```

### Build and run

```bash
# Local development
uv sync --dev                # install deps
make migrate                 # apply schema migrations
make seed                    # populate demo data
make serve                   # run on http://127.0.0.1:8765

# Tests
make test                    # full suite, ~70s
make check                   # ruff + tests (CI gate)
make test-coverage           # HTML coverage report

# Targeted
uv run pytest tests/test_X.py -v
uv run ruff check path/to/file.py
```

### Database

- Schema is hand-rolled; **do not use Alembic**. Migrations in `app/rms/db.py` as `_migration_NNN_*` functions
- Bump `CURRENT_SCHEMA_VERSION` after adding a migration
- Run `make migrate` after pulling to apply pending migrations

### Key rules

- **Money**: All calculations use `Decimal`, never `float`. Persistence through `app/rms/money.py:to_int_gs()`
- **Time**: All datetime math uses `ASUNCION_TZ`. DB stores naive UTC
- **Stock**: Moves are atomic with sale creation. Negative stock allowed
- **Nav**: Never hardcode in templates—use `NAV_GROUPS` in `app/rms/nav.py`
- **No async**: Sync handlers only (DB session lifecycle easier)

## Testing

- 475 tests across all modules
- 80% coverage gate (CI fails below)
- Property-based tests for money/units via hypothesis
- Test conventions: `tests/test_<module>.py`

## Deployment

### Local
```bash
make serve      # http://127.0.0.1:8765
```

### Hosted
```bash
make deploy     # push + deploy to VPS
```

See `docs/operations/2026-09-24-deployment.md` for full topology.

## What users can do

### Core operations
- **Ventas**: POS with void, refunds, receipt sharing
- **Pedidos**: Take customer orders, track fulfillment
- **Producción**: Plan and execute daily production
- **Inventario**: Track stock, variants, packaging
- **Merma**: Log waste by ingredient or recipe

### Catalog management
- **Productos**: CRUD with categories, tags, pricing
- **Recetas**: Create recipes with costing, photos
- **Ingredientes**: Stock tracking, alerts, variants

### Sales & customers
- **Clientes**: CRM with duplicate detection, points
- **Suscripciones**: Subscriptions with invoicing

### Purchasing
- **Reponer**: Reorder management with supplier lock/unlock
- **Proveedores**: Supplier CRUD, price volatility
- **Shopping lists**: Auto-generate from production plans

### Reports & analytics
- **Reportes**: Sales, inventory, financial PDFs
- **Análisis**: Insights, food cost, demand forecasting
- **Dashboard**: KPIs, monthly metrics
- **Auditoría**: Audit log, compliance

## Recent updates (2026-09-10 - 2026-10-05)

- **Phase 3 CI cleanup**: Ruff from 1910→0 errors, currency drift elimination, bug fixes
- **Production v2**: Demand forecasting, production planning, audit log enhancements
- **Static content audit**: 24 PNG screenshots, user guide completion
- **Redesign hardening**: Visual polish, new components, accessibility improvements

## Cross-references

- **Main README**: Project overview, architecture, deployment
- **[app/rms/AGENTS.md](rms/AGENTS.md)** — Engineering hard rules and patterns
- **[CHANGELOG.md](../CHANGELOG.md)** — App-level changelog (separate from repo)
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** — Development workflow and conventions
- **[docs/operations/](../docs/operations/)** — Architecture, deployment, operations docs
- **[docs/user-guide/](../docs/user-guide/)** — User manual with screenshots

---

**Status**: Fase 1-3 complete · Fase 4 planning  
**Visibility**: PUBLIC (no PII; build-only)  
**Last update**: 2026-10-05 (CI cleanup, production v2)