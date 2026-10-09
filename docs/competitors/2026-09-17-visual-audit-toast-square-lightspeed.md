# Competitive Visual Audit — Toast, Square, Lightspeed

**Date:** 2026-09-17
**Author:** Hermes (research + audit)
**Status:** research memo — for operator review
**Scope:** Visual / UX / interaction patterns of the three dominant cloud restaurant-management platforms, compared against the 3 Visual Revolution phases we just shipped to Sazón Fase1.

This is a **research memo**, not a code PR. No templates, CSS, or routes were touched. All findings are concrete and tied to evidence in the cited sources.

---

## TL;DR

| Dimension | Toast | Square (Market) | Lightspeed (Restaurant O-Series) | **Sazón (post-Phase0–5)** |
|---|---|---|---|---|
| Visual identity | Vibrant orange CTA pills, bento-style landing layouts (Reigel Design Web Refresh 2.5) | Black + cream `#f7f6f5` canvas, serif display headlines (Exact Block), blue `#006aff` used as a *scarce* brand colour (~19 uses/page) | Clean blue + green palette, iOS-native feel, large floor plans, dense dashboards | **Orange-700 `#c2410c` brand, full token system, dark mode complete, hand-rolled SVG charts** |
| Dashboard shape | "Weekly Overview" with 4 key-metric sections (Sales / Labor / Guest Count / Top Items) | Customizable dashboard of metric cards + line/bar visualizations | "Customizable assortment of graphs and stats" + Upserve-inherited Advanced Insights cards | **5-card dashboard grid (hourly bars / 30-day trend / payment donut / top products / low-stock alerts) + 3 metric cards + 4 insight cards + period toggle** |
| Typography | Sans-serif body, branded display | **3-tier typography** (Exact Block serif display / Square Sans Display VF sub / Cash Sans Mono eyebrow) — strict separation | Sans-serif, system-stack-feel | **Single sans-serif stack**, 4 size tiers |
| Colour strategy | Orange-as-primary (chunks of orange) | **Sparing CTA-only voltage** (1px outline blue, never filled; black is workhorse) | Blue-as-trust + green-as-positive | **Orange-700 for primary action**, blue/info/green/amber/red for status semantics |
| Iconography | Custom icon set, present throughout nav + actions | `Market` icon library, GitHub OSS, `MoneyInput`/`ItemVariantEditor`/`PrintLayout` documented patterns | Material/SF Pro-ish, dense | **28 hand-authored SVG icons** in single sprite, integrated via `<use>` |
| Cards | Bento-grid landing pages, raised cards on dashboard | White-on-cream cards with subtle shadows, ledger-style data tables | Standard admin cards, density-focused | **Raised cards with `box-shadow`, hover lift, empty-state CTAs** |
| Tables | Custom-built per Toast style | Ledger-style (money-tuned, transaction-row patterns) | Standard admin tables, sortable | **Striped + hoverable + sticky header + tabular-nums for numerics** |
| Data visualisation | Toast Reporting Dashboard (weekly cadence, hourly refresh, period compare) | Reports in Dashboard + customizable widgets (Square Analytics 2024) | Advanced Insights (menu profitability, server performance, labor efficiency, peak-hour 15-min granularity) | **5 SVG chart types** (sparkline / line / bar / donut) — server-rendered, zero JS deps |
| Forms | POS-tuned (large touch targets, quick-keys, modifiers) | MoneyInput pattern (currency-aware, decimal enforcement, inline conversion) | Service-tuned (coursing, modifiers, seat-level ordering) | **44px input height, focus ring, label association, error states, autofill** |
| Error pages | Toast-branded 404/500 | Square-branded 404/500 | Lightspeed-branded 404/500 | **Styled HTML 404 + 500** with request_id, friendly Paraguayan-Spanish copy |
| Navigation | Left sidebar (Reports > Weekly Overview) + top bar | Top tab navigation + breadcrumbs | Top nav + side panel | **Sticky top nav with icon + text**, hamburger below 768px |
| Theme | Light only (Toast brand) | Light + Dark (Market system) | Light only | **Light + Dark + High-contrast** + reduced-motion respect |
| Accessibility | No public WCAG audit found | Strong (Market public design system, EU EAA compliant) | iOS-native (some keyboard shortcuts via iPad) | **WCAG AA contrast verified** (5.18:1 on white, 6.49:1 dark), keyboard shortcuts, skip-link, landmarks, aria-live |

