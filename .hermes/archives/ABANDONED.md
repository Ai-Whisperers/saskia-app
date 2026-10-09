# ABANDONED — archived branches

Date archived: 2026-10-08
Archived by: hermes session (SASKIA-MIG-2,5,6 cleanup)

These branches had unique unmerged work but were too far behind main to rebase
without significant conflict-resolution cost. Archived per "single-developer bus
factor" rule (AGENTS.md rule 36) — stale branch state across sessions burns
context. Bundles are self-contained (full repo history) and can be restored +
rebased when the cost is justified.

## Branches

### `feat/seed-packs-segments` (2 commits, 182 behind main at archive time)
- `a2f6d423` — `pack_demo — vida demo nativa del pack + re-seed CLI`
- `bad61f3d` — `segment seed packs — pre-carga Vaquita-grade para 10 segmentos`
- Bundle: `.hermes/archives/feat-seed-packs-segments.bundle`
- Status when archived: pre-carga Vaquita-grade (10 packs × 161 prods × 161 recetas
  × 799 líneas × 271 ingredients) + 2,174 negocios→pack + 298 prods reales/59
  nego Asunción. NOT loaded to prod. Per memory, this was the Sazón seed-packs
  work. Bundle contains migration 092+ territory.
- Restore: `git fetch .hermes/archives/feat-seed-packs-segments.bundle feat/seed-packs-segments:feat/seed-packs-segments`

### `polish/saskia-p0` (13 commits, 78 behind main at archive time)
- `e847df50` — `Sentry→Telegram activation (1-line before_send hook)`
- `53447626` — `docs: C.1 partial, C.3 done, gemas food_cost enchufado`
- `d29f2c6d` — `cierra huecos de auditoría en rutas destructivas`
- `18e75696` — `arqueo guiado — conteo por denominaciones`
- `559746fe` — `canal Telegram (app/rms/notify.py) + tests`
- (… 8 more)
- Bundle: `.hermes/archives/polish-saskia-p0.bundle`
- Status when archived: SASKIA-208-tier polish batch (Sentry→Telegram wiring,
  audit gap closure on destructive routes, arqueo guiado). Some commits may
  have been partially adopted into main via other PRs (e.g. the C.1 Sentry
  hook is a tiny 1-line wire — likely already on main via a follow-up).
- Restore: `git fetch .hermes/archives/polish-saskia-p0.bundle polish/saskia-p0:polish/saskia-p0`

## Why archive, not rebase

- User constraint: "we allways get stuck on tests" — rebase after 78-182 commits
  WILL hit merge conflicts (style drift, migration renames, ruff format sweeps),
  and each conflict resolution needs a test re-run. Cost-benefit was poor for
  polish/seed work with no production blocker.
- Work is operator-batched polish, not bug fixes blocking production.
- Single-developer rule 36 prefers clean state over carried branch state.

## When to restore

Restore + rebase when the underlying work becomes production-relevant:
- `seed-packs-segments` — if Saskia wants the pre-carga back (Vaquita-grade
  packs loaded as a demo). Re-evaluate the memory note "Nada cargado a prod"
  — if Saskia changes her mind, the seed file is in the bundle.
- `polish/saskia-p0` — if any of the polish items (Sentry→Telegram,
  audit gaps, arqueo guiado) is reopened as a ticket. The bundle is the
  source of truth; cherry-pick individual commits if only some are wanted.
