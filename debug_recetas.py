#!/usr/bin/env python3
"""Debug script to understand /recetas empty table issue."""
import sys, os
sys.path.insert(0, os.getcwd())

os.environ['DATABASE_URL'] = 'sqlite:///./test_recetas_debug.db'
os.environ['SASKIA_TEST_AUTH_DISABLED'] = '1'
os.environ['PYTHONPATH'] = os.getcwd()

from app.rms.db import init_db, make_engine, make_session_factory
from app.rms import db as dbmod

engine = make_engine(os.environ['DATABASE_URL'])
init_db(engine)
factory = make_session_factory(engine)

# Seed data
from tests.factories import make_ingredient, make_recipe, make_product, make_sale, ing_line
with factory() as s:
    flour = make_ingredient(s, name="Harina", unit="kg", stock_qty=2.0, purchase_price_gs=5000, min_stock_qty=1.0)
    egg = make_ingredient(s, name="Huevo", unit="und", stock_qty=20.0, purchase_price_gs=1500, min_stock_qty=0.0)
    recipe = make_recipe(s, name="Galleta", yield_qty=12.0, yield_unit="und",
                         lines=[ing_line(flour, qty=0.3, unit="kg"),
                                ing_line(egg, qty=2.0, unit="und")])
    product = make_product(s, name="Galleta", recipe=recipe, sale_price_gs=8000, portion_label="1 unidad")
    s.commit()
    print(f"Created recipe: id={recipe.id}, name={recipe.name}", file=sys.stderr)

# Now use the app
from app.rms import main as main_module
main_module.app.state.engine = engine
main_module.app.state.session_factory = factory

from fastapi.testclient import TestClient
with TestClient(main_module.app, raise_server_exceptions=False) as c:
    c.get("/healthz")  # prime csrf
    r = c.get('/recetas')
    print(f"STATUS: {r.status_code}", file=sys.stderr)
    body = r.text
    print(f"BODY LEN: {len(body)}", file=sys.stderr)
    
    # Check for table
    if '<table' in body:
        print("TABLE FOUND", file=sys.stderr)
        idx = body.find('<table')
        print(body[idx:idx+1000], file=sys.stderr)
    else:
        print("NO TABLE", file=sys.stderr)
        # Show content around 'recetas' in the body
        idx = body.lower().find('recetas')
        if idx >= 0:
            print(f"recetas found at {idx}:", repr(body[max(0,idx-50):idx+200]), file=sys.stderr)
        
        # Show what the body contains
        print(f"BODY[:1000]: {repr(body[:1000])}", file=sys.stderr)
