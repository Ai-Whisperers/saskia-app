-- Recipe Audit SQL Scripts
-- Run against /data/rms.sqlite (VPS) inside the container:
-- docker exec <container> /opt/venv/bin/python <this_script>.py
-- Or via sqlite3 directly:
-- docker exec <container> sqlite3 /data/rms.sqlite < script.sql

-- ============================================================
-- RECIPE COMPLETENESS AUDIT — VPS LIVE DATABASE
-- Run: docker exec $(docker ps -q --filter name=saskia-vps | head -1) \
--   /opt/venv/bin/python saskia-final-verify.py
-- ============================================================

-- ============================================================
-- CHANGES APPLIED IN BATCH (2026-09-29)
-- ============================================================

-- 1. ALLERGENS — filled NULL for all 20 recipes
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=1;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=2;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten, Nuez' WHERE id=3;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=4;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=5;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten, Frutilla' WHERE id=6;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=7;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten, Pasas' WHERE id=8;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=9;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=10;
UPDATE recipe SET allergens='Gluten' WHERE id=11;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=12;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=13;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=14;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=15;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten' WHERE id=16;
UPDATE recipe SET allergens='Gluten' WHERE id=17;
UPDATE recipe SET allergens='Huevo, Lácteo, Gluten, Nuez, Pasas' WHERE id=18;
UPDATE recipe SET allergens='Huevo, Gluten, Cebolla, Ajo' WHERE id=19;
UPDATE recipe SET allergens='Soja, Gluten' WHERE id=20;

-- 2. FAMILY — categorized all 20 recipes
UPDATE recipe SET family='Muffin' WHERE id IN (1,2,3,14);
UPDATE recipe SET family='Cheesecake' WHERE id IN (4,15);
UPDATE recipe SET family='Hojaldre' WHERE id=5;
UPDATE recipe SET family='Tarta' WHERE id IN (6,18);
UPDATE recipe SET family='Galleta' WHERE id=7;
UPDATE recipe SET family='Rosquilla' WHERE id=8;
UPDATE recipe SET family='Pan dulce' WHERE id IN (9,17);
UPDATE recipe SET family='Waffle' WHERE id IN (10,16);
UPDATE recipe SET family='Pan' WHERE id=11;
UPDATE recipe SET family='Factura' WHERE id=12;
UPDATE recipe SET family='Brownie' WHERE id=13;
UPDATE recipe SET family='Salchicha' WHERE id=19;
UPDATE recipe SET family='Salsa' WHERE id=20;
UPDATE recipe SET family='Cobertura' WHERE id=21;

-- 3. DIFFICULTY — fixed invalid values 4, 5 → 3, 2
UPDATE recipe SET difficulty=3 WHERE id=13 AND difficulty=5;
UPDATE recipe SET difficulty=2 WHERE id=18 AND difficulty=4;

-- 4. NOTES — filled for 12 recipes missing them
UPDATE recipe SET notes='Muffins horneados a 180°C. Rinde 12 unidades. Masa suave y húmeda.' WHERE id=1;
UPDATE recipe SET notes='Muffins de chocolate con chips. Hornear a 180°C por 25-30 min.' WHERE id=2;
UPDATE recipe SET notes='Muffins con trozos de nueces. Hornear a 180°C por 25-30 min.' WHERE id=3;
UPDATE recipe SET notes='Cheesecake horneado a baño María 160°C 50-60 min, luego refrigerate 4+ horas.' WHERE id=4;
UPDATE recipe SET notes='Hojaldre dulce enrollado con dulce de leche. Horno 200°C 15-20 min.' WHERE id=5;
UPDATE recipe SET notes='Tarta holandesa de manzanas. Horno 180°C 35-40 min hasta dorar.' WHERE id=6;
UPDATE recipe SET notes='Galletas neerlandesas de mantequilla. Horno 160°C 12-15 min.' WHERE id=7;
UPDATE recipe SET notes='Rosquillas holandesas fritas. Freír a 175°C 3-4 min por lado.' WHERE id=8;
UPDATE recipe SET notes='Pan dulce trenzado con chocolate. Horno 175°C 30-35 min.' WHERE id=9;
UPDATE recipe SET notes='Waffles holandeses con sirope. Plancha a 180°C 3-4 min.' WHERE id=10;
UPDATE recipe SET notes='Pan lactal casero. Horno 190°C 25-30 min. Molde rectangular.' WHERE id=11;
UPDATE recipe SET notes='Facturas típicas paraguayas. Horno 190°C 15-20 min. Rinde ~24 unidades.' WHERE id=12;

-- 5. RECIPE_PRICING — filled for 13 recipes missing it
-- Formula: cost_total=sum(qty*purchase_price) + labor(min*1500Gs) + packaging
-- Insert format:
-- INSERT INTO recipe_pricing (recipe_id, cost_total_gs, labor_gs, packaging_gs,
--   cost_per_unit_gs, wholesale_gs, private_label_gs, distributor_gs, retail_gs,
--   broker_commission_gs, notes, updated_at)
-- VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);

-- 6. UNIT FIXES — 82 recipe_lines had unit mismatch
-- g→kg for ingredients priced per kg; ml→L for ingredients priced per L
-- Fixed by: UPDATE recipe_line SET qty=qty/1000, line_unit='kg' WHERE id IN (...);
-- Affected recipes: 13, 14, 15, 16, 17, 18, 19, 20, 21

-- 7. SUB-RECETA CREATED — Glaseado de queso crema (id=21)
-- Created as recipe id=21, linked to Carrot Cake (18) as sub_recipe

-- ============================================================
-- KNOWN ISSUES STILL PENDING
-- ============================================================

-- RECIPE 13 (brownie_espresso): recipe_lines contain ~19 non-brownie ingredients
-- (pollo, panceta, cebolla, ajo, ketjap, salsa soja, pan rallado, etc.)
-- These are carryover from frikandel or another recipe merge
-- Action: Manual review of recipe_lines 81-124, delete wrong ingredients
-- After fix, recalculate recipe_pricing for recipe 13
-- CORRECT cost should be ~8.8M Gs (currently shows 12.2M Gs due to bad lines)

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Check all recipes:
-- SELECT id, name, family, allergens, difficulty,
--        CASE WHEN difficulty NOT IN (1,2,3) THEN 'BAD' ELSE 'OK' END as diff_ok,
--        CASE WHEN allergens IS NULL THEN 'MISSING' ELSE 'OK' END as allerg_ok,
--        CASE WHEN family IS NULL THEN 'MISSING' ELSE 'OK' END as family_ok,
--        CASE WHEN notes IS NULL THEN 'MISSING' ELSE 'OK' END as notes_ok
-- FROM recipe ORDER BY id;

-- Check pricing:
-- SELECT r.id, r.name, rp.cost_total_gs, rp.cost_per_unit_gs, rp.wholesale_gs, rp.retail_gs
-- FROM recipe r LEFT JOIN recipe_pricing rp ON rp.recipe_id = r.id
-- ORDER BY r.id;

-- Check sub-recetas:
-- SELECT r.name, sr.name as sub_recipe, rl.qty, rl.line_unit
-- FROM recipe_line rl
-- JOIN recipe r ON r.id = rl.recipe_id
-- JOIN recipe sr ON sr.id = rl.line_ref_id AND rl.line_kind = 'sub_recipe'
-- ORDER BY r.id;
