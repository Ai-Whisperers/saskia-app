# TODO Inventory — Phase 14 audit (2026-10-01)

Output of `rg -n 'TODO|FIXME|XXX' app/` after the Phase 14 push. Three
classes below: (1) stale code TODOs that Phase 14 closed, (2) real
work-tracking TODOs (the next sessions should pick these up), and (3)
non-actionable documentation TODOs (copy reference, inline comments).

## (1) Stale — closed in Phase 14

| File:line | Old comment | Resolved by |
|---|---|---|
| `app/rms/accounting.py:267` | `TODO(phase-3c): wire Expense model` | Phase 14 Batch E — migration 082 + `Expense` model wired into `daily_summary()`. Comment rewritten. |
| `app/rms/accounting.py:333` | duplicate "TODO since phase-3c" inside `daily_summary()` | same — rewritten. |
| `app/routers/herebus.py:489` | `tx.reconciled_by = "system"  # TODO: get from session` | Phase 14 Sprint 1.4 — `reconciled_by` now reads `request.state.user_id` (falls back to "anonymous" under test bypass). New regression test `test_bank_reconcile_sets_reconciled_by_from_session`. |
| `app/templates/pedido_board.html:164` | `// AND the auto-refresh detects a new order. (TODO: wire to refresh handler.)` | Phase 14 — chime plays on reload when `saskia:board-sound-enabled=1` and a new order id appears in `saskia:board-last-order-id`. |
| `app/static/app-improvements.css:330` | `TODO (D15 deeper work): wire this into m.gs() on form submit ...` | Comment rewritten 2026-10-01: every `.currency-input` is `<input type="number">`, browser submits parsed numeric value (never the cosmetic "Gs." prefix). Backend `parse_money_gs()` handles int/float/str. Architecture already prevents the bug. |
| `app/templates/riesgos.html:11` | `{# TODO: wire to POST /riesgos/new ... #}` | Phase 14 batch `f55c079` — `/riesgos/new` POST endpoint + form shipped. |
| `app/rms/nav.py:217` | `# TODO: /clientes/nuevo route` | Phase 14 batch `f55c079` — `/clientes/nuevo` form + POST shipped. |

No code path still uses the placeholder zero.

## (2) Real work-tracking — pick up next session

These all represent real missing functionality or follow-ups. Each has
a recommendation column — Ivan can confirm priority.

| File:line | TODO | Recommended action |
|---|---|---|
| `app/rms/nav.py:217` | `# TODO: /clientes/nuevo route` — nav points to `/clientes` instead | **Add `cliente_nuevo` page** with a small form (name + phone, optional RUC/razón social). Most other CRM rows route to `/clientes/{id}/editar`; a `/clientes/nuevo` is the natural sibling. Wire POST handler in `app/routers/customers.py`. Estimate: 1.5h incl. tests. |
| `app/routers/herebus.py:489` | `tx.reconciled_by = "system"  # TODO: get from session` | **Read username from session** in the reconciliation endpoint. Trivial — pass `request: Request` and read `request.state.user` (or session["user"]). 15 min + 1 test. |
| `app/templates/riesgos.html:11` | `{# TODO: wire to POST /riesgos/new ... #}` | **Add `/riesgos/new` POST endpoint** + small form on the page. Risks are operator-visible (compliance / business risk register); the data model exists but the CRUD surface is missing. Estimate: 2h. |
| `app/templates/pedido_board.html:164` | `// AND the auto-refresh detects a new order. (TODO: wire to refresh handler.)` | **Play a sound on new-order fetch** — the toggle button + audio element are already there; just need to call `audio.play()` from the auto-refresh handler when a new id appears. 20 min + 1 browser test. |
| `app/static/saskia-combo.js:28` | `TODOs (for tomorrow's full implementation):` | This is a list of remaining combo polish items (keyboard nav, aria-live announcements, loading state). Should be its own batch — pick at most 2 of the 6 listed. |
| `app/static/app-improvements.css:330` | `* TODO (D15 deeper work): wire this into m.gs() on form submit so ...` | Money formatter isn't auto-applied on every form input. Decide: ship a small `data-money="true"` opt-in or scan all inputs. Estimate: 1h for the opt-in, 4h for the scan. |
| `app/rms/models/channels.py:56` | `# TODO: Remove these once all code is updated to use Channel enum` | **Legacy CHANNEL_* constants cleanup**. Sweep `app/` for `CHANNEL_WHATSAPP` etc. usages and replace with `Channel.WHATSAPP`. Estimate: 1h grep + patch + 0 regressions. |
| `app/templates/_components/atoms.html:353` | `TODO (tomorrow): wire into filter_toolbar macro` | The filter_toolbar macro is in the same file but the variant listed hasn't been wired. Small refactor: 30 min. |

## (3) Documentation-only TODOs (do not act on)

| File:line | Note |
|---|---|
| `app/rms/validation.py:26-40` | These are regex-shape documentation comments in the docstring of `parse_phone_py` / `parse_ruc_py`. Not actionable. |
| `app/templates/dev_combo_smoke.html:63` | Operator-facing label `<strong>TODO tomorrow:</strong>` in the dev test page — informational. |
| `app/templates/inventario.html:88` + `app/templates/recetas.html:61` | `TODOS` (Spanish for "ALL") inside the multi-filter tooltip copy — not a TODO marker, it's natural language. Don't change. |
| `app/auth_supabase.py:145` | "TODO from them" refers to Supabase's server-side revocation roadmap — not us. |
| `app/rms/models/catalogs_restored.py:38` + `app/rms/models_legacy.py:2133` | Same `# Operators can add/edit/reorder from /settings/categories (TODO).` — superseded by `app/templates/settings_categories.html` which already exists. Grep `/settings/categorias` to verify and remove the stale comment. |
| `app/CHANGELOG.md:798` | A `TODO` mention in the historical changelog — leave as is (it's history). |

## Estimated total to close all (2) items

~7 hours of focused work. Best executed as one batch per item so each
ships with tests + deploy verification.

## Where to file these

Each becomes a `SASKIA-NNN` ticket (per AGENTS.md §Ticket convention) so
the kanban + cron reminders pick them up. Batches G/H/I/J in the
Phase 14 plan already cover (2) at high level; the recommended action
column above is the per-ticket scope.
