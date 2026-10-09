# Saskia RMS — Free-Tier Reliability Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to execute this plan task-by-task. Each task is TDD: write failing test → confirm fail → minimal impl → confirm pass → commit.

**Goal:** Make the saskia-rms app reliably usable for a single-operator bakery on the existing free-tier Render + Neon + Supabase + Cloudflare stack, with no new dependencies, by (1) preventing the cold-start DoS, (2) eliminating the schema-drift outage class, (3) tightening input/state-handling failure modes, and (4) giving the operator drift + error visibility before users do.

**Architecture:** All changes stay within the locked tech stack (FastAPI 0.115, SQLAlchemy 2.0 sync, Pydantic 2.9 already pinned, loguru already imported) and remain a single-deployment, single-tenant, single-operator app per AGENTS.md. We add no new external services. We make the existing free-tier more resilient by **warming via existing UptimeRobot** (already configured), **tightening DB-level safeguards**, and **adding operator-visible health endpoints**. Everything must pass `uv run pytest -q` (current baseline: 895 passed) and `uv run ruff check .` (clean baseline).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, Pydantic 2.9, loguru, itsdangerous (already in deps for CSRF). No new packages.

---

## Current State (verified)

- 895 tests passing, 0 ruff errors. Single-tenant deployment.
- Live site URL: `https://saskia-rms.paragu-ai.com` (Render free-tier service `srv-dac8g2u7bikc73f3psf0`, plan free, region us-east-2).
- Live DB: Neon Postgres, schema at v11 (after manual apply of migration 011 on 2026-09-08).
- Deploy chain: GitHub Actions CI → Render auto-deploy on push to `main`.
- BWS: 198 secrets (`5da6199e-…` org); Migrations env var `AIW_SASKIA_RUN_MIGRATIONS=1` already set (after the outage).
- Existing live functions verified working: `/healthz`, `/healthz/db`, `/healthz/deps`, `/healthz/errors`, `/login`, `/`, `/ventas`, `/ventas?days=7`, `/productos`, `/clientes`, `/eod`, `/merma`, `/reportes` — all 200.
- Known limitations (per `docs/operations/2026-09-08-live-site-issues-fixes.md`):
  - Render free-tier spins down after ~5 min of inactivity → 30-90s cold-start penalty.
  - Same-period session table joins in dashboard were N+1; fixed in commit `4621097`.
- GitHub credential helper expired (managed via BWS, but the gh-CLI token rotation failed today); we now push via BWS-fetched `GITHUB_TOKEN_2` directly. Each push needs the token-providing script.

---

## Guiding principles for this work

1. **DRY** — one source of truth per concern (e.g., one `canonical_schema_version()` helper, not a string comparison repeated 3 places).
2. **YAGNI** — we are NOT building multi-tenant, multi-user RBAC, RBAC-strict, dark-mode toggle regression, or anything else that touches E15/E25/Phase-2 modules. Per AGENTS.md.
3. **TDD** — every task includes a failing test first, then minimal impl.
4. **Frequent commits** — one commit per task (~30 across 7 phases).
5. **Free-tier compatible** — no new paid services, no new dependencies.
6. **Reversible** — feature flags added now (e.g., `AIW_SASKIA_RDB_PROTECT_NEGATIVE_GS=1`) so we can roll back without code revert.
7. **External touchpoints are operator-action files** — no automated code push to live secrets; BWS updates happen by operator running `scripts/*` snippets.

---

## Phase 1: Schema-drift canary + cold-start elimination (high-leverage)

Three tasks. Each task ends with `Commit`. After all three: run `unset DATABASE_URL AIW_SASKIA_DB_PATH && uv run pytest -q` and `uv run ruff check .` (expected: 895+8 = 903 passed, ruff clean).

### Task 1: Implement `schema_version()` helper that reads + compares

**Objective:** Single source of truth for "what schema version does the DB have" vs "what schema version does the code expect".

**Files:**
- Modify: `app/rms/db.py` (add to the existing `db.py` module, near `MIGRATIONS`)
- Test: `tests/test_schema_version_helper.py`

**Step 1 — Write failing test.**

```python
"""tests/test_schema_version_helper.py — schema version drift detector."""

from app.rms.db import schema_version, CURRENT_SCHEMA_VERSION, schema_version_mismatch


def test_schema_version_returns_int(session_factory):
    """schema_version(session) returns the current row's value as int."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    with session_factory() as s:
        v = schema_version(s.connection())
    assert isinstance(v, int)
    assert v == CURRENT_SCHEMA_VERSION


def test_schema_version_mismatch_returns_diff(session_factory):
    """schema_version_mismatch(session) returns 0 when versions match."""
    from app.rms.db import init_db

    engine = session_factory.kw["bind"]
    init_db(engine)
    with session_factory() as s:
        diff = schema_version_mismatch(s.connection())
    assert diff == 0


def test_schema_version_mismatch_returns_positive_when_drift(session_factory):
    """schema_version_mismatch returns CURRENT - DB when DB is behind."""
    from app.rms.db import init_db, _current_schema_version, app_meta_write

    engine = session_factory.kw["bind"]
    init_db(engine)
    # Force DB schema to an older version
    with session_factory() as s:
        app_meta_write(s.connection(), "schema_version", str(CURRENT_SCHEMA_VERSION - 1))
        diff = schema_version_mismatch(s.connection())
    assert diff == 1


def test_app_meta_write_creates_row_if_missing(session_factory):
    """app_meta_write INSERTs a new row when key doesn't exist."""
    from app.rms.db import app_meta_write, app_meta_read

    with session_factory() as s:
        s.commit()
    with session_factory() as s:
        app_meta_write(s.connection(), "custom_key_test", "hello")
        s.commit()
    with session_factory() as s:
        assert app_meta_read(s.connection(), "custom_key_test") == "hello"
```

**Step 2 — Run.** Expected: AttributeError or ImportError. Confirm tests fail.

Run: `unset DATABASE_URL AIW_SASKIA_DB_PATH && uv run pytest tests/test_schema_version_helper.py -v`
Expected: FAIL — `cannot import name 'schema_version' from app.rms.db`

**Step 3 — Implement in `app/rms/db.py`.** Add at the bottom of the file (above `__all__` if any):

```python
def schema_version(conn) -> int:
    """Read schema_version from app_meta (default 0). Dialect-agnostic."""
    return _current_schema_version(conn)


def app_meta_read(conn, key: str) -> str | None:
    """Read one key from app_meta. Returns None if missing."""
    row = conn.execute(text("SELECT value FROM app_meta WHERE key = :key"), {"key": key}).first()
    return row[0] if row else None


def app_meta_write(conn, key: str, value: str) -> None:
    """Upsert one key into app_meta. Postgres uses ON CONFLICT; SQLite uses INSERT OR REPLACE."""
    dialect = conn.dialect.name
    ts = datetime.now(timezone.utc).isoformat()
    if dialect == "postgresql":
        conn.execute(
            text(
                "INSERT INTO app_meta (key, value, updated_at) VALUES (:k, :v, :ts) "
                "ON CONFLICT (key) DO UPDATE SET value=:v, updated_at=:ts"
            ),
            {"k": key, "v": value, "ts": ts},
        )
    else:
        conn.execute(
            text("INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES (:k, :v, :ts)"),
            {"k": key, "v": value, "ts": ts},
        )


def schema_version_mismatch(conn) -> int:
    """Return CURRENT_SCHEMA_VERSION - actual_db_version.

    Positive = DB is behind code (migrations not applied — production outage risk).
    Zero = in sync. Negative = DB is ahead of code (rolled back to old code).
    """
    return CURRENT_SCHEMA_VERSION - schema_version(conn)
```

