"""app.integrations — external integrations layer.

Sprint 2.4 of the 2026-10-02 backend overhaul: extract infra layer
(scrapers, barcode, printer) out of app/rms into a separate package.

Modules:
- scrapers: web scraping for competitor prices
- barcode: barcode generation/parsing
- printer: thermal printer / receipt integration
"""
from app.integrations import barcode, printer, scrapers

__all__ = ["barcode", "printer", "scrapers"]
