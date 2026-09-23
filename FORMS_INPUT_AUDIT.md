# Saskia RMS — Form & Input Audit (2026-09-23)

## Input types in use across the app

| Pattern | Where | Notes |
|---|---|---|
| `<input type="text">` | Most fields | Standard, predictable |
| `<input type="number">` | Prices, quantities, durations | step/min/max attrs correct |
| `<input type="email/password/url/date/time/tel/search">` | Login, image URL, search | Use native validation |
| `<input type="checkbox">` | is_available, dead-only, etc. | Mostly OK, but **many lack explicit `value`** (form posts "on" or nothing) |
| `<input type="hidden">` | Many | Used by combos for value storage |
| `<textarea>` | Notes, audit, descriptions | rows="2-4" mostly |
| `<select>` | Almost none! | **0 native selects in entire codebase** — everything is custom combo or text |
| `saskia-combo` | Recipe line items, customer picker, family, etc. | Custom widget, good UX |
| Tag picker (NEW) | Categoría + Etiquetas + Etiquetas dietarias | Pre-made pills + custom add |

## Problems identified

### 1. **Inconsistent category entry**
- `product.category` was free-text → "Panadería" vs "Panaderia" vs "panadería" become 3 separate categories in the DB
- `recipe.family` was combo but with empty options → operator typed everything
- **FIX**: Both now use pre-populated option lists with allow-custom fallback

### 2. **Inconsistent tag entry**
- `product.tags` and `recipe.dietary_tags` were free-text comma-separated
- Typos, inconsistent naming, no discovery
- **FIX**: Both now use toggle pills with pre-built Paraguayan bakery tags + custom input

### 3. **Tags have no visual feedback in the UI**
- The productos.html page shows `tags` column with no styling
- Tags are stored as "varios, populares, sin-gluten" as a raw string
- **RECOMMENDATION**: Add a `badge` render in the productos.html table

### 4. **Category filter on /productos is text-only**
- `/productos?category=Panadería` works but the dropdown is just a combo
- **RECOMMENDATION**: Add category as a filterable facet with chip-style multi-select

### 5. **No empty-state for tags**
- If `recipe.dietary_tags` is empty, the form shows nothing
- **RECOMMENDATION**: Show "Sin etiquetas dietarias" with subtle styling

### 6. **Long tag strings break layout**
- If a user types "tag-with-a-very-long-name-that-keeps-going", the pill width grows
- **FIX**: Already in our CSS via `padding` and `flex-wrap`

### 7. **No validation feedback on tag count**
- Recipe can have unlimited tags; should cap at ~10 for usability
- **RECOMMENDATION**: Add max-tag warning when >10 are selected

### 8. **Form buttons inconsistently labeled**
- Most forms use "Guardá" (Argentine voseo) which is great for the user
- But some use "Save" or "Submit" in code paths
- **RECOMMENDATION**: Audit all button labels

### 9. **No tooltips on icon-only buttons**
- The Edit/Delete icons in tables lack `title` attributes for hover hints
- **RECOMMENDATION**: Add titles for accessibility

### 10. **Loading states not always shown**
- Form submit doesn't disable the button or show spinner
- Could lead to double-submits
- **RECOMMENDATION**: Add `.is-loading` class on submit

## What was changed in this commit

1. **NEW** `app/templates/_components/tags.html` — reusable tag_picker + category_picker macros with pre-built catalogs:
   - Product categories (Panadería, Pastelería, Dulces, Bollería, Bebidas, Lácteos, Salados, Congelados, Especiales, Temporada, Sin TACC, Vegano, Light)
   - Recipe families (similar + Tortas, Masas, Rellenos, Coberturas, Salsas, Bases)
   - Product tags (Nuevo, Popular, Oferta, Temporada, Vegano, Sin gluten, etc.)
   - Dietary tags (Sin gluten, Sin lactosa, Vegano, Vegetariano, Sin azúcar, Integral, Orgánico, Sin TACC, Bajo en sodio, Bajo en grasa, Kosher, Sin frutos secos, Sin huevo)

2. **UPDATED** `producto_form.html`:
   - Categoría: free-text → searchable combo with pre-built options + allow-custom
   - Etiquetas: free-text comma-separated → toggle pills + custom add

3. **UPDATED** `receta_form.html`:
   - Familia: empty combo → pre-populated with recipe families
   - Etiquetas dietarias: free-text → 13 pre-built pills + custom add

4. **UPDATED** `app/static/app.css` — added global `.tag-pill` styles

5. **UPDATED** `app/static/app.js` — added `initTagPickers()` that auto-wires any `.tag-picker` element

## Backward compatibility

- Storage format unchanged: `tags` and `category` and `dietary_tags` are still comma-separated Text columns
- Existing data with comma-separated values displays correctly (each tag becomes its own pill)
- Forms work the same on submit (just visually different input)

## Pre-made catalogs: extensibility

To add a new category/tag, edit `app/templates/_components/tags.html`:
- `product_category_options()` — product categories
- `recipe_family_options()` — recipe families
- `product_tag_options()` — product tags
- `dietary_tag_options()` — dietary tags

Each is a Jinja list. Add new entries freely.
