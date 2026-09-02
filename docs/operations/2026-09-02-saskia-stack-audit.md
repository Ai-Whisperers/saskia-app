# Saskia RMS — Stack Audit & "Should we upgrade?" Decision

**Date:** 2026-09-02
**Question:** "more than xlsx we should use sheets and databases no? analyze all the technologies we use that should be something better and more professional?"
**Audience:** operator (Ivan)
**Status:** analysis — not yet executed

---

## TL;DR (the honest answer)

**The instinct is half right.** The current stack has **2-3 things that are genuinely under-spec** for a "professional" small-business app. The other things are already correctly chosen for the scale — upgrading them would add cost, complexity, and risk for zero benefit to Saskia.

**The 3 things I'd actually change:**

1. **Local backups: xlsx → CSV + SQLite snapshot.** xlsx is fine for "human opens and reads it" but it's a 200KB binary blob with embedded styles; it's not a real backup format. A SQLite snapshot + CSV exports is what professionals use — restorable, diffable, and small.
2. **No CSS framework → add a tiny utility CSS layer** (Pico.css or similar, <10KB, classless). Current state is server-rendered HTML with vanilla CSS — this is actually good. Don't add Tailwind. The polish that matters is bigger touch targets, mobile-first, and consistent spacing. Pico handles that for free.
3. **No error tracking → add Sentry free tier** (5K events/mo, $0). Currently we have loguru → local file. When hosted, local file dies with the container. Sentry (or GlitchTip, the self-hosted free alternative) gives us stack traces the moment something breaks.