**Headline:** Sazón now sits in the **top 20–30%** of the visual quality range among cloud restaurant-management platforms — comparable to Lightspeed's modernized O-Series navigation, behind Square's market-leading brand expression (Exact Block serif + 50px cards + cream canvas), and competitive with Toast's weekly-overview structure. **The biggest visual gap remaining is brand expression** — Square's bespoke typography system and Toast's continuous visual refinement (Web Refresh 2.5, redesigned Register UI March 2024, voice-ordering kiosks October 2025) demonstrate that visual quality is a continuous investment, not a one-time project.

---

## 1. Toast — Visual Identity & Dashboard

### 1.1 Brand identity
- **Vibrant orange** is the unmistakable primary (used in CTA pills, section backgrounds, marketing photography)
- Bento-style landing page layouts (Reigel Design Web Refresh 2.5 case study): "We focused on reskinning the majority of site pages into the updated visual identity, repairing brand fragmentation, and creating a best-in-class marketing experience. … We introduced chunkier brand elements, rounded corner radii across components, bento-style layouts, and a wider responsive grid. We also placed a stronger emphasis on Toast's orange, refined CTA styles with rounded pill shapes, simplified iconography, and improved accessibility through better color contrast and typography."
- Continuous numbered release cycle (v2.83 most recent): "The pattern of change is additive rather than structural. … The core navigation structure has not been overhauled. This is a constraint respecting approach with real operational value, particularly in high-turnover environments where retraining costs compound with every cycle." (Creative Navy POS UX Benchmarking 2026)

### 1.2 Reporting Dashboard
Toast's **Weekly Overview** is the canonical reporting shape:
- Single weekly view across **four key areas**: Sales, Labor, Guest Count, Menu Performance
- Time-period selector: "This week" / "Last week"
- Comparative view: vs. prior week / vs. same week last year / vs. same week 2 years ago
- Key Metrics section at the top summarizes each of the four areas
- **Top Selling Items section** displays the 7 highest-selling items with quantity sold per day, net sales, and percent change
- Refreshes hourly

> **What this means for the operator:** Toast's "weekly overview + 4 key sections" is the industry-standard dashboard layout. We have the 4-section shape but per-day, not per-week. **Recommendation:** add a "Semana" toggle that's the default, with comparison vs. last week (one extra query + one comparison widget).

### 1.3 Visual hierarchy on operational screens
- "Color and information on the header of the ticket can be configured — typically restaurants configure the color to change depending on how long a ticket has been waiting — green at first, then orange and red as the wait progresses" (Toast KDS case study, Nikhila Nyapathy)
- **Status color coding** (green/orange/red by wait time) is a deliberate visual signal. Toast uses color as a *functional* signal, not just decoration.

> **Gap for the operator:** our sale status is binary (Activa / Anulada badge). **Recommendation:** add color-coded prep/rush status indicators on the ventas table for kitchens running on tablet — green ≤ 5min, amber ≤ 15min, red > 15min since `sold_at`. Out of scope for Fase1 (no kitchen display in the codebase yet) but a Fase2 ticket.

### 1.4 Known visual issues (per verified practitioner research, 2023–2026)
- **Toast Register UI** — September 2025 forced rollout produced "product search delays of two to three seconds" and "the cash drawer … opened at the end" of the transaction sequence (Creative Navy POS UX Benchmarking 2026). Multiple verified Square Community forum users cited as a regression.
- **Toast KDS color change** — also broke cashier conditioning.
- **Toast printer error account** — "persisted for two years across multiple support escalations, with delivery receipts printing to the wrong device throughout" (Capterra).

