#!/usr/bin/env python3
"""Debug script: understand what the /recetas table actually shows."""
import sys, os
sys.path.insert(0, os.getcwd())

os.environ['DATABASE_URL'] = 'sqlite:///./test_r2_debug.db'
os.environ['SASKIA_TEST_AUTH_DISABLED'] = '1'
os.environ['PYTHONPATH'] = os.getcwd()

from app.rms.db import init_db, make_engine, make_session_factory
from app.rms import db as dbmod

engine = make_engine(os.environ['DATABASE_URL'])
init_db(engine)
factory = make_session_factory(engine)

from tests.factories import make_ingredient, make_recipe, make_product, make_sale, ing_line
with factory() as s:
    flour = make_ingredient(s, name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000, min_stock_qty=1.0)
    egg = make_ingredient(s, name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500, min_stock_qty=0.0)
    recipe = make_recipe(s, name="Galleta", yield_qty=12.0, yield_unit="und",
                         lines=[ing_line(flour, qty=0.3, unit="kg"),
                                ing_line(egg, qty=2.0, unit="und")])
    s.commit()
    # Verify what's in the DB
    from app.rms.models import Recipe
    r = s.query(Recipe).get(recipe.id)
    print(f"DB recipe: id={r.id}, name={repr(r.name)}", file=sys.stderr)

from app.rms import main as main_module
main_module.app.state.engine = engine
main_module.app.state.session_factory = factory

from fastapi.testclient import TestClient
with TestClient(main_module.app, raise_server_exceptions=False) as c:
    c.get("/healthz")
    r = c.get('/recetas')
    body = r.text

    # Extract all <td> contents from tbody
    import re
    rows = re.findall(r'<tbody>(.*?)</tbody>', body, re.S)
    if rows:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', rows[0], re.S)
        print(f"TD COUNT in tbody: {len(tds)}", file=sys.stderr)
        for i, td in enumerate(tds):
            clean = re.sub(r'<[^>]+>', '', td).strip()
            print(f"  TD[{i}]: {repr(clean[:60])}", file=sys.stderr)
    else:
        print("NO TBODY FOUND", file=sys.stderr)
        # Check if recipes were found
        if 'Galleta' in body:
            idx = body.find('Galleta')
            print(f"'Galleta' found at {idx}: {repr(body[idx-50:idx+100])}", file=sys.stderr)
        if 'Sin nombre' in body:
            idx = body.find('Sin nombre')
            print(f"'Sin nombre' found at {idx}: {repr(body[idx-100:idx+200])}", file=sys.stderr)
        # Show table area
        tbl = body.find('<table')
        if tbl >= 0:
            print(f"Table at {tbl}: {repr(body[tbl:tbl+500])}", file=sys.stderr)
