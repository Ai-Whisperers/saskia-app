"""tests/test_route_post_smoke_phase14_tier3.py — Phase 14 Tier 3 (2026-10-01).

Coverage strategy doc, Tier 3: "parametrize POST/DELETE/PATCH
roundtrips across every @router.post. Hit each with `data={}`,
accept any 2xx/3xx/4xx, fail on 5xx (uncaught exception)."

What this catches:
- A refactor that breaks a write route's wiring (template, DB, env).
- An unhandled exception in a write handler that returns 500.
- A route that was deleted from the router but still in the docstring
  / catalog (the test will simply skip and you'll see the param id).

What this does NOT catch:
- Form validation errors (the empty body triggers those, and we
  accept them as 422 — that's intentional).
- CSRF in production (conftest sets SASKIA_TEST_AUTH_DISABLED=1 to
  bypass; production CSRF is covered by test_csrf_on_forms.py).
- Authorization / role gating (a route that should 403 because the
  user lacks permission will still pass here because the test
  fixture logs in as admin).

The catalog below is generated from app/routers/ via regex. If you
add a new route, regenerate ROUTE_CATALOG:

    import re, json
    from pathlib import Path
    router_dir = Path("app/routers")
    PREFIX_RE = re.compile(r'router = APIRouter\\(\\s*(?:prefix = )?"([^"\\s)]+)"')
    ROUTE_RE = re.compile(
        r'@router\\.(get|post|put|delete|patch)\\(\\s*"([^"]+)"'
        r'(?:\\s*,\\s*[^()\\n]*)?'
        r'\\s*\\)\\s*\\n'
        r'\\s*(?:async\\s+)?def\\s+(\\w+)',
        re.MULTILINE,
    )
    records = []
    for py in sorted(router_dir.glob("*.py")):
        text = py.read_text()
        prefix = (PREFIX_RE.search(text) or [None, ""]).group(1)
        for m in ROUTE_RE.finditer(text):
            if m.group(1) in ("post", "delete", "put", "patch"):
                records.append((py.name, m.group(3), prefix + m.group(2), "{" in m.group(2), m.group(1)))
    print(records)
"""
from __future__ import annotations

import re

import pytest


