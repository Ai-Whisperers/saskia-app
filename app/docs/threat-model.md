# Threat model — Saskia RMS

> **For Kiki and any future agent reading the app repo.** Defines what we defend
> against, what we deliberately don't defend against, and why.

## TL;DR

The app is **single-user, single-PC, single-trust-boundary**. Anyone with physical
access to the laptop has full access to the data. We trust OS-level user accounts
to keep the laptop itself private. We don't add login screens.

## What we defend against

| Threat | Mitigation |
|---|---|
| Accidental data loss (file corruption, accidental delete) | Auto-backup on startup → local xlsx + encrypted Cloudflare R2 snapshot. 30-day retention local, indefinite cloud. |
| Power loss mid-write corrupting SQLite | WAL mode (`PRAGMA journal_mode=WAL`). Survives crashes; transactional rollback. |
| Power loss leaving sensitive data on disk | `PRAGMA secure_delete=ON`. Deleted rows are zeroed out, not just unlinked. |
| Forgotten default credentials / shared laptop | Documented threat: anyone with the OS-level user account has full access. Mitigated by OS-level user accounts (per-person accounts on shared PCs). |
| Subtle money rounding errors | `Decimal` everywhere; `to_int_gs()` is the ONLY integer-cast path; property-based tests. |
| Float drift in cumulative totals | Same as above + never use float for money; `Decimal(str(value))` everywhere. |
| Time zone confusion (server local ≠ Asunción) | All datetime math uses `zoneinfo.ZoneInfo("America/Asuncion")`. Stored UTC, displayed local. |
| Cross-recipe BOM cycles (A uses B uses A) | Cycle detection in costing engine raises `CycleInRecipeTree`. UI shows error. |
| Negative stock after sales | Allowed (kitchen reality > accounting purity) but red-flash alert on dashboard. |
| Auto-overwrite of recipes during re-import | Confirmation modal showing diff; auto-backup before mutation. |
| Silent PII in PRs | Pre-commit hook blocks `.env`, `credentials.json`, `id_rsa`. Reviewer blocks accidental commits of PII. |
| Logging PII to third parties | Logs are local-only (loguru → `~/AppData/Local/AIW-Saskia/logs/app.log`). No Sentry, no Datadog, no third-party telemetry. |
| CloudFlare R2 holding plaintext data | Encrypted with `age` on her laptop BEFORE upload. R2 holds ciphertext only. |
| CloudFlare R2 breach leaking data | Same: ciphertext is useless without the `age` key, which is on her laptop. |

## What we deliberately don't defend against

| Threat | Why we don't defend |
|---|---|
| Physical access to laptop | Single-user app. OS-level auth is the boundary. We don't add a login screen. |
| Network attacks on the local server | Server binds to `127.0.0.1` only. NOT exposed to LAN. No firewall rules needed. |
| Remote attacker on her Wi-Fi | Same as above — `127.0.0.1` only, no listener on the LAN. |
| Family member seeing supplier phone numbers | OS-level user accounts (per-person) on shared PCs. We don't build multi-tenant. |
| Regulatory compliance (SOC2, HIPAA, GDPR) | Single-user local app. Compliance work belongs to whoever runs the cloud service, not us. |
| PII leak via logs | Logs are local. Logs are gitignored. Logs don't leave her PC. |
| Long-term encrypted-backup compromise | `age` keys live only on her laptop. If she loses both laptop AND forgets to copy her key, encrypted backups are unrecoverable. **Mitigation: documented "save your age key somewhere safe" step in install.** |

## Data classification

| Tier | Examples | Where it lives |
|---|---|---|
| **PII (private)** | Saskia's name, address, phone, bank account, ID | `saskia-context` (private repo), never in `saskia-app` |
| **Operational (private-but-local)** | Recipe ingredients, supplier names, sale history | Local SQLite on her PC. Encrypted R2 snapshots. |
| **Anonymized aggregates** (NOT YET BUILT) | "Top 5 products by margin" | Could be derived from operational data. Not built in fase 1. |
| **Public** | The app's source code | `saskia-app` (public repo). No PII. |

## Incident response

If PII is accidentally committed to `saskia-app` (which is public):

1. Reviewer MUST block the PR.
2. Notify operator (Ivan) immediately via WhatsApp.
3. **Rotate** any token leaked (R2 access key, etc.).
4. Operator amends commit + force-pushes (`git push --force`). History rewrite
   acceptable for PII containment.
5. Lower exposure: was it a private repo? Was it pushed only to a feature branch?
   Was it tagged?
6. If pushed to public main: GH Archive, Software Heritage already cached. Focus
   becomes damage control (Saskia notification, bank statement fraud alerts, etc.).
7. Add post-mortem to `docs/sessions/` (the post-mortem itself contains no PII).

## Audit trail

- Every commit in `saskia-app` is public + signed by GitHub user `Ivan van der Pol`.
- Every PR has review before merge (Kiki or operator).
- Auto-backup events are logged in `app.log` with timestamp + filename (no PII).
- R2 uploads are logged with the timestamp and ciphertext filename (no plaintext).
- CI runs are public on GitHub Actions.

## Single-trust-boundary principle

When in doubt: **assume the OS user account is the trust boundary.** Don't build
auth in the app. Don't build RBAC. Don't build audit logs beyond what we already have.
If Saskia wants multi-user in the future, that's a Fase 2 quote.
