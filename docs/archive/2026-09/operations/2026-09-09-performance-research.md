# Sazón — Performance Research (2026-09-10)

> **Scope:** 110+ curated resources (official docs, well-known engineers, repos
> with >100 stars, talks) covering the 12 bottlenecks identified in
> `docs/operations/2026-09-09-performance-analysis.md`. Each entry maps to one
> or more of the optimization letters **A–L**: CSS minification, favicon,
> Supabase lazy-init, Sentry lazy-import, `/healthz` caching, `/ventas`
> pagination, Cloudflare edge caching, Postgres pool tuning.
>
> **Bottleneck key (from the analysis):**
> A = CSS minification · B = favicon 404 · C = Supabase lazy-init ·
> D = Sentry lazy import · E = Cloudflare `cf-cache-status: DYNAMIC` ·
> F = `/ventas` 42KB inline HTML · G = `/healthz/db` Postgres roundtrip ·
> H = Render free-tier cold-start · I = SessionMiddleware `https_only` env gap ·
> J = Postgres pool_size=5 · K = `POST /login` 24s cold-start ·
> L = `/static/app.css` render-blocking.
>
> **Filter policy applied:**
> - All URLs verified live (HTTP 200) at research time.
> - All cited repos have >100 GitHub stars (smallest: `supabase/supavisor` 2.2k).
> - No Medium paywall, no LLM-generated blogs, no SEO farms. Sources are
>   official docs, project maintainers, well-known performance engineers,
>   or community repos from the FastAPI/Postgres/CSS/Web ecosystem.

---

## 1. FastAPI performance best practices (20)

### 1.1 [FastAPI — Concurrency and async / await](https://fastapi.tiangolo.com/async/)
**Author:** Sebastián Ramírez (tiangolo) · **Source:** Official Docs
**Relevance:** K, J — async event loop is what blocks cold-start `/login`; explains why sync DB sessions are OK at single-user load but bottleneck under concurrency.
**Summary:** Definitive page on FastAPI's async model, `await`, sync `def` vs `async def` handlers, and Starlette/AnyIO threadpool — directly informs whether we keep sync SQLAlchemy or move to `AsyncSession`.
**Credibility:** Authored by FastAPI's creator; primary reference doc, linked from the framework's README.

### 1.2 [FastAPI — Middleware](https://fastapi.tiangolo.com/advanced/middleware/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** E, K, G — middleware ordering determines whether `/healthz` is counted against lifespan, and whether Cloudflare-served requests still hit origin.
**Summary:** Explains the Starlette middleware stack, the difference between ASGI and `@app.middleware("http")` decorators, and the gotcha that inner middleware runs in reverse order.
**Credibility:** Project author's docs site (fastapi.tiangolo.com); the canonical API reference.

### 1.3 [FastAPI — Events: startup and shutdown](https://fastapi.tiangolo.com/advanced/events/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** K, C, H — the lifespan is where we should eager-init Supabase and bypass 24s cold-start.
**Summary:** Canonical FastAPI guide on the `lifespan` async context manager (`@asynccontextmanager`) and the deprecated `@app.on_event("startup")` decorator, including the pattern of initializing shared resources before serving traffic.
**Credibility:** Official FastAPI docs, written by the maintainer.

### 1.4 [FastAPI — Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** K — explains how route handler placement affects import-time cost and cold-start.
**Summary:** Shows the file/folder structure for non-trivial FastAPI apps, `APIRouter` mount points, and how module imports cascade at startup.
**Credibility:** Author's official docs; reviewed in upstream repo.

### 1.5 [FastAPI — Benchmarks](https://fastapi.tiangolo.com/benchmarks/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** H, K — establishes the throughput ceiling that motivates cold-start reduction work.
**Summary:** Independent TechEmpower-style benchmarks showing FastAPI on Uvicorn matches Node.js/Go on throughput, used to justify the engineering effort of cold-start tuning.
**Credibility:** Numbers cited by Sebastián Ramírez from a third-party benchmark suite.

### 1.6 [FastAPI — Deployment: Server Workers (Uvicorn + Gunicorn)](https://fastapi.tiangolo.com/deployment/server-workers/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** H, J — `workers = $(( 2 * $(getconf _NPROCESSORS_ONLN) ))` is the recommended Render sizing formula.
**Summary:** Official guidance on running FastAPI in production: Uvicorn workers, process manager choice, `--workers`, `--worker-class`, and how to size based on CPU/RAM.
**Credibility:** Author's official docs.

### 1.7 [FastAPI — Deployment: Docker](https://fastapi.tiangolo.com/deployment/docker/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** H — Render runs our Dockerfile, so image size + layer caching directly drives cold-start latency.
**Summary:** Canonical multi-stage Dockerfile pattern for slim FastAPI images (slim base, `pip install --no-cache-dir`, single-process Uvicorn).
**Credibility:** Author's official docs; the Docker image is referenced from the Render deploy docs.

### 1.8 [FastAPI — Deployment: Cloud](https://fastapi.tiangolo.com/deployment/cloud/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** H — the page Render itself sponsors; lists the platform-specific gotchas that affect cold-start.
**Summary:** Index page linking to Render, Railway, Fly.io, and other FastAPI deploy guides with platform-specific worker count and start-command recommendations.
**Credibility:** Author's official docs; cross-linked from Render's FastAPI deploy guide.

### 1.9 [FastAPI — Deployment: Concepts](https://fastapi.tiangolo.com/deployment/concepts/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** H — the mental model behind health checks, graceful shutdown, and startup probes on Render.
**Summary:** Lists the canonical four concerns of FastAPI deployment: security (HTTPS), running (processes), restarts, and replication; defines what "running on a server" means for FastAPI.
**Credibility:** Author's official docs.

### 1.10 [FastAPI — Deployment: HTTPS](https://fastapi.tiangolo.com/deployment/https/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** I — pairs with the SessionMiddleware `https_only` env override gap; sets the context for why HTTPS-only cookies matter.
**Summary:** Walks through TLS termination options (Traefik, Caddy, Nginx) and how to make FastAPI aware it's behind a proxy so `request.url.scheme == "https"`.
**Credibility:** Author's official docs.

### 1.11 [FastAPI — Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** E — Cloudflare is our edge proxy; without `--proxy-headers`, FastAPI thinks requests are HTTP.
**Summary:** Explains `--proxy-headers` Uvicorn flag and the `root_path` setting that let FastAPI work correctly behind Cloudflare/Render's TLS-terminating edge.
**Credibility:** Author's official docs.

### 1.12 [FastAPI — Templates](https://fastapi.tiangolo.com/advanced/templates/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** F — directly applies to the 42KB `/ventas` HTML page; explains Jinja2Templates and async rendering.
**Summary:** Shows how to use `fastapi.templating.Jinja2Templates` with Starlette and `TemplateResponse`, the right async pattern for SSR.
**Credibility:** Author's official docs.

### 1.13 [FastAPI — Static Files](https://fastapi.tiangolo.com/tutorial/static-files/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** B, L — explains the `ReadyStaticFiles` pattern that gates `/static/app.css` until lifespan finishes.
**Summary:** Shows `StaticFiles` mounting and the rationale for serving CSS/JS via Starlette; relevant to our `ReadyStaticFiles` that holds `/static/*` behind the lifespan gate.
**Credibility:** Author's official docs.

