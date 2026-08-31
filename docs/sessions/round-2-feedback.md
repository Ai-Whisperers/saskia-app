# Round 2 feedback — review template

> **For Saskia and Kiki.** This is the working agreement for the **second review round** of fase 1, per `docs/plans/2026-08-31-rms-fase-1-dev-plan.md §9 Task 10`.
>
> **Period:** ~3-5 days after Round 1 closes.
> **Focus:** copy (Spanish Paraguayan) + UX polish, NOT new features.

---

## How this round works

1. **Saskia** uses the app day-to-day for 3-5 days during Round 1 (already complete).
2. At the end of Round 1, she sends feedback via WhatsApp. Kiki captures each item as a row below.
3. **Round 2** is **only for cosmetic / copy changes** — anything functional should be a separate quote.
4. Items get a status. Items get fixed in PRs. PRs get committed with `Refs #NNN`.
5. When Round 2 closes, this file becomes the diff against Round 1's v0.1.

## Status legend

| Status | Meaning |
|---|---|
| `OPEN` | Not yet reviewed |
| `ACCEPTED` | In scope, will fix in this round |
| `OUT-OF-SCOPE` | Fase 2 or separate quote |
| `DEFERRED` | Fase 1.5 or later |
| `FIXED` | Implemented; commit SHA noted |
| `WONT-FIX` | Explicitly rejected with reason |

## Severity ladder

| Severity | Meaning | Example |
|---|---|---|
| `blocker` | Cannot use the app | "Sale entry crashes when qty is 0" |
| `major` | Significant friction | "Costo column always shows '—' even when prices are set" |
| `minor` | Polish / UX | "Tab order in sale entry skips qty field" |
| `cosmetic` | Spanish copy / wording | "'Guardá' should be 'Guardar' in this context" |

---

## Round 2 items

<!--
Copy this template and replace the placeholder for each item:

### #NNN — <short title>

**Severity:** blocker | major | minor | cosmetic
**Status:** OPEN
**Reported:** YYYY-MM-DD

**What:** <one-paragraph description>

**Repro:**
1. <step 1>
2. <step 2>
3. <expected vs actual>

**Screenshot:** <attached or linked>

**Saskia says:** <verbatim if useful>

**Build team:** <response, including commit SHA when fixed>

---
-->

### #001 — <example item>

**Severity:** minor
**Status:** FIXED
**Reported:** 2026-XX-XX
**Fixed:** 2026-XX-XX, commit `<sha>`

**What:** ...

---

## Round 2 review summary

When the round closes, fill this in:

- **Items raised:** N
- **Items fixed:** M (status `FIXED`)
- **Items out of scope:** K (status `OUT-OF-SCOPE` or `DEFERRED`)
- **Items rejected:** J (status `WONT-FIX`)
- **Total clock-time on Round 2:** X hours (well below the 70h quote's overflow budget)

## Sign-off

When Saskia is satisfied:

> *Written OK — Round 2 closed. Fase 1 accepted.*
> Saskia Weiss Vander: ___________________________ date: ___________
> AI Whisperers (operator): ___________________________ date: ___________

---

*Generated 2026-09. Per `docs/operations/2026-09-tech-stack-review.md` and `2026-09-comprehensive-improvements-review.md`. Stored in `saskia/docs/sessions/round-2-feedback.md` at the start of Round 2.*