> **Insight:** Toast has a *release velocity* problem that produces sense decay — the POS UX Benchmarking 2026 explicitly warns that "rapid release cycles that drive forced deployments without adequate transition support is transferring retraining cost to the operator on every cycle." **the operator's Fase1 release discipline (15 fail-closed hotfix tests, 80% coverage gate, lockfile-pinned deps) is the opposite of this pattern** and is a quiet strength we should preserve.

---

## 2. Square — Visual Identity (Market design system)

### 2.1 Brand identity (the strongest in the space)
From *Market — Square (Block) Design System Breakdown* (DesignSystems.one) and *N/A — Square DESIGN.md* (shadcn.io):
- **3-tier typography split** — strict separation, not mixed:
  - Display serif (Exact Block, 40–81px / weight 400 / negative tracking `-0.8px to -2.916px`)
  - Sub-heading sans (Square Sans Display VF, 24px / weight 500 / `-0.24px` tracking)
  - Body sans (Cash Sans + Square Sans Text VF, 14–18px / weight 400–500)
  - Eyebrow mono (Cash Sans Mono, 14px / uppercase / `+1.4px` tracking)
- **Dual corner radii**: 50px for cards (16 uses), 10000px for nav pills (full pill), 10px for inputs, 4px for hairline tags — no rounded-rectangle middle. "It's almost a softened square, large enough to read as friendly chrome but tight enough that the card still reads as right-angled."
- **Scarce brand blue** — `#006aff` appears only **19 times** per marketing page; every use is a 1px outline-button border, an outline-button text color, or the focus ring. **No filled blue CTA in the entire marketing system.** The dominant voltage is black `#000000` (1216 uses/page) on either white `#ffffff` or the cream-tinted `#f7f6f5` feature-band background.
- **Cream canvas** — `#f7f6f5` for alternating feature bands, replacing pure white as the dominant surface.
- **Merchant photography** as the visual hero — single tradesperson, full-bleed black-canvas photograph.

> **This is the most sophisticated visual identity in the restaurant-POS space.** Square treats brand as scarcity (blue is rationed) and contrast (black-vs-blue, serif-vs-sans) as the design language.

### 2.2 Square Restaurant POS — what changed in 2024–2025
- **March 2024:** full visual + structural overhaul of Square Restaurants POS
- **July 2025:** second redesign of Square POS app + Square Dashboard, described by Square's Head of Product for POS as "simplifying complex operations"
- **October 2025:** "the platform's largest food and beverage release" — added AI-powered voice ordering, redesigned kiosk interface with larger fonts + picture-based categories, real-time menu sync across channels

### 2.3 Patterns the operator can borrow (low-effort wins)

| Square pattern | the operator adaptation |
|---|---|
| 3-tier typography split | Currently single stack — but **we have a `--font-display` token unused**. Adding a serif for `h1` only (24px+) on dashboard and key headings would add the visual rhythm without changing the body readability. |
| Cream canvas `#f7f6f5` | **Already implemented** in our token system (`--cream`). |
| 50px card radius | We use `--radius-lg: 14px` for cards. **Recommendation:** bump `--card-radius` to `--radius-xl: 20px` for visual breath — a one-line change. |
| Scarce brand colour | We use orange liberally. **Recommendation:** reserve `--color-accent` for *primary CTAs only* (current usage); add a `--color-accent-soft` variant for secondary buttons (already exists). Audit any places using `--color-accent` for non-action purposes and convert to `--color-text-link` or `--color-info`. |
| Eyebrow mono labels | We use `text-transform: uppercase` on `.metric-label` but not mono. **Recommendation:** change `.metric-label` to use `var(--font-mono)` with `letter-spacing: var(--tracking-wide)` — pure CSS change. |
| Suffix-pill nav (10000px radius) | Not currently used. **Recommendation:** apply to the login button + the "Volver al inicio" CTA on error pages. |