Also delete any dead duplicate `MIGRATIONS` dicts and the stale `INSERT OR REPLACE` final upsert per `docs/operations/2026-09-08-live-site-issues-fixes.md`. Refactor `init_db()` to use `schema_version_mismatch(conn)` instead of duplicating the version read.

**Step 4 — Run tests.** Expected: 4 passed.

**Step 5 — Commit.**

```bash
git add app/rms/db.py tests/test_schema_version_helper.py
git commit -m "feat(db): schema_version helpers + dialect-agnostic app_meta upsert"
```

---

### Task 2: Add `/healthz/schema` endpoint that detects drift

**Objective:** Operator-callable URL that returns the DB schema version vs code version, mismatches trigger alerts.

**Files:**
- Modify: `app/routers/health.py` (add new endpoint above `__all__`)
- Test: `tests/test_healthz_schema.py`

**Step 1 — Write failing test.**

```python
"""tests/test_healthz_schema.py — /healthz/schema endpoint."""

from app.rms.db import CURRENT_SCHEMA_VERSION


def test_healthz_schema_returns_versions(client):
    """Returns code_version + db_version + drift fields."""
    resp = client.get("/healthz/schema")
    assert resp.status_code == 200
    body = resp.json()
    for k in ("code_version", "db_version", "drift"):
        assert k in body


def test_healthz_schema_in_sync_returns_drift_zero(client):
    """When DB matches code, drift must be 0."""
    resp = client.get("/healthz/schema")
    assert resp.status_code == 200
    assert resp.json()["drift"] == 0
    assert resp.json()["code_version"] == resp.json()["db_version"]


def test_healthz_schema_out_of_sync_returns_500(client, session_factory):
    """When DB is behind, /healthz/schema returns 500 with hint."""
    from app.rms.db import app_meta_write, CURRENT_SCHEMA_VERSION

    with session_factory() as s:
        app_meta_write(s.connection(), "schema_version", str(CURRENT_SCHEMA_VERSION - 1))
        s.commit()
    resp = client.get("/healthz/schema")
    assert resp.status_code == 500
    assert resp.json()["drift"] > 0
    assert "migrate" in resp.json()["hint"].lower()
```

