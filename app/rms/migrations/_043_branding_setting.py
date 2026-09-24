def _migration_043_branding_setting(conn):
    """Phase 5 — Branding settings.

    Seeds SettingsKV["branding"] with defaults that match the previous
    hardcoded copy in templates/login.html and templates/base.html:
      - business_name: "Saskia RMS"
      - tagline: "Panadería / Bakery — Sistema de gestión"
      - footer: "Sistema local · 2026"
      - accent_color: "#f97316" (CSS --color-accent)
      - logo_path: "" (no logo by default)

    Operators can change any field from /settings/branding without code
    deploy (Phase 5 follow-up UI page).
    """
    import json as _json
    branding = {
        "business_name": "Saskia RMS",
        "tagline": "Panadería / Bakery — Sistema de gestión",
        "footer": "Sistema local · 2026",
        "accent_color": "#f97316",
        "logo_path": "",
    }
    from app.rms.db import app_meta_write, _bump_schema_version
    app_meta_write(conn, "branding", _json.dumps(branding))
    _bump_schema_version(conn, 43)