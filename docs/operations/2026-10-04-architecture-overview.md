# Architecture overview

> **For:** future maintainers, new devs, auditors. A 5-minute tour of
> the Saskia RMS codebase.
> **Date:** 2026-10-04

## What this app is

Saskia RMS is a single-tenant, local-first web app for one bakery
(Saskia, in Asunción, Paraguay). It runs:

- **Locally** on Ivan's laptop (`uv run uvicorn ... --port 8765`)
- **Hosted** on the AIW VPS via Docker Swarm + Cloudflare Tunnel
  (`https://saskia-vps.paragu-ai.com`)

The two deployments share the same code. The local deployment is the
source of truth for "what works on a fresh DB" — the hosted one is
the source of truth for "what's actually running today."

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Web framework | **FastAPI** (sync handlers) | Forms + Jinja templates; async gives no win and complicates DB session lifecycle |
| ORM | **SQLAlchemy 2.x** | We lean on `Mapped[...]` syntax; most code is post-1.4 style |
| Database | **Postgres** (hosted) / **SQLite** (local) | Same schema, both supported |
| Templates | **Jinja2** (server-rendered HTML) | No React/Vue — the user (Saskia) uses a slow phone in a bakery |
| CSS | **Hand-rolled, ~8 files** in `app/static/` | Design system in `app/static/app.css` + helpers |
| Auth | **SessionMiddleware** (signed cookies) + optional Supabase | See "Auth" below |
| Migrations | **Hand-rolled** in `app/rms/db.py` as `_migration_NNN_*` | We do **not** use Alembic |
| Tests | **pytest** + **hypothesis** (for money/units) | Coverage gate 80% |
| Lint | **ruff** | CI gate, see `pyproject.toml` |

## Module map

```
app/
├── rms/                  # domain logic (no HTTP, no templates)
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # constants, ASUNCION_TZ, schema version
│   ├── db.py            # engine, session factory, migrations
│   ├── models/          # SQLAlchemy 2.x models (one file per table group)
│   ├── services/        # cross-cutting services (e.g., template_render, backup)
│   ├── migrations/      # _NNN_*.py hand-rolled migration functions
│   ├── nav.py           # SSOT for nav, breadcrumbs, status pills
│   ├── money.py         # to_int_gs(), Decimal math
│   ├── units.py         # Unit enum + coerce()
│   ├── seed/            # seed data (qseed, fseed, full_demo_seed)
│   ├── integrations/    # R2 storage, etc.
│   └── ...              # ~60 domain modules (one per concern)
├── routers/              # FastAPI routers (one per resource)
├── templates/            # Jinja2 templates
│   ├── base.html        # layout, sidebar (uses NAV_GROUPS)
│   └── *.html           # one per page
├── static/               # CSS, JS, images
└── auth.py / auth_supabase.py
```

## Request lifecycle

```
HTTP request
   ↓
FastAPI middleware (gzip, session)
   ↓
@router.get("/ventas/nueva")  → app/routers/sales.py
   ↓
sale_handler(request, session)  → app/routers/sales.py
   ↓
business logic                 → app/rms/sales.py (or service)
   ↓
SQLAlchemy ORM                 → app/rms/models/sales.py
   ↓
Postgres / SQLite
   ↓
Template render                → app/services/template_render.py
   ↓
app/templates/ventas_nueva.html
   ↓
HTML response
```

The boundary is strict: **routers** call **rms modules** which return
data; **template_render** merges data + `NAV_GROUPS` (from `app/rms/nav.py`)
+ user/role from session; the template renders HTML. Routers never
build HTML strings directly.

## Where to add X

The "Module structure" section of `app/rms/AGENTS.md` is the answer for
most of these. Quick reference:

| You want to | Put it in |
|---|---|
| New page | `app/routers/<thing>.py` + `app/templates/<thing>.html` |
| New SQLAlchemy model | `app/rms/models/<group>.py` + new migration in `app/rms/db.py` |
| New business rule | `app/rms/<module>.py` (if no DB) or DB-touching function with `session: Session` arg |
| New external integration | `app/integrations/<vendor>.py` (e.g., `scrapers.py`, `barcode.py`, `printer.py`) |
| New nav entry | Add to `NAV_GROUPS` in `app/rms/nav.py` — never hardcode in a template |
| New operator setting | Add to `SETTINGS` list in `app/rms/settings.py` |
| New starter tag | Add to `STARTER_TAGS` in `app/rms/tags.py` |
| New endpoint URL | Use the existing `NAV_GROUPS` route, or add it there |