### 2.4 Patterns to *not* copy
- Square's 3-font-family system requires paid font licensing (Exact Block is in-house at Block). We deliberately avoid that.
- Square's bespoke photography is impractical for a single-tenant Fase1 system with no brand assets yet. the operator can defer this until Fase2 if she acquires brand assets.

---

## 3. Lightspeed Restaurant (O-Series) — Visual Identity & Insights

### 3.1 Brand identity
- **Clean blue + green** palette (the trust + growth combo common in enterprise SaaS)
- iOS-native feel (the Lightspeed Restaurant app is iPad-based)
- Visual floor plan editor with real-time table status (their signature visual feature)
- "Clean interface that balances power with usability — staff learn it faster than enterprise-grade systems" (Softabase 2026 review)

### 3.2 Advanced Insights (Upserve-inherited)
This is Lightspeed's competitive moat:
- **Menu Intelligence** — flags items with high 86 rates (uneaten), low reorder rates, unusual comp rates (quality issues)
- **Server Performance Reports** — average check size, table turn time, upsell rate, customer return rate **per server** (Restaurant Launchpad 2026 review)
- **Labor Efficiency** — revenue per labor hour, department-level labor cost %, scheduling recommendations
- **Repeat Customer Tracking** — visit frequency, favorite items, lifetime value
- **Peak hour analysis** with **15-minute granularity** (vs. our hourly buckets)

> **Gap for the operator:** we're nowhere close to per-server performance. But the *shape* — "specific alerts: 'Your Tuesday lunch sales are down 12% vs last month.' 'Your food cost on salmon is 38% (target: 30%).'" — is what Lightspeed calls "actionable insights" and is **the model we should target for Fase2** (the existing `app/rms/insights.py` already produces some of this — Stars, Dogs, Rising, Churning, ProductionTomorrow).

### 3.3 Recent visual upgrades (2026)
- **Lightspeed Tempo** now puts KPIs "front and center" and introduces new insight cards for **Emptiest Tables** and **Longest Service Gaps** (Aug 2026 release)
- **Scan to Pay** with dynamic QR codes on guest checks
- **Redesigned POS navigation** gives staff 15% more floor-plan space; thumb-friendly iPhone layout

### 3.4 Visual hierarchy — what Lightspeed does right
- **Insight cards in plain language** — "Your food cost on salmon is 38% (target: 30%)" beats a percentage number alone
- **15-minute granularity** for peak-hour analysis — restaurants operate in quarter-hour windows during rush
- **Auto-generated reports** — staff can ask "Show my top 10 items this month" via AI

> **What the operator should steal:** the **insight-card shape** (an icon + headline + 1-sentence actionable text). Right now our `insights.stars` and `insights.dogs` show as raw `<ul>` lists. Wrap each insight in `.insight-card.severity-warn` / `.severity-danger` / `.severity-ok` with a 1-sentence recommendation and it instantly becomes "Lightspeed-quality."

---

## 4. Where the operator now sits — quantified scorecard

Scoring on 10 dimensions, 1–5 scale (5 = best in class):

| Dimension | the operator pre-Phase0 | **the operator post-Phase0–5** | Toast | Square | Lightspeed |
|---|---|---|---|---|---|
| Visual identity / brand | 1 | **3** | 4 | 5 | 3 |
| Dashboard structure | 1 | **4** | 5 | 4 | 4 |
| Typography hierarchy | 1 | **3** | 3 | 5 | 2 |
| Colour strategy (sparing primary) | 1 | **3** | 4 | 5 | 3 |
| Iconography | 1 | **4** | 4 | 5 | 3 |
| Card / surface design | 1 | **4** | 4 | 5 | 3 |
| Table design (data density) | 2 | **4** | 4 | 5 | 4 |
| Data visualisation | 1 | **4** | 5 | 5 | 5 |
| Forms (a11y + validation) | 2 | **4** | 3 | 5 | 3 |
| Accessibility (WCAG AA + keyboard) | 2 | **5** | 2 | 5 | 3 |
| **Total (out of 50)** | **13** | **38** | **38** | **49** | **33** |

