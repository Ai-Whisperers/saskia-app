# Sazón — Wishlist

> **Append-only bucket for ideas.** Anyone — Iván, the operator, Kiki, a future operator — can drop
> a new idea here without going through a planning gate. Items move between folders
> (`raw/` → `triaged/` → shipped or `rejected/`); nothing is deleted without a reason.

## How to add an idea

1. Create a new file in `docs/wishlist/raw/` named `YYYY-MM-DD-<short-slug>.md`.
2. Use the template below. **Don't agonize over estimates** — that's what triage is for.
3. Triage happens at Sprint boundaries. Items move to `triaged/` (accepted into a future
   sprint) or `rejected/` (with a one-line reason).

## Folders

| Folder | Meaning |
|---|---|
| `raw/` | Untriaged ideas. Anyone can write here. Append-only. |
| `triaged/` | Items accepted into a future sprint, with cost/phase/owner. |
| `rejected/` | Items explicitly not pursued, with reason. Don't move items here because they "feel unimportant" — only because they're actively out of scope. |

## Naming

- One file per idea. **Never combine ideas.** If you have two, write two files.
- Filename pattern: `YYYY-MM-DD-<short-slug>.md`
- Slug is lowercase, hyphen-separated, ≤ 40 chars.

## Template

```markdown
# <one-line title>

**Date:** YYYY-MM-DD
**Author:** the operator (via WhatsApp) | operator (Iván) | Kiki | auto-detected
**Cost guess:** XS | S | M | L | XL
**Phase guess:** 1.5 | 2 | 3 | 4+ | maybe-never
**Source:** verbatim quote (the operator) | operator note | doc ref | inferred

## What

<one-paragraph description, in the user's words where possible>

## Why now (or why not)

<optional — what triggered this idea>

## Repro / context

<only if relevant — links, screenshots, steps>
```

## Triage move-to-`triaged/` template (append, don't replace)

When an item gets accepted into a sprint, append:

```markdown
## Triage

**Moved to triaged:** YYYY-MM-DD
**Epic / story:** <e.g., E3.S1>
**Estimated effort:** <hours>
**Owner:** <who will build it>
```

## Important: don't lose context

If you `git mv` a file from `raw/` to `triaged/`, keep the file contents intact — **append,
don't rewrite**. The history is part of the project's memory.
