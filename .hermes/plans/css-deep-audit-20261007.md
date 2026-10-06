# CSS Deep Audit & Refactor — saskia-rms

**Date:** 2026-10-07
**Author:** Hermes
**Branch:** main
**Goal:** Modularize, abstract, and harden the CSS layer; eliminate the bug classes that hide in raw values, broken var refs, and scattered styles.

## Current file map

| File | Bytes | Purpose | Should-be in a diff |
|------|-------|---------|---------------------|
| `app.css` | 65,976 | Design tokens + most base styles | One large file |
| `app-components.css` | 32,467 | Component classes (`.btn`, `.card`, `.table`, ...) | One file |
| `app-improvements.css` | 15,776 | Phase 1-4 audit improvements | Should be reorganized by layer |
| `app-shell.css` | 14,703 | App shell (sidebar + topbar) | One file |
| `combobox.css` | 7,833 | Combobox component | One file |
| `users.css` | 4,772 | Users module | Page-specific |
| `dow-hour-heatmap.css` | 1,374 | Chart component | Component |
| `mobile.css` | 2,024 | Mobile-only rules | Should merge into shell |
| `calendar.css` | 42 | Empty (placeholder) | DELETE |
| **Inline `<style>`** | ~40KB across 22 templates | Page-specific CSS | Move to layered files |
| **Inline `style=`** | **1,454 occurrences / 845 unique** | One-off CSS | Migrate ≥6 occurrences |

## Audit findings (10 issues, ranked by impact)

### Critical (ship-blockers)

#### C1. Self-referenced CSS variables silently fail (FIXED in 918c794)

`app.css` had a `:root` alias block with `--card-bg:var(--card-bg)` etc. These self-references are invalid CSS variables, so any consumer using `var(--card-bg, fallback)` silently fell back. Caused white backgrounds in dark mode.

**Status:** Fixed in commit 918c794 — but only the most obvious ones (3 self-refs). Need to verify there are no others lurking.

#### C2. Dark-mode attribute mismatch (DOCUMENTED, NOT YET FIXED)

CSS uses `:root[data-theme="dark"]` selector but the live HTML attribute is `data-sazon-theme="system"`. The runtime JS *does* sync `data-theme="dark"` when toggled, AND the `@media (prefers-color-scheme: dark)` block in `app-improvements.css` covers the OS case. So dark mode works — but only if the user toggles it OR has OS preference set to dark. The default state of a fresh visitor with light-mode OS is **always light**, ignoring any "system" setting.

**Fix:** When `data-sazon-theme="system"`, also call `getComputedStyle` of OS at boot. The current code does — but only for `prefers-color-scheme: dark`, not light. Should set `data-theme="light"` when the OS is light and the user hasn't toggled. This is symmetric and removes ambiguity.

### High priority (correctness bugs)

#### H1. 1454 inline `style="..."` attributes, 845 unique values

Many are duplicated patterns that should be classes. Threshold: migrate styles with ≥6 occurrences (32 unique styles, 341 total) into a `utilities.css` file.

Examples that show ≥6 occurrences:

| Count | Pattern | Proposed class |
|-------|---------|----------------|
| 29 | `font-size:var(--text-sm)` | `.text-sm` |
| 21 | `margin:0` | `.m-0` |
| 20 | `display:inline` | `.d-inline` |
| 19 | `text-align: right` | `.text-right` |
| 18 | `margin-top:4px` | `.mt-1` (assuming 4px ≈ 1×space-1) |
| 18 | `font-size:var(--text-xs)` | `.text-xs` |
| 14 | `margin-top:0` | `.mt-0` |
| 13 | `margin-top:var(--space-3)` | `.mt-3` |
| 11 | `margin-bottom:var(--space-2)` | `.mb-2` |
| 10 | `display:flex; justify-content:space-between; margin-bottom:var(--space-2)` | `.flex-between` |
| 9 | `height:36px` | `.h-control` (semantic) |
| 9 | `font-size:var(--text-xs);text-transform:uppercase;letter-spacing:0.05em` | `.text-label-upper` |
| 7 | `display:none` | `.d-none` |
| 7 | `width:100%; padding: 0.5rem; border-radius: 6px; border: 1px solid var(--border)` | `.note-callout` |