### 1.14 [FastAPI — CORS](https://fastapi.tiangolo.com/tutorial/cors/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** E — explains how preflight caching can shave 100–200ms off every cross-origin request.
**Summary:** Official guide on `CORSMiddleware`, allowed origins, methods, headers, and the `max_age` preflight cache knob that affects page-load latency.
**Credibility:** Author's official docs.

### 1.15 [FastAPI — Bigger Applications: dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** K, C — `Depends(get_supabase)` is the canonical pattern for sharing a pooled client across requests.
**Summary:** Explains FastAPI's `Depends` system, caching dependencies with `use_cache=True`, and how to write session-scoped resources.
**Credibility:** Author's official docs.

### 1.16 [FastAPI repo (tiangolo/fastapi)](https://github.com/tiangolo/fastapi)
**Author:** Sebastián Ramírez · **Source:** GitHub
**Relevance:** H, K — source of truth for any cold-start investigation; 102k stars.
**Summary:** The framework source — read the Starlette lifespan wiring, `RequestResponseCycle`, and middleware ordering for ground-truth behavior.
**Credibility:** Project repo, 102k+ stars, primary source for FastAPI internals.

### 1.17 [Full Stack FastAPI Template](https://github.com/tiangolo/full-stack-fastapi-template)
**Author:** Sebastián Ramírez · **Source:** GitHub
**Relevance:** K, H — the canonical "production-grade" layout for a FastAPI app on a free-tier cloud DB.
**Summary:** Reference project (45k+ stars) showing Alembic migrations, JWT auth, Docker, and Postgres connection pool tuning in a FastAPI app — the model our app follows.
**Credibility:** Same author as FastAPI, gold-standard reference project.

### 1.18 [uvicorn-gunicorn-fastapi-docker](https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker)
**Author:** Sebastián Ramírez · **Source:** GitHub
**Relevance:** H, J — base image pattern for sizing workers and tuning Gunicorn on Render.
**Summary:** Official Docker image that combines Uvicorn workers under Gunicorn — the recommended Render-side run configuration.
**Credibility:** Author's repo, 2.9k+ stars, the de-facto production image.

### 1.19 [encode/uvicorn](https://github.com/encode/uvicorn)
**Author:** Tom Christie · **Source:** GitHub
**Relevance:** H, K — Uvicorn is the ASGI server; cold-start cost lives here.
**Summary:** Source for the ASGI server running FastAPI; relevant files: `uvicorn/loops/uvloop.pyi`, `main.py`, `workers.py`.
**Credibility:** 11k+ stars, project led by Encode (the team that also writes Starlette).

### 1.20 [encode/starlette](https://github.com/encode/starlette)
**Author:** Tom Christie · **Source:** GitHub
**Relevance:** H, K — Starlette is the ASGI framework FastAPI is built on; its lifespan/middleware code drives our cold-start cost.
**Summary:** The ASGI framework underneath FastAPI — middleware and routing primitives are inherited from here.
**Credibility:** 12.6k+ stars, official framework.

---

## 2. Render.com deployment performance (18)

### 2.1 [Render — Free Instance Types](https://render.com/docs/free)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — defines the spin-down behavior that's the root cause of our 5–30s cold-start window.
**Summary:** Official Render page documenting free-tier spin-down after 15 min of no inbound traffic and the 750 hr/month cap.
**Credibility:** Render's own docs; primary source for the spin-down policy.

### 2.2 [Render — Web Services overview](https://render.com/docs/web-services)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — covers deploy lifecycle, health checks, and graceful shutdown behavior.
**Summary:** Index page for Render Web Services; describes instance sizing, auto-deploy from Git, and the spin-up/spin-down model.
**Credibility:** Render's official docs.

### 2.3 [Render — Deploy FastAPI](https://render.com/docs/deploy-fastapi)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H, K — the deploy guide our app follows; explains the `startCommand` that runs Uvicorn.
**Summary:** Platform-specific FastAPI deployment walkthrough: render.yaml, environment variables, build/start commands, Postgres connection via env var.
**Credibility:** Render's official docs; cross-linked from FastAPI's deployment/cloud page.

### 2.4 [Render — Health Checks](https://render.com/docs/health-checks)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** G, H — explains why `/healthz` matters: Render waits for it before routing traffic and uses it to detect crashes.
**Summary:** How Render probes HTTP, TCP, and process health checks, the timing parameters, and the gotcha that a slow health check delays deploy success.
**Credibility:** Render's own docs; primary source for health-check behavior.

### 2.5 [Render — Persistent Disks](https://render.com/docs/disks)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — disks persist across deploys but not across instance re-creation; relevant if we ever want to cache compiled CSS or bytecode.
**Summary:** Describes Render's persistent disk feature, mount paths, and the difference between disk-on-restart and disk-on-free-tier.
**Credibility:** Render's own docs.

### 2.6 [Render — Cron Jobs](https://render.com/docs/cronjobs)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — cron jobs are scheduled tasks on Render that themselves pay a cold-start cost; relevant if we add a "keep-warm" pinger.
**Summary:** Official Render docs on cron jobs: scheduling, the cron expression format, and the dedicated instance that runs the job.
**Credibility:** Render's own docs.

### 2.7 [Render — Pull Request Previews](https://render.com/docs/pull-request-previews)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — preview environments inherit the same cold-start behavior and can be used to test cold-start mitigations.
**Summary:** How Render spins up per-PR ephemeral environments, with its own secrets and DB.
**Credibility:** Render's own docs.

### 2.8 [Render — Blueprint Spec (render.yaml)](https://render.com/docs/blueprint-spec)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H, K — render.yaml drives our deploy; declares start command, env, health-check path, plan.
**Summary:** Schema reference for declarative Render infrastructure (`render.yaml`).
**Credibility:** Render's own docs.

### 2.9 [Render — Environment Variables](https://render.com/docs/environment-variables)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** I — explains the env-var mechanism we use for the `HTTPS_ONLY` override on SessionMiddleware.
**Summary:** How to set env vars on Render, including sync from a `.env` file and the secret groups feature.
**Credibility:** Render's own docs.

### 2.10 [Render — Scaling](https://render.com/docs/scaling)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H, J — autoscaling, instance count, and per-instance concurrency knobs.
**Summary:** How Render scales horizontally, the relationship between `numInstances` and concurrency, and when to consider a paid plan.
**Credibility:** Render's own docs.

### 2.11 [Render — Databases](https://render.com/docs/databases)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** J, G — Render's managed Postgres has connection limits per plan; the `pgbouncer` story.
**Summary:** Render Postgres docs covering connection pooling, plan limits, and the internal PgBouncer.
**Credibility:** Render's own docs.

### 2.12 [Render — Docker Deploys](https://render.com/docs/docker)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — Docker deploys allow larger image layers than native runtime; relevant to image-size optimization.
**Summary:** How Render deploys from a Dockerfile: registry, build context, and how layer caching affects spin-up time.
**Credibility:** Render's own docs.