## Key invariants

These are conventions that the codebase consistently follows. **Breaking
them = bugs.** Full list in `app/rms/AGENTS.md`; the high-traffic ones:

1. **Money is `Decimal`, never `float`.** All persistence goes through
   `to_int_gs()`. DB columns are INTEGER. This is a hard rule because
   Gs. is a 0-decimal currency, so we never need fractional cents.

2. **Time is UTC in DB, America/Asuncion in display.** All datetime
   math uses `ASUNCION_TZ`. `datetime.now()` (no tz) is a bug.

3. **Stock moves are atomic with sale creation.** All-or-nothing.
   Negative stock is allowed (UI shows red alert).

4. **Audit log is mandatory on mutations.** All writes to
   non-transient tables go through `app/rms/audit.py:record()`.

5. **CSRF is required on all state-changing routes.** See
   `app/rms/csrf.py` and the `Depends(require_csrf)` pattern in routers.

6. **No async handlers.** Sync only, because DB session lifecycle
   is easier and FastAPI's threadpool handles it.

7. **No third-party HTTP calls** (except R2 backup). No analytics, no
   error reporting to external services, etc. (Self-hosted QA only.)

8. **DB schema is hand-rolled** in `app/rms/db.py` as
   `_migration_NNN_<name>()` functions. Bump `CURRENT_SCHEMA_VERSION`
   in `app/rms/config.py` after adding one.

9. **DB naive-UTC convention** — `datetime` columns are naive UTC
   (not timezone-aware). This is a wart from the early days; it
   works because every `datetime.now()` call is naive UTC and
   displayed via `ASUNCION_TZ` conversion at the template layer.

10. **`NAV_GROUPS` is SSOT** for sidebar/breadcrumb/cmd-k. Never
    hardcode a nav label in a template — add to `app/rms/nav.py`
    and tests will catch inconsistencies.

## Auth

Two auth modes, picked at startup via `AUTH_MODE` env var:

- **Local (`AUTH_MODE=local`, default in dev):** signed-cookie
  session via `SessionMiddleware`. Login form at `/login`.
  Passwords hashed with bcrypt (`demo` / `admin` in dev).
- **Supabase (`AUTH_MODE=supabase`, default in prod):** delegates
  to Supabase Auth, then mints a local session cookie. Logout is
  best-effort (Supabase may not revoke server-side).

Both modes produce a `request.session["user_id"]` that all
authenticated routes depend on. See `app/auth.py` and
`app/auth_supabase.py`.

## Data: the 5 most important tables

If you're trying to understand the business, start here:

1. **`product`** — every sellable thing (medialuna, torta, etc.).
   Has `price_gs` (integer Gs.), `unit`, `category_id`, `is_active`.
2. **`recipe`** — one per product. Has `yield_qty`, `yield_unit`,
   and a list of `recipe_line` (polymorphic: ingredient or sub-recipe).
3. **`ingredient`** — raw material (harina, huevos, etc.). Has
   `stock_qty` (current), `min_qty` (alert threshold), `cost_gs`
   (latest purchase price).
4. **`sale`** — one per POS sale. Has `sold_at` (naive UTC),
   `total_gs`, `lines` (each a `product_id` + `qty` + `unit_price_gs`).
5. **`audit_log`** — append-only. Every mutation to a tracked table
   writes one row. Has `actor_user_id`, `action`, `entity_type`,
   `entity_id`, `at`, `payload_json`.

## Build and run

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

## Deploy

- **Local:** see above; no deploy step.
- **Hosted:** `git push origin <branch>`, then `make deploy` on the
  VPS pulls + restarts. CI runs `make check` first; green required.

For incident response, see
`docs/operations/2026-09-08-incident-response.md`.

## See also

- [app/rms/AGENTS.md](../../app/rms/AGENTS.md) — the hard rules
- [CHANGELOG.md](../../CHANGELOG.md) — what changed recently
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — how to make changes
- [docs/operations/2026-10-04-phase3-ci-cleanup-postmortem.md](2026-10-04-phase3-ci-cleanup-postmortem.md) — what the CI cleanup did
- [docs/operations/2026-10-04-sibling-session-coordination.md](2026-10-04-sibling-session-coordination.md) — how to avoid stepping on yourself
- [docs/user-guide/README.md](../../user-guide/README.md) — the user-facing manual
