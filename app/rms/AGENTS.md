# AGENTS.md — MOVED to repo root (2026-10-12)

This file was consolidated into the root `AGENTS.md` ("`app/rms/` package
conventions" section + hard rules) to end rule drift between two copies.

Do NOT add rules here. Extend the root AGENTS.md instead.

Pointers for tooling that resolves nested AGENTS.md paths:
- Money / units / time / stock rules → root AGENTS.md rules 1-11, 20-21
- Migrations (incl. atomic_ddl_block Postgres guidance) → rules 12-19 + package section
- Tooling rules 27-30 (old numbering) → root rules 38-41
- Module structure, make cheat sheet → package section in root AGENTS.md