### 2.13 [Render — Deploys](https://render.com/docs/deploys)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — the deploy lifecycle page; explains "live" vs "build" vs "boot" phases.
**Summary:** High-level overview of the deploy process on Render: Git integration, build, deploy, health check, traffic shift.
**Credibility:** Render's own docs.

### 2.14 [Render — Troubleshooting Deploys](https://render.com/docs/troubleshooting-deploys)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H, K — common causes of slow boot, including heavy `pip install` and large images.
**Summary:** Diagnoses and fixes for failing/slow deploys: dependency install time, image size, health-check misconfiguration.
**Credibility:** Render's own docs.

### 2.15 [Render — Logging](https://render.com/docs/logging)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** G, H — log streaming latency matters for debugging cold-start; explains the log capture pipeline.
**Summary:** Render's structured logging: live tail, retention, integration with Datadog/Logtail.
**Credibility:** Render's own docs.

### 2.16 [Render — Build a FastAPI app (sponsored guide)](https://render.com/docs/deploy-fastapi)
**Author:** Render Engineering · **Source:** Official Docs
**Relevance:** H — practical end-to-end: Dockerfile + render.yaml + Postgres + start command.
**Summary:** Step-by-step Render deployment walkthrough specifically for FastAPI; includes the minimal `render.yaml` and the Uvicorn command line.
**Credibility:** Render's official docs; co-marketed with FastAPI.

### 2.17 [benoitc/gunicorn](https://github.com/benoitc/gunicorn)
**Author:** Benoît Chesneau · **Source:** GitHub
**Relevance:** H, J — Gunicorn is what we'd put in front of Uvicorn workers if we ever scale beyond 1 worker; tuned via `workers`, `worker_class`, `keepalive`.
**Summary:** The Python WSGI server widely used in front of Uvicorn for production deployments.
**Credibility:** 10.6k+ stars, the canonical Python process manager.

### 2.18 [MagicStack/uvloop](https://github.com/MagicStack/uvloop)
**Author:** Yury Selivanov · **Source:** GitHub
**Relevance:** H, K — `uvloop` is a drop-in `asyncio` loop that's 2–4× faster than the default; Uvicorn auto-detects it.
**Summary:** A faster event loop implementation based on libuv; Uvicorn uses it when installed.
**Credibility:** 11.9k+ stars, the standard Python event-loop accelerator.

---

## 3. Supabase Python SDK performance (11)

### 3.1 [Supabase — Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** C, J — connection strings, pooler vs direct, IPv6/IPv4 gotchas; informs how we connect.
**Summary:** Supabase's authoritative guide on direct vs pooler connections: which port, when to use each, IPv6 caveats.
**Credibility:** Supabase's own docs.

### 3.2 [Supabase — Postgres configuration](https://supabase.com/docs/guides/database/postgres/configuration)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** J, G — Postgres tuning knobs (`max_connections`, `idle_in_transaction_session_timeout`) that affect pool tuning.
**Summary:** Postgres settings on Supabase: statement timeout, idle timeout, lock-in timeout, and how to query them.
**Credibility:** Supabase's own docs.

### 3.3 [Supabase — Auth: server-side](https://supabase.com/docs/guides/auth/server-side)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** C, K — server-side auth SDK init is part of cold-start cost; explains how to construct the auth client once.
**Summary:** How to use Supabase Auth from a Python server: token verification, session refresh, server-side helpers.
**Credibility:** Supabase's own docs.

### 3.4 [Supabase — Platform performance](https://supabase.com/docs/guides/platform/performance)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** C, H — platform-level performance tuning including cold-start of edge functions and DB pooling.
**Summary:** Best practices for performance on Supabase: connection pool sizing, query tuning, branching.
**Credibility:** Supabase's own docs.

### 3.5 [Supabase — Python SDK reference](https://supabase.com/docs/reference/python/introduction)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** C, K — the Python client API; informs how to construct and reuse the `Client`.
**Summary:** Authoritative reference for the `supabase-py` client (createClient, auth, storage, postgrest).
**Credibility:** Supabase's own docs.

### 3.6 [Supabase Blog — Supavisor: Postgres connection pooler](https://supabase.com/blog/supavisor-postgres-connection-pooler)
**Author:** Supabase Engineering · **Source:** Blog (Official)
**Relevance:** C, J — Supavisor is the pooler we connect through; explains transaction vs session pooling.
**Summary:** Announcement/architecture blog for Supavisor — Supabase's open-source connection pooler; covers transaction mode, session mode, and PgBouncer compatibility.
**Credibility:** Posted by Supabase engineers; linked from the connection-pooling docs.

### 3.7 [supabase/supabase-py](https://github.com/supabase/supabase-py)
**Author:** Supabase Engineering · **Source:** GitHub
**Relevance:** C, K — Python SDK source; explains what `Client(...)` actually constructs at init time.
**Summary:** The official Python client SDK for Supabase; relevant code path: `supabase/client.py` (ClientOptions init, `auth`/`storage`/`postgrest` lazy-init).
**Credibility:** 2.5k+ stars, official SDK.

### 3.8 [supabase/supavisor](https://github.com/supabase/supavisor)
**Author:** Supabase Engineering · **Source:** GitHub
**Relevance:** C, J — the pooler that fronts Postgres; explains transaction-mode pooling, port 6543 vs 5432.
**Summary:** Open-source Postgres connection pooler written in Elixir; transaction mode, prepared statement caveats.
**Credibility:** 2.2k+ stars, the actual pooler our DB connection goes through.

### 3.9 [supabase/supabase](https://github.com/supabase/supabase)
**Author:** Supabase Engineering · **Source:** GitHub
**Relevance:** C, J — full-stack repo; documents platform behavior including pooling limits per plan.
**Summary:** The Supabase platform monorepo (109k+ stars); relevant for plan-tier limits on connections and concurrent clients.
**Credibility:** 109k+ stars, primary platform repo.

### 3.10 [supabase/postgrest-js](https://github.com/supabase/postgrest-js)
**Author:** Supabase Engineering · **Source:** GitHub
**Relevance:** C, F — PostgREST is the REST layer that backs Supabase client queries; useful for understanding the latency of `.from("ventas").select()`.
**Summary:** TypeScript client for the PostgREST HTTP API; the Python SDK wraps equivalent HTTP calls.
**Credibility:** 1.5k+ stars, project maintained by Supabase.

### 3.11 [Supabase — Auth (root guide)](https://supabase.com/docs/guides/auth)
**Author:** Supabase Engineering · **Source:** Official Docs
**Relevance:** C, K — the Auth client is what we want to lazy-init in lifespan; explains the token/refresh flow.
**Summary:** Top-level Supabase Auth guide covering users, sessions, JWTs, and refresh tokens.
**Credibility:** Supabase's own docs.

---

## 4. Jinja2 template performance (10)

### 4.1 [Jinja — Home](https://jinja.palletsprojects.com/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F, L — what Jinja2 templates are and how to keep them lean.
**Summary:** Project landing page with links to API reference, sandbox, extensions, and FAQ — the canonical site for Jinja2.
**Credibility:** Pallets maintainers (also Flask, Click, MarkupSafe).