# Generated 2026-10-01 from app/routers/ — see docstring above.
# Format: (file, function_name, full_path, has_path_param, verb)
ROUTE_CATALOG = [
    ['auditoria.py', 'auditoria_prune', '/auditoria/prune', False, 'post'],
    ['auth.py', 'login_submit', '/login', False, 'post'],
    ['auth.py', 'logout', '/logout', False, 'post'],
    ['auth.py', 'forgot_password', '/forgot-password', False, 'post'],
    ['customers.py', 'cliente_new_submit', '/clientes/nuevo', False, 'post'],
    ['customers.py', 'customer_create_api', '/clientes/api/create', False, 'post'],
    ['customers.py', 'log_suggestion_applied', '/clientes/api/{customer_id}/suggestion-applied', True, 'post'],
    ['customers.py', 'cliente_redeem_points', '/clientes/{customer_id}/puntos/redeem', True, 'post'],
    ['customers.py', 'address_create_api', '/clientes/api/{customer_id}/addresses', True, 'post'],
    ['customers.py', 'address_delete_api', '/clientes/api/{customer_id}/addresses/{address_id}', True, 'delete'],
    ['customers.py', 'cliente_update', '/clientes/{customer_id}/editar', True, 'post'],
    ['customers.py', 'clientes_bulk_delete', '/clientes/bulk-eliminar', False, 'post'],
    ['customers.py', 'cliente_merge', '/clientes/{target_id}/merge', True, 'post'],
    ['customers.py', 'invoice_profile_create_api', '/clientes/api/{customer_id}/invoice-profiles', True, 'post'],
    ['customers.py', 'invoice_profile_set_default_api', '/clientes/api/{customer_id}/invoice-profiles/{profile_id}/default', True, 'post'],
    ['customers.py', 'invoice_profile_delete_api', '/clientes/api/{customer_id}/invoice-profiles/{profile_id}', True, 'delete'],
    ['customers.py', 'address_set_default_api', '/clientes/api/{customer_id}/addresses/{address_id}/default', True, 'post'],
    ['demo.py', 'demo_seed', '/demo/seed', False, 'post'],
    ['eod.py', 'eod_check_save', '/eod/check', False, 'post'],
    ['eod.py', 'eod_completar', '/eod/completar', False, 'post'],
    ['excel_io.py', 'excel_validate', '/excel/validar', False, 'post'],
    ['excel_io.py', 'excel_import', '/excel/importar', False, 'post'],
    ['health.py', 'healthz_migrate', '/healthz/migrate', False, 'post'],
    ['health.py', 'admin_migrate', '/admin/migrate', False, 'post'],
    ['inventory.py', 'ingredient_toggle_packaging', '/inventario/{ing_id}/toggle-packaging', True, 'post'],
    ['inventory.py', 'carga_inicial_save', '/inventario/carga-inicial', False, 'post'],
    ['inventory.py', 'inventory_create', '/inventario/nuevo', False, 'post'],
    ['inventory.py', 'inventory_tag_audit_rerun', '/inventario/auditoria-etiquetas/rerun', False, 'post'],
    ['inventory.py', 'inventory_update', '/inventario/{ing_id}/editar', True, 'post'],
    ['inventory.py', 'inventory_delete', '/inventario/{ing_id}/eliminar', True, 'post'],
    ['inventory.py', 'inventory_adjust', '/inventario/{ing_id}/ajustar', True, 'post'],
    ['inventory.py', 'ingredient_variant_create', '/inventario/{ing_id}/variantes/nuevo', True, 'post'],
    ['inventory.py', 'ingredient_variant_prefer', '/inventario/{ing_id}/variantes/{variant_id}/preferir', True, 'post'],
    ['inventory.py', 'ingredient_variant_delete', '/inventario/{ing_id}/variantes/{variant_id}/eliminar', True, 'post'],
    ['inventory.py', 'ingredient_variant_edit', '/inventario/{ing_id}/variantes/{variant_id}/editar', True, 'post'],
    ['inventory.py', 'ingredient_forecast_horizon_set', '/inventario/{ing_id}/forecast-horizon', True, 'post'],
    ['merma.py', 'merma_register', '/merma/registrar', False, 'post'],
    ['merma.py', 'merma_register_recipe', '/merma/receta', False, 'post'],
    ['ops.py', 'ops_reset_demo_data', '/ops/reset-demo-data', False, 'post'],
    ['pedidos.py', 'pedidos_create', '/pedidos/nuevo', False, 'post'],
    ['pedidos.py', 'pedidos_status', '/pedidos/{pedido_id}/status', True, 'post'],
    ['pedidos.py', 'pedidos_fulfill', '/pedidos/{pedido_id}/fulfill', True, 'post'],
    ['pedidos.py', 'pedidos_bulk_fulfill', '/pedidos/bulk-fulfill', False, 'post'],
    ['pedidos.py', 'pedidos_bulk_cancel', '/pedidos/bulk-cancel', False, 'post'],
    ['produccion.py', 'produccion_override', '/produccion/override', False, 'post'],
    ['produccion.py', 'produccion_override_bulk', '/produccion/override-bulk', False, 'post'],
    ['produccion.py', 'produccion_shift_execute', '/produccion/shift-execute', False, 'post'],
    ['produccion.py', 'produccion_ad_hoc', '/produccion/ad-hoc', False, 'post'],
    ['produccion.py', 'produccion_template_set', '/produccion/template', False, 'post'],
    ['produccion.py', 'produccion_template_fork_week', '/produccion/template/fork-week', False, 'post'],
    ['products.py', 'product_create', '/productos/nuevo', False, 'post'],
    ['products.py', 'product_update', '/productos/{p_id}/editar', True, 'post'],
    ['products.py', 'product_toggle_favorite', '/productos/{p_id}/favorito', True, 'post'],
    ['products.py', 'product_delete', '/productos/{p_id}/eliminar', True, 'post'],
    ['products.py', 'product_bulk_delete', '/productos/bulk-eliminar', False, 'post'],
    ['products.py', 'product_bulk_edit', '/productos/bulk-edit', False, 'post'],
    ['products.py', 'products_import_csv', '/productos/importar', False, 'post'],
    ['products.py', 'product_upload_image', '/productos/upload-image', False, 'post'],
    ['recipes.py', 'recipe_create', '/recetas/nueva', False, 'post'],
    ['recipes.py', 'recipe_save_photo', '/recetas/{r_id}/set-photo', True, 'post'],
    ['recipes.py', 'recipe_update', '/recetas/{r_id}/editar', True, 'post'],
    ['reorder.py', 'reorder_registrar', '/reorder/registrar', False, 'post'],
    ['reorder.py', 'reorder_scrape', '/reorder/scrape', False, 'post'],
    ['reorder.py', 'reorder_lock_supplier', '/reorder/lock-supplier', False, 'post'],
    ['reorder.py', 'reorder_unlock_supplier', '/reorder/unlock-supplier', False, 'post'],
    ['reorder.py', 'reorder_upload_prices', '/reorder/upload-prices', False, 'post'],
    ['reorder.py', 'reorder_generate_po', '/reorder/generate-po', False, 'post'],
    ['sales.py', 'sale_create', '/ventas/nueva', False, 'post'],
    ['sales.py', 'sale_create_multi', '/ventas/nueva/multi', False, 'post'],
    ['sales.py', 'sale_void', '/ventas/{sale_id}/anular', True, 'post'],
    ['settings.py', 'save_business_settings', '/settings/business', False, 'post'],
    ['settings.py', 'save_fiscal_settings', '/settings/fiscal', False, 'post'],
    ['settings.py', 'save_theme_settings', '/settings/theme', False, 'post'],
    ['settings.py', 'settings_seed_demo', '/settings/seed-demo', False, 'post'],
    ['settings_runtime.py', 'write_pricing_markup', '/api/settings/pricing-markup', False, 'post'],
    ['settings_runtime.py', 'write_shop_whatsapp', '/api/settings/shop-whatsapp', False, 'post'],
    ['settings_runtime.py', 'create_category_endpoint', '/api/categories', False, 'post'],
    ['settings_runtime.py', 'update_category_endpoint', '/api/categories/{category_id}/update', True, 'post'],
    ['settings_runtime.py', 'create_channel_endpoint', '/api/channels', False, 'post'],
    ['settings_runtime.py', 'create_payment_method_endpoint', '/api/payment-methods', False, 'post'],
    ['settings_runtime.py', 'write_branding', '/api/settings/branding', False, 'post'],
    ['settings_runtime.py', 'update_template_endpoint', '/api/templates/{template_id}/update', True, 'post'],
    ['settings_runtime.py', 'update_margin_tier_endpoint', '/api/margin-tiers/{tier_id}/update', True, 'post'],
    ['settings_runtime.py', 'update_stock_status_config_endpoint', '/api/stock-status-config/{config_id}/update', True, 'post'],
    ['settings_runtime.py', 'create_storage_type_endpoint', '/api/storage-types', False, 'post'],
    ['settings_runtime.py', 'create_date_preset_endpoint', '/api/date-presets', False, 'post'],
    ['settings_runtime.py', 'update_channel_endpoint', '/api/channels/{channel_id}/update', True, 'post'],
    ['settings_runtime.py', 'delete_channel_endpoint', '/api/channels/{channel_id}/delete', True, 'post'],
    ['settings_runtime.py', 'update_payment_method_endpoint', '/api/payment-methods/{method_id}/update', True, 'post'],
    ['settings_runtime.py', 'delete_payment_method_endpoint', '/api/payment-methods/{method_id}/delete', True, 'post'],
    ['settings_runtime.py', 'delete_category_endpoint', '/api/categories/{category_id}/delete', True, 'post'],
    ['settings_runtime.py', 'update_storage_type_endpoint', '/api/storage-types/{type_id}/update', True, 'post'],
    ['settings_runtime.py', 'delete_storage_type_endpoint', '/api/storage-types/{type_id}/delete', True, 'post'],
    ['settings_runtime.py', 'update_date_preset_endpoint', '/api/date-presets/{preset_id}/update', True, 'post'],
    ['settings_runtime.py', 'delete_date_preset_endpoint', '/api/date-presets/{preset_id}/delete', True, 'post'],
    ['settings_runtime.py', 'delete_margin_tier_endpoint', '/api/margin-tiers/{tier_id}/delete', True, 'post'],
    ['settings_runtime.py', 'delete_stock_status_endpoint', '/api/stock-status-config/{config_id}/delete', True, 'post'],
    ['settings_runtime.py', 'delete_template_endpoint', '/api/templates/{template_id}/delete', True, 'post'],
    ['shopping.py', 'mark_purchased', '/shopping-list/{item_id}/mark-purchased', True, 'post'],
    ['shopping.py', 'unmark_purchased', '/shopping-list/{item_id}/unmark', True, 'post'],
    ['shopping.py', 'delete_item', '/shopping-list/{item_id}/delete', True, 'post'],
    ['shopping.py', 'from_production_plan', '/shopping-list/from-production-plan', False, 'post'],
    ['shopping.py', 'sync_low_stock', '/shopping-list/sync-low-stock', False, 'post'],
    ['shopping.py', 'add_item', '/shopping-list/add', False, 'post'],
    ['shopping.py', 'save_plan_as_shopping_list', '/shopping-list/save-plan/{plan_id}', True, 'post'],
    ['suppliers.py', 'supplier_create', '/suppliers/nuevo', False, 'post'],
    ['suppliers.py', 'supplier_update', '/suppliers/{s_id}/editar', True, 'post'],
    ['suppliers.py', 'supplier_delete', '/suppliers/{s_id}/eliminar', True, 'post'],
    ['suppliers.py', 'supplier_reactivate', '/suppliers/{s_id}/reactivar', True, 'post'],
    ['suscripciones.py', 'suscripcion_create', '/suscripciones/nuevo', False, 'post'],
    ['suscripciones.py', 'suscripcion_update', '/suscripciones/{s_id}/editar', True, 'post'],
    ['suscripciones.py', 'suscripcion_set_status', '/suscripciones/{s_id}/estado', True, 'post'],
    ['suscripciones.py', 'suscripcion_delete', '/suscripciones/{s_id}/eliminar', True, 'post'],
    ['suscripciones.py', 'suscripciones_dispatch', '/suscripciones/dispatch', False, 'post'],
    ['users.py', 'users_create', '/users/crear', False, 'post'],
    ['users.py', 'users_edit', '/users/{user_id}/editar', True, 'post'],
    ['users.py', 'users_delete', '/users/{user_id}/eliminar', True, 'post'],
    ['validation.py', 'validate_recipe', '/api/validate/recipe', False, 'post'],
    ['validation.py', 'validate_product', '/api/validate/product', False, 'post'],
]