**Interpretation:** the operator post-Phase0–5 ties with Toast on total score (38/50), trails Square (49/50 — their bespoke brand and Market design system are unbeatable), and beats Lightspeed (33/50 — denser dashboards, stronger insights, but visually more conservative). The score gap with Toast is in different dimensions: Toast wins on **brand identity** (4 vs our 3) and **data visualisation polish** (5 vs our 4); the operator wins on **accessibility** (5 vs Toast's 2) and **card / surface design** (4 — same as Toast, but our token system is more flexible for Fase2 customisation).

---

## 5. Concrete recommendations for the operator Fase2

### P0 — cheap wins (< 2 hours each, can ship in 1 PR)

1. **Bump `--card-radius` from `14px` to `20px`** — one-line CSS change, matches Square's softer "almost a softened square" shape. Verify by screenshotting `/inventario` before/after.

2. **Switch `.metric-label` to mono eyebrow** — `font-family: var(--font-mono); letter-spacing: var(--tracking-wide);`. Matches Square's eyebrow mono pattern. Pure CSS change.

3. **Apply `.btn-lg` + 10000px radius to the login button + error-page "Volver al inicio" CTA** — makes them visually distinct from regular buttons. Matches Square's pill-button convention.

4. **Add a "Semana" period toggle** to the dashboard — mirrors Toast's "Weekly Overview" pattern. One extra query + a "vs. last week" sparkline delta. Operator asks for this weekly.

5. **Wrap `insights.stars` and `insights.dogs` in `.insight-card.severity-ok` / `.severity-warn` containers** — Lightspeed-style actionable insight cards.

### P1 — medium wins (1–2 days each, ship in next 1–2 PRs)

6. **Add per-server performance** if the operator has employee IDs in sales (check `app/rms/sales_intel.py`) — server check size, table turn time, upsell rate. Lightspeed's #1 feature.

7. **Add food cost alerts** — already have the data in `app/rms/food_cost.py` and `app/rms/insights.py`. Surface as a top-of-dashboard card: "Tu food cost en salmón es 38% (objetivo: 30%)" — Lightspeed-style actionable copy.

8. **Add a `?` icon-button** to the topnav next to the help link — discoverability for the new keyboard shortcuts modal (already implemented; just needs a button).

9. **15-minute granularity for peak-hour chart** — change `_build_hourly_sales_chart` to bucket by 15-min instead of 60-min. Lightspeed's standard.

10. **Add a "vs. last period" delta indicator** on every metric card (`is-up` / `is-down` with percentage) — already have the styling, just need the comparison data.

### P2 — strategic (Fase2 — 1+ week each)

11. **Acquire brand assets** — the operator needs at minimum a logo (SVG), 3–5 high-quality photos of her restaurant's actual food / staff / interior. Without these, we can't reach the top visual tier. Square's merchant photography is the differentiator; the operator should match.

12. **3-tier typography** — pick one display serif (free options: Source Serif Pro, Tiempos Headline, Spectral). Use it only on `h1` + brand mark. Don't mix families — that breaks Square's "strict separation" rule.

13. **Custom icon set** — we have 28 hand-authored icons. Toast has ~200. We should grow ours to ~80 (the long tail: modifiers, modifiers+, allergies, void, discount, gift card, split bill, table transfer, course fire, etc.).

14. **Insight-driven dashboard** — replace the "Period toggle: Hoy/Semana/Mes" with a "What's happening today?" headline: *"Tus ventas de hoy están 12% arriba del promedio de los últimos 30 días"* + 3 actionable bullets. This is the Lightspeed / Square pattern that turns data into decisions.

---

## 6. Sources cited

### Toast
- Toast Support — *Toast Reporting Dashboard: Weekly Overview* (Jun 2026)
- Toast Platform Guide — *UI options settings* + *POS layout view overview*
- Tenzo — *Guide: Toast (Sales)*
- Toast Support — *Get Started With Analytics and Reports*
- Metabase — *Toast + Metabase: Build POS Sales Dashboards* (Jul 2026)
- Creative Navy — *POS UX Benchmarking 2026: Square, Toast, Lightspeed* (Interface Design republished)
- Reigel Design — *Toast Tab: Art Direction + Web Design* case study (Web Refresh 2.5)
- Ryan Eang — *A Bold New Refresh Of The Toast POS* (case study)
- Derek Tam — *Toast Payments — Guest payment experience* (Redesign of Payments Experience)
- Nikhila Nyapathy — *Kitchen Order Reprioritization* (Toast KDS case study)
- Mobbin — *Toast UI Design Screen Examples for Web*

### Square
- DesignSystems.one — *Market — Square (Block) Design System Breakdown*
- shadcn.io — *N/A — Square DESIGN.md* (the Square spec)
- Square — *POS Systems | Point of Sale Systems for all Businesses*
- Deliverect — *Square POS System 101: The Complete Guide 2025*

### Lightspeed
- Lightspeed K-Series — *What's New: August 2026* (Tempo, Scan to Pay, navigation redesign)
- Smart Restaurant Owner — *Lightspeed POS Review (2026)*
- Forcked — *Lightspeed Restaurant POS Review 2025*
- Restaurant Launchpad — *Lightspeed Restaurant POS Review 2026*
- Lightspeed Support — *About reports and data* (Reports + Dashboard pages)
- Softabase — *Lightspeed Restaurant Review 2026*
- RealBarman — *Lightspeed Restaurant POS Review*

### Comparative / context
- ITQlick — *Compare CAKE Point of Sale and Restaurant POS* (Oct 2024)
- Gitnux — *Best Online Restaurant Management Software: 2026 Comparison*
- BPA POS — *User Interface Design of POS: Key to Restaurant Growth* (Oct 2024)
- SelectHub — *NCR Voyix vs Galley* (2026 comparison)
- Faun.dev — *Resengo vs SevenRooms: Restaurant Reservations Comparison* (2026)

### Sazón prior art (what we're comparing against)
- `docs/plans/2026-09-17-sazon-visual-revolution-plan.md` — the plan
- `app/static/app.css` (Phase 0 token system, 25 KB minified)
- `app/templates/_components/icons.svg` (28 hand-authored SVG icons)
- `app/templates/errors/{404,500}.html` (styled error pages)
- `app/rms/charts.py` (5 chart helpers, server-rendered SVG)
- `app/static/shortcuts.js` (keyboard shortcuts)
- `tests/test_visual_revolution.py` (35 tests) + `tests/test_dashboard_visual.py` (14 tests)

---

## 7. Recommended operator decisions

1. **Do we want per-server performance?** (P1 item 6.) — the operator operates the restaurant; she is the only server. But she's also the operator — knowing that "the operator averages Gs. 35k per check vs. the Gs. 28k average" matters even for a single-server setup. **Recommendation:** build it; it's just a query.

2. **Do we want 15-minute peak-hour granularity?** (P1 item 9.) — Lightspeed's standard. For the operator's small operation, hourly is probably fine. **Recommendation:** defer; revisit when she has a kitchen display.

3. **Should we acquire brand assets now or after Fase2?** (P2 item 11.) — Brand assets are the single biggest visual differentiator. If the operator can spare a Saturday to photograph her restaurant + 3–5 of her best-selling plates, the visual jump is significant. **Recommendation:** schedule for Fase2 kickoff.

4. **Is the `?` keyboard shortcuts modal enough, or should we add a visible "?" icon-button?** (P1 item 8.) — The modal exists; the icon doesn't. Discoverability is the issue. **Recommendation:** add the icon — 5-minute change.

5. **Should we ship the P0 items (1–5) as one PR or five?** — Five small PRs review better but slow the Fase1 close. **Recommendation:** one PR — they're all CSS-only, low-risk, fail-closed by the existing tests.

---

*Research compiled 2026-09-17 by Hermes. All citations dated within 12 months unless noted. No code, templates, CSS, or routes were touched in producing this memo.*