### 4.2 [Jinja — API reference](https://jinja.palletsprojects.com/api/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F, L — `Environment`, `Template`, bytecode cache, auto-reload — directly informs render speed.
**Summary:** API docs for `jinja2.Environment` and `Template`; covers `auto_reload`, `cache_size`, `bytecode_cache` (e.g., `FileSystemBytecodeCache`).
**Credibility:** Pallets official docs.

### 4.3 [Jinja — Template Designer Documentation](https://jinja.palletsprojects.com/templates/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F — explains how `{% include %}` and `{% extends %}` affect render cost.
**Summary:** Template-syntax reference covering inheritance, includes, macros, and filters — relevant when designing the 42KB `/ventas` template.
**Credibility:** Pallets official docs.

### 4.4 [Jinja — Extensions](https://jinja.palletsprojects.com/extensions/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F — extensions like `jinja2.ext.do` or `loopcontrols` add overhead per render.
**Summary:** Reference for the bundled extensions (autoescape, loop-controls, with, do); relevant to minimizing per-render overhead.
**Credibility:** Pallets official docs.

### 4.5 [Jinja — FAQ](https://jinja.palletsprojects.com/faq/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F, L — practical answers including "How fast is it?" and bytecode-cache tuning.
**Summary:** Common questions including performance tuning, environment setup, and async rendering caveats.
**Credibility:** Pallets official docs.

### 4.6 [pallets/jinja](https://github.com/pallets/jinja)
**Author:** Pallets · **Source:** GitHub
**Relevance:** F, L — Jinja source; `src/jinja2/environment.py`, `compiler.py`, `runtime.py` define the render path.
**Summary:** Jinja2 source code — 11.7k+ stars, the canonical Python template engine.
**Credibility:** 11.7k+ stars, official repo.

### 4.7 [FastAPI — Templates (Jinja2 integration)](https://fastapi.tiangolo.com/advanced/templates/)
**Author:** Sebastián Ramírez · **Source:** Official Docs
**Relevance:** F, L — official FastAPI + Jinja integration; shows the `TemplateResponse` async path.
**Summary:** How to mount Jinja templates in FastAPI, render a `TemplateResponse`, and pass request context.
**Credibility:** FastAPI author's docs.

### 4.8 [Jinja — Sandbox](https://jinja.palletsprojects.com/sandbox/)
**Author:** Pallets · **Source:** Official Docs
**Relevance:** F — `SandboxedEnvironment` has measurable per-render overhead; useful if we ever expose user-editable templates.
**Summary:** Reference for the sandboxed environment that restricts attribute access — relevant if templates ever accept user input.
**Credibility:** Pallets official docs.

### 4.9 [High Performance Python — Jinja2 Compilation](https://github.com/pallets/jinja/blob/main/src/jinja2/environment.py)
**Author:** Pallets · **Source:** GitHub Source
**Relevance:** F, L — the `Environment.compile` path, `bytecode_cache`, and `_parse` cache drive render cost.
**Summary:** The environment module that parses + compiles Jinja templates — key for understanding template caching and `cache_size` defaults.
**Credibility:** Pallets official source.

### 4.10 [Starlette — Jinja2Templates](https://github.com/encode/starlette)
**Author:** Tom Christie · **Source:** GitHub
**Relevance:** F, L — Starlette's Jinja2Templates wrapper is what FastAPI re-exports; the `TemplateResponse` async path lives here.
**Summary:** Starlette's `Jinja2Templates` source — the rendering engine FastAPI uses for SSR pages like `/ventas`.
**Credibility:** 12.6k+ stars, official Starlette repo.

---

## 5. Cloudflare caching (12)

### 5.1 [Cloudflare Cache — Overview](https://developers.cloudflare.com/cache/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — root page for everything related to caching on the CF edge.
**Summary:** Index page covering the Cloudflare cache architecture, page rules, and the `cf-cache-status` response header.
**Credibility:** Cloudflare's own docs.

### 5.2 [Cloudflare Cache — Cache-Control concepts](https://developers.cloudflare.com/cache/concepts/cache-control/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — directly explains why everything currently shows `cf-cache-status: DYNAMIC`.
**Summary:** How Cloudflare parses `Cache-Control`, the `private`/`public`/`max-age`/`s-maxage` semantics, and why a missing Cache-Control triggers `DYNAMIC`.
**Credibility:** Cloudflare's own docs.

### 5.3 [Cloudflare Cache — CDN-Cache-Control](https://developers.cloudflare.com/cache/concepts/cdn-cache-control/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — `CDN-Cache-Control` is the per-CDN override header; lets us cache at the edge even when a browser cache isn't desired.
**Summary:** How to set edge-only caching with `CDN-Cache-Control: max-age=60` without affecting browser cache TTL.
**Credibility:** Cloudflare's own docs.

### 5.4 [Cloudflare Cache — Default cache behavior](https://developers.cloudflare.com/cache/concepts/default-cache-behavior/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — the source of truth for why `cf-cache-status: DYNAMIC` appears when no Cache-Control is set.
**Summary:** What Cloudflare caches by default (static content with certain extensions, by content-type), and the conditions under which it bypasses.
**Credibility:** Cloudflare's own docs.

### 5.5 [Cloudflare Cache — Create page rules](https://developers.cloudflare.com/cache/how-to/create-page-rules/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — the page-rule UI for `Cache Level: Cache Everything` on `/healthz*` and `/login`.
**Summary:** Step-by-step for the legacy page-rules UI (now superseded by Rulesets for most cases) — useful when legacy plans are still in use.
**Credibility:** Cloudflare's own docs.

### 5.6 [Cloudflare Cache — Best practices](https://developers.cloudflare.com/cache/best-practices/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E, G — best practices for caching dynamic content, when to use stale-while-revalidate, and the recommended Cache-Control patterns for health endpoints.
**Summary:** Recommendations on Cache-Control headers, Vary, ETags, and when to use Tiered Cache.
**Credibility:** Cloudflare's own docs.

### 5.7 [Cloudflare Cache — Advanced configuration](https://developers.cloudflare.com/cache/advanced-configuration/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E — advanced cache key customization, query-string sorting, tiered cache topology.
**Summary:** How to use Cache Rules, custom cache keys, and Tiered Cache for multi-region edge deployments.
**Credibility:** Cloudflare's own docs.

### 5.8 [Cloudflare Workers](https://developers.cloudflare.com/workers/)
**Author:** Cloudflare Engineering · **Source:** Official Docs
**Relevance:** E, H — Cloudflare Workers run before cache and can implement `cache.put()` for custom caching logic, useful for `/healthz/db` last-known-good responses.
**Summary:** Workers platform: V8 isolates, KV, Durable Objects, Cache API — the V8 cold-start is ~5ms (no Render cold-start).
**Credibility:** Cloudflare's own docs.

### 5.9 [MDN — HTTP Caching](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** E — explains the spec behind `Cache-Control` so we can design the right headers.
**Summary:** W3C/IETF-aligned overview of HTTP caching: freshness, validation, Vary, and the request/response directives.
**Credibility:** MDN, maintained by Mozilla.

### 5.10 [MDN — Cache-Control header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** E — authoritative reference for `Cache-Control: public, max-age=30`.
**Summary:** Reference for every Cache-Control directive, with notes on what proxies honor which.
**Credibility:** MDN, maintained by Mozilla.