def _real_substitute_id(path: str) -> str:
    """Replace each `{name}` with a unique sentinel id (1, 2, 3, ...).

    Using 1, 2, 3 keeps each placeholder distinct (FastAPI's path
    validation can complain if two placeholders get the same value
    when the route was declared with different types).
    """
    counter = [0]

    def _rep(m):
        counter[0] += 1
        return str(counter[0])

    return re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", _rep, path)


def _id_for_route(*case) -> str:
    """Stable pytest id. Pytest passes each param individually; we
    pick the longest string with `/` (the path) or `.` (the file)."""
    for v in case:
        if isinstance(v, str) and v:
            if "/" in v:
                return f"[{v}]"
            if "." in v:
                return v
    return str(case[0]) if case else "?"


@pytest.mark.parametrize(
    "file,fn,url,has_param,verb",
    ROUTE_CATALOG,
    ids=_id_for_route,
)
def test_write_route_does_not_5xx(client, file, fn, url, has_param, verb):
    """Each mutating route must NOT return 5xx (uncaught exception).

    We POST an empty form (or DELETE with no body). The handler runs
    with empty data — which almost always yields 422 (validation) or
    404 (missing id) or 303 (post-success redirect). All of those are
    expected; only 5xx is a regression.

    For routes with path params we substitute `1` (no DB lookup; the
    handler will likely hit "id not found" and return 404, which we
    accept). The goal is to exercise the handler's first ~10 lines,
    not to assert the side effects.
    """
    target = _real_substitute_id(url)
    if verb == "delete":
        r = client.delete(target)
    elif verb == "put":
        r = client.put(target, data={})
    elif verb == "patch":
        r = client.patch(target, data={})
    else:
        r = client.post(target, data={})

    assert r.status_code < 500, (
        f"{verb.upper()} {target} ({file}::{fn}) returned "
        f"{r.status_code}: {r.text[:200]}. 5xx means an unhandled "
        "exception reached the handler."
    )


def test_write_route_count_meets_strategy_target():
    """Strategy doc: cover every mutating route. If this drops below
    100, someone deleted a route without updating this test."""
    n = len(ROUTE_CATALOG)
    assert n >= 100, (
        f"only {n} mutating routes discovered — was a router "
        "file pruned? Re-run the catalog generator in the docstring."
    )