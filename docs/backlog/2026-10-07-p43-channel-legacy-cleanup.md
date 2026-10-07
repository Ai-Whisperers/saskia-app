# P43 — Complete channel-legacy cleanup (2026-10-07)

## Goal
Eliminate every remaining raw channel string literal in app/ that
should be using `Channel.X.value`. After P42 we refactored the
write paths. P43 finishes the job on:
- Model defaults (`Sale.channel`, `Pedido.channel`)
- Seed/demo data that bypasses the enum
- The bug where `pedido.channel == "WhatsApp"` (uppercase) never matches
- Read-side defaults in HEREBUS, dispatcher, catalogs
- DB seed tuples
- The literal `CHANNEL_DEFAULT = "mostrador"` constant

## Out of scope
- Notification kind (`"whatsapp"` in notifications.py) — different
  domain (email/sms/whatsapp), NOT a sale channel. Don't conflate.
- `customer.preferred_channel` literals — different column, different
  domain.
- `phone`/`instagram` customer marketing-source literals — different
  domain.
- Display sites in sales.py:103, :581 (already noted as future work).

## Tasks

### Tier 1 — Bugs and DB-blockers (will break after P41 deploy)
1. **`app/routers/pedidos.py:2078-2079`** — `pedido.channel == "WhatsApp"`
   (uppercase) will never match because channel values are lowercase.
   Bug silently disables WhatsApp template matching. Fix: compare
   against `Channel.WHATSAPP.value` (lowercase). Add a regression test.

2. **`app/rms/seed/pack_demo.py:132`** —
   `["whatsapp", "phone", "instagram"]` for `customer.preferred_channel`.
   Note: `customer.preferred_channel` is NOT covered by migration 111
   CHECK (only Sale / Pedido are). So this is a stylistic refactor,
   not a bug. Keep raw but add comment.
   Actually `pack_demo.py:192` is the bug —
   `channels = ["whatsapp", "whatsapp", "whatsapp", "mostrador", "phone", "pedidosya"]`
   — used for `sale.channel`. The `"phone"` here WILL break DB CHECK.
   Fix: replace `"phone"` with `Channel.OTHER.value`.

3. **`app/rms/notifications.py:156, 186, 189, 198, 281`** — verify
   these are notification-kind (email/sms/whatsapp), NOT sale channel.
   If they are notification-kind, leave them. Add docstring note.

### Tier 2 — Model defaults and central constants
4. **`app/rms/models_legacy.py:492`** — `default="mostrador"` on
   `Sale.channel`. Use `Channel.MOSTRADOR.value`.

5. **`app/rms/models_legacy.py:1773`** — `default="whatsapp"` on
   `Pedido.channel`. Use `Channel.WHATSAPP.value`.

6. **`app/rms/schemas.py:45-59`** — `CHANNEL_DEFAULT = "mostrador"`.
   Replace with `Channel.MOSTRADOR.value`.

7. **`app/rms/catalogs.py:49`** — `default_channel_code` fallback
   `"mostrador"`. Use `Channel.MOSTRADOR.value`.

### Tier 3 — Read/write sites in non-P42 files
8. **`app/routers/herebus.py:1069`** — `s.channel or "mostrador"`.
   Read site. Use `Channel.MOSTRADOR.value`.

9. **`app/services/suscripcion_dispatcher.py:173, 201`** —
   `channel="whatsapp"`. Write sites (suscription-related). Use enum.

10. **`app/rms/db.py:1860-1864`** — Channel seed tuples. Use enum.

### Tier 4 — Tests
11. **`tests/test_P42_channel_enum_integration.py`** — extend with:
    - Regression test for the `pedido.channel == "WhatsApp"` bug fix
    - All defaults are enum values (Sale, Pedido, schemas, catalogs)
    - pack_demo channels don't include `"phone"` anymore
    - herebus and dispatcher read/write sites use enum

## Estimated scope
- 11 distinct edits across 9 files
- ~25 lines of new tests
- No new migrations
- No behavior changes (Tier 1 fix restores silent bug; Tiers 2-3 are
  stylistic; Tier 4 is verification)

## Acceptance
- `ruff check` clean on changed files (excluding pre-existing findings
  in sibling's territory)
- `pytest tests/test_P42_channel_enum_integration.py tests/test_P39_channel_lowercase.py tests/test_P43_channel_enum_central.py -v` all green
- Wider regression suite (P40, P41, held_sale, ventas_redesign,
  db_check_constraints, e2e/flows.py): all green