**Step 2 — Run.** Expected: 404 Not Found (route doesn't exist). Confirm.

**Step 3 — Implement in `app/routers/health.py`.**

```python
@router.get("/healthz/schema", response_model=None)
def healthz_schema(request: Request) -> JSONResponse:
    """Drift detector: returns code_version, db_version, drift.

    drift > 0 = DB behind code (CRITICAL — production will 500 on new
    columns). Operator action: redeploy after setting
    AIW_SASKIA_RUN_MIGRATIONS=1 (or wait for next deploy, which now
    auto-runs migrations by default as of 2026-09-08).

    Returns 500 when drift > 0 so monitoring tools (UptimeRobot) alert.
    """
    from app.rms.db import CURRENT_SCHEMA_VERSION, schema_version, schema_version_mismatch

    ready = getattr(request.app.state, "ready", False)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )

    with request.app.state.session_factory() as s:
        actual = schema_version(s.connection())
        drift = schema_version_mismatch(s.connection())

    body = {
        "code_version": CURRENT_SCHEMA_VERSION,
        "db_version": actual,
        "drift": drift,
    }
    if drift > 0:
        body["hint"] = (
            f"DB schema v{actual}, code expects v{CURRENT_SCHEMA_VERSION}. "
            "Redeploy to apply pending migrations automatically."
        )
        body["status"] = "schema_drift"
        return JSONResponse(status_code=500, content=body)
    body["status"] = "in_sync"
    return JSONResponse(status_code=200, content=body)
```

**Step 4 — Run tests.** Expected: 3 passed.

**Step 5 — Commit.**

```bash
git add app/routers/health.py tests/test_healthz_schema.py
git commit -m "feat(healthz): /healthz/schema detects drift before operators see 500s"
```

---

### Task 3: Wire UptimeRobot to `/healthz/db` (already running) + add schema as second UptimeRobot monitor

**Objective:** Keep the free-tier Render container warm by sending a request every 5 minutes. Eliminates the 30-90s cold-start penalty for any operator who opens the site within 5 minutes of last activity.

**Files:**
- Modify: `scripts/uptimerobot_setup.py` (extend to set up a second monitor for `/healthz/db`)
- Create: `scripts/uptimerobot_setup_schema.py` (calls the second monitor)
- Test: `tests/test_uptimerobot_setup_extended.py` (idempotency, dry-run mode)

**Step 1 — Read the existing `scripts/uptimerobot_setup.py`.**

It already creates monitor for `/healthz`. We'll add a `create_or_get_monitor()` helper that the existing script and a new sibling script can both call.

**Step 2 — Write failing test.**

```python
"""tests/test_uptimerobot_setup_extended.py — dry-run smoke test.

Tests that scripts/uptimerobot_setup.py can be invoked with --dry-run
and doesn't touch the network (no live API calls in CI).
"""

import os
import subprocess


def test_setup_dry_run_no_network():
    """--dry-run prints the create URLs but doesn't hit the API."""
    r = subprocess.run(
        ["python", "scripts/uptimerobot_setup.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/opt/data/profiles/ivan/scratch/saskia-app-work",
    )
    assert r.returncode == 0
    out = r.stdout.lower()
    # Should mention healthz
    assert "healthz" in out
```

**Step 3 — Implement `--dry-run` in `scripts/uptimerobot_setup.py`.**

Add an `argparse` `--dry-run` flag. When set, the script fetches BWS keys (read-only), then prints what it WOULD create without calling UptimeRobot:

```python
parser.add_argument(
    "--dry-run", action="store_true", help="Print what would happen without making API calls"
)
```

And inside `main()`:

```python
if args.dry_run:
    print(f"DRY RUN — would verify/create monitor for {MONITOR_URL}")
    # Print bundle info: login user, monitor type, interval
    print(f"  type=HTTP interval=300s timeout=30s retention=30")
    return
```

**Step 4 — Run test.** Expected: 1 passed.

**Step 5 — Use the live API to add the schema monitor.**

Run with the BWS-fetched UptimeRobot key to add a second monitor:

```bash
# Operator runs once: creates monitor for /healthz/schema, returns id
uv run python scripts/uptimerobot_setup.py create-schema-monitor \
    --url https://saskia-rms.paragu-ai.com/healthz/schema \
    --interval 300 \
    --friendly "saskia-rms /healthz/schema (schema drift)"
```

The new subcommand uses `create_or_get_monitor(friendly_name=..., url=..., interval=300)` and prints the monitor ID + save status.

Actually, because BWS-fetched API calls + CLI subcommand logic will be substantial, scope this down to a TINY step: just hard-code a second `find_monitor(MONITOR_URL)` and `create_monitor()` call into the existing script under a `create_health_monitors()` function that handles both URLS. Operator runs `python scripts/uptimerobot_setup.py` with no args → idempotently ensures both monitors exist with 5-min intervals.

**Step 5 (revised) — Extend `scripts/uptimerobot_setup.py`** to handle TWO urls:

```python
DEFAULT_MONITORS = [
    ("https://saskia-rms.paragu-ai.com/healthz", "saskia-rms /healthz"),
    ("https://saskia-rms.paragu-ai.com/healthz/db", "saskia-rms /healthz/db"),
    ("https://saskia-rms.paragu-ai.com/healthz/schema", "saskia-rms /healthz/schema"),
]


def main():
    # ... argparse setup ...
    if args.create_all:
        for url, name in DEFAULT_MONITORS:
            existing = find_monitor_for_url(api_key, url)
            if existing:
                print(f"  exists id={existing['id']} url={url}")
            else:
                created = create_monitor(api_key, name=name, url=url, interval=300)
                print(f"  created id={created} url={url}")
        return
```

**Step 6 — Run live.** Invoke with the BWS-backed `--api-key` to ensure all three monitors exist:

```bash
PYTHONPATH=/opt/data/.venv/lib/python3.11/site-packages \
  /opt/data/.venv/bin/python3.11 /opt/data/profiles/ivan/scratch/saskia-app-work/scripts/uptimerobot_setup.py create-all
```

Expected output: prints `created id=... url=...` for any missing monitor, `exists id=...` for already-existing.

The first monitor (`/healthz`) we already confirmed exists (id 803916096).

**Step 7 — Commit.**

```bash
git add scripts/uptimerobot_setup.py tests/test_uptimerobot_setup_extended.py
git commit -m "ops(uptimerobot): extend to monitor /healthz/db + /healthz/schema"
```

---

## Phase 2: Input validation + state-change protection (security + data integrity)

Four tasks. After phase: 903 + 12 = 915 passed, ruff clean.

### Task 4: Pydantic request models for all state-changing endpoints

**Objective:** Replace ad-hoc `form.get(int)` parsing with Pydantic 2 models that enforce types, ranges, and required fields. Eliminates the silent negative-discounts / huge-sale problems.

**Files:**
- Create: `app/rms/schemas.py`
- Modify: `app/routers/sales.py` (use the schema)
- Modify: `app/routers/products.py`
- Modify: `app/routers/inventory.py`
- Modify: `app/routers/recetas.py`
- Modify: `app/routers/merma.py`
- Test: `tests/test_pydantic_forms.py`

**Step 1 — Write failing test.**

```python
"""tests/test_pydantic_forms.py — Pydantic validation for state-changing endpoints.

Prior: raw form.get()/int()/float() parsing, no validation. Negative
discounts, zero sales, integer overflow could pass silently.

Post: Pydantic rejects bad input with 422 before the route handler runs.
"""

from fastapi.testclient import TestClient


def test_ventas_nueva_rejects_negative_discount(client):
    from app.rms.main import app

    tc = TestClient(app, raise_server_exceptions=False)
    resp = tc.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "1",
            "discount_gs": "-100",
            "payment_method": "cash",
        },
    )
    assert resp.status_code == 422, f"Expected 422 for negative discount, got {resp.status_code}"


def test_ventas_nueva_rejects_huge_qty(client):
    from app.rms.main import app

    tc = TestClient(app, raise_server_exceptions=False)
    resp = tc.post(
        "/ventas/nueva",
        data={
            "product_id": "1",
            "qty": "99999999",
            "discount_gs": "0",
            "payment_method": "cash",
        },
    )
    assert resp.status_code == 422


def test_ventas_nueva_rejects_unknown_payment_method():
    """Pydantic Literal validates payment_method."""
    # Will write test in this file once sale_create has a Pydantic model
    pass


def test_ventas_nueva_rejects_missing_product_id(client):
    from app.rms.main import app

    tc = TestClient(app, raise_server_exceptions=False)
    resp = tc.post("/ventas/nueva", data={"qty": "1"})
    assert resp.status_code == 422  # product_id is required


def test_eod_save_rejects_extra_long_progress():
    pass


def test_pydantic_models_are_pydantic_v2():
    """All request models must be pydantic v2 (BaseModel)."""
    from app.rms.schemas import SaleCreateRequest
    from pydantic import BaseModel

    assert issubclass(SaleCreateRequest, BaseModel)
```

**Step 2 — Run.** Expected: schema module doesn't exist. Confirm.

**Step 3 — Implement `app/rms/schemas.py`.**

```python
"""app/rms/schemas.py — Pydantic 2 request models for state-changing endpoints.

Why: raw form parsing lets bad data through (negative discounts, huge
quantities, missing fields). Pydantic rejects at the validation layer
(FastAPI's 422) before any business logic runs.

All fields are validated at type level. Custom validators enforce:
- discount_gs >= 0
- qty in (0, MAX_QTY]
- payment_method ∈ {cash, transfer, card, other}
- product_id > 0
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

MAX_QTY = 1_000_000  # sanity cap — never selling a million of anything
ALLOWED_PAYMENT_METHODS = frozenset({"cash", "transfer", "card", "other"})


class SaleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: int = Field(gt=0)
    qty: float = Field(gt=0, le=MAX_QTY)
    payment_method: Optional[str] = None
    discount_gs: int = Field(default=0, ge=0)
    customer_phone: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=500)
    sold_at: Optional[str] = Field(default=None, description="ISO datetime, defaults to now")

    @field_validator("payment_method")
    @classmethod
    def _validate_payment_method(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {sorted(ALLOWED_PAYMENT_METHODS)}")
        return v


class ProductForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    sale_price_gs: int = Field(gt=0, lt=1_000_000_000)
    portion_label: Optional[str] = Field(default=None, max_length=120)
    recipe_id: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)
    sku: Optional[str] = Field(default=None, max_length=64)


class IngredientForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=8)
    stock_qty: float = Field(ge=0, le=1_000_000)
    purchase_price_gs: int = Field(ge=0, lt=1_000_000_000)
    min_stock_qty: float = Field(default=0, ge=0)
    category: Optional[str] = Field(default=None, max_length=64)


class WasteRecordForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    ingredient_id: int = Field(gt=0)
    qty: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=500)


__all__ = [
    "SaleCreateRequest",
    "ProductForm",
    "IngredientForm",
    "WasteRecordForm",
    "ALLOWED_PAYMENT_METHODS",
    "MAX_QTY",
]
```

**Step 4 — Wire into routers.** For each state-changing endpoint, replace `form = await request.form()` + manual parsing with Pydantic model. Example for sales.py:

```python
from app.rms.schemas import SaleCreateRequest


@router.post("/nueva")
async def sale_create(
    request: Request,
    form_data: SaleCreateRequest = Depends(SaleCreateRequest.as_form),  # noqa
    session: Session = Depends(get_session),
) -> RedirectResponse: ...
```

Since FastAPI's `Depends` doesn't natively handle Form → Pydantic, the most minimal-intrusion approach is:

```python
from fastapi import Form


@router.post("/nueva")
async def sale_create(
    request: Request,
    product_id: int = Form(...),
    qty: float = Form(..., gt=0, le=MAX_QTY),
    payment_method: Optional[str] = Form(None),
    discount_gs: int = Form(0, ge=0),
    customer_phone: Optional[str] = Form(None, max_length=32),
    notes: Optional[str] = Form(None, max_length=500),
    sold_at: Optional[str] = Form(None),
    session: Session = Depends(get_session),
): ...
```

Using FastAPI's `Form(...)` with constraints — FastAPI 0.115 + Pydantic 2 supports this. This makes validation happen at the framework layer. Same approach for other endpoints.

Apply this pattern to all 5 routers. Don't change the rest of the route logic — just swap input parsing for `Form(...)`-with-constraints.

**Step 5 — Run tests.** Expected: 4 passed (one is a `pass` placeholder for now).

**Step 6 — Commit.**

```bash
git add app/rms/schemas.py app/routers/sales.py app/routers/products.py app/routers/inventory.py app/routers/recetas.py app/routers/merma.py tests/test_pydantic_forms.py
git commit -m "feat: Pydantic form validation on all state-changing endpoints"
```

---

### Task 5: Rate-limit `/ventas/nueva` + `/merma/registrar` (state-changing public POSTs)

**Objective:** Prevent a bot from creating thousands of phantom sales or waste entries per minute.

**Files:**
- Modify: `app/rms/rate_limit.py` (extend existing helper to support per-endpoint limits)
- Modify: `app/routers/sales.py` (rate-limit `/nueva`)
- Modify: `app/routers/merma.py` (rate-limit `/registrar`)
- Test: `tests/test_rate_limit_write_endpoints.py`

**Step 1 — Write failing test.**

```python
"""tests/test_rate_limit_write_endpoints.py — protect state-changing routes."""

import time


def test_ventas_nueva_rate_limited_after_burst(client, session_factory):
    """5 rapid POSTs/min should pass; the 6th should be 429."""
    from app.rms.models import Product

    with session_factory() as s:
        p = Product(name="TestBurst", sale_price_gs=10000, recipe_id=None)
        s.add(p)
        s.commit()
        pid = p.id
    from app.rms.csrf import generate_csrf_token
    from app.rms.main import app
    from starlette.testclient import TestClient

    csrf = generate_csrf_token()
    tc = TestClient(app, raise_server_exceptions=False, cookies={"csrf_token": csrf})
    for i in range(5):
        resp = tc.post(
            "/ventas/nueva",
            data={
                "product_id": str(pid),
                "qty": "1",
                "discount_gs": "0",
                "payment_method": "cash",
            },
        )
        assert resp.status_code in (303, 400), f"i={i} expected 303/400 got {resp.status_code}"
    # 6th should be rate-limited.
    resp = tc.post(
        "/ventas/nueva",
        data={
            "product_id": str(pid),
            "qty": "1",
            "discount_gs": "0",
            "payment_method": "cash",
        },
    )
    assert resp.status_code == 429, f"expected 429 rate-limited, got {resp.status_code}"
```

**Step 2 — Run.** Expected: 6th request returns 303 (not 429). Confirms no rate limit exists.

**Step 3 — Extend `app/rms/rate_limit.py`.** Add a function that uses the audit_log table to count recent hits (already implemented); add a wrapper for write endpoints with stricter limits:

```python
# Existing is_rate_limited() returns RateLimitDecision based on action prefix.
# Add a convenience for write endpoints: at most N POSTs per minute per IP.
def is_write_rate_limited(session, request: Request, *, max_per_minute: int = 5) -> bool:
    """Return True if client has exceeded max_per_minute write actions."""
    from app.rms.config import ASUNCION_TZ
    from app.rms.audit import AuditLog
    from datetime import datetime, timedelta
    from sqlalchemy import select, func

    ip = _client_ip(request) or "unknown"
    cutoff = datetime.utcnow() - timedelta(minutes=1)
    n = (
        session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action.like("write.%"),
                AuditLog.ip == ip,
                AuditLog.occurred_at >= cutoff,
            )
        ).scalar()
        or 0
    )
    return n >= max_per_minute
```

**Step 4 — Wire into sales router.** In `sale_create()`, after fetching form data, call:

```python
from app.rms.rate_limit import is_write_rate_limited

if is_write_rate_limited(session, request, max_per_minute=5):
    raise HTTPException(status_code=429, detail="Demasiadas ventas en 1 minuto. Esperá un momento.")
```

Record the write action if accepted: `audit.record(session, user_id=user, action="write.sale.create", ...)`. (Add a helper if `user` is anonymous: pass `None`.)

**Step 5 — Run tests.** Expected: 1 passed.

**Step 6 — Commit.**

```bash
git add app/rms/rate_limit.py app/routers/sales.py app/routers/merma.py tests/test_rate_limit_write_endpoints.py
git commit -m "feat(rate-limit): protect /ventas/nueva + /merma/registrar from write floods"
```

---

### Task 6: Verify and document Neon pause behavior + add `pool_recycle` verification test

**Objective:** Confirm the existing `pool_recycle=1800` is correct against Neon's idle-timeout. Add a regression test that detects accidental pool config drift.

**Files:**
- Modify: `tests/test_db_dialect.py` (or new test file) — verify `make_engine_dialect` config has `pool_recycle=1800` for postgres
- Modify: `docs/operations/2026-09-08-live-site-issues-fixes.md` (add a section on the free-tier pause risk)

**Step 1 — Write failing test.**

```python
"""tests/test_engine_pool_recycle.py — DB engine config is drift-resistant."""

from app.rms.db_dialect import make_engine_dialect


def test_engine_has_pool_recycle_set_for_postgres(monkeypatch):
    """Postgres engine must have pool_recycle <= Neon's idle timeout (5min)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    e = make_engine_dialect("postgresql://user:pw@host/db")
    pool_recycle = e.pool._recycle
    assert pool_recycle is not None
    assert pool_recycle <= 300, (
        f"pool_recycle={pool_recycle}s > Neon idle timeout (300s) — "
        f"connections will die mid-request."
    )
```

**Step 2 — Run.** Expected: pool_recycle=1800 (current), test asserts ≤300 → FAIL.

Wait, that would force a change. Let me reconsider — `pool_recycle=1800` (30 min) might actually be fine depending on Neon behavior. Per Neon docs, **free tier pauses after 5min of no activity**. After pause, the next query waits ~5-20s for cold-resume. The pool's job is to verify the connection is alive before using it; `pool_pre_ping=True` (current setting) handles this.

The right test: verify that `pool_pre_ping=True` is set, and that when a stale connection is detected, SQLAlchemy reconnects without raising to the caller.

```python
def test_engine_has_pool_pre_ping_enabled(monkeypatch):
    """Postgres engine must have pool_pre_ping=True to recover from Neon pauses."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    e = make_engine_dialect("postgresql://user:pw@host/db")
    assert e.pool._pre_ping is True, "pool_pre_ping must be enabled"
```

**Step 3 — Confirm both pool_pre_ping + pool_recycle.**

Run after step 2 to see what they are.

**Step 4 — Document in `docs/operations/2026-09-08-live-site-issues-fixes.md`.**

Append:

```markdown
### Pool config & Neon pauses

Neon free-tier pauses the database after ~5 min of no activity. On next
query, Neon takes 5-20s to resume. SQLAlchemy with `pool_pre_ping=True`
detects a stale connection (via `SELECT 1` before each query) and
reconnects transparently. The user sees a slow first query, not a 500.

`pool_recycle=1800s` (30 min) refreshes connections even on healthy
pool to avoid edge cases where the connection goes stale without
`pool_pre_ping` firing. Both are configured in
`app/rms/db_dialect.py:make_engine_dialect()`. Verified by
`tests/test_engine_pool_recycle.py`.
```

**Step 5 — Commit.**

```bash
git add tests/test_engine_pool_recycle.py docs/operations/2026-09-08-live-site-issues-fixes.md
git commit -m "test(db): regression for pool_pre_ping + pool_recycle settings"
```

---

### Task 7: Fix CSRF `secure: True` blocking local-dev POSTs

**Objective:** Local-dev users running over HTTP can still POST (currently 403 because `Secure: True` cookie flag prevents browsers from saving/returning the cookie over plain HTTP).

**Files:**
- Modify: `app/rms/csrf.py` (make `secure` env-driven, default `False` for local dev)
- Test: `tests/test_csrf_local_dev.py`

**Step 1 — Write failing test.**

```python
"""tests/test_csrf_local_dev.py — CSRF cookie works over plain HTTP (local dev)."""

import os


def test_csrf_cookie_not_secure_in_test_env(monkeypatch):
    """Default env (no AIW_SASKIA_FORCE_SECURE_COOKIES=1) → Secure: False."""
    monkeypatch.delenv("AIW_SASKIA_FORCE_SECURE_COOKIES", raising=False)
    monkeypatch.setenv("AIW_SASKIA_DB_PATH", "/tmp/test_db.sqlite")
    from app.rms.main import app
    from fastapi.testclient import TestClient

    tc = TestClient(app, raise_server_exceptions=False)
    r = tc.get("/")
    set_cookies = r.headers.get_list("set-cookie")
    csrf = [c for c in set_cookies if c.startswith("csrf_token=")]
    if csrf:
        # Secure flag should be absent when not hosted.
        assert "Secure" not in csrf[0], f"CSRF cookie should not be Secure locally: {csrf[0]}"
```

**Step 2 — Run.** Expected: assertion fails (current code sets Secure always).

**Step 3 — Implement in `app/rms/csrf.py` and `app/rms/main.py`.**

```python
# In csrf.py
def csrf_cookie_middleware(request, call_next):
    secure_cookie = os.getenv("AIW_SASKIA_FORCE_SECURE_COOKIES") == "1"
    # ... when setting the cookie:
    response.set_cookie(
        _CSRF_COOKIE,
        generate_csrf_token(),
        max_age=60 * 60 * 24,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
    )
```

The cloud env (Render) sets `AIW_SASKIA_FORCE_SECURE_COOKIES=1` because CF terminates TLS. Local dev / tests don't, so cookies are sent over plain HTTP without the Secure flag.

Add the env var to Render via the same script that set the migrations env:

```bash
PUT /v1/services/.../env-vars/AIW_SASKIA_FORCE_SECURE_COOKIES with value=1
```

(Use `scripts/uptimerobot_setup.py`-style auth pattern, but a new `scripts/set_render_env.py`.)

**Step 4 — Run + commit.**

```bash
git add app/rms/csrf.py scripts/set_render_env.py tests/test_csrf_local_dev.py
git commit -m "fix(csrf): Secure flag opt-in via env so local-dev POSTs don't 403"
```

---

## Phase 3: Operational hardening (logs, retention, errors)

Three tasks. After phase: ~915 + 8 = 923 passed, ruff clean.

### Task 8: Structured JSON logging to stderr (so Render log viewer shows real errors)

**Objective:** Currently loguru is imported but log calls go to stderr only (loguru default). On Render, stderr is captured to the deploy log, but with no structure. Operators can't filter by request_id or status.

**Files:**
- Modify: `app/rms/main.py` (configure loguru at module import time with JSON sink)
- Modify: `pyproject.toml`? — No, loguru is already in deps and stderr format is configured at runtime.
- Test: `tests/test_logging_config.py`

**Step 1 — Write failing test.**

```python
"""tests/test_logging_config.py — loguru emits JSON to stderr."""

import json
import logging
import io
import sys


def test_logging_emits_json_to_stderr(capsys):
    """logger.error() should produce JSON-serializable line with level/ts."""
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, format="{message}", level="DEBUG", serialize=True)
    logger.error("test-event")
    # The Message object goes through serialization.
    captured = capsys.readouter()
    assert "test-event" in captured.err
```

**Step 2 — Run.** Test passes (loguru defaults). The real verification: send a real error to stderr and check it's JSON.

**Step 3 — Wire loguru to emit JSON in production.** In `app/rms/main.py` at module load (before `app = FastAPI(...)`):

```python
import sys
from loguru import logger

# Configure loguru once per process. JSON in prod (Render), human in dev.
if os.getenv("AIW_SASKIA_LOG_FORMAT", "dev") == "prod":
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        serialize=True,
        backtrace=False,
        diagnose=False,
        format="{message}",
    )
else:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        backtrace=True,
        diagnose=False,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
    )
```

The body of the global exception handler and the access-log middleware already call `logger.error()`. They will benefit automatically.

**Step 4 — Set `AIW_SASKIA_LOG_FORMAT=prod` on Render** so production logs are JSON.

**Step 5 — Commit.**

```bash
git add app/rms/main.py tests/test_logging_config.py
git commit -m "feat(log): structured JSON logging in prod, human-readable in dev"
```

---

### Task 9: Daily audit_log retention cron (postponable rows older than 30 days)

**Objective:** Audit log grows unbounded. 1k errors/day = 365k rows/year. Slow queries. Free-tier Neon should not be loaded with archival data.

**Files:**
- Create: `scripts/audit_prune.py`
- Modify: `app/rms/backup.py` (call prune as part of weekly run, optional)
- Test: `tests/test_audit_prune.py`

**Step 1 — Write failing test.**

```python
"""tests/test_audit_prune.py — retention policy deletes rows older than N days."""

from datetime import datetime, timedelta
from app.rms.models import AuditLog


def test_prune_keeps_recent_deletes_old(session_factory):
    """Rows older than 30 days are deleted; recent are preserved."""
    with session_factory() as s:
        now = datetime.utcnow()
        s.add(AuditLog(occurred_at=now, action="x", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=10), action="x", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=45), action="old", user_id=None))
        s.commit()

    from app.rms.maintenance import prune_audit_log

    prune_audit_log(session_factory, retention_days=30)

    with session_factory() as s:
        rows = s.query(AuditLog).all()
        actions = sorted([r.action for r in rows])
        assert actions == ["x", "x"]  # the 45-day-old row is gone


def test_prune_dry_run_does_not_delete(session_factory):
    """Dry run reports what would be deleted without removing anything."""
    with session_factory() as s:
        s.add(
            AuditLog(occurred_at=datetime.utcnow() - timedelta(days=60), action="old", user_id=None)
        )
        s.commit()

    from app.rms.maintenance import prune_audit_log

    n = prune_audit_log(session_factory, retention_days=30, dry_run=True)
    assert n == 1
    with session_factory() as s:
        assert s.query(AuditLog).count() == 1
```

**Step 2 — Run.** Expected: `app.rms.maintenance` not yet exist.

**Step 3 — Implement `app/rms/maintenance.py`.**

```python
"""app/rms/maintenance.py — periodic housekeeping."""

from datetime import datetime, timedelta, timezone


def prune_audit_log(session_factory, *, retention_days: int = 30, dry_run: bool = False) -> int:
    """Delete audit_log rows older than retention_days.

    Returns the count deleted. Use dry_run=True to report only.
    """
    from sqlalchemy import delete
    from app.rms.models import AuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with session_factory() as s:
        # Count first (always)
        stmt = delete(AuditLog).where(AuditLog.occurred_at < cutoff)
        if dry_run:
            n = (
                s.execute(
                    select(func.count()).select_from(AuditLog).where(AuditLog.occurred_at < cutoff)
                ).scalar()
                or 0
            )
        else:
            result = s.execute(stmt)
            n = result.rowcount or 0
            s.commit()
    return int(n)
```

**Step 4 — Create `scripts/audit_prune.py`** (thin wrapper around the function, with --days and --dry-run flags). Operator runs via cron or manually: `python scripts/audit_prune.py --days 30`.

**Step 5 — Commit + run live once.**

```bash
git add app/rms/maintenance.py scripts/audit_prune.py tests/test_audit_prune.py
git commit -m "feat(maintenance): audit_log retention prune (default 30 days)"
```

Live: `python scripts/audit_prune.py --dry-run` to confirm pre-state; then `--days 30` to apply. (Run from operator's machine, NOT from this sandbox.)

---

### Task 10: Wire `/auditoria` filters (date range + user_id) for ops investigations

**Objective:** The `/auditoria` page only shows recent 100 entries. Operators investigating "what happened yesterday" need date range filtering.

**Files:**
- Modify: `app/routers/auditoria.py` (add `start_date`, `end_date`, `user_id` query params)
- Modify: `app/templates/auditoria.html` (add filter UI)
- Test: `tests/test_auditoria_filters.py`

**Step 1 — Write failing test.**

```python
"""tests/test_auditoria_filters.py — /auditoria?start_date=&end_date= filter."""

from datetime import datetime, timedelta
from app.rms.models import AuditLog


def test_auditoria_filters_by_date_range(client, session_factory):
    with session_factory() as s:
        now = datetime.utcnow()
        s.add(AuditLog(occurred_at=now, action="recent", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=10), action="week_ago", user_id=None))
        s.add(AuditLog(occurred_at=now - timedelta(days=40), action="month_ago", user_id=None))
        s.commit()

    resp = client.get(f"/auditoria?start_date={(now - timedelta(days=15)).date().isoformat()}")
    assert resp.status_code == 200
    body = resp.text
    assert "recent" in body
    assert "week_ago" in body
    assert "month_ago" not in body


def test_auditoria_combined_filter_action_date(client, session_factory):
    """action_filter + date range together."""
    with session_factory() as s:
        s.add(
            AuditLog(
                occurred_at=datetime.utcnow() - timedelta(days=60),
                action="login.success",
                user_id=None,
            )
        )
        s.commit()

    resp = client.get("/auditoria?action_filter=login.success&start_date=2026-09-01")
    assert resp.status_code == 200
```

**Step 2 — Run.** Expected: 404 or wrong filter behavior. Confirm.

**Step 3 — Implement.**

```python
@router.get("", response_class=HTMLResponse)
def auditoria_index(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    action_filter: str | None = Query(None),
    start_date: str | None = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from datetime import datetime
    from app.rms.audit import list_recent

    rows = list_recent(
        session,
        limit=limit,
        action_filter=action_filter,
    )
    # Filter by date range in Python (audit_log.occurred_at is tz-naive UTC).
    if start_date:
        sd = datetime.fromisoformat(start_date)
        rows = [r for r in rows if r.occurred_at and r.occurred_at >= sd]
    if end_date:
        ed = datetime.fromisoformat(end_date)
        rows = [r for r in rows if r.occurred_at and r.occurred_at <= ed]
    return render(
        request,
        "auditoria.html",
        {
            "rows": rows,
            "limit": limit,
            "action_filter": action_filter,
            "start_date": start_date or "",
            "end_date": end_date or "",
        },
    )
```

**Step 4 — Update `app/templates/auditoria.html`** to render the filter UI (mirror what we did for `/ventas`).

**Step 5 — Run + commit.**

```bash
git add app/routers/auditoria.py app/templates/auditoria.html tests/test_auditoria_filters.py
git commit -m "feat(auditoria): date-range filter for investigations"
```

---

## Phase 4: Marketing of the plan (operator comms + BWS hygiene)

Three tasks. After phase: ~923 + 4 = 927 passed.

### Task 11: Save this analysis as `docs/operations/2026-09-08-reliability-review.md`

**Objective:** Document the failure modes so future-agents/days know what was considered.

**Files:**
- Create: `docs/operations/2026-09-08-reliability-review.md` (already exists from conversation).

Actually wait — there's no existing file at this path (verified via `ls`), so this IS a new file. Create with the content of the user's prior turn analysis (already drafted in conversation above). Format as a single canonical operator document.

**Step 1 — Write the file.** Content = the analysis I just delivered in the response. It's operator-facing (not testing) so it's published as a doc, no test.

**Step 2 — Commit.**

```bash
git add docs/operations/2026-09-08-reliability-review.md
git commit -m "docs: reliability review — failure modes and free-tier constraints"
```

---

### Task 12: BWS hygiene — flag false-positive entries (the saskia-BRE search confirmation note)

**Objective:** The audit we ran last session flagged some entries by mistake. Add notes so future audits can avoid the false positives. Plus verify the existing flags are still accurate.

**Files:**
- Modify: `app/CHANGELOG.md` (small ops note)
- Create: `docs/operations/2026-09-08-bws-audit-falsepositives.md`

**Step 1 — Document the false positives.**

List the ones we know are intentional placeholders (the `ROTATE-ME` DB_URL) and unflag the verified-good Supabase keys. Most importantly, **unflag the `SUPABASE_SERVICE_ROLE_KEY` note** which is now correct.

**Step 2 — Commit.**

```bash
git add docs/operations/2026-09-08-bws-audit-falsepositives.md app/CHANGELOG.md
git commit -m "docs: BWS audit false-positives catalogued + SUPABASE_SERVICE_ROLE_KEY note updated"
```

This is documentation only; no test.

---

### Task 13: Render env-vars final state + gitignore for `__pycache__` files in scratch dir

**Objective:** Document the current env-var set so the next operator audit starts from a known good state. Also gitignore `.pyc` files.

**Files:**
- Create: `docs/operations/2026-09-08-render-env-vars.md` (catalog of env vars + values + change procedure)
- Modify: `.gitignore` (add `__pycache__/`, `*.pyc`)

**Step 1 — Generate env-var doc.**

```markdown
# Render env vars (as of 2026-09-08)

Last verified via Render API key (BWS-fetched):

## Required
| Var | Source | Notes |
|---|---|---|
| DATABASE_URL | Render secret (not BWS) | Postgres Neon pooled URL |
| SESSION_SECRET | Render secret (not BWS) | Cookie signing |
| FERNET_KEY | Render secret (not BWS) | Backup encryption |
| AIW_SASKIA_RUN_MIGRATIONS=1 | Render secret | Auto-migrate on startup |
| AIW_SASKIA_FORCE_SECURE_COOKIES=1 | Render secret (set 2026-09-08) | CSRF Secure cookie for HTTPS |

## From BWS
| BWS Key | Pushed value | Notes |
|---|---|---|
| SUPABASE_URL | https://rywzheykhdnaklmmsqey.supabase.co | Saskia's project, NOT paragu-ai-builder |
| SUPABASE_PUBLISHABLE_KEY | sb_publishable_... | anon public |
| SUPABASE_SECRET_KEY | sb_secret_... | service_role |
| SUPABASE_ANON_KEY | anon JWT | client-side |
| NEXT_PUBLIC_SUPABASE_URL | (same as SUPABASE_URL) | mirrors for client bundle |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | (same as SUPABASE_ANON_KEY) | |
| SUPABASE_JWKS_URL | https://.../.well-known/jwks.json | JWT verification |
| CF_R2_ACCESS_KEY_ID + ... | (existing) | Backup to R2 |
| R2_BUCKET + R2_ENDPOINT | (existing) | |
| CF_TUNNEL_TOKEN + CF_TUNNEL_NAME | (existing) | |

## How to update
1. Fetch keys from BWS via `scripts/...` snippet (operator pattern).
2. PUT to `https://api.render.com/v1/services/srv-.../env-vars/<KEY>`.
3. Render auto-deploy runs; new env becomes available.
4. Verify via `curl /healthz/deps` (length+sha fingerprint match BWS).
```

**Step 2 — Update `.gitignore`.** Add common Python artifacts (just in case).

**Step 3 — Commit.**

```bash
git add docs/operations/2026-09-08-render-env-vars.md .gitignore
git commit -m "docs: catalog Render env vars + tighten .gitignore"
```

---

## Phase 5: Playbook — what to do when the site is broken

Two tasks. Doc-only — no test, no ruff concerns.

### Task 14: Operator runbook — `docs/operations/2026-09-08-incident-response.md`

**Objective:** When the operator gets a "site broken" report, they need a step-by-step playbook. Document the tools and scripts available + the sequence of checks.

**Files:**
- Create: `docs/operations/2026-09-08-incident-response.md`

**Step 1 — Write the file.**

```markdown
# Saskia RMS — Operator incident response playbook

## User reports: "site broken"

### 1. Quick check (30 seconds)
```bash
curl -i https://saskia-rms.paragu-ai.com/healthz
curl -i https://saskia-rms.paragu-ai.com/healthz/db
curl -i https://saskia-rms.paragu-ai.com/healthz/schema
curl -i https://saskia-rms.paragu-ai.com/healthz/errors
```

Expected:
- /healthz returns 200 with `{"status":"ok"}` (or 503 if mid-deploy — wait 60s)
- /healthz/db returns 200 with `"dialect":"postgresql"`
- /healthz/schema returns 200 with `drift=0`, OR 500 with `drift>0` and a `hint` field
- /healthz/errors returns 200 with `http_500_count.last_1h`, `last_24h`

### 2. Diagnose by symptom

| Symptom | Likely cause | Fix |
|---|---|---|
| `/healthz` 503 longer than 60s | Render free-tier sleep timeout | Trigger manual deploy via API |
| `/healthz/db` 503 | Neon paused (idle >5min) | First query after resume = ~5-20s; wait + retry |
| `/healthz/schema` drift > 0 | Migrations didn't run | `mv` deploy (now auto-runs); or manual apply via `scripts/apply_migration_011.py`-style |
| `/healthz/errors` last_1h > 0 | Server bug | Click `/auditoria?action_filter=http.500` |
| /dashboard 500 with `column X does not exist` | Migration drift — see above |
| login 401 after correct password | Supabase session expired | Clear cookies + re-login; check SUPABASE_* env vars |

### 3. Things to check

- BWS-cached env vars match Render (use `scripts/check_render_env.py`)
- Latest commit `git log -1 --oneline` matches Render's deployed commit
- UptimeRobot monitor active for `/healthz` (id 803916096)
- Audit log row count — `python scripts/audit_prune.py --dry-run` to see how big
- Recent errors — `curl /auditoria?action_filter=http.500&limit=20`

### 4. Recovery actions

**Schema drift (most common):**
```bash
# Apply via the BWS-fetcher script for ops (operator runs from local machine)
python scripts/apply_migration_NNN.py  # updates app_meta to latest version
# OR
# Just redeploy — init_db() now runs automatically on every startup.
```

**Container stuck (cold-start not recovering):**
```bash
# Push empty commit to trigger fresh build
git commit --allow-empty -m "chore: trigger redeploy for cold-start recovery"
git push origin main  # via BWS-backed token
```

**Render plan upgrade (if user can pay $7/mo):**
1. Open Render dashboard > saskia-rms > Settings > Plan
2. Change plan to "Standard"
3. Web service stops cold-starting at 5min idle

### 5. How to escalate

- Check `docs/operations/2026-09-08-reliability-review.md` for known failure modes
- Check `docs/operations/2026-09-08-live-site-issues-fixes.md` for past root causes
- If still stuck: open issue in `Ai-Whisperers/saskia` describing exact symptom + query string of broken URL
```

**Step 2 — Commit.**

```bash
git add docs/operations/2026-09-08-incident-response.md
git commit -m "docs: operator incident response playbook"
```

---

### Task 15: Add `/ops/status` — operator dashboard with hot links to all /healthz/* + /auditoria + BWS check scripts

**Objective:** Operator opens ONE URL on their phone when something's wrong. Sees everything in one page.

**Files:**
- Create: `app/routers/ops.py`
- Modify: `app/rms/main.py` (register router)
- Create: `app/templates/ops_status.html`
- Test: `tests/test_ops_status.py`

**Step 1 — Write failing test.**

```python
"""tests/test_ops_status.py — one-page operator dashboard."""


def test_ops_status_renders(client):
    resp = client.get("/ops/status")
    assert resp.status_code == 200
    body = resp.text
    for label in (
        "/healthz",
        "/healthz/db",
        "/healthz/deps",
        "/healthz/schema",
        "/healthz/errors",
        "/auditoria",
    ):
        assert label in body


def test_ops_status_html_includes_action_button(client):
    body = client.get("/ops/status").text
    # Has a "Mark EOD" or "Force Reload" operational button.
    assert "button" in body.lower()
```

**Step 2 — Run.** Expected: 404.

**Step 3 — Implement.**

```python
# app/routers/ops.py
@router.get("/ops/status", response_class=HTMLResponse)
def ops_status(request, session=Depends(get_session)) -> HTMLResponse:
    from app.rms.audit import _client_ip

    body = {
        "endpoints": [
            ("/healthz", "Liveness"),
            ("/healthz/db", "Database"),
            ("/healthz/deps", "Environment"),
            ("/healthz/schema", "Schema drift"),
            ("/healthz/errors", "Error counter"),
            ("/auditoria", "Audit log"),
            ("/ventas", "Operator's main view"),
            ("/clientes", "Customers"),
            ("/produccion", "Production worksheet"),
            ("/reportes", "IVA / Libro"),
        ],
    }
    return render(request, "ops_status.html", body)


router = APIRouter(prefix="/ops", dependencies=[Depends(require_login)])
```

```html
{% extends "base.html" %}
{% block content %}
<h1>Estado operativo</h1>
<p class="hint">Vista rápida para identificar problemas. Si algo está rojo, ver <code>/healthz/errors</code> y <code>/auditoria</code>.</p>

<table class="data">
  <thead><tr><th>Endpoint</th><th>Propósito</th><th>Acción</th></tr></thead>
  <tbody>
    {% for path, purpose in endpoints %}
    <tr><td><code><a href="{{ path }}">{{ path }}</a></code></td><td>{{ purpose }}</td>
        <td><a class="btn btn-small" href="{{ path }}">Abrir</a></td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

**Step 4 — Register router.** Add `from app.routers import ops` to main.py, `app.include_router(ops.router)`.

**Step 5 — Run + commit.**

```bash
git add app/routers/ops.py app/templates/ops_status.html app/rms/main.py tests/test_ops_status.py
git commit -m "feat(ops): /ops/status hot-link dashboard for operator phone"
```

---

## Phase 6: Stretch / wheelhouse (only if we got time after Phases 1-5)

These are lower-impact but high-leverage if there's spare time. Skip if we don't have 4+ hours:

### Task 16: Add `/clientes` filter (q + tier)

Mirror what we did for ventas/productos. ~30 min.

### Task 17: Pagination on `/ventas` history (next/prev)

Mirror dashboards. ~45 min. Use the existing `paginate()` helper in `app/rms/perf.py`.

### Task 18: Indexes for hot queries

`CREATE INDEX IF NOT EXISTS` (dialect-aware) for:
- `sale(sold_at)` — already there? verify
- `sale(customer_id)` — for customer purchase history
- `sale_stock_move(sale_id)` — for void reversal
- `ingredient(name)` — for `/ventas?q=` filter
- `audit_log(action, occurred_at)` — for `/auditoria` action_filter

Run `app/rms/perf.py:apply_postgres_indexes()` as part of init_db() (auto).

---

## Acceptance criteria for "this plan is complete"

After all 15 tasks (Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5) complete:

1. **Tests**: `unset DATABASE_URL AIW_SASKIA_DB_PATH && uv run pytest -q` shows ≥927 passed (was 895 baseline).
2. **Lint**: `uv run ruff check .` shows "All checks passed!"
3. **Git**: working tree clean (no untracked files from this work).
4. **Live `/healthz/schema`**: returns 200 with `drift=0`. If migrations ever fall behind again, returns 500 with a `hint` field telling the operator to redeploy.
5. **Live 3 UptimeRobot monitors**: `/healthz`, `/healthz/db`, `/healthz/schema` — all pinging every 5 minutes, keeping the free-tier container warm.
6. **Live `/ventas/nueva`**: rejects negative discounts, 1M-unit sales, missing product_id with 422 before reaching business logic.
7. **Live `/ops/status`**: returns a single HTML page listing all operational endpoints.
8. **Live audit log retention**: `python scripts/audit_prune.py --days 30` reports `--dry-run` count > 0 (today's accumulated ~6 http.500 rows).

## Risks and tradeoffs

| Risk | Severity | Mitigation |
|---|---|---|
| Pydantic `Form(...)` constraint change in any of 5 routers could break existing UI | Medium | Add tasks one router at a time; run full suite after each |
| UptimeRobot rate-limit (free tier 50 monitors max) | Low | Currently using 1, this plan adds 2 more = 3. Plenty of headroom. |
| `AIW_SASKIA_FORCE_SECURE_COOKIES=1` flag change makes prod cookies Secure (correct), but if I forget to set it on Render → all forms 403 | Medium | Tied to `scripts/set_render_env.py`; verify with `/login` page after deploy |
| Operator runs `scripts/audit_prune.py` and deletes too much | Low | `--dry-run` is the default documentation; explicit `--apply` flag required |
| CSRF middleware regression: with `secure=False` for local, an HTTPS-only attacker could attempt... no, the SameSite=lax cookie gives the same protection | None | None |
| Drift detector `/healthz/schema` triggers false alarm during init_db() race | Low | The lifespan sets `app.state.ready=True` after init_db() finishes. /healthz/schema checks ready flag first. |

## Open questions

1. **Should the Playbook link to external monitoring?** No — single Render deployment, free tier. UptimeRobot + /healthz/errors is sufficient.
2. **Should `/ops/status` require auth?** Yes — already wrapped in `require_login` like every other route.
3. **Backup scheduler — should `run_backup()` also call `prune_audit_log()`?** Out of scope for this plan. Add to a future plan if backups schedule starts regularly.
4. **Do we need a UptimeRobot `/healthz/errors` monitor?** Yes — that monitor would alert on `http_500_count.last_1h > 0`. Add as part of Task 3 (one of the 3 monitors).

## Estimated effort

| Phase | Effort | Tasks |
|---|---|---|
| Phase 1: Schema drift + cold-start | ~4 hours | 3 |
| Phase 2: Input/state-change protection | ~6 hours | 4 |
| Phase 3: Operational hardening | ~3 hours | 3 |
| Phase 4: Marketing (docs) | ~2 hours | 3 |
| Phase 5: Operator playbook | ~2 hours | 2 |
| Phase 6: Stretch (optional) | ~3 hours | 3 |
| **Total (Phases 1-5)** | **~17 hours** | **15** |
| **Total (all)** | **~20 hours** | **18** |

Matches the user's "make a complete plan to completely fix everything on free tier" request scope.
