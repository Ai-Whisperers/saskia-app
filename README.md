# Sazón — Bakery Management System

> **The operator's app** for one bakery (La Vaquita Feliz, Asunción, Paraguay). Full restaurant-management system: sales, inventory, recipes, production planning, customers, financials, audit. Local-first + hosted dual deployment.
>
> **Status (2026-10-09):** Schema v117 · 350 routes (51 routers) · 7,961 tests (718 files) · 131 templates · 1,530 commits.
> **Active deployment:** [sazon-vps.paragu-ai.com](https://sazon-vps.paragu-ai.com) (VPS via Docker Swarm + Cloudflare Tunnel).

---

## 👥 If you are…

| You are… | Start here | Then read |
|---|---|---|
| **The operator (Saskia)** running the bakery | [docs/user-guide/](docs/user-guide/) (Spanish, with screenshots) | [docs/operations/loyalty-pos-cheatsheet.md](docs/operations/loyalty-pos-cheatsheet.md) for the loyalty-POS workflow |
| **A new developer** joining the project | This README (5 min) → [CONTRIBUTING.md](CONTRIBUTING.md) (5 min) → [AGENTS.md](AGENTS.md) (15 min — the hard rules) | [app/rms/AGENTS.md](app/rms/AGENTS.md) for app-level conventions |
| **An AI agent** (Kiki, future sessions) | [AGENTS.md](AGENTS.md) — every rule is binding | [docs/roadmap/EXECUTION-PLAN.md](docs/roadmap/EXECUTION-PLAN.md) for "what to ship next" |
| **Debugging a production issue** | [docs/operations/](docs/operations/) (day-to-day runbooks) | [docs/roadmap/sessions/](docs/roadmap/sessions/) for recent incident postmortems |
| **Looking up a design decision** | [docs/roadmap/decisions/](docs/roadmap/decisions/) (ADRs) | [docs/roadmap/historical-plans/INDEX.md](docs/roadmap/historical-plans/INDEX.md) for archived plans |
| **Reviewing CI / test health** | [docs/roadmap/STATUS.md](docs/roadmap/STATUS.md) (live state) | [docs/operations/2026-10-04-test-infra-one-pager.md](docs/operations/2026-10-04-test-infra-one-pager.md) |
| **Auditing past work** | [docs/roadmap/audits/INDEX.md](docs/roadmap/audits/INDEX.md) | [docs/roadmap/sessions/INDEX.md](docs/roadmap/sessions/INDEX.md) |

---

## ⚡ Quick start (60 seconds)

```bash
git clone https://github.com/Ai-Whisperers/sazon-app.git
cd sazon-app
make install          # uv sync --all-extras
make migrate          # apply schema migrations
make seed             # populate demo data
make serve            # run on http://127.0.0.1:8765
```

Then open <http://127.0.0.1:8765> and log in as `demo` / `admin`.

**Common shortcuts:** `make` (full list) · `make test` (~70s, full suite) · `make check` (ruff + tests, CI gate) · `make deploy` (push to VPS).

---

## 🏗️ Architecture

```
┌────────────────────┐      ┌─────────────────────────┐
│ Local Dev          │      │ Hosted Production       │
│ 127.0.0.1:8765     │      │ sazon-vps.paragu-ai.com │
│ SQLite + uvicorn   │      │ Postgres + Docker Swarm │
│                    │      │ Cloudflare Tunnel       │
└────────┬───────────┘      └────────────┬────────────┘
         │                               │
         └───────────┬───────────────────┘
                     ▼
   ┌───────────────────────────────────────┐
   │  FastAPI 0.115  ·  sync handlers      │
   │  Jinja2 templates  ·  no JS build     │
   │  SQLAlchemy 2.x  ·  hand-rolled migs  │
   │  80% test coverage (pytest+hypothesis)│
   └───────────────────────────────────────┘
```

**Tech stack:** FastAPI · SQLAlchemy 2.x · Jinja2 · SQLite (local) / PostgreSQL (hosted) · ruff (lint+format) · pytest (test) · uv (deps) · Docker Swarm + Cloudflare Tunnel (hosted).

**Module layout:** 91 RMS modules in `app/rms/` (domain logic, no HTTP) · 51 routers in `app/routers/` (HTTP layer) · 131 templates in `app/templates/` · 12 SQLAlchemy models in `app/rms/models/` · 117 schema migrations in `app/rms/migrations/` (hand-rolled, no Alembic).

### Where to add X

| You want to… | Put it in |
|---|---|
| New page | `app/routers/<thing>.py` + `app/templates/<thing>.html` |
| New SQL model | `app/rms/models/<group>.py` + new migration in `app/rms/migrations/` |
| Business rule | `app/rms/<module>.py` (pure functions) or `app/rms/services/` (with `session: Session`) |
| External integration | `app/integrations/<vendor>.py` (scrapers, barcode, printer) |
| Nav entry | `NAV_GROUPS` in `app/rms/nav.py` (never hardcode in templates) |
| Operator setting | `app/rms/settings_registry.py` (single source of truth, 42 settings) |
| CSS / styling | `app/static/css/` (component-scoped files) |
| Test | `tests/test_<module>.py` (pytest) — see [docs/operations/2026-10-04-test-infra-one-pager.md](docs/operations/2026-10-04-test-infra-one-pager.md) |

---

## 📁 Repository structure

```
sazon-app/                                       ~6,500 files · 1,530 commits
├── README.md                                    ← you are here
├── AGENTS.md                                    392 lines: hard rules (read before any PR)
├── CHANGELOG.md                                 app-level changelog (CI-enforced updates)
├── CONTRIBUTING.md                              dev workflow + commit conventions
├── WHAT_NEXT.md                                 daily-standup-style priority list
├── Makefile                                     25+ targets (install, serve, test, deploy, …)
│
├── app/                                         the application
│   ├── main.py                                  FastAPI app + middleware
│   ├── routers/                                 51 HTTP routers (sales, recipes, …)
│   ├── templates/                               131 Jinja2 templates
│   ├── static/                                  images, CSS, JS (no build step)
│   ├── rms/                                     91 domain modules (no HTTP, no templates)
│   │   ├── AGENTS.md                            app-level hard rules (subset of root AGENTS.md)
│   │   ├── db.py                                migration runner
│   │   ├── main.py                              app-bootstrap helpers
│   │   ├── config.py                            schema version + settings keys
│   │   ├── money.py                             ⭐ all money math (Decimal only, never float)
│   │   ├── settings_registry.py                 ⭐ 42 operator-facing settings
│   │   ├── models/                              12 SQLAlchemy models
│   │   ├── migrations/                          36 migration files (v082 → v117)
│   │   ├── seed/                                demo data + Saskia pack loader
│   │   └── services/                            18 service modules
│   ├── integrations/                            external (Supabase, OSRM, OCR)
│   ├── observability/                           Sentry, metrics, health checks
│   └── migrations/                              root-level migration re-exports
│
├── tests/                                       718 test files (~8K tests)
│   ├── test_*.py                                unit + integration
│   ├── e2e/                                     17 browser-driven E2E
│   ├── browser/                                 6 session-level
│   ├── _lib/                                    shared test helpers
│   └── fixtures/                                factory-boy + DB seeds
│
├── scripts/                                     52 operator/dev scripts
│   ├── backup.py, backup_cron.py                daily backup pipeline
│   ├── ci_alert.py                              Slack-on-failure
│   ├── capture_screenshots.py                   visual regression
│   └── check_no_secrets.py                      pre-commit secret scan
│
├── docs/                                        338 .md files (32.7 MB)
│   ├── README.md                                docs map (start here for /docs)
│   ├── operations/                              40 day-to-day runbooks (deploys, incidents)
│   ├── roadmap/                                 ⭐ 74 .md: STATUS, BACKLOG, EXECUTION-PLAN, epics
│   │   ├── STATUS.md                            live state (schema, routes, deploy URL)
│   │   ├── BACKLOG.md                           merged P0/P1/P2/P3 forward-looking work
│   │   ├── EXECUTION-PLAN.md                    ⭐ the next-2-sprints punchlist
│   │   ├── IMPROVEMENT_BACKLOG.md               older operational backlog
│   │   ├── epics/                               25 epics (E1–E25) across 6 phases
│   │   ├── decisions/                           ADRs + canonical-roadmap alignment
│   │   ├── audits/                              one-shot post-fix summaries
│   │   ├── sessions/                            multi-session recovery plans
│   │   └── historical-plans/                    archived v1/v2/v3 plans
│   ├── user-guide/                              26 .md, Spanish, screenshots
│   ├── analysis/                                one-time analysis outputs
│   ├── archive/                                 44 archived/redirected files
│   ├── intake/                                  raw ticket-seed ideas
│   ├── wishlist/                                long-shot backlog
│   ├── plans/                                   26 working + draft plans
│   ├── reports/                                 26 generated reports (redesign, audits)
│   ├── ux/                                      UX design notes + copy
│   ├── adr/                                     architecture-decision records
│   ├── decisions/                               cross-team decisions
│   ├── upgrades/                                historical upgrade plans
│   └── superpowers/                              writing-plans reference
│
├── deliverables/                                4 high-level hand-off docs
├── deploy/                                      Docker Swarm + VPS configs
├── installer/                                   4 macOS-installer round notes
├── state/                                       live state snapshots
└── tools/                                       misc tooling
```

**Auto-generated tree; for live state see [docs/roadmap/STATUS.md](docs/roadmap/STATUS.md).**

---

## 🧭 Where to find things

### Operations & deployment
- [docs/operations/](docs/operations/) — 40 day-to-day runbooks
- [docs/operations/2026-10-09-three-env-deploy.md](docs/operations/2026-10-09-three-env-deploy.md) — three-env (local / staging / prod) deployment topology
- [docs/operations/2026-10-05-produccion-v2-deploy-runbook.md](docs/operations/2026-10-05-produccion-v2-deploy-runbook.md) — production v2 deploy steps
- [docs/operations/backup-cron.md](docs/operations/backup-cron.md) — daily 03:15 backup cadence
- [docs/operations/healthz-db-runbook.md](docs/operations/healthz-db-runbook.md) — `/healthz`, `/healthz/deps`, `/healthz/backup`
- [docs/operations/PRODUCTION_500_RUNBOOK.md](docs/operations/PRODUCTION_500_RUNBOOK.md) — production 500 error triage
- [docs/operations/worktree-policy.md](docs/operations/worktree-policy.md) — operator policy on parallel worktrees
- [docs/operations/loyalty-pos-cheatsheet.md](docs/operations/loyalty-pos-cheatsheet.md) — POS workflow for loyalty points

### Roadmap & planning
- [docs/roadmap/STATUS.md](docs/roadmap/STATUS.md) — current state (live)
- [docs/roadmap/EXECUTION-PLAN.md](docs/roadmap/EXECUTION-PLAN.md) — next-2-sprints punchlist
- [docs/roadmap/BACKLOG.md](docs/roadmap/BACKLOG.md) — merged P0–P3 backlog
- [docs/roadmap/epics/00-EPIC-PLAN-EXTRACT.md](docs/roadmap/epics/00-EPIC-PLAN-EXTRACT.md) — 25-epic long-term plan
- [docs/roadmap/decisions/](docs/roadmap/decisions/) — ADRs

### Engineering rules
- [AGENTS.md](AGENTS.md) — 392-line hard-rule bible (read before any PR)
- [app/rms/AGENTS.md](app/rms/AGENTS.md) — app-level rules (subset; the money/unit/time/stock rules)
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev workflow + commit conventions
- [CHANGELOG.md](CHANGELOG.md) — release history (CI-enforced updates per the AGENTS.md rule)

### User-facing
- [docs/user-guide/](docs/user-guide/) — Spanish manual with screenshots
- [installer/](installer/) — macOS installer round notes
- [docs/operations/loyalty-pos-cheatsheet.md](docs/operations/loyalty-pos-cheatsheet.md) — POS cheat sheet

### Historical / archive
- [docs/archive/](docs/archive/) — 44 archived/redirected files (kept for history)
- [docs/roadmap/historical-plans/INDEX.md](docs/roadmap/historical-plans/INDEX.md) — original v1/v2/v3 plans
- [docs/roadmap/audits/](docs/roadmap/audits/) — one-shot audit reports (post-fix summaries)

---

## 🚀 Key engineering rules (TL;DR)

> Full rules: [AGENTS.md](AGENTS.md). The below is the cheat-sheet for "what will break if I violate it."

### Money
- **All money use `Decimal`, never `float`.** Persistence via `app/rms/money.py:to_int_gs()`. DB columns are INTEGER (no decimal currencies in Paraguay).

### Time
- All datetime math uses `ASUNCION_TZ` (UTC−4). DB stores naive UTC; display converts. `datetime.now()` without timezone = bug.

### Stock
- Stock moves are atomic with sale creation. Negative stock allowed (UI shows red alert). Void reverses stock moves fully.

### Migrations
- **Hand-rolled, no Alembic.** Files in `app/rms/migrations/_NNN_*.py`; runner in `app/rms/db.py`. Bump `CURRENT_SCHEMA_VERSION` after adding.

### Auth
- Two modes via `AUTH_MODE`: **local** (cookie + `demo`/`admin`) or **Supabase** (hosted, prod).

### Tests
- `make test` (~70s, full suite). 80% coverage gate. CI enforces `app/CHANGELOG.md` update on `app/`, `scripts/`, `tests/`, `.github/` changes.

---

## 📊 Status & provenance

| | |
|---|---|
| **Repo** | [Ai-Whisperers/sazon-app](https://github.com/Ai-Whisperers/sazon-app) |
| **Production URL** | <https://sazon-vps.paragu-ai.com> |
| **Schema version** | v117 (2026-10-09) |
| **Tests** | 7,961 (718 files) |
| **Routes** | 350 (51 routers) |
| **Templates** | 131 (Jinja2) |
| **Commits** | 1,530 |
| **First commit** | 2026-08-31 (split from `Ai-Whisperers/saskia` initial) |
| **License** | MIT (visibility: public, no PII) |
| **Maintainer** | Iván Weiss Van Der Pol (AIW founder) |

### Last 5 commits

```
1c63a5b6 refactor(reorder): reduce reorder_upload_prices complexity 30→1
079cc12f refactor(auditoria): reduce auditoria_export_csv complexity 31→0
6bb43a6c Merge pull request #89 from Ai-Whisperers/chore/root-cleanup-2026-10-09
123afefa refactor(tagging): reduce repair_ingredient complexity 31→2
6ca34c08 refactor(supplier): reduce get_price_comparison complexity 31→1
```

### Companion resources

- [AGENTS.md](AGENTS.md) — engineering hard rules (canonical)
- [CHANGELOG.md](CHANGELOG.md) — release history
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow + conventions
- [docs/operations/](docs/operations/) — operator-facing runbooks
- [docs/user-guide/](docs/user-guide/) — Spanish operator manual
- [docs/roadmap/](docs/roadmap/) — roadmap, backlog, epics, decisions, audits

---

**Last README overhaul:** 2026-10-09 (worktree `saskia-app-readme`, branch `docs/readme-overhaul-2026-10-09`).
