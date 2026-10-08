"""app/rms/messages.py — User-facing error/success messages.

Centralized so:
- Spanish (vos) wording stays consistent across all pages
- Messages can be i18n-extracted later by switching the lookup
- No more typos / inconsistent capitalization in inline strings

Each constant is a short user-facing string. Use these instead of
hardcoded f-strings in router bodies.
"""

from __future__ import annotations

# ─── Generic ─────────────────────────────────────────────────────
OK = "Listo."
CANCELLED = "Operación cancelada."
INVALID_INPUT = "Revisá los datos e intentá de nuevo."

# ─── Auth ────────────────────────────────────────────────────────
LOGIN_REQUIRED = "Necesitás iniciar sesión para acceder."
INVALID_CREDENTIALS = "Email o contraseña incorrectos."
SESSION_EXPIRED = "Tu sesión expiró. Volvé a iniciar sesión."

# ─── Pedidos ─────────────────────────────────────────────────────
PEDIDO_NOT_FOUND = "Pedido no encontrado."
PEDIDO_DELETED = "Pedido eliminado."
PEDIDO_STATUS_CHANGED = "Estado del pedido actualizado."
PEDIDO_INVALID_STATUS = "Estado de pedido inválido."
PEDIDO_LINE_REMOVED = "Línea eliminada del pedido."
PEDIDO_MIN_ORDER_NOT_MET = "Pedido no alcanza el mínimo de la zona de delivery."

# ─── Recetas ─────────────────────────────────────────────────────
RECIPE_NOT_FOUND = "Receta no encontrada."
RECIPE_DELETED = "Receta eliminada."
RECIPE_IMAGE_UPDATED = "Foto de receta actualizada."
RECIPE_DUPLICATE_LINE = "Esa receta ya tiene esa línea de ingrediente."
RECIPE_INVALID_YIELD = "El rendimiento debe ser mayor a cero."
RECIPE_LINE_QTY_POSITIVE = "La cantidad debe ser mayor a cero."
RECIPE_NAME_REQUIRED = "El nombre de la receta es obligatorio."
RECIPE_INVALID_UNIT = "Unidad inválida."
RECIPE_DUPLICATE_NAME = "Ya existe una receta con ese nombre."
RECIPE_LINES_REQUIRED = "La receta debe tener al menos un ingrediente o sub-receta."
RECIPE_CYCLE_DETECTED = "Las sub-recetas crean una dependencia cíclica."

# ─── Ingredientes / Inventario ──────────────────────────────────
INGREDIENT_NOT_FOUND = "Ingrediente no encontrado."
INGREDIENT_NEGATIVE_STOCK = "El stock no puede ser negativo."
INGREDIENT_DUPLICATE_NAME = "Ya existe un ingrediente con ese nombre."
INGREDIENT_DELETED = "Ingrediente eliminado."
INGREDIENT_NAME_REQUIRED = "El nombre del ingrediente es obligatorio."

# ─── Clientes ────────────────────────────────────────────────────
CUSTOMER_NOT_FOUND = "Cliente no encontrado."
CUSTOMER_DUPLICATE_PHONE = "Ya existe un cliente con ese teléfono."
CUSTOMER_DELETED = "Cliente eliminado."

# ─── Productos ───────────────────────────────────────────────────
PRODUCT_NOT_FOUND = "Producto no encontrado."
PRODUCT_HAS_SALES = "No se puede eliminar un producto con ventas registradas."
PRODUCT_DELETED = "Producto eliminado."

# ─── Ventas ──────────────────────────────────────────────────────
SALE_NOT_FOUND = "Venta no encontrada."
SALE_INVALID_CHANNEL = "Canal de venta inválido."
SALE_DELETED = "Venta eliminada."
SALE_SKU_REQUIRED = "Indicá el SKU del producto."
SALE_SKU_NOT_FOUND = "SKU no encontrado."
SALE_PRODUCT_OR_SKU_REQUIRED = "Elegí un producto o escaneá un SKU."
SALE_QTY_TOO_HIGH = "La cantidad no puede ser mayor al máximo permitido."
SALE_DISCOUNT_TOO_HIGH = "El descuento no puede ser mayor al máximo permitido."
SALE_INVALID_DATE = "Fecha de venta inválida."
SALE_INVALID_PAYMENT_METHOD = "Forma de pago inválida."
SALE_CUSTOMER_NOT_FOUND = "El cliente seleccionado no existe."
SALE_RATE_LIMITED = "Demasiadas ventas en poco tiempo. Esperá un momento."
# SASKIA-MIG-2: pre-shift session gate. Cash sales need an open arqueo
# so the cierre-Z can compute expected = opening + efectivo del período.
# Non-cash sales (QR, transferencia, fiado) are NOT blocked.
SALE_CASH_SESSION_REQUIRED = (
    "Para registrar ventas en efectivo necesitás abrir la caja. "
    "Abrí la caja acá o cambiá el método de pago."
)
SALE_BODY_INVALID = "Cuerpo de petición inválido."
SALE_TOO_MANY_ITEMS = "Máximo 50 ítems por venta."

# ─── Mermas ──────────────────────────────────────────────────────
WASTE_NOT_FOUND = "Registro de merma no encontrado."
WASTE_DELETED = "Merma eliminada."
WASTE_REASON_REQUIRED = "Indicá el motivo de la merma."

# ─── Usuarios ────────────────────────────────────────────────────
USER_NOT_FOUND = "Usuario no encontrado."
USER_ALREADY_EXISTS = "Ya existe un usuario con ese email."
USER_DEACTIVATED = "Usuario desactivado."
USER_ROLE_REQUIRED = "Indicá el rol del usuario."
USER_DELETED = "Usuario eliminado."

# ─── Settings ────────────────────────────────────────────────────
SETTING_NOT_FOUND = "Configuración no encontrada."
SETTING_INVALID_VALUE = "Valor inválido para esta configuración."

# ─── Herebus (Drive integration) ────────────────────────────────
WISHLIST_ITEM_NOT_FOUND = "Item de wishlist no encontrado."
WISHLIST_ITEM_PURCHASED = "Item marcado como comprado."
RISK_NOT_FOUND = "Riesgo no encontrado."
BENCHMARK_NOT_FOUND = "Benchmark no encontrado."
BENCHMARK_UPDATED = "Benchmark actualizado."
BANK_TX_NOT_FOUND = "Transacción bancaria no encontrada."
BANK_CATEGORY_UPDATED = "Categoría actualizada."
BANK_ADDED = "Transacción registrada."
DELIVERY_ZONE_NOT_FOUND = "Zona de delivery no encontrada."
SHOPPING_LIST_ITEM_NOT_FOUND = "Item de lista de compras no encontrado."
SHOPPING_LIST_PURCHASED = "Item marcado como comprado."
SHOPPING_LIST_DELETED = "Item eliminado de la lista."
SHOPPING_LIST_UNMARKED = "Marcamos el item como pendiente de nuevo."

# ─── Generic helpers ─────────────────────────────────────────────


def with_detail(msg: str, detail: str) -> str:
    """Append a parenthetical detail to a message.

    >>> with_detail(PRODUCT_DELETED, "Tarta de manzana")
    'Producto eliminado. (Tarta de manzana)'
    """
    return f"{msg} ({detail})"


def with_id(msg: str, entity_id: int | str) -> str:
    """Append an entity id to a message."""
    return f"{msg} #{entity_id}."