The single-script approach: generate `utilities.css` from a YAML, then sed the templates. Single reviewable PR.

#### H2. 22 templates with inline `<style>` blocks (~40KB total)

The biggest is `produccion.html` (7.3KB), then `receta_form.html` (11.5KB — also has a lot of duplicated button styles).

These styles are page-specific and should live in a new `app/templates/produccion/components.css` (etc.) included only by the templates that need them. This:
1. Eliminates duplicate loading (only `produccion.html` loads it)
2. Makes the structure of each page visible by file inclusion
3. Cuts body HTML size (browser doesn't carry the CSS for pages that don't use it)

Alternative: put them all in `app-improvements.css` and accept the broader load. Faster, no template changes, lower impact.

**Decision:** Move `produccion.html` styles to `app-improvements.css` (they're already partly there). Keep `<style>` blocks in templates that have truly unique styling (e.g. `menu_publico.html`).

#### H3. Hardcoded hex colors in templates (76 occurrences)

WCAG trap. Most common offenders:
- `#111827` (gray-300) — text color used in inline
- `#fff` (white) — backgrounds
- `#f59e0b` (amber-500) — warning, fails AA on white (2.5:1)
- `#fef3c7` (amber-100) — warning soft
- `#f3f4f6` (gray-100) — subtle backgrounds

**Fix:** Sweep `produccion.html` (the worst offender) and replace with `var(--color-...)` tokens. Add a runtime test that fails if a template uses any of these literal hexes.

#### H4. Hardcoded `font-size: Npx` instead of `--text-*` tokens

20+ templates use `font-size: 11px`, `12px`, `13px`. These don't scale with user browser zoom or theme.

**Fix:** Sweep to `--text-xs`, `--text-sm`, `--text-md` tokens.

### Medium priority (architecture)

#### M1. ITCSS layer organization missing

The 4 CSS files load in this order:
1. `app.css` (tokens + base)
2. `app-improvements.css` (utilities + page-specific)
3. `app-shell.css` (shell)
4. `app-components.css` (components)
5. `combobox.css`, `calendar.css`, `mobile.css`

But within `app.css` everything is mixed: `:root` tokens, body styles, button styles, form styles, table styles. There's no clear separation between "settings" (no output) and "components" (CSS output).

**Fix:** Use native CSS `@layer` to enforce ITCSS order:

```css
@layer tokens, base, elements, components, utilities;

@layer tokens {
  /* :root vars */
}
@layer base {
  /* body, html, a, h1-h6, p */
}
@layer elements {
  /* form, input, button defaults */
}
@layer components {
  /* .btn, .card, .table, .sidebar */
}
@layer utilities {
  /* .mt-3, .text-right, .d-flex */
}
```

This makes the cascade predictable without file-load gymnastics. Native CSS, zero JS, no build step.

#### M2. `app-improvements.css` is a kitchen sink

Looking at the section markers, it contains: stacking context vars, auto dark mode, focus rings, touch targets, utility classes, bulk actions, pagination, table controls, column widths, reduced motion, print styles, recipe form, form sections, time fields, difficulty stars, cost summary, mobile phone breakpoint.

**Fix:** Reorganize. Use `@layer` to keep the order but improve naming. Document the file as "phase-based improvements, layered by function."

#### M3. Components that reach for raw colors instead of tokens

`.production-row--has-pedido` uses `var(--color-info-soft)` (good).
`.step-btn` uses `var(--color-surface)` (good, after fix).
But `.btn-primary` uses `var(--color-accent)` for bg AND `var(--color-accent-fg)` for text — both correct.

The pitfall elsewhere: `var(--color-danger)` as TEXT color. The skill (`server-rendered-design-system` pitfall #29) says:
> Using `--color-danger` for inline text renders at 3.84:1 on white — fails WCAG AA.

**Fix:** grep `color: var(--color-(danger|warn|success)\)` without `-fg` — should return ZERO.

#### M4. `calendar.css` is 42 bytes (effectively empty)

**Fix:** Delete the file and remove the link from `base.html`.

### Low priority (polish)

#### L1. `combobox.css` overlaps with `app-components.css`

Some `.btn`, `.input` styles are redefined. Audit and merge.

#### L2. `mobile.css` could merge into `app-shell.css`

`mobile.css` only contains the bottom-nav styles. `app-shell.css` already has the sidebar. Move for cohesion.

#### L3. `dow-hour-heatmap.css` is an island

1.3KB but never imported in `base.html`. Verify it's imported by the one page that uses it.

## The refactor plan (6 PRs, ship in order)

#### PR1: Foundation — `@layer` cascade + token audit (1-2 hours)

1. Add `@layer tokens, base, elements, components, utilities;` to `app.css` top
2. Wrap the existing `:root` blocks in `@layer tokens { ... }`
3. Wrap body/html/h1-h6/etc. in `@layer base { ... }`
4. Wrap form/input/button defaults in `@layer elements { ... }`
5. Audit: any rule that uses `!important` outside utilities?
6. Add a regression test that asserts each layer has the expected presence

**Files touched:** `app.css`, `tests/test_css_layers.py`

#### PR2: Empty file cleanup + `mobile.css` merge (30 min)

1. Delete `calendar.css` (42 bytes, unused)
2. Merge `mobile.css` into `app-shell.css` (the bottom-nav styles)
3. Remove from `base.html` link list

**Files touched:** `app-shell.css`, `base.html`, `tests/test_css_inventory.py`

#### PR3: Utilities extraction from inline styles (1-2 hours)

1. Build `utilities.css` with the 32 high-frequency patterns (≥6 occurrences)
2. Single sed pass over `app/templates/` to remove each inline style and add the class
3. Test: assert each migration-target appears in <expected_count> templates and not more
4. Add `utilities.css` to `base.html` after `app.css`, before `app-shell.css`
6. Wrap in `@layer utilities { ... }`

**Files touched:** `utilities.css` (new), `tests/test_utilities.py`, `base.html`, ~30 templates

#### PR4: Inline `<style>` block migration (1 hour)

1. Move `produccion.html` <style> → `app-improvements.css` (under `@layer components { }`)
2. Move `receta_form.html` <style> → `app-improvements.css`
3. Move `settings.html`, `pedido_board.html`, `menu_publico.html` <style> blocks similarly
4. Leave truly page-unique blocks (e.g. `login.html`) alone for now — minor

**Files touched:** `app-improvements.css`, 8 templates, tests

#### PR5: Hex color sweep in templates (1 hour)

1. Identify all hardcoded hex colors in `app/templates/` (76 occurrences)
2. Replace with `var(--color-...)` equivalents from the design system
3. Add a test that fails if any template uses a literal hex (allow list for print/preview pages)

**Files touched:** 12 templates, `tests/test_no_hex_colors.py`

#### PR6: Dark-mode attribute discipline (30 min)

1. Fix `base.html` JS to set `data-theme="light"` when OS is light and user hasn't toggled (symmetric with dark)
2. Document the bootstrap sequence in the plan file
3. Test: load page with `prefers-color-scheme: light` and verify `data-theme="light"` is set

**Files touched:** `base.html`, `tests/test_theme_bootstrap.py`

## Out of scope (explicit)

- **Component class extraction** (`.card` → `.elevated`, etc.). The current names are fine; renaming is busywork.
- **Build pipeline** (Sass, PostCSS, Lightning CSS). The repo is intentionally build-free.
- **Tailwind**. Forbidden by repo policy.
- **WCAG compliance audit.** That's a separate skill (`saskia-rms-wcag-audit`). This refactor makes the foundation cleaner but doesn't add WCAG fixes.
- **Removing duplicate rules between `app-components.css` and other files.** Possible 30-40 min win but requires running the visual audit after to confirm no regressions.

## Verification checklist

For each PR:

- [ ] `pytest` passes (full suite, not just the new tests)
- [ ] `curl -sS <page> | wc -c` — body size should NOT increase
- [ ] `curl -sS <page>` — visual classes appear
- [ ] Live deploy (`bash scripts/deploy.sh`) and verify in browser
- [ ] Take a screenshot, diff against the previous one

Final verification:

- [ ] All CSS files load
- [ ] Tokens resolve (no `var(--undefined, fallback)` left)
- [ ] Inline style= count drops from 1454 → ~600 (one-offs kept)
- [ ] Inline `<style>` count drops from 22 → ~5 (only unique pages)
- [ ] No hardcoded hex colors in templates (allow list for print)
- [ ] Dark mode toggles work in both directions

## Estimated time

| PR | Time | Risk |
|----|------|------|
| PR1 @layer | 1-2 h | low (additive, no rule moves) |
| PR2 empty cleanup | 30 min | very low |
| PR3 utilities | 1-2 h | medium (template sed could miss edge cases) |
| PR4 <style> migrate | 1 h | low |
| PR5 hex sweep | 1 h | medium (color semantics matter) |
| PR6 dark mode | 30 min | low |
| **Total** | **5-7 h** | |

## Decisions to confirm with operator

1. **Do we want utility classes that mirror Tailwind naming** (`.mt-3`, `.text-right`)? It's faster to learn for someone who's used Tailwind, but adds another layer of abstraction. Alternative: semantic class names (`.stack-vertical`, `.text-label`). The operator's preference decides.
2. **Do we accept the risk of renaming `data-theme` to also work with `data-sazon-theme`?** Currently they're separate (one for the browser's media query, one for the app's persistence). Merging simplifies but changes one user's mental model.
3. **Should PR4 leave `menu_publico.html` alone?** It's a public-facing page; its styles might be better left embedded (faster first paint, no extra HTTP request for visitors who may not be logged in).

---

## Appendix: The 32 utility candidates (auto-generated from inline style= inventory)

```python
# Generated by audit-and-rollout-utility.py
# Threshold: ≥6 occurrences across templates

'font-size:var(--text-sm);': '.text-sm',                   # 29
'margin:0': '.m-0',                                         # 21
'display:inline': '.d-inline',                              # 20
'text-align: right': '.text-right',                         # 19
'margin-top:4px': '.mt-1',                                  # 18
'font-size:var(--text-xs);': '.text-xs',                    # 18
'margin-top:0': '.mt-0',                                    # 14
'margin-top:var(--space-3);': '.mt-3',                      # 13
'margin-bottom:var(--space-2);': '.mb-2',                  # 11
'margin-bottom: 1rem': '.mb-6',                            # 11
'margin-bottom: var(--space-3);': '.mb-3',                 # 11
'margin-left:var(--space-2);': '.ml-2',                    # 10
'display: flex; justify-content: space-between; margin-bottom: var(--space-2);': '.flex-between mb-2',  # 10
'margin: 0': '.m-0',                                        # 9
'height:36px': '.h-control',                                # 9
'font-size:var(--text-xs);text-transform:uppercase;letter-spacing:0.05em': '.text-label-upper',  # 9
'font-size: 12px': '.text-xs',                              # 8 (merge with .text-xs)
'display:block; margin-bottom: var(--space-1); font-weight:bold': '.block-bold',  # 8
'display: flex; gap: var(--space-2); flex-wrap: wrap': '.flex-gap-2-wrap',  # 7
'font-size: var(--text-sm);': '.text-sm',                   # 7 (merge)
'flex:1': '.flex-1',                                        # 7
'margin-top:2rem': '.mt-8',                                 # 7
'margin-bottom:var(--space-3);': '.mb-3',                  # 7
'display:none': '.d-none',                                  # 7
'margin-bottom:0': '.mb-0',                                 # 7
'display: none': '.d-none',                                 # 7 (merge)
'width:100%; padding: 0.5rem; border-radius: 6px; border: 1px solid var(--border);': '.note-callout',  # 7
'text-align:center': '.text-center',                        # 6
'margin: var(--space-1) 0 0 0': '.mt-1',                    # 6
'margin-top: var(--space-2);': '.mt-2',                     # 6
'display:inline-flex; align-items:center; gap: var(--space-2);': '.inline-flex-center-gap-2',  # 6
'font-size:var(--text-md);': '.text-md',                    # 6
```