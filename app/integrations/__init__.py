"""app.integrations — external integrations layer.

Sprint 2.4 of the 2026-10-02 backend overhaul: extract infra layer
(scrapers, barcode, printer) out of app/rms into a separate package.

Modules:
- scrapers: web scraping for competitor prices
- barcode: barcode generation/parsing
- printer: thermal printer / receipt integration
- email_outbound: SMTP outbound email with retry (S2 robustness PR7)
"""

from app.integrations import barcode, email_outbound, printer, scrapers

__all__ = ["barcode", "email_outbound", "printer", "scrapers"]
