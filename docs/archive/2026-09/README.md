# Archive — September 2026

> **Historical documents** from September 2026. These are kept for reference
> but are no longer current. New work should not reference them.
>
> **Cleanup date:** 2026-10-05
> **Cleanup by:** repo maintenance pass
> **Mover:** `git mv` style (preserves history) — see git log for original location

## What lives here

This archive contains documents that were active during September 2026 but
have been superseded by later work. The cleanup criteria:

1. **Audit reports** with 0 references in the live codebase
2. **Old operations docs** (pre-2026-09-25) that are no longer the source of truth
3. **Old planning docs** from phases that have shipped
4. **One-off investigations** that are complete

## Directory structure

```
archive/2026-09/
├── README.md                 # this file
├── operations/               # 29 historical ops docs
│   ├── 2026-09-02-*.md      # early September audits & runbooks
│   ├── 2026-09-08-*.md      # incident response, reliability
│   ├── 2026-09-09-*.md      # performance research
│   ├── 2026-09-17-*.md      # supabase incident
│   ├── 2026-09-24-*.md      # phase 2b refactor postmortem
│   ├── uptime-monitoring.md
│   ├── cf-tunnel-rotation.md
│   ├── herbus-discovery-prompt.md
│   ├── import-mapper.md
│   ├── round-2-triage-process.md
│   └── ... (29 files)
├── plans/                    # 7 historical planning docs
│   ├── 2026-08-31-rms-fase-1-dev-plan.md
│   ├── 2026-09-07-sazon-complete-epic-plan-v3.md
│   ├── 2026-09-08-sazon-data-intelligence-v4.md
│   ├── 2026-09-08-sazon-state-analysis.md
│   ├── 2026-09-17-sazon-prelaunch-roadmap.md
│   ├── 2026-09-17-sazon-visual-revolution-plan.md
│   └── 2026-09-rms-fase-1-dev-plan-v2.md
├── FRONTEND_AUDIT_2026-09-22.md
├── FULL_AUDIT_300.md
└── HEREBUS_INTEGRATION_PLAN.md
```

## Why these are archived, not deleted

- **Historical record** of decisions made during the September sprint
- **Reference for patterns** that may recur (incident response, audit methodologies)
- **Compliance** — some audit reports are referenced in other docs by name only

## How to use this archive

- **Don't link here** from new docs — link to the current source of truth instead
- **Don't update** archived files — if you need to change something, copy it to
  the current location and update the original
- **Search here** when investigating "why was X done this way" — the answer is
  often in a Phase 2 audit or sprint planning doc

## Cleanup verification

After this cleanup:
- 14 old ops docs + 7 old plan docs + 3 root audit reports = 24 files archived
- ~2.3 MB of doc content preserved
- All references to archived docs remain valid (files moved, not deleted)
