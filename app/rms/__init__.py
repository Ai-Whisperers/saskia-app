"""app/rms — Saskia RMS Fase 1.

The restaurant-management system core. Module structure:

config          — paths, ports, env vars
db              — engine, session, pragmas (WAL, secure_delete, FK), versioned migrations
models          — SQLAlchemy ORM (ingredient, recipe_line, recipe, product, sale, sale_stock_move, import_batch)
money           — Decimal helpers + Guaraní formatting (Paraguayan convention)
units           — Unit enum with aliases (g/kg/ml/l/und)
costing         — pure functions for recipe cost, product cost, margin
main            — FastAPI app entry point (lifespan + router mounts)

All modules are import-safe. The package can be imported without side
effects (no DB connection, no logging setup). Side effects happen in
`main.run()` only.
"""