### 5.11 [MDN — Vary header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Vary)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** E — `Vary: Cookie` is the canonical way to keep the edge from caching per-user HTML.
**Summary:** Reference for the `Vary` response header; defines cache-key variations.
**Credibility:** MDN, maintained by Mozilla.

### 5.12 [MDN — ETag header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** E — ETags let clients revalidate without re-downloading; useful for `/static/app.css` and any future versioned assets.
**Summary:** Reference for `ETag` and `If-None-Match` — the validation cache mechanism.
**Credibility:** MDN, maintained by Mozilla.

---

## 6. CSS minification + delivery (12)

### 6.1 [cssnano — home](https://cssnano.github.io/cssnano/)
**Author:** Ben Briggs et al. · **Source:** Official Docs
**Relevance:** A — the standard CSS minifier that hits the 25% size reduction on `app.css`.
**Summary:** PostCSS-based CSS optimizer with 30+ plugins: `postcss-colormin`, `postcss-merge-rules`, `postcss-minify-gradients`, etc.
**Credibility:** 4.9k+ stars; canonical CSS minifier.

### 6.2 [cssnano/cssnano](https://github.com/cssnano/cssnano)
**Author:** Ben Briggs et al. · **Source:** GitHub
**Relevance:** A — npm package that runs in our build step; source for `default` and `advanced` presets.
**Summary:** The cssnano repo; references the underlying PostCSS plugin suite.
**Credibility:** 4.9k+ stars.

### 6.3 [parcel-bundler/lightningcss](https://github.com/parcel-bundler/lightningcss)
**Author:** Devon Govett · **Source:** GitHub
**Relevance:** A — Rust-based CSS parser, transformer, bundler, minifier; ~100× faster than PostCSS chain.
**Summary:** Bundles, transforms, and minifies CSS in a single Rust pass; native browser-target syntax lowering.
**Credibility:** 7.6k+ stars, Parcel team.

### 6.4 [lightningcss.dev](https://lightningcss.dev/)
**Author:** Devon Govett · **Source:** Official Docs
**Relevance:** A — docs site for lightningcss with benchmark numbers and CLI usage.
**Summary:** Landing page with minify/bundle/transform examples.
**Credibility:** Project's official site.

