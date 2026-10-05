"""app.observability — outbound alerts + Sentry wiring.

Tier 8 (2026-10-01). All integrations gated on env vars so dev runs
without keys:
- ``app.observability.sentry`` — re-export the lifespan hook from
  ``app.rms.main`` (kept there to avoid an import cycle at module
  load time).
- ``app.observability.email`` — Resend transactional email.
"""