**The things I would NOT change** (operator may think these are "unprofessional" but they're correct):

- ❌ SQLite for local + Postgres for hosted — right size, right tool
- ❌ Server-rendered HTML + Jinja2 — right for a 1-user internal app, not a SPA
- ❌ Vanilla CSS — right, see above
- ❌ `bcrypt` + `SessionMiddleware` — right, see Supabase Auth discussion below
- ❌ `bcrypt` is fine — `argon2` is "more professional" but bcrypt is the universal default and well-audited
- ❌ Sync SQLAlchemy — async is the "professional" choice in 2026 but adds 30% complexity for 0% benefit at single-user scale
- ❌ `openpyxl` for xlsx I/O — there's no "more professional" alternative for Excel in Python; pandas is heavier and worse at preserving formatting

**The decision-required items:**

- **Auth: stay with Supabase (current) or self-host with FastAPI Users?** Both are "professional." Supabase saves build hours; FastAPI Users saves recurring dependency on a third-party SaaS. **Default: Supabase**, per the 200h plan.
- **Local backups: keep xlsx + add SQLite snapshot, OR replace xlsx entirely with SQLite snapshot?** The user asked "sheets > xlsx" — the real answer is "xlsx is for humans to look at; SQLite snapshot is for actually restoring data. We need both, not one or the other."

---

## 1. The user's question, parsed

"more than xlsx we should use sheets and databases no?"

Three things in that question, two of which need different answers:

- **"xlsx vs Sheets"** — xlsx (Excel file) is not the same as Google Sheets. xlsx is a *file format*. Google Sheets is a *service*. The real comparison is:
  - xlsx file (openpyxl writes it, user opens in Excel/LibreOffice) ← current
  - CSV file (universal, diffable, smaller) ← better as a backup format
  - Google Sheets (cloud, multi-user editing, real-time) ← overkill for 1 user
  - SQLite snapshot (binary DB file, restorable to byte-perfect state) ← best for backup, worst for "open and look"

  **Recommendation:** keep xlsx for "human opens Excel and reads it" (operator convenience, monthly reports), but **add SQLite snapshot for actual backup** (already implemented in `app/services/r2_backup.py` for cloud; add the same for local export).

- **"we should use ... databases"** — already do. SQLite for local, Postgres for hosted. This isn't the question; the question is "is Postgres the right choice vs MySQL/SQLite-only/Mongo/etc."

- **"no?"** — yes, we should think about this. The audit below does that.

---

## 2. Stack audit — full table

| Layer | Current choice | "Professional" alt | Verdict | Why |
|---|---|---|---|---|
| **Database (local)** | SQLite + WAL | Postgres-only, DuckDB, LiteFS | **KEEP** | SQLite at 0.5GB / single-user / no LAN access is correct. DuckDB is read-optimized (wrong). LiteFS is for distributed SQLite (overkill). |
| **Database (hosted)** | Neon Postgres (free 0.5GB) | Supabase Postgres, RDS, Crunchy, your-own-VPS | **KEEP** | Neon chosen specifically: never pauses, free, scale-to-zero with 5ms cold start. The alternatives are either paid, pause-prone, or operationally heavier. |
| **ORM** | SQLAlchemy 2.0 sync | SQLModel, Tortoise, Piccolo, raw asyncpg | **KEEP** | SQLAlchemy 2.0 is the most mature Python ORM. SQLModel is a thin FastAPI wrapper that's slower to mature. Async adds 30% complexity for 0% benefit. |
| **Web framework** | FastAPI | Django, Litestar, Flask | **KEEP** | FastAPI is the standard. Django would be overkill (ORM + admin + auth built in, but we don't need any of that). Litestar is younger and less proven. |
| **Server** | uvicorn[standard] | gunicorn+uvicorn, hypercorn, granian | **KEEP** | uvicorn is the canonical ASGI server. gunicorn manages workers but Render free uses 1 worker so it's not needed. |
| **Auth** | Supabase Auth (with bcrypt fallback) | Auth0, Clerk, Keycloak, roll-our-own | **KEEP with caveat** | Supabase gives us JWT validation, JWKS caching, password reset email, all free tier. Auth0/Clerk are paid. Keycloak is self-hosted (operational burden). Roll-our-own is a security risk. **Caveat:** tied to Supabase uptime — see "Risks" below. |
| **Password hashing** | bcrypt (cost 12) | argon2id, scrypt | **KEEP** | bcrypt is universally audited, well-supported, and the default everywhere. argon2id is technically more modern but bcrypt is "professional enough" — the security gap is negligible. **If using Supabase Auth**, we don't hash at all (they do). |
| **Session** | Starlette SessionMiddleware (signed cookie, itsdangerous) | JWT in cookie, OAuth2 token, server-side store | **KEEP** | Signed cookies are the standard for server-rendered HTML. JWT is for SPAs / cross-domain. OAuth2 is for "log in with Google." |
| **Templates** | Jinja2 + server-rendered HTML | HTMX, React, Vue, Svelte, Alpine.js | **KEEP** | Server-rendered HTML is the right choice for a 1-user internal app. HTMX is fine for the v2 plan but not needed for v1. **See "When to add HTMX" below.** |
| **CSS** | vanilla CSS (6212 bytes, single file) | Tailwind, Bootstrap, Pico.css, Bulma, daisyUI | **MAYBE** | Vanilla CSS is fine but limited. Tailwind/Bootstrap are overkill (huge CSS, big learning curve). **Pico.css (10KB, classless) is the right "professional" middle ground** — semantic HTML gets nice styling for free. **Decision: yes, add Pico via CDN.** |
| **JS** | none | Alpine.js, HTMX, vanilla JS | **MAYBE later** | For Fase 1 (CRUD forms), no JS needed. For Fase 2 WhatsApp orders (real-time), HTMX or Alpine would be useful. Don't add until Fase 2. |
| **Forms** | FastAPI Form() + HTML | django-form, WTForms, pydantic-forms | **KEEP** | FastAPI's built-in Form() is sufficient. WTForms is more powerful but adds a dep. |
| **Validation** | Pydantic 2 | Marshmallow, attrs, dataclasses | **KEEP** | Pydantic is the FastAPI default; well-maintained; the standard. |
| **Logging** | loguru → local file | structlog, Sentry, Loki+Grafana | **MAYBE** | loguru is fine. Sentry would add error tracking (free tier). Loki+Grafana is operational overkill. **Decision: yes, add Sentry free tier for hosted.** |
| **Backups (local)** | xlsx (Excel) | SQLite snapshot, CSV exports, json dumps | **CHANGE** | xlsx is fine for "operator opens Excel once a month" but NOT a real backup. Add SQLite snapshot for actual restore + CSV per table for diffability. Keep xlsx for human-readable monthly export. |
| **Backups (cloud)** | encrypted SQLite snapshot in Cloudflare R2 | S3, Backblaze B2, rsync.net, GitHub LFS | **KEEP** | R2 free tier is generous (10GB). Encrypted snapshots are already implemented. S3 is paid. Backblaze is $0.005/GB but R2 is free. |
| **Email (password reset)** | Brevo (planned) | Resend, SendGrid, Mailgun, Postmark | **DECISION** | All have free tiers. Brevo (300/day free) is enough. **Default: Brevo** unless operator prefers Resend (better DX). |
| **WhatsApp** | Evolution API (operator's own instance) | Twilio, MessageBird, WhatsApp Business API direct | **KEEP** | Evolution is what they have. Twilio is $$$. |
| **CI/CD** | GitHub Actions | CircleCI, GitLab CI, Buildkite, Drone | **KEEP** | GitHub Actions is free for public repos. Already wired up. |
| **Monitoring** | UptimeRobot (5-min ping) | Better Stack, Checkly, Datadog, Pingdom | **KEEP** | UptimeRobot is free (50 monitors). Better Stack is nicer UI but paid. |
| **Secrets** | BWS (Bitwarden Secrets) | 1Password, AWS Secrets Manager, Doppler, Vault | **KEEP** | BWS is what they have. All alternatives are paid or operationally heavier. |
| **Python deps** | uv (Astral) | Poetry, pip-tools, pipenv, PDM | **KEEP** | uv is the modern standard (10-100× faster, single binary, lockfile). Poetry is the prior gen. |
| **Linter/format** | ruff | black+isort+flake8, pylint | **KEEP** | ruff is the modern standard (replaces 5+ tools with one). |
| **Testing** | pytest + hypothesis | unittest, nose | **KEEP** | pytest is the standard. hypothesis adds property-based testing (we already use it). |
| **Pre-commit** | pre-commit + ruff + pytest + custom secret guard | husky, lint-staged | **KEEP** | pre-commit is the standard. We just added the secret guard. |
| **Container** | Dockerfile (python:3.13-slim) | distroless, chainguard, alpine | **KEEP** | python:3.13-slim is fine for Render/Fly. Chainguard is "more secure" but adds complexity. |
| **Process manager** | none (single uvicorn process) | supervisord, systemd, honcho | **KEEP** | Single process. Render handles process management. |

---

## 3. The 3 things I'd change (concrete recommendations)

### Change 1: Local backups — xlsx + add SQLite snapshot + add CSV

**Current:** `app/services/auto_backup.py` writes one xlsx file per backup, contains all tables as sheets.

**Problem:** xlsx is a 200KB binary blob with embedded styles. You can't:
- Diff two backups (no `diff` works on xlsx)
- Restore a single table (have to load all)
- Restore to byte-perfect state (xlsx has lossy type conversion — float precision loss is documented)
- Back up fast (openpyxl is slow)

**Proposed:**

| Format | What it contains | Used for | Already in repo? |
|---|---|---|---|
| **xlsx** | All tables, formatted for human reading | Monthly report emailed to operator; Saskia can download to "have a copy" | ✅ Yes (`export_xlsx.py`) |
| **CSV per table** | One CSV per table (ingredients, recipes, sales, etc.) | Diff-friendly, restorable row-by-row, importable anywhere | ❌ Add |
| **SQLite snapshot** | Byte-perfect copy of the DB | Full restore (down to the second) | ✅ Yes for cloud (`r2_backup.py`), ❌ **not for local** |

**Implementation:**
1. Add `app/services/export_csv.py` (~50 lines) — writes 8 CSVs to `BACKUP_DIR/csv/`
2. Extend `auto_backup.py` to write all 3 formats on each backup cycle
3. Document in `installer/README.md`: "3 backup formats, each for a different purpose"

**Effort:** ~3 hours. **Risk:** very low (additive). **Operator hours saved:** ~5h/year (faster troubleshooting, easier audits).

### Change 2: CSS — add mobile-first polish + dark mode toggle

**Current:** `app/static/app.css` (6212 bytes of hand-written CSS, semantic class names, warm-amber palette). Already professional. Two real gaps:

- **No mobile responsiveness audit.** Tables overflow on phone. Forms go edge-to-edge. Nav doesn't collapse on narrow screens.
- **No dark mode.** Saskia opens the app at 6 AM in a dim kitchen; light theme is harsh.
- **No print styles.** Monthly close report prints with nav and footer.

**Proposed** — three small additions, not a CSS framework rewrite:

1. **Mobile-responsive @media queries** in `app.css` (add ~80 lines)
   - Tables: horizontal scroll on narrow screens (`overflow-x: auto`)
   - Forms: full width on mobile, max-width 600 on desktop
   - Nav: stack vertically below 600px
2. **Dark mode via CSS variable swap** (add ~30 lines)
   - Toggle via `[data-theme="dark"]` attribute on `<html>`
   - Single button in nav-right that sets a `localStorage` flag
3. **Print stylesheet** (add ~20 lines)
   - Hide nav, footer, buttons
   - Tables: full width, no overflow
   - Headers: keep visible

**Implementation cost:** ~2 hours (no template refactor, just CSS + 5 lines of JS for the toggle).

**Why NOT add a CSS framework (Pico, Tailwind, Bootstrap):**

I considered Pico.css (10KB, classless) and **rejected it** after reading the current `base.html` + `app.css`. The existing CSS uses custom semantic classes (`.btn`, `.form-row`, `.topnav`, `.data` table) and a custom warm-amber palette. Pico would:
- Set `body { margin: 0 }` and conflict with our `--bg`
- Style `button` / `input` / `form` automatically and conflict with our `.btn` / `.form-row`
- Require either refactoring every template (huge cost) OR adding a `class="pico"` scope (complex, fragile)

**The hand-rolled CSS is the right call**; we just need to add the polish above. Doing this respects the work already done and avoids introducing CSS fights.

### Change 3: Error tracking — add Sentry (free tier, 5K events/mo)

**Current:** `loguru → /tmp/saskia-logs/app.log` (Render free ephemeral disk — lost on every deploy).

**Problem:** When something breaks in hosted mode, the only signal is "Saskia messaged Ivan." No stack traces, no breadcrumbs, no aggregation. Render's free tier log retention is short.

**Proposed:** Sentry free tier (5K events/mo, 1 user, 7-day retention). It's the industry standard and free for our scale.
- Catch exceptions in FastAPI handlers automatically
- Capture slow queries, 500 errors, auth failures
- Get email alerts on new error types
- View stack traces with local variables (privacy-controlled)

**Alternatives considered:**
- **GlitchTip** (self-hosted, open-source Sentry clone): more work, free, but operator runs another service
- **Highlight.io**: similar to Sentry, newer, free tier
- **Just better logging to a file**: doesn't help when we don't check the file

**Default: Sentry.** If operator has privacy concerns (error reports contain business data), use GlitchTip.

**Implementation:**
1. Sign up at sentry.io (free, no credit card)
2. Create Python project, get DSN
3. Add `sentry-sdk[fastapi]` to pyproject.toml
4. Initialize in `app/rms/main.py` lifespan:
   ```python
   import sentry_sdk

   if os.getenv("SENTRY_DSN"):
       sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1)
   ```
5. Add `SENTRY_DSN` env var to Render

**Effort:** ~1 hour. **Risk:** low (gated by env var). **Operator hours saved:** enormous (catch bugs in <1 day instead of waiting for Saskia to report).

---

## 4. The things I would NOT change (defending the current choices)

### "Postgres is overkill, just use MySQL"

**No.** Postgres is the right choice. Reasons:
- **Neon is Postgres-native** (their whole company is Postgres-as-a-service)
- **JSONB** is needed for app_meta.value flexibility
- **NUMERIC(12,4)** is needed for exact qty math (no float drift)
- **TIMESTAMP WITH TIME ZONE** for sale timestamps
- **Supabase is Postgres** (if we ever migrate auth)
- **Postgres-specific features** we use: CHECK constraints, generated columns (future), partial indexes (future)

MySQL would force compromises on 4 of these. Not worth it.

### "bcrypt is old, use argon2"

**No.** bcrypt is universally deployed, audited, and the default in every framework. argon2id won the PHC (Password Hashing Competition) in 2015, but the practical security difference is negligible for cost=12. **Supabase handles password hashing for us anyway** (in the hosted pivot), so this doesn't even matter.

### "Use Django, it's more 'professional'"

**No.** Django is a great framework but it's a *batteries-included* framework — it brings its own ORM, its own admin, its own auth, its own form library, its own template engine. For a 1-user app where we've built exactly what we need, switching to Django means:
- Replacing SQLAlchemy with Django ORM (lose 2.0 sync mode features)
- Replacing our auth with Django's (lose Supabase integration)
- Replacing Jinja2 with Django templates (lose 1 dep, gain nothing)
- Replacing FastAPI with Django (lose async-everywhere-ready, gain admin)

Effort: ~40 hours of rewrite. Benefit: ~0 for Saskia. **Wrong answer.**

### "Add Tailwind for 'professional' look"

**No.** Tailwind is 50KB+ of CSS and a complete paradigm shift (utility classes instead of semantic CSS). It's great for new projects; for a finished project, switching means rewriting every template. **Pico.css is the right answer** (see Change 2) — semantic HTML gets styled for free.

### "Add GraphQL instead of REST"

**No.** GraphQL is great for multi-client / public APIs. For a 1-user internal app with 6 routes, it's massive over-engineering. REST is correct.

### "Add Redis for caching"

**No.** No cache needed at single-user scale. Postgres + Neon handles 1000s of req/s for free. Adding Redis is 1 more moving piece to break.

### "Use Docker Compose / Kubernetes"

**No.** Render/Fly runs the single container. Adding orchestration is operational overhead with no benefit.

### "Use TypeScript frontend (React/Vue/Svelte)"

**No.** Server-rendered HTML is the right choice for a 1-user app. JS framework adds bundle size, build complexity, hydration bugs, and ~3 hours of "why isn't this rendering right" debugging. **The only time to add HTMX or Alpine is when we have a real interactive need** (Fase 2 WhatsApp orders, real-time dashboard). Not for Fase 1.

### "Replace Evolution API with WhatsApp Business API direct"

**No.** Evolution API is what they have. WhatsApp Business API requires Meta approval, costs $0.005/msg, and is operationally heavier. Evolution is fine.

---

## 5. The decision-required items

### Decision A: Auth backend

| Option | Effort | Pros | Cons |
|---|---|---|---|
| **Supabase Auth** (current plan) | 0 (already wired) | Free tier, JWT validation, password reset email, JWKS caching | Tied to Supabase uptime (rare, but possible) |
| **Auth0** | ~6h to swap | Industry default, well-known | Free tier only 7K MAU; then $35/mo |
| **Clerk** | ~6h to swap | Best DX, modern UI components | Free tier 10K MAU then $25/mo |
| **Keycloak self-hosted** | ~20h | Full control, no third-party | Operator runs another service |
| **FastAPI Users** (roll-our-own with bcrypt) | ~10h to swap | No third-party dependency | Lose JWT validation, password reset, JWKS |

**Default: Supabase.** It's what we have, it's free, it works. The "tied to Supabase uptime" risk is small (Supabase has 99.9% SLA, multi-region failover). **Decision: keep Supabase.**

### Decision B: Local backup format

| Option | Effort | Pros | Cons |
|---|---|---|---|
| **xlsx only** (current) | 0 | Human-readable, operator can open in Excel | Slow to write, lossy, not diffable |
| **SQLite snapshot only** | ~2h | Byte-perfect, fast, restorable | Not human-readable |
| **CSV per table only** | ~2h | Universal, diffable, fast | No schema; restore needs SQL knowledge |
| **All three** (proposed) | ~3h | Best of all worlds | More files in backup folder |

**Default: all three.** xlsx for human, CSV for diff, SQLite for restore. **Decision: implement all three.**

### Decision C: Error tracking

| Option | Effort | Pros | Cons |
|---|---|---|---|
| **Sentry** (proposed) | ~1h | Free tier 5K events, industry standard, alerts | Third-party SaaS (privacy: error reports may contain business data) |
| **GlitchTip self-hosted** | ~6h | Free, open-source Sentry clone, data stays in EU | Operator runs another service |
| **Better local logging only** | ~1h | No third-party | We never check the logs unless Saskia reports a bug |

**Default: Sentry**, gated by env var. If operator is privacy-cautious, GlitchTip. **Decision: ask operator.**

---

## 6. Recommended change order

| # | Change | Effort | Operator risk | Value to Saskia |
|---|---|---|---|---|
| 1 | Local backups: xlsx + SQLite snapshot + CSV | 3h | very low | medium (we can recover from more disasters) |
| 2 | Add Pico.css for "feels professional" | 2h | very low | high (UX polish) |
| 3 | Add Sentry for error tracking | 1h | low (gated by env) | medium (faster bug fixes) |
| 4 | Add dark mode toggle | 1h | very low | medium (cosmetic) |
| 5 | Documentation polish | 2h | none | low |

**Total:** ~9 hours of dev work, **all additive (no breaking changes)**, can be done in 1-2 work sessions.

---

## 7. What I would do immediately (operator OK assumed)

Per the 200h plan budget (43h used / 157h remaining), I have plenty of hours. Here's what I'd ship without further asking:

1. **Add CSV export** (`app/services/export_csv.py`) — extends `auto_backup.py` to write CSV alongside xlsx. ~3h.
2. **Add SQLite snapshot to local backup** (`auto_backup.py`) — uses `sqlite3` stdlib to write byte-perfect copy next to xlsx/CSV. ~1h.
3. **Add Pico.css** — download to `app/static/pico.min.css`, add to `base.html`, leave `app.css` as overrides. ~2h.
4. **Wire Sentry** — gated by `SENTRY_DSN` env var, init in `lifespan()`. ~1h.
5. **Update AGENTS.md** to document the additions. ~30m.

**Total: ~7.5 hours, all in this turn's scope.** Operator still needs to:
- Decide on backup format (default: all three) — confirm or override
- Sign up at sentry.io (if going with Sentry) — or approve GlitchTip path
- Add `SENTRY_DSN` env var to Render

**If operator wants all of it, I'll execute.** Otherwise, pick which subset.

---

## 8. Honest summary

| "Unprofessional" feeling | Real cause | Real fix |
|---|---|---|
| "The local backup is just an xlsx file" | Yes, but also SQLite snapshot is the actual backup. Add CSV for diff. | **Change 1** |
| "The UI looks basic" | It does. Add Pico.css for semantic styling. | **Change 2** |
| "How will I know when something breaks?" | You won't, unless Saskia messages you. Add Sentry. | **Change 3** |
| "The DB feels small" | It's right-sized. 0.5GB is enough for 5 years of Saskia's data. | None needed |
| "Why is the auth bcrypt and not [X]" | It IS bcrypt via Supabase (or fallback to local bcrypt). Argon2 is academically better but bcrypt is industry standard. | None needed |
| "Why no Redis / GraphQL / Docker Compose / etc." | Because they're not needed at this scale. | None needed |
| "Why is the CSS just 6KB?" | Because we don't need more. Add Pico for the polish that matters. | **Change 2** |

The 3 changes above (backups + Pico + Sentry) close the gap between "what we have" and "what looks/feels professional." The rest is correctly chosen for the scale.

---

## Appendix: file pointers

- Decision doc: `docs/operations/2026-09-02-saskia-decision-hosted-pivot.md`
- Team tasks: `docs/operations/2026-09-02-saskia-team-tasks.md`
- Agent messages: `docs/operations/2026-09-02-saskia-agent-messages.md`
- Round 1 template: `installer/ROUND-1-NOTES.md`
- Pre-commit guard: `scripts/check_no_secrets.py`
- Current auto_backup: `app/services/auto_backup.py` (write xlsx)
- Current R2 backup: `app/services/r2_backup.py` (write encrypted SQLite snapshot to R2)
- 200h plan: `/opt/data/profiles/ivan/.hermes/plans/2026-09-01-saskia-200h-plan.md`

---

*Generated 2026-09-02. Operator decision: proceed with Changes 1-3 (default), or pick a subset, or reject all.*