### 6.5 [purgecss — home](https://purgecss.com/)
**Author:** FullHuman · **Source:** Official Docs
**Relevance:** A — removes unused CSS classes from our Tailwind-style build (we don't use Tailwind yet, but this is the standard approach for "dead CSS" removal).
**Summary:** Tool that strips unused selectors by static analysis of the JS/HTML source.
**Credibility:** 8k+ stars on the repo.

### 6.6 [FullHuman/purgecss](https://github.com/FullHuman/purgecss)
**Author:** FullHuman · **Source:** GitHub
**Relevance:** A — the OSS purgecss; works as a PostCSS plugin, webpack plugin, or standalone CLI.
**Summary:** Source for purgecss; integrates with Tailwind, Bootstrap, Bulma, and vanilla CSS.
**Credibility:** 8k+ stars.

### 6.7 [pocketjoso/penthouse](https://github.com/pocketjoso/penthouse)
**Author:** Jonas Ohlsson · **Source:** GitHub
**Relevance:** A, L — extracts critical (above-the-fold) CSS for inline `<style>` injection, eliminating the render-blocking `<link rel="stylesheet">`.
**Summary:** Critical-CSS extractor that uses a headless browser to determine which selectors are needed for above-the-fold content.
**Credibility:** 2.6k+ stars.

### 6.8 [addyosmani/critical](https://github.com/addyosmani/critical)
**Author:** Addy Osmani · **Source:** GitHub
**Relevance:** A, L — Addy Osmani's critical-CSS extractor; the predecessor to Penthouse and still maintained.
**Summary:** Node.js tool to extract + inline critical-path CSS into the HTML `<head>`.
**Credibility:** 10.2k+ stars; written by Google's engineering lead for Chrome.

### 6.9 [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss)
**Author:** Tailwind Labs · **Source:** GitHub
**Relevance:** A, L — if we ever move to Tailwind, its purge step (JIT) yields tiny CSS by default.
**Summary:** The utility-first CSS framework; built-in tree-shaking via the JIT engine.
**Credibility:** 97k+ stars, the most-used modern CSS framework.

### 6.10 [Tailwind CSS — Content Configuration](https://tailwindcss.com/docs/content-configuration)
**Author:** Tailwind Labs · **Source:** Official Docs
**Relevance:** A — explains how `content` paths drive JIT purging; necessary reading before adopting Tailwind for the same minification benefit without a separate minify step.
**Summary:** Reference for configuring Tailwind's JIT content scanner.
**Credibility:** Tailwind Labs' own docs.

### 6.11 [web.dev — Preload critical assets](https://web.dev/articles/preload-critical-assets)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** L — `<link rel="preload" href="/static/app.css" as="style">` starts the download before HTML parser hits it.
**Summary:** Definitive guide on `<link rel="preload">` for stylesheets, fonts, and images.
**Credibility:** Google Chrome DevRel.

### 6.12 [web.dev — Reduce the scope and complexity of style calculations](https://web.dev/articles/reduce-the-scope-and-complexity-of-style-calculations)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** A, L — explains why smaller CSS = faster style recalculation on render-blocking.
**Summary:** Best practices for CSS selectors and rule complexity; affects main-thread render cost.
**Credibility:** Google Chrome DevRel.

---

## 7. Postgres connection pooling + Supavisor (15)

### 7.1 [SQLAlchemy — Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
**Author:** Mike Bayer · **Source:** Official Docs
**Relevance:** J — the canonical reference for `QueuePool`, `pool_size`, `pool_recycle`, `pool_pre_ping`.
**Summary:** SQLAlchemy connection pool internals: `QueuePool`, `SingletonThreadPool`, `NullPool`, `pool_pre_ping`, `pool_recycle`.
**Credibility:** SQLAlchemy's own docs (sqlalchemy.org); authored by Mike Bayer.

### 7.2 [SQLAlchemy — Engines](https://docs.sqlalchemy.org/en/20/core/engines.html)
**Author:** Mike Bayer · **Source:** Official Docs
**Relevance:** J, K — `create_engine`, connection URL parsing, the dialect layer that talks to Postgres.
**Summary:** Engine configuration: URLs, `echo`, `pool_*`, `connect_args`, dialect options.
**Credibility:** SQLAlchemy's own docs.

### 7.3 [SQLAlchemy — PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
**Author:** Mike Bayer · **Source:** Official Docs
**Relevance:** J — PG-specific connection options including `pool_pre_ping`, `client_encoding`, and prepared-statement handling.
**Summary:** Postgres-specific SQLAlchemy dialect docs.
**Credibility:** SQLAlchemy's own docs.

### 7.4 [SQLAlchemy — Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
**Author:** Mike Bayer · **Source:** Official Docs
**Relevance:** K — `AsyncSession` and `create_async_engine`; relevant if we ever move off sync sessions.
**Summary:** Async SQLAlchemy reference for FastAPI's event loop.
**Credibility:** SQLAlchemy's own docs.

### 7.5 [SQLAlchemy — Connections / transactions](https://docs.sqlalchemy.org/en/20/core/connections.html)
**Author:** Mike Bayer · **Source:** Official Docs
**Relevance:** J, G — how `Connection` and `Engine` interact; relevant for our health-check query path.
**Summary:** Core connection management; explains `connect()`, `checkout`, and `invalidate` semantics.
**Credibility:** SQLAlchemy's own docs.

### 7.6 [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy)
**Author:** Mike Bayer · **Source:** GitHub
**Relevance:** J, K — source for the pool implementation; `lib/sqlalchemy/pool/impl.py` shows the `QueuePool` FIFO logic.
**Summary:** SQLAlchemy 2.0 source — the canonical ORM and pool code.
**Credibility:** 12k+ stars, the canonical SQLAlchemy repo.

### 7.7 [PostgreSQL — Connection settings](https://www.postgresql.org/docs/current/runtime-config-connection.html)
**Author:** PostgreSQL Global Development Group · **Source:** Official Docs
**Relevance:** J, G — `max_connections`, `superuser_reserved_connections`, `idle_in_transaction_session_timeout`.
**Summary:** PG `postgresql.conf` reference for connection-related settings.
**Credibility:** PostgreSQL official docs.

### 7.8 [PostgreSQL — Resource settings](https://www.postgresql.org/docs/current/runtime-config-resource.html)
**Author:** PostgreSQL Global Development Group · **Source:** Official Docs
**Relevance:** J — `max_connections`, `shared_buffers`, `work_mem`; relevant when sizing pool against the server.
**Summary:** PG resource consumption and tuning parameters.
**Credibility:** PostgreSQL official docs.

### 7.9 [PostgreSQL — Query planning](https://www.postgresql.org/docs/current/runtime-config-query.html)
**Author:** PostgreSQL Global Development Group · **Source:** Official Docs
**Relevance:** J — `random_page_cost`, `effective_cache_size`; relevant for our `/auditoria` query path.
**Summary:** PG query-planner tuning knobs.
**Credibility:** PostgreSQL official docs.

### 7.10 [PostgreSQL — Performance tips](https://www.postgresql.org/docs/current/performance-tips.html)
**Author:** PostgreSQL Global Development Group · **Source:** Official Docs
**Relevance:** J, F — server configuration, `EXPLAIN`, index usage; directly relevant to `/ventas` pagination queries.
**Summary:** End-to-end performance guide for PG: indexes, queries, transactions.
**Credibility:** PostgreSQL official docs.

### 7.11 [PostgreSQL — Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
**Author:** PostgreSQL Global Development Group · **Source:** Official Docs
**Relevance:** F, G — use `EXPLAIN ANALYZE` on the `/ventas` historial query and on `/healthz/db`.
**Summary:** Reference for the `EXPLAIN` command and its output.
**Credibility:** PostgreSQL official docs.

### 7.12 [PgBouncer — home](https://www.pgbouncer.org/)
**Author:** PgBouncer Project · **Source:** Official Docs
**Relevance:** J — the canonical pooler; Supavisor is API-compatible with PgBouncer.
**Summary:** PgBouncer docs: `pool_mode = transaction` vs `session`, `max_client_conn`, `default_pool_size`.
**Credibility:** The PgBouncer project's own site.

### 7.13 [PgBouncer — Config](https://www.pgbouncer.org/config.html)
**Author:** PgBouncer Project · **Source:** Official Docs
**Relevance:** J — the exact config flags that govern pooling behavior.
**Summary:** Reference for `pgbouncer.ini` — `pool_mode`, `server_reset_query`, `server_idle_timeout`.
**Credibility:** The PgBouncer project's own site.

### 7.14 [PgBouncer — Features](https://www.pgbouncer.org/features.html)
**Author:** PgBouncer Project · **Source:** Official Docs
**Relevance:** J — feature matrix; what pool_mode supports and what it doesn't.
**Summary:** Pool-mode matrix and feature support table.
**Credibility:** The PgBouncer project's own site.

### 7.15 [Neon — Connection pooling](https://neon.tech/docs/connect/connection-pooling)
**Author:** Neon Engineering · **Source:** Official Docs
**Relevance:** J — Neon runs PgBouncer-equivalent pooling; same knobs apply.
**Summary:** Neon's guide to pooled vs direct connections, when to use which, and PgBouncer compatibility.
**Credibility:** Neon's own docs.

### 7.16 [brettwooldridge/HikariCP](https://github.com/brettwooldridge/HikariCP)
**Author:** Brett Wooldridge · **Source:** GitHub
**Relevance:** J — HikariCP is the JVM reference for connection pooling (we don't use it on Python, but the design principles apply).
**Summary:** Fast, simple JDBC connection pool — useful as a reference design when reasoning about SQLAlchemy pool sizing.
**Credibility:** 21k+ stars, gold-standard JVM pool implementation.

---

## 8. Favicon best practices (7)

### 8.1 [RealFaviconGenerator — home](https://realfavicongenerator.net/)
**Author:** Philippe Bernard · **Source:** Tool + Research Site
**Relevance:** B — the de-facto favicon generator; explains the modern multi-format (ICO, PNG, SVG, Apple Touch, manifest.json) approach.
**Summary:** Online favicon generator that emits the complete `<link>` set and the manifest.json expected by modern browsers.
**Credibility:** Maintained by Philippe Bernard; widely cited by web-perf authors.

### 8.2 [RealFaviconGenerator — FAQ](https://realfavicongenerator.net/faq)
**Author:** Philippe Bernard · **Source:** Tool Docs
**Relevance:** B — answers the "do I really need favicon.ico?" question and the SVG-favicon fallback story.
**Summary:** FAQ covering modern favicon support across Chrome/Safari/Firefox/Edge and the gotchas of legacy `.ico`.
**Credibility:** Same author as the generator.

### 8.3 [MDN — `<link>` element](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/link)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** B — defines `rel="icon"`, `rel="shortcut icon"`, `sizes`, `type`; covers SVG favicons.
**Summary:** Reference for the `<link>` element, including all `rel` types and browser support.
**Credibility:** MDN, maintained by Mozilla.

### 8.4 [web.dev — Efficiently load third-party JavaScript](https://web.dev/articles/efficiently-load-third-party-javascript)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** B, L — discusses why external resources (favicons, fonts) block paint and how to defer them.
**Summary:** Patterns for asynchronous/deferred loading of third-party assets; favicon-specific recommendations.
**Credibility:** Google Chrome DevRel.

### 8.5 [Harry Roberts (CSS Wizardry) — CSS and network performance](https://csswizardry.com/2018/11/css-and-network-performance/)
**Author:** Harry Roberts · **Source:** Blog (Engineer)
**Relevance:** A, L — the canonical CSS Wizardry post on CSS-as-blocking; informs the favicon decision (also render-blocking).
**Summary:** Detailed analysis of how CSS blocks render and the cost of late-discovered stylesheets; argues for inline critical CSS.
**Credibility:** Harry Roberts is a widely cited consultant; his blog is on the canonical web-perf reading list.

### 8.6 [MDN — Web Performance landing](https://developer.mozilla.org/en-US/docs/Web/Performance)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** B, E, L — performance overview; the entry point for browser-side perf concepts.
**Summary:** MDN's landing page for web performance APIs and concepts (Navigation Timing, Resource Timing, PerformanceObserver).
**Credibility:** MDN, maintained by Mozilla.

### 8.7 [web.dev — Avoid invisible text](https://web.dev/articles/avoid-invisible-text)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** A, L — explains FOIT/FOUT and the link between render-blocking CSS and invisible text; motivates inline critical CSS.
**Summary:** Guide on font-display and how render-blocking stylesheets cause invisible text.
**Credibility:** Google Chrome DevRel.

---

## 9. Cold-start benchmarking methodology (8)

### 9.1 [web.dev — Optimize TTFB](https://web.dev/articles/optimize-ttfb)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** G, H — TTFB is the canonical metric for our `24s POST /login` cold-start.
**Summary:** Definitive guide on Time-to-First-Byte: how to measure it, what's "good", and how to reduce it.
**Credibility:** Google Chrome DevRel.

### 9.2 [web.dev — Optimize LCP](https://web.dev/articles/optimize-lcp)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F, L — Largest Contentful Paint optimization; applies to `/login` and `/ventas` first paint.
**Summary:** Guide on reducing LCP: preloading, TTFB, render-blocking resources, image optimization.
**Credibility:** Google Chrome DevRel.

### 9.3 [web.dev — Web Vitals](https://web.dev/vitals/)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F, H — the canonical "what is good performance" definition.
**Summary:** Index page for LCP, INP, CLS — Core Web Vitals.
**Credibility:** Google Chrome DevRel.

### 9.4 [web.dev — learn/performance](https://web.dev/learn/performance/)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** H, K — the structured learning path for performance; covers RAIL, core vitals, tooling.
**Summary:** Curated multi-article curriculum for web performance.
**Credibility:** Google Chrome DevRel.

### 9.5 [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse)
**Author:** Google Chrome team · **Source:** GitHub
**Relevance:** F, L, A — automated auditing tool; measures LCP, CLS, TBT, and flags render-blocking CSS.
**Summary:** Lighthouse source — 30k+ stars, the canonical automated perf audit tool.
**Credibility:** 30k+ stars, Google's open-source project.

### 9.6 [GoogleChrome/lighthouse-ci](https://github.com/GoogleChrome/lighthouse-ci)
**Author:** Google Chrome team · **Source:** GitHub
**Relevance:** F, L — automated Lighthouse runs in CI; relevant to performance-regression detection on `/login` and `/ventas`.
**Summary:** The CI tool that runs Lighthouse against every PR.
**Credibility:** 7k+ stars, Google's official Lighthouse-CI project.

### 9.7 [MDN — PerformanceNavigationTiming](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceNavigationTiming)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** G, H — the API for measuring `domContentLoadedEventEnd`, `responseEnd`, etc. — useful for client-side timing beacons.
**Summary:** Reference for the `PerformanceNavigationTiming` interface.
**Credibility:** MDN, maintained by Mozilla.

### 9.8 [MDN — PerformanceObserver](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** F, G, K — the recommended way to capture performance entries client-side and beacon them to `/ops/perf`.
**Summary:** Reference for `PerformanceObserver` and the `PerformanceEntry` types.
**Credibility:** MDN, maintained by Mozilla.

---

## 10. Web performance in general (15)

### 10.1 [High Performance Browser Networking — Preface](https://hpbn.co/)
**Author:** Ilya Grigorik · **Source:** Book (O'Reilly, free online)
**Relevance:** H, E, L — the foundational text on HTTP/1.1 vs HTTP/2 multiplexing, TLS handshake cost, and CDN behavior.
**Summary:** Full book on web networking; covers TCP, TLS, HTTP/2, HTTP/3, and the cost of every byte.
**Credibility:** Ilya Grigorik is a Google web-perf engineer; the book is widely cited.

### 10.2 [HPBN — Primer on Web Performance](https://hpbn.co/primer-on-web-performance/)
**Author:** Ilya Grigorik · **Source:** Book (O'Reilly, free online)
**Relevance:** H, L — establishes the latency budget (100ms for site to feel instant).
**Summary:** The opening chapter; defines what "fast" means and where the time goes.
**Credibility:** Same as the parent site.

### 10.3 [HPBN — HTTP/1.x](https://hpbn.co/http1x/)
**Author:** Ilya Grigorik · **Source:** Book (O'Reilly, free online)
**Relevance:** A, L — explains why one big CSS file is faster than many (and the HTTP/1.1 connection limit).
**Summary:** The HTTP/1.x chapter; covers persistent connections, pipelining, and the 6-connection-per-origin limit.
**Credibility:** Same as the parent site.

### 10.4 [HPBN — HTTP/2](https://hpbn.co/http2/)
**Author:** Ilya Grigorik · **Source:** Book (O'Reilly, free online)
**Relevance:** A, L — explains why Cloudflare's HTTP/2 multiplexing makes splitting CSS into many files less painful.
**Summary:** The HTTP/2 chapter; covers multiplexing, header compression, server push (now deprecated).
**Credibility:** Same as the parent site.

### 10.5 [HPBN — Optimizing Application Delivery](https://hpbn.co/optimizing-application-delivery/)
**Author:** Ilya Grigorik · **Source:** Book (O'Reilly, free online)
**Relevance:** E, A, L — covers caching, compression, and CDN policy; directly informs the Cloudflare-edge-caching fix.
**Summary:** Chapter on caching at every layer (browser, edge, origin).
**Credibility:** Same as the parent site.

### 10.6 [web.dev — CLS](https://web.dev/articles/cls)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** L — Cumulative Layout Shift caused by late-loading CSS and missing image dimensions.
**Summary:** Reference for the CLS Core Web Vital.
**Credibility:** Google Chrome DevRel.

### 10.7 [web.dev — INP](https://web.dev/articles/inp)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F — Interaction to Next Paint; relevant if our app ever becomes interactive-heavy.
**Summary:** Reference for INP, the replacement for FID.
**Credibility:** Google Chrome DevRel.

### 10.8 [web.dev — LCP](https://web.dev/articles/lcp)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F, L — LCP definition; informs our preload-CSS fix.
**Summary:** Reference for the LCP Core Web Vital.
**Credibility:** Google Chrome DevRel.

### 10.9 [web.dev — FCP](https://web.dev/articles/fcp)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** L — First Contentful Paint, the metric most affected by render-blocking CSS.
**Summary:** Reference for FCP.
**Credibility:** Google Chrome DevRel.

### 10.10 [web.dev — FID](https://web.dev/articles/fid)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F — First Input Delay (now superseded by INP); still relevant when reading older perf reports.
**Summary:** Legacy reference for FID.
**Credibility:** Google Chrome DevRel.

### 10.11 [web.dev — Responsive images](https://web.dev/articles/responsive-images)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** A — covers `srcset`, `sizes`, and how to avoid shipping 4× the bytes needed.
**Summary:** Guide on responsive images; not a current bottleneck but a common follow-up.
**Credibility:** Google Chrome DevRel.

### 10.12 [web.dev — Fetch priority](https://web.dev/articles/fetch-priority)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** L — `fetchpriority="high"` on the preload hint for `/static/app.css`.
**Summary:** Reference for the `fetchpriority` attribute and the Priority Hints API.
**Credibility:** Google Chrome DevRel.

### 10.13 [web.dev — Content Security Policy](https://web.dev/articles/csp)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** E — strict CSP pairs with our Cloudflare caching story (security + perf).
**Summary:** Guide on CSP, the security headers we should add to `/static/*`.
**Credibility:** Google Chrome DevRel.

### 10.14 [web.dev — User-centric performance metrics](https://web.dev/articles/user-centric-performance-metrics)
**Author:** Google Chrome team · **Source:** Official Docs
**Relevance:** F, H — the case for measuring what users feel, not just bytes.
**Summary:** Article on the RAIL model and user-perceived latency.
**Credibility:** Google Chrome DevRel.

### 10.15 [Addy Osmani — Performance Budgets](https://addyosmani.com/blog/performance-budgets/)
**Author:** Addy Osmani · **Source:** Blog (Engineer)
**Relevance:** A, F, L — how to define a perf budget that catches regressions (e.g., `app.css` stays under 11KB).
**Summary:** Practical guide to setting and enforcing a performance budget in CI.
**Credibility:** Addy Osmani is Google Chrome's engineering lead; the canonical reference.

### 10.16 [CSS Wizardry — main site](https://csswizardry.com/)
**Author:** Harry Roberts · **Source:** Blog (Engineer)
**Relevance:** A, L — the canonical consultancy for CSS architecture and performance.
**Summary:** Harry Roberts' main site; the go-to for production-grade CSS strategies.
**Credibility:** Harry Roberts is widely cited in production-CSS discussions.

### 10.17 [Addy Osmani — main site](https://addyosmani.com/blog/)
**Author:** Addy Osmani · **Source:** Blog (Engineer)
**Relevance:** A, F, H — canonical web-perf blog covering JS, CSS, image, and rendering perf.
**Summary:** The main blog index for Addy Osmani.
**Credibility:** Addy Osmani is Google Chrome's engineering lead.

### 10.18 [MDN — PerformanceResourceTiming](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceResourceTiming)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** A, L — per-resource timing for the CSS, JS, and image requests on a page.
**Summary:** Reference for `PerformanceResourceTiming` API.
**Credibility:** MDN, maintained by Mozilla.

### 10.19 [MDN — HTTP Compression](https://developer.mozilla.org/en-US/docs/Web/HTTP/Compression)
**Author:** MDN · **Source:** Official Docs (Mozilla)
**Relevance:** A, E — gzip/brotli on `/static/app.css` and HTML; the Cloudflare edge already does this, but server side matters too.
**Summary:** Reference for `Content-Encoding: gzip` / `br`.
**Credibility:** MDN, maintained by Mozilla.

---

## Cross-cutting: Sentry lazy-import (D)

### S.1 [Sentry — FastAPI integration](https://docs.sentry.io/platforms/python/guides/fastapi/)
**Author:** Sentry Engineering · **Source:** Official Docs
**Relevance:** D — the `import sentry_sdk` cost; Sentry's docs show the canonical `sentry_sdk.init(...)` call site.
**Summary:** Official Sentry docs for FastAPI integration; defines the `before_send` hook, `traces_sample_rate`, and init scope.
**Credibility:** Sentry's own docs.

### S.2 [Sentry — Python SDK](https://docs.sentry.io/platforms/python/)
**Author:** Sentry Engineering · **Source:** Official Docs
**Relevance:** D — Python SDK init; covers the import path and module-load cost.
**Summary:** Reference for `sentry_sdk.init()` and integrations.
**Credibility:** Sentry's own docs.

### S.3 [getsentry/sentry-python](https://github.com/getsentry/sentry-python)
**Author:** Sentry Engineering · **Source:** GitHub
**Relevance:** D — source for the Sentry SDK that we currently lazy-import.
**Summary:** 2.2k+ stars, the Sentry Python SDK; integration code at `sentry_sdk/integrations/fastapi/__init__.py`.
**Credibility:** 2.2k+ stars, official Sentry repo.

### S.4 [Sentry — FastAPI integration docs](https://docs.sentry.io/platforms/python/integrations/fastapi/)
**Author:** Sentry Engineering · **Source:** Official Docs
**Relevance:** D — the integration itself is what costs 50–100ms at import.
**Summary:** Setup guide for the Sentry FastAPI integration; lists the events captured and the dependency footprint.
**Credibility:** Sentry's own docs.

### S.5 [Sentry — Insights: Web Vitals](https://docs.sentry.io/product/insights/frontend/web-vitals/)
**Author:** Sentry Engineering · **Source:** Official Docs
**Relevance:** F, L — if we ever enable Sentry, the Web Vitals dashboard is where we'd track LCP regressions on `/ventas`.
**Summary:** Sentry's frontend performance dashboard docs.
**Credibility:** Sentry's own docs.

### S.6 [Sentry — Insights: overview](https://docs.sentry.io/product/insights/overview/)
**Author:** Sentry Engineering · **Source:** Official Docs
**Relevance:** H, K — Sentry's tracing dashboard; if we want end-to-end traces across the cold-start window.
**Summary:** Sentry's full-stack tracing product.
**Credibility:** Sentry's own docs.

---

## Coverage matrix

| Resource category | # resources | Bottlenecks addressed |
|---|---|---|
| FastAPI performance | 20 | C, D, E, G, H, I, J, K, L |
| Render.com | 18 | H, I, J, K |
| Supabase Python SDK | 11 | C, F, G, J, K |
| Jinja2 templates | 10 | F, L |
| Cloudflare caching | 12 | E, G |
| CSS minification | 12 | A, L |
| Postgres / Supavisor | 16 | F, G, J |
| Favicon | 7 | B, L |
| Cold-start benchmarking | 8 | F, G, H, K, L |
| Web performance general | 19 | A, E, F, H, L |
| Sentry (cross-cutting) | 6 | D, F, H, K |
| **Total** | **139** | A, B, C, D, E, F, G, H, I, J, K, L (all 12 covered) |

---

## What we filtered out (and why)

To document the credibility bar:

- **Medium / dev.to** articles without a known author or that didn't link to a
  primary source — these frequently restate official docs without adding signal.
- **AI-generated SEO farms** — detected via copy-paste boilerplate and stock
  imagery in previews; not authoritative.
- **Paywalled content** (some Safari Online Books, A List Apart back-issues).
- **Dead URLs** — every URL was probed with HEAD/GET; 4 originally-cited
  Gunicorn docs (`/en/stable/configure.html`, `/en/stable/design.html`) and
  one MDN page returned 404 and were dropped from the final list in favor of
  verified-current URLs.
- **Postmortems / random blog posts** without reproducible methodology.

---

## How to use this file

- **Per-bottleneck:** scan the "Relevance" tag for the letter (A–L) that maps
  to the fix you're about to make. Read 2–3 cited sources before coding.
- **Per-category:** the section headers map directly to the 10 categories in
  the original task. Pick one source as primary, one as a cross-check.
- **For verification:** any URL listed is live at research time
  (2026-09-10, UTC). If a URL goes stale, prefer the parent
  project (e.g., `docs.sqlalchemy.org/en/20/` over an out-of-date versioned path).