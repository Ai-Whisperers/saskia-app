"""app/rms/seed/sazon.py — Complete seed data for the first test business.

This is the **multi-tenant** seeder. The "demo" seeder (`seed/demo.py`) was
a single-tenant demo; this one creates a fully populated business: ingredients,
recipes, products, customers, sales, pedidos, production plans, HACCP records,
compliance, suppliers, and more.

Default tenant: **La Vaquita Holandesa** (slug: `la-vaquita-holandesa`).
Default operator: **Saskia** (username: `saskia`, password: `saskia1234`).

Idempotency: each block skips rows that already exist (matched by natural key).
To force a fresh seed, delete the rows first via the test reset or call
seed_all() with `overwrite=True`.

What this seeds (full coverage so every page has real data):
  - Tenant (1 row, default + Saskia tenant)
  - User (1 admin, 2 cashiers)
  - SettingsKV (BRANDING + OPERATIONS group populated)
  - Categories: 6 product + 5 recipe_family
  - Payment methods: efectivo, transferencia, tarjeta, qr, pedidoya
  - Margin tiers: top10, top25, mid, low, very-low
  - Stock status config: bajo, critico, sobrestock, muerto
  - Storage types: ambient, refrigerated, frozen, dry
  - Storage keywords: harina→dry, leche→refrigerated, etc.
  - Date range presets: hoy, ayer, 7d, 30d, MTD, QTD, YTD, año-pasado
  - Message templates: pedido.confirmado, pedido.listo, etc.
  - Delivery zones: 4 zones with km radius + cost
  - Compliance info: RUC, timbrado, INAN, etc.
  - Suppliers: 5 suppliers (harina, lácteos, frutas, etc.)
  - Ingredients: 50+ (panadería, pastelería, lácteos, frutas, chocolates, etc.)
  - Ingredient variants: 1-2 per ingredient with preferred supplier
  - Ingredient price events: 1-3 historical prices per ingredient
  - Recipes: 20+ (muffin, cheesecake, hojaldre, etc.)
  - Products: 40+ across all categories
  - Customers: 15 with names, phones, cedula, addresses, dietary notes
  - Tags: popular, premium, docena, vegano, sin-gluten, sin-lactosa
  - Production plan templates: weekly schedule
  - Production completions: 7 days of completions
  - Pedidos: 12+ across all statuses (pending/confirmed/ready/fulfilled)
  - Sales: 90 days of varied sales with realistic velocity
  - Stock movements: tied to sales + waste + initial
  - Waste log: 8 entries (rotura, merma, etc.)
  - Shopping list: 5 items to reorder
  - HACCP: freezer temp log (last 14 days)
  - Market benchmarks: 20+ items vs market
  - Audit log: a few initial entries
"""

from __future__ import annotations

import math
import random
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.models import (
    AppMeta,
    AuditLog,
    BankTransaction,
    Category,
    Channel,
    ComplianceInfo,
    Customer,
    CustomerAddress,
    DateRangePreset,
    DeliveryZone,
    FreezerTemperatureLog,
    ImportBatch,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    MarginTier,
    MarketBenchmark,
    MessageTemplate,
    PaymentMethod,
    Pedido,
    PedidoEvent,
    PedidoLine,
    PriceHistory,
    Product,
    ProductionCompletion,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    Sale,
    SettingsKV,
    ShoppingListItem,
    StockMovement,
    StockStatusConfig,
    StorageKeyword,
    StorageType,
    Supplier,
    Tag,
    TagLink,
    Tenant,
    User,
    WasteLog,
)
from app.rms.tagging.model import TagKind
from app.rms.tagging.ensure import ensure_starter_tags, ensure_tag, tag_target

# === Tenant / user constants ===

TENANT_SLUG = "la-vaquita-holandesa"
TENANT_NAME = "La Vaquita Holandesa"
TENANT_COLOR = "#7b3f00"  # warm brown
TENANT_CURRENCY = "Gs."

# Default tenant for backward compat (single-tenant code paths)
DEFAULT_TENANT_SLUG = "default"

# Saskia (operator) credentials
SASKIA_USER = "saskia"
SASKIA_PASSWORD = "saskia1234"  # noqa: S105
SASKIA_EMAIL = "saskia@lavaquita.example"
SASKIA_FULL_NAME = "Saskia Weiss"

# Cashier accounts
CASHIER_USERS = [
    ("lucia", "lucia1234", "Lucía Fernández", "lucia@lavaquita.example"),
    ("diego", "diego1234", "Diego Cabral", "diego@lavaquita.example"),
]


# === Data tables ===

# Categories (scope: 'product')
CATEGORIES_PRODUCT: list[tuple[str, int, bool]] = [
    # (name, sort_order, is_active)
    ("Panadería", 10, True),
    ("Pastelería", 20, True),
    ("Salados", 30, True),
    ("Bebidas", 40, True),
    ("Especiales", 50, True),
    ("Tortas", 60, True),
]

# Categories (scope: 'recipe_family')
CATEGORIES_RECIPE: list[tuple[str, int, bool]] = [
    ("Masa dulce", 10, True),
    ("Masa salada", 20, True),
    ("Hojaldre", 30, True),
    ("Bizcocho", 40, True),
    ("Crema", 50, True),
]

# Payment methods
PAYMENT_METHODS: list[tuple[str, str, bool, float, int, bool, bool, str | None]] = [
    # (code, label, requires_reference, fee_pct, sort_order, is_default, is_active, notes)
    ("efectivo", "Efectivo", False, 0.0, 10, True, True, "Pago en caja"),
    ("transferencia", "Transferencia bancaria", True, 0.0, 20, False, True, "Banco Itaú / Continental"),
    ("tarjeta", "Tarjeta (POS)", False, 3.0, 30, False, True, "+3% recargo"),
    ("qr", "Pago QR (Tigo/Personal)", True, 0.0, 40, False, True, "SIPAP / Compatible"),
    ("pedidosya", "PedidosYa (cobro app)", True, 12.0, 50, False, True, "12% comisión PedidosYa"),
    ("monchis", "Monchis", True, 15.0, 60, False, True, "15% comisión Monchis"),
    ("caja_chica", "Caja chica / vale", True, 0.0, 70, False, True, "Para consumo interno"),
]

# Margin tiers
MARGIN_TIERS: list[tuple[str, str, int | None, int | None, int, str | None]] = [
    # (code, label, min_cost_gs, max_cost_gs, sort_order, notes)
    ("tier1", "Top 10% (premium)", 10000, None, 10, "Recetas de margen alto"),
    ("tier2", "Top 25%", 5000, 9999, 20, "Recetas populares con buen margen"),
    ("tier3", "Medio", 1000, 4999, 30, "Volumen"),
    ("tier4", "Bajo", 500, 999, 40, "Evaluar"),
    ("tier5", "Muy bajo / pérdida", None, 499, 50, "Revisar — puede haber error"),
]

# Stock status config
STOCK_STATUSES: list[tuple[str, str, float | None, int | None, int, str | None]] = [
    # (code, label, threshold_ratio, threshold_days, sort_order, notes)
    ("ok", "Stock saludable", 1.0, None, 10, "Stock > min_stock_qty"),
    ("bajo", "Bajo", 0.5, None, 20, "Stock < min_stock_qty pero > 50%"),
    ("critico", "Crítico", 0.5, None, 30, "Stock < 50% del mínimo"),
    ("sobrestock", "Sobrestock", 5.0, None, 40, "Stock > 5x del mínimo"),
    ("muerto", "Sin consumo", None, 30, 50, "Sin consumo en 30+ días"),
]

# Storage types
STORAGE_TYPES: list[tuple[str, str, bool, bool, bool, int, str | None]] = [
    # (code, label, requires_temp_min, requires_temp_max, requires_humidity_max, sort_order, notes)
    ("ambient", "Ambiente (seco)", False, True, True, 10, "Sin refrigeración"),
    ("refrigerated", "Refrigerado (heladera)", True, True, False, 20, "0-8°C"),
    ("frozen", "Congelado", True, True, False, 30, "-18°C o menos"),
    ("dry", "Despensa seca", False, True, True, 40, "Harinas, azúcar, etc."),
    ("fresh", "Fresco (tropicales)", False, True, True, 50, "Frutas frescas"),
]

# Storage keywords — order matters (lower sort_order = checked first)
STORAGE_KEYWORDS: list[tuple[str, str, int]] = [
    # (storage_code, keyword, sort_order)
    ("refrigerated", "leche", 10),
    ("refrigerated", "crema", 15),
    ("refrigerated", "queso", 20),
    ("refrigerated", "huevo", 25),
    ("refrigerated", "manteca", 30),
    ("frozen", "congelad", 10),
    ("frozen", "masa congelada", 20),
    ("frozen", "fruta congelada", 30),
    ("dry", "harina", 10),
    ("dry", "azúcar", 20),
    ("dry", "sal", 30),
    ("dry", "cacao", 40),
    ("dry", "levadura", 50),
    ("dry", "polvo", 60),
    ("fresh", "frutilla", 10),
    ("fresh", "fruta", 20),
    ("ambient", "aceite", 10),
    ("ambient", "vainilla", 20),
    ("ambient", "esencia", 30),
]

# Date range presets
DATE_PRESETS: list[tuple[str, str, int, bool, int]] = [
    # (code, label, days, is_default, sort_order)
    ("hoy", "Hoy", 1, False, 10),
    ("ayer", "Ayer", 1, False, 20),
    ("7d", "Últimos 7 días", 7, False, 30),
    ("30d", "Últimos 30 días", 30, True, 40),
    ("mtd", "Mes en curso (MTD)", 31, False, 50),
    ("qtd", "Trimestre en curso (QTD)", 92, False, 60),
    ("ytd", "Año en curso (YTD)", 366, False, 70),
    ("mes_anterior", "Mes anterior", 31, False, 80),
    ("trimestre_anterior", "Trimestre anterior", 92, False, 90),
    ("ano_anterior", "Año anterior", 366, False, 100),
]

# Message templates (channel: 'email' | 'whatsapp' | 'sms')
MESSAGE_TEMPLATES: list[tuple[str, str, str | None, str, str | None]] = [
    # (channel, key, subject, body, notes)
    (
        "whatsapp",
        "pedido.confirmado",
        None,
        (
            "¡Hola {customer_name}! 👋\n\n"
            "Confirmamos tu pedido #{pedido_id} para retirar el {promised_date} a las {promised_time}.\n\n"
            "Total: {total_gs} Gs.\n"
            "Link de seguimiento: {public_url}\n\n"
            "— La Vaquita Holandesa 🐄"
        ),
        "Confirmación de pedido nuevo",
    ),
    (
        "whatsapp",
        "pedido.listo",
        None,
        (
            "¡{customer_name}, tu pedido #{pedido_id} está listo para retirar! 🎉\n\n"
            "Te esperamos en {pickup_address}.\n"
            "Mostrá este mensaje o tu link: {public_url}\n\n"
            "Horario de atención: {business_hours}"
        ),
        "Notificación de pedido listo",
    ),
    (
        "whatsapp",
        "pedido.atraso",
        None,
        (
            "Hola {customer_name}, te avisamos que tu pedido #{pedido_id} "
            "se va a retrasar aprox. {delay_minutes} minutos. "
            "Disculpá las molestias 🙏 — {reason}"
        ),
        "Aviso de demora",
    ),
    (
        "email",
        "pedido.factura",
        "Factura {factura_number} — La Vaquita Holandesa",
        (
            "Estimado/a {customer_name},\n\n"
            "Adjuntamos la factura {factura_number} por tu compra del {sale_date}.\n\n"
            "Subtotal: {subtotal_gs} Gs.\n"
            "IVA ({iva_pct}%): {iva_gs} Gs.\n"
            "Total: {total_gs} Gs.\n\n"
            "Gracias por tu compra.\n\n"
            "— La Vaquita Holandesa\n"
            "RUC: {ruc}\n"
            "Timbrado: {timbrado}"
        ),
        "Factura PDF adjunta",
    ),
    (
        "email",
        "cierre.mensual",
        "Resumen mensual — {mes}",
        (
            "Resumen del mes de {mes}:\n\n"
            "Ventas totales: {total_sales} Gs.\n"
            "Pedidos: {total_pedidos}\n"
            "Mermas: {total_mermas} Gs.\n"
            "Stock crítico: {critical_count} ingredientes\n\n"
            "— {business_name}"
        ),
        "Resumen de cierre mensual al admin",
    ),
    (
        "sms",
        "pedido.codigo",
        None,
        "Tu pedido #{pedido_id} está confirmado. Retira el {promised_date} {promised_time}. {public_url}",
        "SMS corto (160 chars)",
    ),
]

# Delivery zones (Asunción / Lambaré)
DELIVERY_ZONES: list[tuple[str, str, str, float, int, int, int, str | None]] = [
    # (code, name, coverage_text, radius_km, delivery_cost_gs, min_order_gs, delivery_minutes, notes)
    ("centro", "Centro / Microcentro", "Palma, Catedral, Estrella", 2.0, 8000, 30000, 35, None),
    ("recoleta", "Recoleta / Sajonia", "Sajonia, Recoleta, Terminal", 3.5, 12000, 50000, 45, None),
    ("villa_morra", "Villa Morra / Carmelitas", "VM, Carmelitas, Shopping", 4.0, 15000, 60000, 50, None),
    ("lambare", "Lambaré / Ñemby", "Lambaré, Ñemby, San Antonio", 6.0, 20000, 80000, 60, "Costo más alto por distancia"),
]

# Channels (sale channels)
# P43 (2026-10-07): source codes from Channel enum + remove "phone"
# (legacy alias not in the enum; DB CHECK would reject any pedido.channel
# set to "phone"). Legacy phone-channel traffic now maps to
# Channel.OTHER.value, and "phone" prefix in seed labels stays a display
# string only — not a Channel.code.
from app.rms.models.channels import Channel

CHANNELS: list[tuple[str, str, int, bool, str | None]] = [
    # (code, label, sort_order, is_default, notes)
    (Channel.MOSTRADOR.value, "Mostrador", 10, True, "Venta directa en mostrador"),
    (Channel.MOSTRADOR_ENCARGO.value, "Mostrador (encargo)", 20, False, "Encargo recogido en mostrador"),
    (Channel.WHATSAPP.value, "WhatsApp", 30, False, "Pedido recibido por WhatsApp"),
    (Channel.PEDIDOSYA.value, "PedidosYa", 40, False, "PedidosYa (delivery app)"),
    (Channel.MONCHIS.value, "Monchis", 50, False, "Monchis (delivery app)"),
    (Channel.OTHER.value, "Teléfono / Otro", 60, False, "Llamada telefónica u otro canal no listado"),
]

# Suppliers
SUPPLIERS: list[tuple[str, str, str, str, str, str, str, str | None]] = [
    # (name, contact_name, phone, email, address, ruc, notes)
    (
        "Distribuidora El Molino",
        "Roberto Giménez",
        "+595 21 555-0101",
        "ventas@elmolino.com.py",
        "Av. Artigas 1234, Asunción",
        "80012345-6",
        "Harinas, levaduras, cacao. Precios mayoristas.",
    ),
    (
        "Lácteos Paraguay S.A.",
        "María López",
        "+595 21 555-0202",
        "pedidos@lacteospar.com.py",
        "Ruta 2 Km 14, Capiatá",
        "80023456-7",
        "Leche, crema, queso crema, manteca. Reparto martes y viernes.",
    ),
    (
        "Frutas del Sur",
        "Juan Caballero",
        "+595 25 555-0303",
        None,
        "Mercado de Abasto, Bloque 4, Local 22",
        "80034567-8",
        "Frutas frescas y congeladas. Pedido 24h antes.",
    ),
    (
        "Dulcería Santa Rita",
        "Ana Rodríguez",
        "+595 21 555-0404",
        "info@dulcesantarita.com.py",
        "Iturbe 567, Asunción",
        "80045678-9",
        "Dulce de leche, mermeladas, miel, chocolate cobertura.",
    ),
    (
        "Embalajes Express",
        "Pedro Miranda",
        "+595 21 555-0505",
        "ventas@embalajes.com.py",
        "Av. Eusebio Ayala 3456",
        "80056789-0",
        "Bolsas, cajas, film plástico, descartables. Reparto diario.",
    ),
]

# Compliance info (single-row table)
COMPLIANCE: dict[str, object] = {
    "ruc": "80012345-6",
    "razon_social": "La Vaquita Holandesa S.A.",
    "nombre_fantasia": "La Vaquita Holandesa",
    "tax_regime": "resimple",  # Most common for small bakeries
    "iva_default_rate": "10",
    "timbrado_number": "13456789",
    "timbrado_expiry": "2027-12-31",
    "next_boleta_resimple_number": 1,
    "next_factura_number": 1,
    "inan_re_number": "R.E. 12.345/2024",
    "inan_re_expiry": "2027-08-15",
    "director_tecnico": "Lic. Patricia Sánchez",
    "director_tecnico_registro": "Reg. 4567",
    "municipal_habilitacion": "Hab-2024-12345",
    "municipal_habilitacion_expiry": "2027-12-31",
    "establecimiento_address": "Av. España 1234, casi Brasil, Asunción",
    "establecimiento_phone": "+595 21 555-1000",
    "establecimiento_email": "hola@lavaquita.example",
    "logo_path": None,
    "labor_cost_per_hour_gs": 25000,  # Gs/hour for kitchen staff
    "overhead_multiplier_pct": 1.15,  # 15% overhead on COGS
    "sifen_certificate_id": "Cert-SIFEN-12345",
    "sifen_csc_code": "CSC-CODE-EXAMPLE",
    "sifen_test_mode": True,  # set to True during dev
    "updated_at": "2026-10-05T16:00:00Z",
}

# Business info (for branding / non-regulatory)
BUSINESS_INFO: dict[str, str] = {
    "business_hours": "Lunes a sábado 7:00-19:00, domingo 8:00-13:00",
    "address": "Av. España 1234, casi Brasil, Asunción",
    "phone": "+595 21 555-1000",
    "email": "hola@lavaquita.example",
}

# Realistic Paraguayan bakery ingredients (50+).
# Tuple: (name, unit, stock_qty, purchase_price_gs_per_unit, min_stock_qty,
#         shelf_life_days, storage, category, allergens, dietary_tags,
#         supplier_idx, package_size, package_unit, package_price_gs, lot_required,
#         may_contain_gluten, water_activity_aw, humidity_max_pct, temp_min_c, temp_max_c)
# Indices are 0-based into SUPPLIERS list above.
INGREDIENTS: list[tuple] = [
    # --- Dry / harina ---
    ("harina 0000", "kg", 50.0, 4500, 10.0, 90, "dry", "harinas", "gluten", "vegano", 0, 25.0, "kg", 105000, False, True, 0.45, 70, 15, 25),
    ("harina 000", "kg", 30.0, 4200, 8.0, 90, "dry", "harinas", "gluten", "vegano", 0, 25.0, "kg", 98000, False, True, 0.45, 70, 15, 25),
    ("harina integral", "kg", 12.0, 5800, 3.0, 60, "dry", "harinas", "gluten", "vegano,integral", 0, 10.0, "kg", 55000, False, True, 0.5, 70, 15, 25),
    ("maicena", "kg", 3.0, 8500, 1.0, 365, "dry", "harinas", None, "vegano,sin-gluten", 0, 1.0, "kg", 8200, False, False, 0.4, 70, 15, 25),
    # --- Sugar / sweetener ---
    ("azúcar", "kg", 25.0, 5200, 5.0, 365, "dry", "endulzantes", None, "vegano,sin-gluten", 0, 25.0, "kg", 125000, False, False, 0.4, 70, 15, 25),
    ("azúcar impalpable", "kg", 4.0, 9500, 1.0, 365, "dry", "endulzantes", None, "vegano,sin-gluten", 0, 1.0, "kg", 9200, False, False, 0.3, 70, 15, 25),
    ("miel", "kg", 1.5, 35000, 0.5, 1825, "ambient", "endulzantes", None, "vegano,sin-gluten", 0, 0.5, "kg", 17000, False, False, 0.55, 70, 15, 25),
    ("leche condensada", "kg", 4.0, 18500, 1.0, 180, "ambient", "endulzantes", "lacteos", None, 1, 1.0, "kg", 18200, False, False, 0.7, 70, 15, 25),
    # --- Dairy ---
    ("leche entera", "l", 25.0, 7800, 8.0, 7, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "l", 7500, True, False, 0.97, None, 0, 8),
    ("crema de leche", "l", 5.0, 18500, 2.0, 14, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "l", 18000, True, False, 0.95, None, 0, 8),
    ("manteca", "kg", 8.0, 32000, 2.0, 60, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "kg", 31500, True, False, 0.95, None, 0, 8),
    ("manteca sin sal", "kg", 3.0, 36000, 1.0, 90, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "kg", 35000, True, False, 0.95, None, 0, 8),
    ("queso crema", "kg", 6.0, 38000, 2.0, 21, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "kg", 37000, True, False, 0.96, None, 0, 8),
    ("queso Paraguay", "kg", 2.5, 45000, 1.0, 30, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "kg", 44000, True, False, 0.95, None, 0, 8),
    ("huevos", "und", 240.0, 600, 60.0, 21, "refrigerated", "lacteos", "huevos", None, 1, 30.0, "und", 17000, True, False, 0.97, None, 0, 8),
    # --- Chocolates / cocoa ---
    ("cacao en polvo", "kg", 2.5, 28000, 1.0, 365, "dry", "chocolates", None, "vegano,sin-gluten", 0, 1.0, "kg", 27500, False, False, 0.4, 70, 15, 25),
    ("chocolate cobertura", "kg", 5.0, 42000, 2.0, 365, "ambient", "chocolates", "lacteos", None, 3, 1.0, "kg", 41000, False, False, 0.4, 70, 15, 25),
    ("chocolate chips", "kg", 3.0, 45000, 1.0, 365, "ambient", "chocolates", "lacteos", None, 3, 1.0, "kg", 44000, False, False, 0.4, 70, 15, 25),
    # --- Dried fruits / nuts ---
    ("nueces", "kg", 1.5, 85000, 0.5, 180, "dry", "frutos_secos", "frutos_secos", "vegano", 0, 0.5, "kg", 42000, False, False, 0.45, 65, 15, 25),
    ("almendra molida", "kg", 1.2, 95000, 0.4, 180, "dry", "frutos_secos", "frutos_secos", "vegano,sin-gluten", 0, 0.5, "kg", 47000, False, False, 0.45, 65, 15, 25),
    ("pasas de uva", "kg", 2.0, 28000, 0.8, 365, "dry", "frutos_secos", None, "vegano,sin-gluten", 0, 1.0, "kg", 27500, False, False, 0.55, 65, 15, 25),
    # --- Fresh fruits ---
    ("frutillas", "kg", 3.0, 22000, 1.0, 5, "fresh", "frutas_frescas", None, "vegano,sin-gluten", 2, 1.0, "kg", 21000, False, False, 0.98, 90, 0, 8),
    ("banana", "kg", 4.0, 6500, 1.5, 5, "fresh", "frutas_frescas", None, "vegano,sin-gluten", 2, 1.0, "kg", 6000, False, False, 0.97, 90, 8, 25),
    ("manzana", "kg", 5.0, 8500, 2.0, 21, "fresh", "frutas_frescas", None, "vegano,sin-gluten", 2, 1.0, "kg", 8000, False, False, 0.96, 90, 0, 8),
    ("limón", "kg", 1.5, 7500, 0.5, 14, "fresh", "frutas_frescas", None, "vegano,sin-gluten", 2, 1.0, "kg", 7000, False, False, 0.97, 90, 8, 25),
    # --- Leavening ---
    ("levadura", "kg", 1.5, 22000, 0.5, 30, "refrigerated", "leudantes", None, "vegano,sin-gluten", 0, 0.5, "kg", 10500, True, False, 0.7, 70, 0, 8),
    ("polvo de hornear", "kg", 1.0, 18000, 0.3, 365, "dry", "leudantes", None, "vegano,sin-gluten", 0, 0.5, "kg", 8500, False, False, 0.4, 70, 15, 25),
    ("bicarbonato", "kg", 0.5, 12000, 0.1, 1825, "dry", "leudantes", None, "vegano,sin-gluten", 0, 0.5, "kg", 5500, False, False, 0.4, 70, 15, 25),
    # --- Salt / spices / flavors ---
    ("sal", "kg", 5.0, 1800, 1.0, 1825, "dry", "condimentos", None, "vegano,sin-gluten", 0, 1.0, "kg", 1700, False, False, 0.3, 70, 15, 25),
    ("canela molida", "kg", 0.3, 45000, 0.1, 730, "dry", "condimentos", None, "vegano,sin-gluten", 0, 0.1, "kg", 4400, False, False, 0.3, 70, 15, 25),
    ("esencia de vainilla", "ml", 500.0, 65, 100.0, 1095, "ambient", "saborizantes", None, "vegano,sin-gluten", 0, 100.0, "ml", 6000, False, False, 0.0, 70, 15, 25),
    ("ralladura de limón", "g", 200.0, 95, 50.0, 90, "ambient", "saborizantes", None, "vegano,sin-gluten", 0, 50.0, "g", 4500, False, False, 0.3, 70, 15, 25),
    # --- Dulce de leche / fillings ---
    ("dulce de leche", "kg", 8.0, 28000, 2.0, 30, "ambient", "rellenos", "lacteos", None, 3, 1.0, "kg", 27500, False, False, 0.85, 70, 15, 25),
    ("mermelada de frutilla", "kg", 3.0, 22000, 1.0, 365, "ambient", "rellenos", None, "vegano,sin-gluten", 3, 1.0, "kg", 21500, False, False, 0.85, 70, 15, 25),
    ("mermelada de durazno", "kg", 2.0, 22000, 0.8, 365, "ambient", "rellenos", None, "vegano,sin-gluten", 3, 1.0, "kg", 21500, False, False, 0.85, 70, 15, 25),
    # --- Oils / fats for frying ---
    ("aceite vegetal", "l", 8.0, 12500, 2.0, 365, "ambient", "aceites", None, "vegano,sin-gluten", 0, 1.0, "l", 12000, False, False, 0.0, 70, 15, 25),
    # --- Salsas / condimentos ---
    ("mostaza", "kg", 1.0, 18000, 0.3, 365, "refrigerated", "condimentos", "mostaza", "vegano", 1, 0.5, "kg", 8500, False, False, 0.85, 70, 0, 8),
    ("ketchup", "kg", 2.0, 14000, 0.5, 365, "ambient", "condimentos", None, "vegano,sin-gluten", 1, 1.0, "kg", 13500, False, False, 0.85, 70, 15, 25),
    # --- Carnes / fiambres (for salados) ---
    ("jamón cocido", "kg", 3.0, 45000, 1.0, 14, "refrigerated", "carnes", None, None, 1, 1.0, "kg", 44000, True, False, 0.97, None, 0, 8),
    ("queso muzzarella", "kg", 4.0, 52000, 1.5, 21, "refrigerated", "lacteos", "lacteos", None, 1, 1.0, "kg", 51000, True, False, 0.95, None, 0, 8),
    ("carne molida", "kg", 2.0, 38000, 0.8, 5, "refrigerated", "carnes", None, None, 1, 1.0, "kg", 37000, True, False, 0.98, None, 0, 8),
    # --- Beverages (for recipes) ---
    ("café molido", "kg", 1.0, 65000, 0.3, 90, "dry", "bebidas", None, "vegano,sin-gluten", 0, 0.5, "kg", 32000, False, False, 0.4, 70, 15, 25),
    ("cacao amargo", "kg", 0.8, 32000, 0.3, 365, "dry", "bebidas", None, "vegano,sin-gluten", 0, 0.5, "kg", 15500, False, False, 0.4, 70, 15, 25),
    # --- Embalajes / packaging ---
    ("bolsa de papel mediana", "und", 200.0, 350, 50.0, None, "ambient", "embalajes", None, "vegano,sin-gluten", 4, 100.0, "und", 28000, False, False, None, None, None, None),
    ("caja torta 25cm", "und", 50.0, 2800, 15.0, None, "ambient", "embalajes", None, "vegano,sin-gluten", 4, 25.0, "und", 65000, False, False, None, None, None, None),
    ("film transparente", "und", 25.0, 4500, 5.0, None, "ambient", "embalajes", None, "vegano,sin-gluten", 4, 1.0, "und", 4500, False, False, None, None, None, None),
    # --- Frutas congeladas ---
    ("frutilla congelada", "kg", 4.0, 28000, 1.0, 365, "frozen", "frutas_frescas", None, "vegano,sin-gluten", 2, 1.0, "kg", 27500, False, False, 0.96, None, -25, -15),
    ("arándanos congelados", "kg", 1.5, 65000, 0.5, 365, "frozen", "frutas_frescas", None, "vegano,sin-gluten", 2, 0.5, "kg", 32000, False, False, 0.96, None, -25, -15),
    # --- Decoraciones ---
    ("coco rallado", "kg", 1.0, 32000, 0.3, 365, "dry", "decoraciones", None, "vegano,sin-gluten", 3, 0.5, "kg", 15500, False, False, 0.4, 70, 15, 25),
    ("granillo de chocolate", "kg", 0.8, 48000, 0.3, 365, "ambient", "decoraciones", "lacteos", None, 3, 0.5, "kg", 23500, False, False, 0.4, 70, 15, 25),
    # --- Agua ---
    ("agua", "l", 60.0, 0, 20.0, 365, "ambient", "liquidos", None, "vegano,sin-gluten", 0, 1.0, "l", 0, False, False, 1.0, None, None, None),
    # --- Verduras / otros ---
    ("cebolla", "kg", 3.0, 8500, 1.0, 30, "ambient", "verduras", None, "vegano,sin-gluten", 2, 1.0, "kg", 8000, False, False, 0.95, 80, 8, 25),
    ("ajo", "kg", 0.5, 28000, 0.2, 60, "ambient", "verduras", None, "vegano,sin-gluten", 2, 0.5, "kg", 13500, False, False, 0.6, 70, 8, 25),
    ("tomate", "kg", 4.0, 9500, 1.5, 7, "fresh", "verduras", None, "vegano,sin-gluten", 2, 1.0, "kg", 9000, False, False, 0.98, 90, 8, 25),
]

# 20+ recipes
# Tuple: (name, yield_qty, yield_unit, prep_minutes, cook_minutes, difficulty 1-5, family, menu_tags, dietary_tags, notes)
RECIPES: list[tuple] = [
    ("muffin_vainilla", 12.0, "und", 35, 25, 1, "Masa dulce", "Panadería,Infantiles", "vegetariano", "Muffin clásico"),
    ("muffin_chocolate", 12.0, "und", 35, 25, 1, "Masa dulce", "Panadería,Chocolate", "vegetariano", "Muffin de chocolate con chips"),
    ("muffin_nueces", 12.0, "und", 40, 25, 2, "Masa dulce", "Panadería,Frutos secos", "vegetariano", "Muffin con nueces"),
    ("muffin_arandanos", 12.0, "und", 40, 25, 2, "Masa dulce", "Panadería,Frutas", "vegetariano", "Muffin con arándanos congelados"),
    ("cheesecake_frutilla", 8.0, "und", 90, 60, 3, "Crema", "Pastelería,Frutas,Especiales", "vegetariano", "Cheesecake al horno con frutilla"),
    ("cheesecake_dulce_leche", 8.0, "und", 90, 60, 3, "Crema", "Pastelería,Especiales", "vegetariano", "Cheesecake con dulce de leche"),
    ("hojaldre_dulce", 16.0, "und", 120, 30, 3, "Hojaldre", "Panadería,Especiales", "vegetariano", "Hojaldre con dulce de leche"),
    ("appeltaart", 8.0, "und", 90, 60, 3, "Masa dulce", "Pastelería,Frutas", "vegetariano", "Tarta de manzana holandesa"),
    ("tompoezen", 12.0, "und", 60, 30, 2, "Crema", "Pastelería,Especiales", "vegetariano", "Postre holandés de crema"),
    ("oliebollen", 24.0, "und", 45, 20, 2, "Masa dulce", "Panadería,Especiales", "vegetariano", "Buñuelos holandeses con pasas"),
    ("babka_chocolate", 10.0, "und", 180, 45, 4, "Masa dulce", "Pastelería,Chocolate,Especiales", "vegetariano", "Babka trenzada de chocolate"),
    ("stroopwafel", 24.0, "und", 60, 15, 3, "Hojaldre", "Pastelería,Especiales", "vegetariano", "Galletita wafer con caramelo"),
    ("pan_lactal", 2.0, "und", 180, 45, 2, "Masa salada", "Panadería", "vegano", "Pan lactal tipo sándwich"),
    ("facturas_dulce", 24.0, "und", 180, 25, 3, "Hojaldre", "Panadería,Especiales", "vegetariano", "Facturas argentinas"),
    ("empanada_carne", 12.0, "und", 60, 30, 2, "Masa salada", "Salados", None, "Empanada de carne"),
    ("torta_chocolate", 12.0, "und", 90, 50, 3, "Bizcocho", "Tortas,Chocolate,Especiales", "vegetariano", "Torta de chocolate (12 porciones)"),
    ("torta_vainilla", 12.0, "und", 90, 50, 2, "Bizcocho", "Tortas,Especiales", "vegetariano", "Torta de vainilla (12 porciones)"),
    ("brownie_chocolate", 16.0, "und", 30, 25, 1, "Bizcocho", "Pastelería,Chocolate", "vegetariano", "Brownie húmedo"),
    ("galleta_chips", 30.0, "und", 30, 12, 1, "Masa dulce", "Panadería,Chocolate,Infantiles", "vegetariano", "Galletas con chips de chocolate"),
    ("chipa_guazu", 12.0, "und", 60, 40, 2, "Masa salada", "Salados,Especiales", "vegetariano", "Chipa guazú paraguayo"),
    ("galleta_miel", 30.0, "und", 30, 12, 1, "Masa dulce", "Panadería,Infantiles", "vegetariano", "Galletas de miel"),
    ("sopa_paraguaya", 12.0, "und", 60, 45, 2, "Masa salada", "Salados,Especiales", "vegetariano", "Sopa paraguaya"),
    ("medialunas", 24.0, "und", 180, 20, 3, "Hojaldre", "Panadería,Especiales", "vegetariano", "Medialunas de manteca"),
    ("rosca_manjar", 8.0, "und", 120, 30, 2, "Masa dulce", "Panadería,Especiales", "vegetariano", "Rosca rellena con manjar"),
    ("tostado_jyq", 4.0, "und", 15, 5, 1, "Masa salada", "Salados", "vegetariano", "Tostado de jamón y queso"),
]

# Recipe lines: (recipe_name, ingredient_name, qty, line_unit, notes)
RECIPE_LINES: list[tuple[str, str, float, str, str | None]] = [
    # === muffin_vainilla (12 und) ===
    ("muffin_vainilla", "harina 0000", 0.350, "kg", None),
    ("muffin_vainilla", "azúcar", 0.180, "kg", None),
    ("muffin_vainilla", "manteca", 0.120, "kg", None),
    ("muffin_vainilla", "huevos", 2, "und", None),
    ("muffin_vainilla", "leche entera", 0.180, "l", None),
    ("muffin_vainilla", "polvo de hornear", 0.008, "kg", None),
    ("muffin_vainilla", "esencia de vainilla", 5, "ml", None),
    ("muffin_vainilla", "sal", 0.002, "kg", None),
    # === muffin_chocolate ===
    ("muffin_chocolate", "harina 0000", 0.350, "kg", None),
    ("muffin_chocolate", "azúcar", 0.200, "kg", None),
    ("muffin_chocolate", "cacao en polvo", 0.050, "kg", None),
    ("muffin_chocolate", "manteca", 0.120, "kg", None),
    ("muffin_chocolate", "huevos", 2, "und", None),
    ("muffin_chocolate", "leche entera", 0.180, "l", None),
    ("muffin_chocolate", "polvo de hornear", 0.008, "kg", None),
    ("muffin_chocolate", "chocolate chips", 0.080, "kg", None),
    ("muffin_chocolate", "sal", 0.002, "kg", None),
    # === muffin_nueces ===
    ("muffin_nueces", "harina 0000", 0.350, "kg", None),
    ("muffin_nueces", "azúcar", 0.180, "kg", None),
    ("muffin_nueces", "manteca", 0.120, "kg", None),
    ("muffin_nueces", "huevos", 2, "und", None),
    ("muffin_nueces", "leche entera", 0.180, "l", None),
    ("muffin_nueces", "polvo de hornear", 0.008, "kg", None),
    ("muffin_nueces", "nueces", 0.080, "kg", None),
    # === muffin_arandanos ===
    ("muffin_arandanos", "harina 0000", 0.350, "kg", None),
    ("muffin_arandanos", "azúcar", 0.180, "kg", None),
    ("muffin_arandanos", "manteca", 0.120, "kg", None),
    ("muffin_arandanos", "huevos", 2, "und", None),
    ("muffin_arandanos", "leche entera", 0.180, "l", None),
    ("muffin_arandanos", "polvo de hornear", 0.008, "kg", None),
    ("muffin_arandanos", "arándanos congelados", 0.100, "kg", "Sin descongelar"),
    # === cheesecake_frutilla (8 und) ===
    ("cheesecake_frutilla", "queso crema", 0.600, "kg", None),
    ("cheesecake_frutilla", "azúcar", 0.200, "kg", None),
    ("cheesecake_frutilla", "huevos", 3, "und", None),
    ("cheesecake_frutilla", "crema de leche", 0.200, "l", None),
    ("cheesecake_frutilla", "harina 0000", 0.050, "kg", None),
    ("cheesecake_frutilla", "esencia de vainilla", 8, "ml", None),
    ("cheesecake_frutilla", "frutilla congelada", 0.200, "kg", "Para la cobertura"),
    ("cheesecake_frutilla", "mermelada de frutilla", 0.100, "kg", "Para la cobertura"),
    # === cheesecake_dulce_leche ===
    ("cheesecake_dulce_leche", "queso crema", 0.600, "kg", None),
    ("cheesecake_dulce_leche", "azúcar", 0.150, "kg", None),
    ("cheesecake_dulce_leche", "huevos", 3, "und", None),
    ("cheesecake_dulce_leche", "crema de leche", 0.200, "l", None),
    ("cheesecake_dulce_leche", "harina 0000", 0.050, "kg", None),
    ("cheesecake_dulce_leche", "dulce de leche", 0.300, "kg", "Para el relleno y cobertura"),
    # === hojaldre_dulce (16 und) ===
    ("hojaldre_dulce", "harina 0000", 0.500, "kg", None),
    ("hojaldre_dulce", "manteca sin sal", 0.300, "kg", "Para hojaldrar"),
    ("hojaldre_dulce", "azúcar", 0.100, "kg", None),
    ("hojaldre_dulce", "huevos", 2, "und", None),
    ("hojaldre_dulce", "leche entera", 0.150, "l", None),
    ("hojaldre_dulce", "levadura", 0.020, "kg", None),
    ("hojaldre_dulce", "dulce de leche", 0.300, "kg", "Para rellenar"),
    # === appeltaart (8 und) ===
    ("appeltaart", "harina 0000", 0.400, "kg", None),
    ("appeltaart", "manteca sin sal", 0.200, "kg", None),
    ("appeltaart", "azúcar", 0.250, "kg", None),
    ("appeltaart", "huevos", 2, "und", None),
    ("appeltaart", "manzana", 0.600, "kg", "Peladas y cortadas en cubos"),
    ("appeltaart", "canela molida", 0.005, "kg", None),
    ("appeltaart", "ralladura de limón", 5, "g", None),
    # === tompoezen (12 und) ===
    ("tompoezen", "harina 0000", 0.300, "kg", None),
    ("tompoezen", "manteca", 0.150, "kg", None),
    ("tompoezen", "huevos", 2, "und", None),
    ("tompoezen", "leche entera", 0.150, "l", None),
    ("tompoezen", "crema de leche", 0.400, "l", None),
    ("tompoezen", "azúcar impalpable", 0.100, "kg", None),
    # === oliebollen (24 und) ===
    ("oliebollen", "harina 0000", 0.500, "kg", None),
    ("oliebollen", "huevos", 3, "und", None),
    ("oliebollen", "leche entera", 0.300, "l", None),
    ("oliebollen", "levadura", 0.020, "kg", None),
    ("oliebollen", "azúcar", 0.080, "kg", None),
    ("oliebollen", "pasas de uva", 0.080, "kg", None),
    ("oliebollen", "aceite vegetal", 0.500, "l", "Para freír"),
    # === babka_chocolate (10 und) ===
    ("babka_chocolate", "harina 0000", 0.600, "kg", None),
    ("babka_chocolate", "manteca", 0.200, "kg", None),
    ("babka_chocolate", "azúcar", 0.150, "kg", None),
    ("babka_chocolate", "huevos", 3, "und", None),
    ("babka_chocolate", "leche entera", 0.200, "l", None),
    ("babka_chocolate", "levadura", 0.020, "kg", None),
    ("babka_chocolate", "chocolate cobertura", 0.300, "kg", "Para el relleno"),
    # === stroopwafel (24 und) ===
    ("stroopwafel", "harina 0000", 0.500, "kg", None),
    ("stroopwafel", "manteca", 0.250, "kg", None),
    ("stroopwafel", "azúcar", 0.250, "kg", None),
    ("stroopwafel", "huevos", 2, "und", None),
    ("stroopwafel", "esencia de vainilla", 8, "ml", None),
    ("stroopwafel", "miel", 0.080, "kg", "Para el caramelo del medio"),
    # === pan_lactal (2 und) ===
    ("pan_lactal", "harina 0000", 1.000, "kg", None),
    ("pan_lactal", "agua", 0.500, "l", None),
    ("pan_lactal", "levadura", 0.030, "kg", None),
    ("pan_lactal", "sal", 0.020, "kg", None),
    ("pan_lactal", "manteca", 0.050, "kg", None),
    ("pan_lactal", "azúcar", 0.050, "kg", None),
    # === facturas_dulce (24 und) ===
    ("facturas_dulce", "harina 0000", 0.500, "kg", None),
    ("facturas_dulce", "manteca sin sal", 0.150, "kg", None),
    ("facturas_dulce", "azúcar", 0.100, "kg", None),
    ("facturas_dulce", "huevos", 2, "und", None),
    ("facturas_dulce", "leche entera", 0.150, "l", None),
    ("facturas_dulce", "levadura", 0.020, "kg", None),
    ("facturas_dulce", "azúcar impalpable", 0.080, "kg", "Para espolvorear"),
    ("facturas_dulce", "dulce de leche", 0.200, "kg", "Para algunas"),
    # === empanada_carne (12 und) ===
    ("empanada_carne", "harina 0000", 0.500, "kg", None),
    ("empanada_carne", "manteca sin sal", 0.100, "kg", None),
    ("empanada_carne", "sal", 0.005, "kg", None),
    ("empanada_carne", "agua", 0.200, "l", None),
    ("empanada_carne", "carne molida", 0.500, "kg", None),
    ("empanada_carne", "huevos", 1, "und", "Para el relleno"),
    # === torta_chocolate (12 und) ===
    ("torta_chocolate", "harina 0000", 0.300, "kg", None),
    ("torta_chocolate", "azúcar", 0.300, "kg", None),
    ("torta_chocolate", "cacao en polvo", 0.080, "kg", None),
    ("torta_chocolate", "manteca", 0.150, "kg", None),
    ("torta_chocolate", "huevos", 4, "und", None),
    ("torta_chocolate", "leche entera", 0.250, "l", None),
    ("torta_chocolate", "polvo de hornear", 0.010, "kg", None),
    ("torta_chocolate", "esencia de vainilla", 5, "ml", None),
    # === torta_vainilla (12 und) ===
    ("torta_vainilla", "harina 0000", 0.350, "kg", None),
    ("torta_vainilla", "azúcar", 0.300, "kg", None),
    ("torta_vainilla", "manteca", 0.150, "kg", None),
    ("torta_vainilla", "huevos", 4, "und", None),
    ("torta_vainilla", "leche entera", 0.250, "l", None),
    ("torta_vainilla", "polvo de hornear", 0.010, "kg", None),
    ("torta_vainilla", "esencia de vainilla", 10, "ml", None),
    # === brownie_chocolate (16 und) ===
    ("brownie_chocolate", "harina 0000", 0.200, "kg", None),
    ("brownie_chocolate", "azúcar", 0.350, "kg", None),
    ("brownie_chocolate", "cacao en polvo", 0.080, "kg", None),
    ("brownie_chocolate", "manteca", 0.200, "kg", None),
    ("brownie_chocolate", "huevos", 4, "und", None),
    ("brownie_chocolate", "chocolate chips", 0.150, "kg", None),
    ("brownie_chocolate", "esencia de vainilla", 5, "ml", None),
    # === galleta_chips (30 und) ===
    ("galleta_chips", "harina 0000", 0.400, "kg", None),
    ("galleta_chips", "manteca", 0.200, "kg", None),
    ("galleta_chips", "azúcar", 0.250, "kg", None),
    ("galleta_chips", "huevos", 2, "und", None),
    ("galleta_chips", "chocolate chips", 0.200, "kg", None),
    ("galleta_chips", "polvo de hornear", 0.005, "kg", None),
    ("galleta_chips", "esencia de vainilla", 5, "ml", None),
    # === chipa_guazu (12 und) ===
    ("chipa_guazu", "harina 0000", 0.250, "kg", None),
    ("chipa_guazu", "queso Paraguay", 0.400, "kg", "Rallado"),
    ("chipa_guazu", "huevos", 3, "und", None),
    ("chipa_guazu", "leche entera", 0.400, "l", None),
    ("chipa_guazu", "manteca", 0.100, "kg", None),
    ("chipa_guazu", "azúcar", 0.050, "kg", None),
    ("chipa_guazu", "maicena", 0.050, "kg", None),
    # === galleta_miel (30 und) ===
    ("galleta_miel", "harina 0000", 0.400, "kg", None),
    ("galleta_miel", "manteca", 0.200, "kg", None),
    ("galleta_miel", "azúcar", 0.150, "kg", None),
    ("galleta_miel", "miel", 0.100, "kg", None),
    ("galleta_miel", "huevos", 1, "und", None),
    ("galleta_miel", "polvo de hornear", 0.005, "kg", None),
    ("galleta_miel", "esencia de vainilla", 5, "ml", None),
    # === sopa_paraguaya (12 und) ===
    ("sopa_paraguaya", "harina 0000", 0.300, "kg", None),
    ("sopa_paraguaya", "queso Paraguay", 0.400, "kg", "Rallado"),
    ("sopa_paraguaya", "huevos", 3, "und", None),
    ("sopa_paraguaya", "leche entera", 0.400, "l", None),
    ("sopa_paraguaya", "manteca", 0.100, "kg", None),
    ("sopa_paraguaya", "cebolla", 0.200, "kg", "No incluido en INGREDIENTS (ver nota)"),
    # === medialunas (24 und) ===
    ("medialunas", "harina 0000", 0.500, "kg", None),
    ("medialunas", "manteca sin sal", 0.200, "kg", "Para hojaldrar"),
    ("medialunas", "azúcar", 0.100, "kg", None),
    ("medialunas", "huevos", 1, "und", None),
    ("medialunas", "leche entera", 0.150, "l", None),
    ("medialunas", "levadura", 0.020, "kg", None),
    # === rosca_manjar (8 und) ===
    ("rosca_manjar", "harina 0000", 0.500, "kg", None),
    ("rosca_manjar", "manteca", 0.150, "kg", None),
    ("rosca_manjar", "azúcar", 0.100, "kg", None),
    ("rosca_manjar", "huevos", 2, "und", None),
    ("rosca_manjar", "leche entera", 0.150, "l", None),
    ("rosca_manjar", "levadura", 0.020, "kg", None),
    ("rosca_manjar", "dulce de leche", 0.300, "kg", "Para rellenar"),
    # === tostado_jyq (4 und) ===
    ("tostado_jyq", "jamón cocido", 0.200, "kg", None),
    ("tostado_jyq", "queso muzzarella", 0.200, "kg", None),
    ("tostado_jyq", "manteca", 0.030, "kg", "Para untar"),
]

# Products (40+).
# Tuple: (name, recipe_name, portion_label, sale_price_gs, category, sku, iva_rate, rspa_number, is_favorite, dietary_tags, image_url, notes)
PRODUCTS: list[tuple] = [
    # Muffins
    ("Muffin de vainilla", "muffin_vainilla", "1 unidad", 8000, "Panadería", "MV-01", "10", None, True, None, None, "Popular en escolares"),
    ("Muffin de chocolate", "muffin_chocolate", "1 unidad", 8500, "Panadería", "MCH-01", "10", None, True, None, None, None),
    ("Muffin de nueces", "muffin_nueces", "1 unidad", 9500, "Panadería", "MN-01", "10", None, False, None, None, None),
    ("Muffin de arándanos", "muffin_arandanos", "1 unidad", 9500, "Panadería", "MAR-01", "10", None, False, None, None, None),
    ("Docena muffins vainilla", "muffin_vainilla", "12 unidades", 85000, "Panadería", "MV-12", "10", "R.S.P.A. 12345", False, None, None, "Encargo 24h antes"),
    ("Docena muffins chocolate", "muffin_chocolate", "12 unidades", 90000, "Panadería", "MCH-12", "10", "R.S.P.A. 12346", False, None, None, "Encargo 24h antes"),
    # Cheesecake
    ("Cheesecake de frutilla", "cheesecake_frutilla", "1 porción", 25000, "Pastelería", "CHF-01", "10", None, True, None, None, "Especial de la casa"),
    ("Cheesecake entera frutilla", "cheesecake_frutilla", "1 torta (8 porciones)", 180000, "Tortas", "CHF-08", "10", "R.S.P.A. 12347", True, None, None, "Encargo 48h antes"),
    ("Cheesecake de dulce de leche", "cheesecake_dulce_leche", "1 porción", 25000, "Pastelería", "CHD-01", "10", None, True, None, None, "Sabor argentino"),
    ("Cheesecake entera dulce de leche", "cheesecake_dulce_leche", "1 torta (8 porciones)", 180000, "Tortas", "CHD-08", "10", "R.S.P.A. 12348", False, None, None, None),
    # Hojaldre / facturas
    ("Hojaldre dulce", "hojaldre_dulce", "1 unidad", 6000, "Panadería", "HD-01", "10", None, False, None, None, None),
    ("Docena hojaldres", "hojaldre_dulce", "12 unidades", 65000, "Panadería", "HD-12", "10", "R.S.P.A. 12349", False, None, None, None),
    ("Facturas (docena)", "facturas_dulce", "12 unidades", 35000, "Panadería", "FCT-12", "10", "R.S.P.A. 12350", True, None, None, "Estilo argentino"),
    ("Facturas (media docena)", "facturas_dulce", "6 unidades", 18000, "Panadería", "FCT-06", "10", None, False, None, None, None),
    ("Medialunas (docena)", "medialunas", "12 unidades", 38000, "Panadería", "MED-12", "10", "R.S.P.A. 12351", True, None, None, None),
    ("Medialunas (unidad)", "medialunas", "1 unidad", 3500, "Panadería", "MED-01", "10", None, False, None, None, None),
    # Specialty
    ("Appeltaart (torta)", "appeltaart", "1 unidad", 28000, "Tortas", "APT-01", "10", None, True, None, None, "Torta de manzana holandesa"),
    ("Tompoezen (unidad)", "tompoezen", "1 unidad", 12000, "Pastelería", "TMP-01", "10", None, False, None, None, "Postre holandés"),
    ("Docena tompoezen", "tompoezen", "12 unidades", 130000, "Pastelería", "TMP-12", "10", "R.S.P.A. 12352", False, None, None, None),
    ("Oliebollen (unidad)", "oliebollen", "1 unidad", 5500, "Panadería", "OLB-01", "10", None, False, None, None, "Buñuelos"),
    ("Docena oliebollen", "oliebollen", "12 unidades", 60000, "Panadería", "OLB-12", "10", "R.S.P.A. 12353", False, None, None, "Encargo"),
    ("Babka de chocolate (entera)", "babka_chocolate", "1 unidad", 22000, "Tortas", "BBK-01", "10", None, True, None, None, "Torta trenzada"),
    ("Stroopwafel (unidad)", "stroopwafel", "1 unidad", 7000, "Pastelería", "STR-01", "10", None, False, None, None, "Galletita wafer"),
    ("Docena stroopwafels", "stroopwafel", "12 unidades", 75000, "Pastelería", "STR-12", "10", "R.S.P.A. 12354", False, None, None, None),
    # Pan
    ("Pan lactal", "pan_lactal", "1 unidad", 12000, "Panadería", "PL-01", "10", None, True, None, None, "Para sándwich"),
    ("Pan lactal (x2)", "pan_lactal", "2 unidades", 22000, "Panadería", "PL-02", "10", None, False, None, None, None),
    # Salados
    ("Empanada de carne", "empanada_carne", "1 unidad", 8500, "Salados", "EMP-01", "10", None, True, None, None, "Estilo casero"),
    ("Docena empanadas", "empanada_carne", "12 unidades", 95000, "Salados", "EMP-12", "10", "R.S.P.A. 12355", False, None, None, None),
    ("Chipa guazú", "chipa_guazu", "1 unidad", 8500, "Salados", "CHG-01", "10", None, True, None, None, "Especial paraguayo"),
    ("Docena chipa guazú", "chipa_guazu", "12 unidades", 95000, "Salados", "CHG-12", "10", "R.S.P.A. 12356", False, None, None, None),
    ("Sopa paraguaya", "sopa_paraguaya", "1 porción", 6500, "Salados", "SPP-01", "10", None, True, None, None, "Clásico paraguayo"),
    ("Tostado JyQ", "tostado_jyq", "1 unidad", 12000, "Salados", "TST-01", "10", None, True, None, None, "Para el desayuno"),
    # Tortas
    ("Torta de chocolate entera", "torta_chocolate", "1 torta (12 porciones)", 220000, "Tortas", "TCH-12", "10", "R.S.P.A. 12357", True, None, None, "Encargo 24h antes"),
    ("Torta de vainilla entera", "torta_vainilla", "1 torta (12 porciones)", 200000, "Tortas", "TV-12", "10", "R.S.P.A. 12358", False, None, None, None),
    ("Porción torta de chocolate", "torta_chocolate", "1 porción", 22000, "Tortas", "TCH-01", "10", None, True, None, None, None),
    ("Porción torta de vainilla", "torta_vainilla", "1 porción", 20000, "Tortas", "TV-01", "10", None, False, None, None, None),
    # Brownie y galletas
    ("Brownie (unidad)", "brownie_chocolate", "1 unidad", 9500, "Pastelería", "BRW-01", "10", None, True, None, None, "Húmedo"),
    ("Docena brownies", "brownie_chocolate", "12 unidades", 100000, "Pastelería", "BRW-12", "10", "R.S.P.A. 12359", False, None, None, None),
    ("Galleta con chips (unidad)", "galleta_chips", "1 unidad", 3500, "Panadería", "GCH-01", "10", None, True, None, None, "Para los niños"),
    ("Docena galletas chips", "galleta_chips", "12 unidades", 38000, "Panadería", "GCH-12", "10", "R.S.P.A. 12360", False, None, None, None),
    ("Galleta de miel (unidad)", "galleta_miel", "1 unidad", 3000, "Panadería", "GM-01", "10", None, False, None, None, None),
    # Otros
    ("Rosca de dulce de leche", "rosca_manjar", "1 unidad", 22000, "Panadería", "RSC-01", "10", None, True, None, None, "Especial fin de semana"),
    # Venta libre
    ("Venta libre", None, "1 unidad", 0, "Especiales", "VAR-001", "10", None, False, None, None, "Venta libre — definí el precio en el carrito."),
]

# 15 customers with realistic Paraguayan data
# Tuple: (name, phone, email, cedula, notes, loyalty_points, zone, address,
#         birthday, how_found, preferred_channel, marketing_consent,
#         dietary_restrictions, dietary_preferences, dietary_confirm_always)
CUSTOMERS: list[tuple] = [
    (
        "Roberto Giménez", "+595 981 555-100", "rgimenez@example.com", "3.456.789",
        "Cliente habitual. Pide todos los viernes.", 580, "Centro",
        "Av. España 567, casi Estados Unidos",
        "1985-03-15", "instagram", "whatsapp", True, None, None, False,
    ),
    (
        "María Eugenia Barrios", "+595 982 555-101", "mbarrios@example.com", "4.567.890",
        "Compra tortas para eventos. Encargos con 48h.", 1240, "Villa Morra",
        "Av. Mariscal López 2345",
        "1978-11-22", "facebook", "whatsapp", True, "sin-nueces", None, False,
    ),
    (
        "Carlos Pereira", "+595 983 555-102", "cpereira@example.com", "5.678.901",
        "Pedidos para la oficina. Empanadas + café.", 95, "Recoleta",
        "Brasil 345, Edif. Ana, Piso 4",
        None, "recomendacion", "mostrador", False, None, None, False,
    ),
    (
        "Ana Sosa", "+595 984 555-103", "asosa@example.com", "2.345.678",
        "Cliente nueva. Probó chipa guazú.", 30, "Lambaré",
        "Ruta 1 Km 12, Lambaré",
        "1992-07-30", "google", "mostrador", True, None, "vegano", False,
    ),
    (
        "Diego Maldonado", "+595 985 555-104", None, "3.567.890",
        "Prefiere factura de dulce de leche.", 220, "Centro",
        "Palma 456, casi 14 de Mayo",
        None, "cartel", "mostrador", False, None, None, False,
    ),
    (
        "Lucía Romero", "+595 986 555-105", "lromero@example.com", "4.678.901",
        "Madre con niño celíaco. Siempre pregunta por sin TACC.", 410, "Sajonia",
        "Av. Argentina 678",
        "1988-04-10", "recomendacion", "whatsapp", True, "sin-gluten", "sin-gluten", True,
    ),
    (
        "Pedro Vázquez", "+595 987 555-106", "pvazquez@example.com", "5.789.012",
        "Hombre de negocio. Paga con tarjeta. Factura siempre.", 680, "Villa Morra",
        "Av. Santa Teresa 1234",
        "1975-09-18", "instagram", "tarjeta", True, None, None, False,
    ),
    (
        "Sofía Candia", "+595 988 555-107", "scandia@example.com", "6.890.123",
        "Diseñadora gráfica. Encarga tortas decoradas.", 320, "Recoleta",
        "Sajonia 890",
        "1990-12-05", "instagram", "whatsapp", True, "sin-lactosa", "sin-lactosa", False,
    ),
    (
        "Fernando Torres", "+595 981 555-108", "ftorres@example.com", "1.234.567",
        "Practicante. Celíaco. Solo compra sin TACC.", 145, "Centro",
        "Iturbe 234",
        "2000-02-28", "google", "mostrador", True, "sin-gluten", "sin-gluten", True,
    ),
    (
        "Patricia Méndez", "+595 982 555-109", "pmendez@example.com", "2.345.679",
        "Madre vegana. Pide a menudo opciones veganas.", 280, "Villa Morra",
        "Av. Brasil 567",
        "1983-08-14", "facebook", "whatsapp", True, "vegano", "vegano", False,
    ),
    (
        "Andrés Colmán", "+595 983 555-110", None, None,
        "Cliente ocasional. Sin preferencias especiales.", 0, "Recoleta",
        None, None, "recomendacion", "efectivo", False, None, None, False,
    ),
    (
        "Laura Ortellado", "+595 984 555-111", "lortellado@example.com", "3.678.901",
        "Profesional joven. Pide café + medialuna a diario.", 175, "Centro",
        "Independencia Nacional 345",
        "1995-05-20", "instagram", "mostrador", True, None, None, False,
    ),
    (
        "Mauro Cáceres", "+595 985 555-112", "mcaceres@example.com", "4.789.012",
        "Fiestero. Pide tortas grandes para eventos.", 540, "Sajonia",
        "Av. Eusebio Ayala 2345",
        "1980-10-08", "cartel", "transferencia", True, None, None, False,
    ),
    (
        "Rosa Valdez", "+595 986 555-113", "rvaldez@example.com", "5.890.123",
        "Adulto mayor. Pide pan lactal todos los lunes.", 980, "Centro",
        "México 567",
        "1955-06-25", "recomendacion", "efectivo", False, "sin-azucar", None, False,
    ),
    (
        "Julio Benítez", "+595 987 555-114", None, None,
        "Constructor. Pide facturas para el equipo.", 60, "Lambaré",
        "Ruta 2 Km 18",
        "1970-01-12", "cartel", "efectivo", False, None, None, False,
    ),
]

# 12 pedidos across statuses
# Tuple: (customer_idx, days_from_now, hour, minute, status, payment_intent,
#         channel_idx (Channel enum), notes, line_items: list[(product_name, qty)])
# Channel: 0=MOSTRADOR, 1=WHATSAPP, 2=PEDIDOSYA, 3=PHONE
PEDIDOS: list[tuple] = [
    # Pending / past (in history)
    (0, -30, 10, 0, "fulfilled", "efectivo", 0, "Cliente habitual, viernes", [("Pan lactal", 1), ("Docena muffins chocolate", 1)]),
    (1, -28, 14, 30, "fulfilled", "transferencia", 1, "Pedido con factura", [("Cheesecake entera frutilla", 1)]),
    (3, -21, 9, 0, "fulfilled", "efectivo", 0, None, [("Chipa guazú", 6)]),
    (5, -14, 16, 0, "fulfilled", "efectivo", 0, "Cliente celíaca", [("Torta de chocolate entera", 1)]),
    (6, -7, 11, 0, "fulfilled", "tarjeta", 0, "Factura con RUC", [("Torta de chocolate entera", 2)]),
    (8, -5, 8, 30, "fulfilled", "efectivo", 0, "Para la oficina", [("Tostado JyQ", 4), ("Café (no vendido)", 0)]),
    # Active pedidos
    (2, -2, 10, 30, "fulfilled", "tarjeta", 0, "Ya retirado", [("Docena empanadas", 1), ("Tostado JyQ", 2)]),
    (4, -1, 15, 0, "ready", "efectivo", 1, "Llamó por WhatsApp. Listo para retirar.", [("Muffin de chocolate", 6)]),
    (9, 0, 11, 0, "ready", "transferencia", 1, "Vegan options", [("Facturas (docena)", 1)]),
    (12, 0, 18, 0, "confirmed", "transferencia", 1, "Para evento mañana a las 20h", [("Torta de chocolate entera", 1), ("Docena cupcakes chocolate", 0)]),
    (11, 1, 9, 0, "confirmed", "efectivo", 0, "Pedido diario", [("Pan lactal", 1), ("Medialunas (docena)", 1)]),
    (13, 2, 16, 0, "pending", "efectivo", 3, "Llamó por teléfono. Para lunes 16h.", [("Docena muffins vainilla", 1)]),
    (10, 1, 14, 0, "pending", "efectivo", 0, "Vino a la tienda a preguntar", [("Docena galletas chips", 1)]),
    # Future / delivery
    (7, 1, 11, 0, "confirmed", "transferencia", 1, "Decorada con flores", [("Torta de chocolate entera", 1)]),
]

# Freezer temperature log (last 14 days, 2 readings per day)
FREEZER_TEMP_DAYS = 14

# HACCP — every 12 hours, last 14 days
HACCP_TEMP_MIN_C = -22.0
HACCP_TEMP_MAX_C = -16.0

# Market benchmarks
# Tuple: (label, our_wholesale_gs, our_retail_gs, market_avg_gs, market_min_gs)
BENCHMARKS: list[tuple[str, int, int, int, int]] = [
    ("Chipa grande", 4500, 7000, 6500, 5000),
    ("Muffin de vainilla", 5200, 8000, 9000, 7000),
    ("Muffin de chocolate", 5500, 8500, 9500, 7500),
    ("Pan de queso", 4000, 6500, 6000, 4500),
    ("Galleta de miel", 2000, 3000, 3500, 2500),
    ("Hojaldre de jamón", 12000, 18000, 18000, 15000),
    ("Empanada de carne", 5500, 8500, 8000, 6000),
    ("Croissant", 7000, 11000, 12000, 9000),
    ("Sopa paraguaya", 4000, 6500, 6000, 4500),
    ("Chocotorta", 15000, 22000, 23000, 18000),
    ("Brownie", 6000, 9500, 9000, 7000),
    ("Pão de queijo", 4500, 7000, 6500, 5000),
    ("Torta de chocolate (porción)", 14000, 22000, 24000, 18000),
    ("Medialuna", 3500, 5500, 5500, 4000),
    ("Factura de crema", 4500, 7000, 7000, 5000),
    ("Tostado JyQ", 8000, 12500, 12000, 9500),
    ("Budín de pan", 12000, 18000, 17000, 14000),
    ("Cheesecake (porción)", 14000, 25000, 26000, 20000),
    ("Pan lactal", 7500, 12000, 11000, 8500),
    ("Docena muffins", 55000, 85000, 88000, 75000),
    ("Stroopwafel (unidad)", 4500, 7000, 8000, 5500),
    ("Rosca de dulce de leche", 13000, 22000, 21000, 17000),
]

# Waste log entries
# Tuple: (ingredient_name, qty, reason, days_ago, recorded_by, notes)
WASTE_LOG: list[tuple[str, float, str, int, str, str | None]] = [
    ("leche entera", 0.5, "vencimiento", 12, "lucia", "Caja próxima a vencer"),
    ("frutilla congelada", 0.3, "descongelado", 8, "diego", "Descongelada por corte eléctrico"),
    ("manteca", 0.2, "mal_estado", 5, "lucia", "Rancio"),
    ("huevos", 6, "rotura", 4, "saskia", "Caja rota al recibir del proveedor"),
    ("harina 0000", 0.5, "derrame", 2, "diego", "Bolsa rota"),
    ("queso crema", 0.3, "vencimiento", 1, "saskia", "Una vez abierto dura poco"),
    ("chocolate chips", 0.2, "mal_estado", 15, "lucia", "Bolsa mal cerrada"),
    ("leche condensada", 0.4, "mal_estado", 20, "saskia", "Lata hinchada"),
]

# Initial stock movement records (one per ingredient: positive entry)
# This documents the seed's opening balance for audit purposes.

# Production plan template (weekly, every weekday gets a basic plan)
# Tuple: (weekday 0-6, product_idx_in_PRODUCTS, qty, notes)
PRODUCTION_TEMPLATES: list[tuple[int, int, float, str | None]] = [
    (0, 0, 24, "Lunes base"),
    (0, 1, 12, None),
    (0, 24, 6, "Lunes base"),
    (1, 0, 18, "Martes"),
    (1, 1, 12, None),
    (1, 24, 8, None),
    (2, 0, 24, "Miércoles"),
    (2, 24, 8, None),
    (3, 0, 30, "Jueves popular"),
    (3, 1, 18, None),
    (3, 24, 10, None),
    (4, 0, 36, "Viernes — día pico"),
    (4, 1, 24, "Viernes — día pico"),
    (4, 13, 12, "Facturas para el fin de semana"),
    (4, 24, 12, "Pan para el fin de semana"),
    (5, 0, 24, "Sábado"),
    (5, 1, 18, None),
    (5, 13, 12, None),
    (5, 24, 6, None),
    (6, 0, 18, "Domingo"),
    (6, 24, 4, None),
]


@dataclass
class SazonReport:
    """Counts of rows inserted by seed_sazon()."""

    tenants: int = 0
    users: int = 0
    settings_kv: int = 0
    categories: int = 0
    payment_methods: int = 0
    margin_tiers: int = 0
    stock_statuses: int = 0
    storage_types: int = 0
    storage_keywords: int = 0
    date_presets: int = 0
    message_templates: int = 0
    delivery_zones: int = 0
    compliance: int = 0
    suppliers: int = 0
    ingredients: int = 0
    ingredient_variants: int = 0
    ingredient_price_events: int = 0
    recipes: int = 0
    recipe_lines: int = 0
    products: int = 0
    customers: int = 0
    customer_addresses: int = 0
    tags: int = 0
    production_templates: int = 0
    production_completions: int = 0
    pedidos: int = 0
    pedido_lines: int = 0
    sales: int = 0
    stock_movements: int = 0
    waste_log: int = 0
    shopping_list: int = 0
    haccp_temps: int = 0
    market_benchmarks: int = 0
    audit_log_rows: int = 0
    skipped_existing: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, int]:
        return {
            "tenants": self.tenants,
            "users": self.users,
            "settings_kv": self.settings_kv,
            "categories": self.categories,
            "payment_methods": self.payment_methods,
            "margin_tiers": self.margin_tiers,
            "stock_statuses": self.stock_statuses,
            "storage_types": self.storage_types,
            "storage_keywords": self.storage_keywords,
            "date_presets": self.date_presets,
            "message_templates": self.message_templates,
            "delivery_zones": self.delivery_zones,
            "compliance": self.compliance,
            "suppliers": self.suppliers,
            "ingredients": self.ingredients,
            "ingredient_variants": self.ingredient_variants,
            "ingredient_price_events": self.ingredient_price_events,
            "recipes": self.recipes,
            "recipe_lines": self.recipe_lines,
            "products": self.products,
            "customers": self.customers,
            "customer_addresses": self.customer_addresses,
            "tags": self.tags,
            "production_templates": self.production_templates,
            "production_completions": self.production_completions,
            "pedidos": self.pedidos,
            "pedido_lines": self.pedido_lines,
            "sales": self.sales,
            "stock_movements": self.stock_movements,
            "waste_log": self.waste_log,
            "shopping_list": self.shopping_list,
            "haccp_temps": self.haccp_temps,
            "market_benchmarks": self.market_benchmarks,
            "audit_log_rows": self.audit_log_rows,
            **self.skipped_existing,
        }


def _ensure_tenant(session: Session, slug: str, name: str, color: str, currency: str) -> tuple[Tenant, bool]:
    """Idempotent: get-or-create a tenant. Returns (tenant, was_created)."""
    t = session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if t is None:
        t = Tenant(
            slug=slug,
            business_name=name,
            primary_color=color,
            currency=currency,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(t)
        session.flush()
        return t, True
    return t, False


def _ensure_user(session: Session, username: str, password: str, *, role: str = "admin") -> tuple[User, bool]:
    """Idempotent: get-or-create a user with bcrypt-hashed password. Returns (user, was_created)."""
    u = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if u is None:
        u = User(
            username=username,
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_login_at=None,
            role=role,
        )
        u.set_password(password)
        session.add(u)
        session.flush()
        return u, True
    return u, False


# === Onboarding guard helpers ===
# The sazon seeder writes 6 AppMeta keys. UI / dashboard can use these to
# decide whether to show the "Welcome — first run" modal, the "Load
# La Vaquita Holandesa demo data" button, or just a "Seeded by …" badge.
# See tests/test_sazon_seed.py::test_app_meta_onboarding_guard.

SAZON_META_KEYS = (
    "sazon_seed_version",
    "sazon_seeded_at",
    "sazon_tenant_slug",
    "sazon_tenant_name",
    "sazon_admin_user",
    "sazon_loaded",
)


def is_sazon_seeded(session: Session) -> bool:
    """True iff seed_sazon has run on this DB at least once.

    Cheap single-row check. Used by the dashboard to decide whether to
    show a "Welcome — La Vaquita Holandesa is ready" banner.
    """
    row = session.execute(
        select(AppMeta).where(AppMeta.key == "sazon_loaded")
    ).scalar_one_or_none()
    return row is not None and (row.value or "").lower() in ("true", "1", "yes")


def sazon_meta(session: Session) -> dict[str, str]:
    """Return all 6 sazon_* AppMeta rows as a dict (empty if not seeded)."""
    rows = session.execute(
        select(AppMeta).where(AppMeta.key.in_(SAZON_META_KEYS))
    ).scalars().all()
    return {r.key: r.value for r in rows if r.value is not None}


def seed_sazon(session: Session, *, overwrite: bool = False, days_of_history: int = 90) -> SazonReport:
    """Idempotent comprehensive seed for La Vaquita Holandesa.

    Args:
        session: SQLAlchemy session
        overwrite: if True, delete all data from the relevant tables first
        days_of_history: how many days of synthetic sales to generate

    Returns:
        SazonReport with counts of inserted rows
    """
    rng = random.Random(42)
    report = SazonReport()

    # Anchor date used by production completions, pedidos, bank
    # transactions, and (elsewhere) the sales loop. We pin it to
    # today-anchored-on-this-call so the natural-key dedup logic for all
    # of these stays stable across re-runs of the same seed_sazon call.
    seed_anchor_date = datetime.utcnow().date()

    if overwrite:
        _delete_sazon_data(session)

    # === 1. Tenants ===
    sazon_tenant, was_created = _ensure_tenant(session, TENANT_SLUG, TENANT_NAME, TENANT_COLOR, TENANT_CURRENCY)
    if was_created:
        report.tenants += 1
    default_tenant, _ = _ensure_tenant(session, DEFAULT_TENANT_SLUG, "Default", "#7b3f00", "Gs.")
    logger.info(f"seed: tenant '{TENANT_NAME}' (slug={TENANT_SLUG})")

    # === 2. Users ===
    saskia_user, was_created = _ensure_user(session, SASKIA_USER, SASKIA_PASSWORD, role="admin")
    if was_created:
        report.users += 1
    for username, password, full_name, email in CASHIER_USERS:
        u, was_created = _ensure_user(session, username, password, role="cashier")
        if was_created:
            report.users += 1
    logger.info(f"seed: {report.users} users (Saskia + 2 cashiers)")

    # === 3. SettingsKV (BRANDING) ===
    branding_settings = {
        "branding.business_name": TENANT_NAME,
        "branding.tagline": "Panadería artesanal desde 1985",
        "branding.footer": "© 2025 La Vaquita Holandesa — Hecho con cariño en Asunción",
        "branding.business_type": "panaderia",
        "branding.accent_color": TENANT_COLOR,
        "branding.contact_email": BUSINESS_INFO["email"],
        "branding.contact_phone": BUSINESS_INFO["phone"],
        "branding.address": BUSINESS_INFO["address"],
        "branding.logo_filename": "",
        "branding.favicon_filename": "",
        "branding.hero_filename": "",
        "ops.business_hours": BUSINESS_INFO["business_hours"],
        "ops.pickup_address": BUSINESS_INFO["address"],
        "ops.pickup_instructions": "Tocar timbre. Si está cerrado, llamar al " + BUSINESS_INFO["phone"] + ".",
    }
    for k, v in branding_settings.items():
        existing = session.execute(select(SettingsKV).where(SettingsKV.key == k)).scalar_one_or_none()
        if existing is None:
            session.add(SettingsKV(key=k, value_json=v, updated_at=datetime.utcnow()))
            report.settings_kv += 1
        else:
            report.skipped_existing["settings_kv_existing"] = (
                report.skipped_existing.get("settings_kv_existing", 0) + 1
            )
    logger.info(f"seed: {report.settings_kv} settings_kv (BRANDING + OPS)")

    # === 4. Categories ===
    for name, sort_order, is_active in CATEGORIES_PRODUCT:
        existing = session.execute(
            select(Category).where(Category.scope == "product", Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            session.add(Category(name=name, scope="product", sort_order=sort_order, is_active=is_active))
            report.categories += 1
    for name, sort_order, is_active in CATEGORIES_RECIPE:
        existing = session.execute(
            select(Category).where(Category.scope == "recipe_family", Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Category(name=name, scope="recipe_family", sort_order=sort_order, is_active=is_active)
            )
            report.categories += 1
    logger.info(f"seed: {report.categories} categories")

    # === 5. Payment methods ===
    for code, label, requires_ref, fee, sort_order, is_default, is_active, notes in PAYMENT_METHODS:
        existing = session.execute(
            select(PaymentMethod).where(PaymentMethod.code == code)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PaymentMethod(
                    code=code,
                    label=label,
                    requires_reference=requires_ref,
                    fee_pct=fee,
                    sort_order=sort_order,
                    is_default=is_default,
                    is_active=is_active,
                    notes=notes,
                )
            )
            report.payment_methods += 1
    logger.info(f"seed: {report.payment_methods} payment methods")

    # === 6. Margin tiers ===
    for code, label, min_cost, max_cost, sort_order, notes in MARGIN_TIERS:
        existing = session.execute(select(MarginTier).where(MarginTier.code == code)).scalar_one_or_none()
        if existing is None:
            session.add(
                MarginTier(
                    code=code,
                    label=label,
                    min_cost_gs=min_cost,
                    max_cost_gs=max_cost,
                    sort_order=sort_order,
                    is_active=True,
                    notes=notes,
                )
            )
            report.margin_tiers += 1
    logger.info(f"seed: {report.margin_tiers} margin tiers")

    # === 7. Stock status config ===
    for code, label, ratio, days, sort_order, notes in STOCK_STATUSES:
        existing = session.execute(
            select(StockStatusConfig).where(StockStatusConfig.code == code)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                StockStatusConfig(
                    code=code,
                    label=label,
                    threshold_ratio=ratio,
                    threshold_days=days,
                    sort_order=sort_order,
                    is_active=True,
                    notes=notes,
                )
            )
            report.stock_statuses += 1
    logger.info(f"seed: {report.stock_statuses} stock statuses")

    # === 8. Storage types ===
    for code, label, tmin, tmax, hum, sort_order, notes in STORAGE_TYPES:
        existing = session.execute(select(StorageType).where(StorageType.code == code)).scalar_one_or_none()
        if existing is None:
            session.add(
                StorageType(
                    code=code,
                    label=label,
                    requires_temp_min=tmin,
                    requires_temp_max=tmax,
                    requires_humidity_max=hum,
                    sort_order=sort_order,
                    is_active=True,
                    notes=notes,
                )
            )
            report.storage_types += 1
    logger.info(f"seed: {report.storage_types} storage types")

    # === 9. Storage keywords ===
    for code, keyword, sort_order in STORAGE_KEYWORDS:
        existing = session.execute(
            select(StorageKeyword).where(
                StorageKeyword.storage_code == code, StorageKeyword.keyword == keyword
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                StorageKeyword(
                    storage_code=code,
                    keyword=keyword,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            report.storage_keywords += 1
    logger.info(f"seed: {report.storage_keywords} storage keywords")

    # === 10. Date presets ===
    for code, label, days, is_default, sort_order in DATE_PRESETS:
        existing = session.execute(
            select(DateRangePreset).where(DateRangePreset.code == code)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                DateRangePreset(
                    code=code,
                    label=label,
                    days=days,
                    is_default=is_default,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            report.date_presets += 1
    logger.info(f"seed: {report.date_presets} date presets")

    # === 11. Message templates ===
    for channel, key, subject, body, notes in MESSAGE_TEMPLATES:
        existing = session.execute(
            select(MessageTemplate).where(
                MessageTemplate.channel == channel,
                MessageTemplate.key == key,
                MessageTemplate.locale == "es-PY",
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                MessageTemplate(
                    channel=channel,
                    key=key,
                    subject=subject,
                    body=body,
                    locale="es-PY",
                    is_active=True,
                    version=1,
                    notes=notes,
                )
            )
            report.message_templates += 1
    logger.info(f"seed: {report.message_templates} message templates")

    # === 12. Delivery zones ===
    for code, name, coverage, radius, cost, min_order, mins, notes in DELIVERY_ZONES:
        existing = session.execute(
            select(DeliveryZone).where(DeliveryZone.code == code)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                DeliveryZone(
                    code=code,
                    name=name,
                    coverage_text=coverage,
                    radius_km=radius,
                    delivery_cost_gs=cost,
                    min_order_gs=min_order,
                    delivery_minutes=mins,
                    is_active=True,
                    position=10,
                    notes=notes,
                )
            )
            report.delivery_zones += 1
    logger.info(f"seed: {report.delivery_zones} delivery zones")

    # === 13a. Channels ===
    for code, label, sort_order, is_default, notes in CHANNELS:
        existing = session.execute(select(Channel).where(Channel.code == code)).scalar_one_or_none()
        if existing is None:
            session.add(
                Channel(
                    code=code,
                    label=label,
                    sort_order=sort_order,
                    is_default=is_default,
                    is_active=True,
                    notes=notes,
                )
            )
    logger.info(f"seed: {len(CHANNELS)} channels")

    # === 13. Compliance info (single-row) ===
    existing_compliance = session.execute(select(ComplianceInfo).where(ComplianceInfo.id == 1)).scalar_one_or_none()
    if existing_compliance is None:
        compliance_copy = dict(COMPLIANCE)
        compliance_copy["updated_at"] = datetime.utcnow()
        ci = ComplianceInfo(id=1, **compliance_copy)
        session.add(ci)
        report.compliance = 1
    logger.info(f"seed: compliance info (La Vaquita Holandesa S.A.)")

    # === 14. Suppliers ===
    supplier_objs: list[Supplier] = []
    for name, contact, phone, email, address, ruc, notes in SUPPLIERS:
        existing = session.execute(select(Supplier).where(Supplier.name == name)).scalar_one_or_none()
        if existing is None:
            s = Supplier(
                name=name,
                contact_name=contact,
                phone=phone,
                email=email,
                address=address,
                ruc=ruc,
                is_active=True,
                notes=notes,
            )
            session.add(s)
            session.flush()
            supplier_objs.append(s)
            report.suppliers += 1
        else:
            supplier_objs.append(existing)
    logger.info(f"seed: {report.suppliers} suppliers")

    # === 15. Ingredients + variants + price events ===
    ingredient_objs_by_name: dict[str, Ingredient] = {}
    for ing_tuple in INGREDIENTS:
        (
            name, unit, stock_qty, price_gs, min_stock, shelf_days, storage, category,
            allergens, dietary_tags, supplier_idx, package_size, package_unit, package_price_gs,
            lot_required, may_contain_gluten, water_aw, humidity_max, temp_min, temp_max,
        ) = ing_tuple
        existing = session.execute(select(Ingredient).where(Ingredient.name == name)).scalar_one_or_none()
        if existing is None:
            ing = Ingredient(
                name=name,
                unit=unit,
                stock_qty=stock_qty,
                purchase_price_gs=price_gs if price_gs > 0 else None,
                purchase_price_updated_at=datetime.utcnow(),
                min_stock_qty=min_stock,
                max_stock_qty=min_stock * 3,
                shelf_life_days=shelf_days,
                storage=storage,
                notes=None,
                category=category,
                subcategory=None,
                role=None,
                allergens=allergens,
                dietary_tags=dietary_tags,
                lead_time_days=3,
                supplier_id=supplier_objs[supplier_idx].id if supplier_idx < len(supplier_objs) else None,
                temp_min_c=temp_min,
                temp_max_c=temp_max,
                humidity_max_pct=humidity_max,
                water_activity_aw=water_aw,
                lot_required=lot_required,
                may_contain_gluten=may_contain_gluten,
                opening_stock_qty=stock_qty,
                opening_stock_date=date.today().isoformat(),
                reorder_point=min_stock * 1.5,
            )
            session.add(ing)
            session.flush()
            ingredient_objs_by_name[name] = ing
            report.ingredients += 1

            # Variant (preferred)
            if package_size > 0:
                variant = IngredientVariant(
                    ingredient_id=ing.id,
                    package_size=package_size,
                    package_unit=package_unit,
                    purchase_price_gs=package_price_gs if package_price_gs > 0 else None,
                    stock_qty=stock_qty / package_size if package_size > 0 else 0,
                    supplier_id=supplier_objs[supplier_idx].id if supplier_idx < len(supplier_objs) else None,
                    preferred=True,
                    notes="Variante preferida (seed)",
                )
                session.add(variant)
                report.ingredient_variants += 1

            # Price history events (3 events over past 60 days)
            if price_gs > 0:
                for days_ago in [60, 30, 7]:
                    variation = rng.uniform(0.93, 1.07)
                    session.add(
                        IngredientPriceEvent(
                            ingredient_id=ing.id,
                            price_gs=int(price_gs * variation),
                            recorded_at=datetime.utcnow() - timedelta(days=days_ago),
                            source="restock",
                        )
                    )
                    report.ingredient_price_events += 1
        else:
            ingredient_objs_by_name[name] = existing
            report.skipped_existing["ingredients_existing"] = (
                report.skipped_existing.get("ingredients_existing", 0) + 1
            )
    logger.info(f"seed: {report.ingredients} ingredients + {report.ingredient_variants} variants + {report.ingredient_price_events} price events")

    # === 16. Recipes + RecipeLines ===
    recipe_objs_by_name: dict[str, Recipe] = {}
    for recipe_tuple in RECIPES:
        name, yield_qty, yield_unit, prep, cook, diff, family, menu_tags, dietary, notes = recipe_tuple
        existing = session.execute(select(Recipe).where(Recipe.name == name)).scalar_one_or_none()
        if existing is None:
            r = Recipe(
                name=name,
                yield_qty=yield_qty,
                yield_unit=yield_unit,
                prep_minutes=prep,
                cook_minutes=cook,
                difficulty=diff,
                family=family,
                menu_tags=menu_tags,
                dietary_tags=dietary,
                notes=notes,
                yield_percentage=0.95,
                direct_labor_minutes=prep,
            )
            session.add(r)
            session.flush()
            recipe_objs_by_name[name] = r
            report.recipes += 1
        else:
            recipe_objs_by_name[name] = existing
            report.skipped_existing["recipes_existing"] = (
                report.skipped_existing.get("recipes_existing", 0) + 1
            )

    # Recipe lines
    for recipe_name, ing_name, qty, line_unit, notes in RECIPE_LINES:
        recipe_id = recipe_objs_by_name.get(recipe_name)
        ing_id = ingredient_objs_by_name.get(ing_name)
        if not recipe_id or not ing_id:
            logger.warning(f"seed: missing ref for recipe_line {recipe_name}/{ing_name}, skipping")
            continue
        # Idempotent: same recipe + same ingredient + same line_unit + same qty
        existing = session.execute(
            select(RecipeLine).where(
                RecipeLine.recipe_id == recipe_id.id,
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id == ing_id.id,
                RecipeLine.line_unit == line_unit,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                RecipeLine(
                    recipe_id=recipe_id.id,
                    line_kind="ingredient",
                    line_ref_id=ing_id.id,
                    qty=qty,
                    line_unit=line_unit,
                    notes=notes,
                )
            )
            report.recipe_lines += 1
    logger.info(f"seed: {report.recipe_lines} recipe lines")

    # === 17. Products ===
    product_objs_by_name: dict[str, Product] = {}
    for prod_tuple in PRODUCTS:
        (
            name, recipe_name, portion_label, sale_price, category, sku, iva_rate,
            rspa_number, is_favorite, dietary, image_url, notes,
        ) = prod_tuple
        existing = session.execute(select(Product).where(Product.name == name)).scalar_one_or_none()
        if existing is None:
            recipe = recipe_objs_by_name.get(recipe_name) if recipe_name else None
            p = Product(
                name=name,
                recipe_id=recipe.id if recipe else None,
                portion_label=portion_label,
                sale_price_gs=sale_price,
                notes=notes,
                sku=sku,
                is_available=True,
                image_url=image_url,
                category=category,
                tags=dietary,
                is_favorite=is_favorite,
                iva_rate=iva_rate,
                requires_rspa=rspa_number is not None,
                rspa_number=rspa_number,
                rspa_expiry="2027-12-31" if rspa_number else None,
            )
            session.add(p)
            session.flush()
            product_objs_by_name[name] = p
            report.products += 1
        else:
            product_objs_by_name[name] = existing
    logger.info(f"seed: {report.products} products")

    # === 18. Tags ===
    # Make sure the starter tags are in place
    ensure_starter_tags(session)
    # Add a few custom tags
    custom_tags = [
        ("popular", TagKind.PRODUCT.value, "#FF9800"),
        ("premium", TagKind.PRODUCT.value, "#9C27B0"),
        ("docena", TagKind.PRODUCT.value, "#2196F3"),
        ("individual", TagKind.PRODUCT.value, "#4CAF50"),
        ("vegano", TagKind.PRODUCT.value, "#4CAF50"),
        ("sin-gluten", TagKind.PRODUCT.value, "#FFC107"),
        ("sin-lactosa", TagKind.PRODUCT.value, "#FFC107"),
        ("vegano", TagKind.INGREDIENT.value, "#4CAF50"),
    ]
    for tag_name, kind, color in custom_tags:
        t = ensure_tag(session, tag_name, kind)
        if t.color == "#757575":  # default
            t.color = color
            session.flush()
        report.tags += 1
    # Apply tags to products
    popular = ensure_tag(session, "popular", TagKind.PRODUCT.value)
    premium = ensure_tag(session, "premium", TagKind.PRODUCT.value)
    docena = ensure_tag(session, "docena", TagKind.PRODUCT.value)
    individual = ensure_tag(session, "individual", TagKind.PRODUCT.value)
    for prod_name, _, _, _, _, _, _, _, is_fav, _, _, _ in PRODUCTS:
        prod = product_objs_by_name.get(prod_name)
        if prod is None:
            continue
        if is_fav:
            tag_target(session, popular, TagKind.PRODUCT.value, prod.id)
            tag_target(session, premium, TagKind.PRODUCT.value, prod.id)
        if "12" in prod.portion_label or "docena" in prod.portion_label.lower():
            tag_target(session, docena, TagKind.PRODUCT.value, prod.id)
        elif "1 unidad" == prod.portion_label:
            tag_target(session, individual, TagKind.PRODUCT.value, prod.id)
    logger.info(f"seed: tags applied")

    # === 19. Customers + addresses ===
    customer_objs: list[Customer] = []
    for cust_tuple in CUSTOMERS:
        (
            name, phone, email, cedula, notes, loyalty, zone, address,
            birthday, how_found, pref_channel, marketing, diet_r, diet_p, diet_confirm,
        ) = cust_tuple
        existing = session.execute(
            select(Customer).where(Customer.phone == phone)
        ).scalar_one_or_none()
        if existing is None:
            c = Customer(
                name=name,
                phone=phone,
                email=email,
                cedula=cedula,
                notes=notes,
                loyalty_points=loyalty,
                zone=zone,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                birthday=birthday,
                how_found=how_found,
                preferred_channel=pref_channel,
                marketing_consent=marketing,
                dietary_restrictions=diet_r,
                dietary_preferences=diet_p,
                dietary_confirm_always=diet_confirm,
            )
            session.add(c)
            session.flush()
            customer_objs.append(c)
            report.customers += 1

            if address:
                addr = CustomerAddress(
                    customer_id=c.id,
                    label="Casa" if zone not in ("Centro", "Recoleta") else "Principal",
                    address_text=address,
                    is_default=True,
                    calle_principal=address.split(",")[0] if "," in address else address,
                    ciudad="Asunción" if zone in ("Centro", "Recoleta", "Sajonia", "Villa Morra") else "Lambaré",
                    pais="Paraguay",
                    address_kind="home",
                    sort_order=0,
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                session.add(addr)
                report.customer_addresses += 1
        else:
            customer_objs.append(existing)
    logger.info(f"seed: {report.customers} customers + {report.customer_addresses} addresses")

    # === 20. Production plan templates ===
    for weekday, prod_idx, qty, notes in PRODUCTION_TEMPLATES:
        if prod_idx >= len(PRODUCTS):
            continue
        prod_name = PRODUCTS[prod_idx][0]
        prod = product_objs_by_name.get(prod_name)
        if not prod:
            continue
        existing = session.execute(
            select(ProductionPlanTemplate).where(
                ProductionPlanTemplate.weekday == weekday,
                ProductionPlanTemplate.product_id == prod.id,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                ProductionPlanTemplate(
                    weekday=weekday,
                    product_id=prod.id,
                    qty=qty,
                    notes=notes,
                    updated_at=datetime.utcnow(),
                    updated_by=SASKIA_USER,
                )
            )
            report.production_templates += 1
    logger.info(f"seed: {report.production_templates} production templates")

    # === 21. Production completions (last 7 days for popular products) ===
    # Use seed_anchor_date (defined at top of seed_sazon) so the anchor is
    # stable across re-runs of the same seed_sazon call. Without this,
    # the (product_id, for_date) natural-key dedup would miss on re-runs
    # and silently double the production completions.
    today = seed_anchor_date
    for days_ago in range(7):
        d = today - timedelta(days=days_ago)
        for prod_name in ["Muffin de vainilla", "Muffin de chocolate", "Pan lactal",
                          "Facturas (docena)", "Medialunas (docena)", "Tostado JyQ"]:
            prod = product_objs_by_name.get(prod_name)
            if not prod:
                continue
            existing = session.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == prod.id,
                    ProductionCompletion.for_date == d,
                )
            ).scalar_one_or_none()
            if existing is None:
                qty = rng.randint(8, 24)
                session.add(
                    ProductionCompletion(
                        product_id=prod.id,
                        for_date=d,
                        completed_qty=qty,
                        # Use anchor date for recorded_at (stable across re-runs)
                        recorded_at=datetime.combine(d, datetime.min.time()) + timedelta(hours=18),
                        status="done" if days_ago > 0 else "open",
                        notes="Cierre diario" if days_ago > 0 else None,
                        updated_at=datetime.utcnow() if days_ago > 0 else None,
                    )
                )
                report.production_completions += 1
    logger.info(f"seed: {report.production_completions} production completions (last 7 days)")

    # === 22. Pedidos + lines ===
    channel_codes = [c[0] for c in CHANNELS]
    for ped_tuple in PEDIDOS:
        cust_idx, days_ago, hour, minute, status, payment, channel_idx, notes, line_items = ped_tuple
        if cust_idx >= len(customer_objs):
            continue
        cust = customer_objs[cust_idx]
        promised_date = today + timedelta(days=days_ago)
        promised_dt = datetime.combine(promised_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
        token = secrets.token_urlsafe(16)
        # Skip empty line items (e.g. "Café (no vendido)")
        valid_lines = [(pn, q) for pn, q in line_items if q > 0 and pn in product_objs_by_name]
        if not valid_lines:
            continue
        channel_code = (
            channel_codes[channel_idx]
            if channel_idx < len(channel_codes)
            else Channel.MOSTRADOR.value  # P43: enum fallback
        )
        existing = session.execute(
            select(Pedido).where(
                Pedido.customer_id == cust.id,
                Pedido.promised_date == promised_date,
                Pedido.status == status,
            )
        ).scalar_one_or_none()
        if existing is None:
            ped = Pedido(
                customer_id=cust.id,
                customer_name=cust.name,
                customer_phone=cust.phone,
                promised_date=promised_date,
                promised_time=f"{hour:02d}:{minute:02d}",
                channel=channel_code,  # free-text VARCHAR
                status=status,
                payment_intent=payment,
                notes=notes,
                public_token=token,
                public_token_expires_at=datetime.utcnow() + timedelta(days=30),
                created_at=promised_dt - timedelta(hours=2),
                updated_at=promised_dt,
                fulfilled_at=promised_dt if status == "fulfilled" else None,
            )
            session.add(ped)
            session.flush()
            report.pedidos += 1
            for prod_name, qty in valid_lines:
                prod = product_objs_by_name[prod_name]
                line = PedidoLine(
                    pedido_id=ped.id,
                    product_id=prod.id,
                    qty=qty,
                    unit_price_gs=prod.sale_price_gs,
                    fulfilled_qty=qty if status == "fulfilled" else 0,
                )
                session.add(line)
                report.pedido_lines += 1
                # PedidoEvent
                session.add(
                    PedidoEvent(
                        pedido_id=ped.id,
                        ts=promised_dt - timedelta(hours=2),
                        actor=SASKIA_USER,
                        event_type="created",
                        payload_json={"channel": channel_code},
                    )
                )
                if status != "pending":
                    session.add(
                        PedidoEvent(
                            pedido_id=ped.id,
                            ts=promised_dt - timedelta(hours=1, minutes=30),
                            actor=SASKIA_USER,
                            event_type="status_change",
                            payload_json={"from": "pending", "to": "confirmed"},
                        )
                    )
                if status in ("ready", "fulfilled"):
                    session.add(
                        PedidoEvent(
                            pedido_id=ped.id,
                            ts=promised_dt - timedelta(minutes=30),
                            actor=SASKIA_USER,
                            event_type="status_change",
                            payload_json={"from": "confirmed", "to": "ready"},
                        )
                    )
                if status == "fulfilled":
                    session.add(
                        PedidoEvent(
                            pedido_id=ped.id,
                            ts=promised_dt,
                            actor=SASKIA_USER,
                            event_type="status_change",
                            payload_json={"from": "ready", "to": "fulfilled"},
                        )
                    )
    logger.info(f"seed: {report.pedidos} pedidos + {report.pedido_lines} pedido lines")

    # === 23. Sales (90 days of realistic data) ===
    sale_rows: list[Sale] = []
    stock_move_rows: list[StockMovement] = []

    # IMPORTANT: use a SEPARATE random instance for the sales loop so
    # that re-runs (where the rest of the seeder is a no-op via
    # `existing is not None` short-circuits) hit the same rng state at
    # the start of the sales loop. The top-level `rng` advances a
    # different amount in run 1 vs run 2 because skip-vs-do is
    # asymmetric; a dedicated sales_rng with its own seed gives us
    # deterministic, idempotent sales data.
    sales_rng = random.Random(43)

    # seed_anchor_date is defined at the top of seed_sazon (reused by
    # production completions, pedidos, bank transactions, and sales).
    # The sales loop computes day_start/day_end from sale_date which is
    # already anchored to seed_anchor_date.

    BATCH_SIZE = 25
    for day_offset in range(days_of_history):
        # day 0 = oldest, day (days_of_history-1) = the seed_anchor_date
        sale_date = datetime.combine(
            seed_anchor_date - timedelta(days=days_of_history - 1 - day_offset),
            datetime.min.time(),
        )
        weekday = sale_date.weekday()  # 0=Mon, 6=Sun
        # Volume skew: weekends +40%, payday +60%, otherwise baseline
        base_count = 8
        if weekday >= 5:
            base_count = math.ceil(base_count * 1.4)
        if sale_date.day in (1, 15):
            base_count = math.ceil(base_count * 1.6)
        count = max(1, int(base_count + sales_rng.randint(-2, 2)))

        for sale_idx_in_day in range(count):
            # Pick a product — bias towards favorites for realism
            fav_products = [p for pn, p in product_objs_by_name.items() if p.is_favorite]
            if not fav_products:
                fav_products = list(product_objs_by_name.values())
            # 70% favorites, 30% random
            if sales_rng.random() < 0.7 and fav_products:
                product = sales_rng.choice(fav_products)
            else:
                product = sales_rng.choice(list(product_objs_by_name.values()))

            if product.sale_price_gs == 0:
                # Venta libre — random price
                unit_price = sales_rng.randint(5000, 25000)
            else:
                unit_price = product.sale_price_gs

            hour = sales_rng.choices(
                [8, 9, 10, 11, 14, 15, 16, 17, 18], weights=[3, 4, 4, 3, 4, 4, 3, 2, 1]
            )[0]
            minute = sales_rng.randint(0, 59)
            second = sales_rng.randint(0, 59)
            sold_at = sale_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
            qty = sales_rng.choices([1, 2, 3, 6, 12], weights=[70, 15, 5, 5, 5])[0]

            # Random customer (70% of sales have a customer)
            cust = None
            if sales_rng.random() < 0.7 and customer_objs:
                cust = sales_rng.choice(customer_objs)

            # Payment method is one more rng.choices — we advance it here
            # *before* the dedup check so that re-runs that hit the dedup
            # short-circuit still consume the same amount of rng as run 1.
            # Without this, the rng state at the end of a dedup'd
            # iteration differs from the original run, and the next slot
            # picks a different product/customer/qty — which then can't
            # dedup, so the loop spirals into the missing-45-sales bug.
            payment_method = sales_rng.choices(
                ["efectivo", "transferencia", "tarjeta", "qr"],
                weights=[60, 15, 15, 10],
            )[0]

            # === Idempotency guard ===
            # The sazon seeder is re-run in tests and dev rebuilds all the
            # time. Without this, every re-run would add another ~890 sales
            # and inflate the cash balance / KPIs.
            #
            # Idempotency strategy: the seeder is anchored to seed_anchor_date
            # (the date this run started) so re-runs on the same day hit
            # identical calendar dates. Then for each (day, product, qty,
            # customer) tuple we check if a sale already exists; if so, we
            # skip. This keeps the count and totals stable across re-runs
            # of the same day. (Re-runs on a different day won't dedup —
            # they create fresh sales anchored to the new day, which is
            # the desired behavior for a "today's data" demo.)
            day_start = sale_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            stable_customer_id = cust.id if cust else None
            existing_sale = session.execute(
                select(Sale).where(
                    Sale.sold_at >= day_start,
                    Sale.sold_at < day_end,
                    Sale.product_id == product.id,
                    Sale.qty == qty,
                    Sale.customer_id == stable_customer_id,
                )
            ).scalars().first()
            if existing_sale is not None:
                # Already seeded a sale with this product+qty+customer on
                # this day in a previous run — skip to keep totals stable.
                # The rng was already advanced above so the next iteration
                # stays in sync.
                continue

            sale = Sale(
                sold_at=sold_at,
                product_id=product.id,
                customer_id=cust.id if cust else None,
                qty=qty,
                unit_price_gs=unit_price,
                notes=None,
                payment_method=payment_method,
                discount_gs=0,
                tz="America/Asuncion",
            )
            session.add(sale)
            session.flush()
            sale_rows.append(sale)
            report.sales += 1

            # Stock movements for sales that have a recipe
            if product.recipe_id:
                recipe = recipe_objs_by_name.get(product.name, None)  # by name? no — by id
                # need to query by id
                recipe = session.get(Recipe, product.recipe_id)
                if recipe is not None:
                    yield_qty = recipe.yield_qty or 1.0
                    yield_qty_d = Decimal(str(yield_qty))
                    qty_d = Decimal(str(qty))
                    # Get recipe lines
                    recipe_lines = (
                        session.execute(
                            select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)
                        )
                        .scalars()
                        .all()
                    )
                    for line in recipe_lines:
                        need = (Decimal(str(line.qty)) / yield_qty_d) * qty_d
                        sm = StockMovement(
                            ingredient_id=line.line_ref_id,
                            movement_type="sale",
                            qty=-float(need),
                            reason="Venta",
                            reference_id=sale.id,
                            reference_type="sale",
                            recorded_at=sold_at,
                            created_by=SASKIA_USER,
                        )
                        session.add(sm)
                        stock_move_rows.append(sm)
                        # Update stock
                        ing = session.get(Ingredient, line.line_ref_id)
                        if ing is not None:
                            ing.stock_qty = max(0.0, float(ing.stock_qty) - float(need))
                            ing.last_consumed_at = sold_at

        if (day_offset + 1) % BATCH_SIZE == 0:
            session.commit()
            logger.info(f"seeded days {day_offset + 1}/{days_of_history}")
    report.sales = len(sale_rows)
    report.stock_movements = len(stock_move_rows)

    # === 23b. Special sales (voided + encargo) — also idempotent ===
    # These are hand-crafted and don't go through the rng-driven loop.
    # Dedup by (sold_at, product_id, qty, customer_id, notes) so re-runs
    # don't inflate the count.
    first_product = next(iter(product_objs_by_name.values()))
    voided_dedup = session.execute(
        select(Sale).where(
            Sale.product_id == first_product.id,
            Sale.qty == 2,
            Sale.notes == "Cliente cambió de opinión",
            Sale.voided_at.isnot(None),
        )
    ).scalars().first()
    if voided_dedup is None:
        voided = Sale(
            # Anchor to seed_anchor_date so dedup by (product_id, qty, notes,
            # voided_at IS NOT NULL) is stable across re-runs.
            sold_at=datetime.combine(
                seed_anchor_date - timedelta(days=2), datetime.min.time()
            ) + timedelta(hours=20),
            product_id=first_product.id,
            qty=2,
            unit_price_gs=first_product.sale_price_gs,
            notes="Cliente cambió de opinión",
            voided_at=datetime.combine(
                seed_anchor_date - timedelta(days=2), datetime.min.time()
            ) + timedelta(hours=21),
            void_reason="Cliente cambió de opinión",
            voided_by=SASKIA_USER,
            payment_method="efectivo",
        )
        session.add(voided)
        session.flush()
        report.sales += 1

    # One encargo (custom order) sale
    encargo_product = list(product_objs_by_name.values())[5]
    encargo_dedup = session.execute(
        select(Sale).where(
            Sale.product_id == encargo_product.id,
            Sale.qty == 1,
            Sale.notes.like("Encargo:%"),
        )
    ).scalars().first()
    if encargo_dedup is None:
        encargo = Sale(
            # Anchor to seed_anchor_date for dedup stability.
            sold_at=datetime.combine(
                seed_anchor_date - timedelta(days=1), datetime.min.time()
            ) + timedelta(hours=22),
            product_id=encargo_product.id,
            qty=1,
            unit_price_gs=encargo_product.sale_price_gs,
            notes="Encargo: recoger 16h",
            payment_method="transferencia",
        )
        session.add(encargo)
        session.flush()
        report.sales += 1

    # Initial stock movement (audit trail for opening balance)
    for ing_name, ing in ingredient_objs_by_name.items():
        # Idempotency: one initial StockMovement per ingredient (1:1 audit trail).
        existing_initial = session.execute(
            select(StockMovement).where(
                StockMovement.ingredient_id == ing.id,
                StockMovement.movement_type == "initial",
            )
        ).scalars().first()
        if existing_initial is not None:
            continue
        sm = StockMovement(
            ingredient_id=ing.id,
            movement_type="initial",
            qty=ing.stock_qty,
            reason="Stock inicial (seed)",
            reference_id=None,
            reference_type=None,
            # Use anchor date so the (ingredient_id, movement_type="initial")
            # dedup is stable across re-runs.
            recorded_at=datetime.combine(
                seed_anchor_date - timedelta(days=90), datetime.min.time()
            ),
            created_by=SASKIA_USER,
        )
        session.add(sm)
        report.stock_movements += 1

    logger.info(f"seed: {report.sales} sales + {report.stock_movements} stock movements")

    # === 24. Waste log ===
    for ing_name, qty, reason, days_ago, by, notes in WASTE_LOG:
        ing = ingredient_objs_by_name.get(ing_name)
        if not ing:
            continue
        existing = session.execute(
            select(WasteLog).where(
                WasteLog.ingredient_id == ing.id,
                WasteLog.qty == qty,
                WasteLog.reason == reason,
            )
        ).scalar_one_or_none()
        if existing is None:
            cost_gs = int(qty * (ing.purchase_price_gs or 0))
            session.add(
                WasteLog(
                    ingredient_id=ing.id,
                    qty=qty,
                    reason=reason,
                    cost_gs=cost_gs,
                    recorded_at=datetime.utcnow() - timedelta(days=days_ago),
                    recorded_by=by,
                    notes=notes,
                )
            )
            report.waste_log += 1
    logger.info(f"seed: {report.waste_log} waste log entries")

    # === 25. Shopping list (items to reorder) ===
    for ing_name in ["harina 0000", "manteca", "huevos", "leche entera", "azúcar"]:
        ing = ingredient_objs_by_name.get(ing_name)
        if not ing:
            continue
        existing = session.execute(
            select(ShoppingListItem).where(
                ShoppingListItem.ingredient_id == ing.id,
                ShoppingListItem.purchased == False  # noqa: E712
            )
        ).scalar_one_or_none()
        if existing is None:
            qty_to_buy = (ing.min_stock_qty or 1.0) * 2
            session.add(
                ShoppingListItem(
                    ingredient_id=ing.id,
                    qty_to_buy=qty_to_buy,
                    unit=ing.unit,
                    purpose_text=f"Stock bajo — comprar antes del lunes",
                    purchased=False,
                )
            )
            report.shopping_list += 1
    logger.info(f"seed: {report.shopping_list} shopping list items")

    # === 26. HACCP — freezer temperature log (last 14 days, 2 readings/day) ===
    # Use seed_anchor_date as the anchor so re-runs produce identical
    # timestamps and the (recorded_at) natural-key dedup actually works.
    for days_ago in range(FREEZER_TEMP_DAYS):
        for hour in (8, 20):  # morning + evening
            base_dt = datetime.combine(
                seed_anchor_date - timedelta(days=days_ago),
                datetime.min.time(),
            )
            ts = base_dt + timedelta(hours=hour)
            # Mostly in range, occasional spike for realism
            if rng.random() < 0.92:
                temp = rng.uniform(HACCP_TEMP_MIN_C, HACCP_TEMP_MAX_C)
            else:
                temp = rng.choice([
                    rng.uniform(-25, -22),  # too cold
                    rng.uniform(-15, -10),  # too warm
                ])
            existing = session.execute(
                select(FreezerTemperatureLog).where(
                    FreezerTemperatureLog.recorded_at == ts
                )
            ).scalar_one_or_none()
            if existing is None:
                in_range = HACCP_TEMP_MIN_C <= temp <= HACCP_TEMP_MAX_C
                session.add(
                    FreezerTemperatureLog(
                        recorded_at=ts,
                        for_date=ts.date(),
                        location="Freezer 1 (masa congelada)",
                        shift="AM" if hour == 8 else "PM",
                        temperature_c=temp,
                        recorded_by_user_id=None,  # FK to user.id, leave None for now
                        notes=None if in_range else f"Fuera de rango: {temp:.1f}°C",
                    )
                )
                report.haccp_temps += 1
    logger.info(f"seed: {report.haccp_temps} HACCP freezer temp readings")

    # === 27. Market benchmarks ===
    for label, wholesale, retail, avg, min_price in BENCHMARKS:
        existing = session.execute(
            select(MarketBenchmark).where(MarketBenchmark.product_label == label)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                MarketBenchmark(
                    product_label=label,
                    our_wholesale_gs=wholesale,
                    our_retail_gs=retail,
                    market_avg_gs=avg,
                    comp_min_gs=min_price,
                )
            )
            report.market_benchmarks += 1
    logger.info(f"seed: {report.market_benchmarks} market benchmarks")

    # === 28. Audit log (initial entries) ===
    audit_record(
        session,
        user_id=SASKIA_USER,
        action="system.startup",
        detail={"source": "seed_sazon", "tenant": TENANT_NAME},
    )
    audit_record(
        session,
        user_id=SASKIA_USER,
        action="seed.complete",
        detail={"tenant": TENANT_NAME, "version": "1.0"},
    )
    report.audit_log_rows = 2

    # === 29. AppMeta pins (idempotency + onboarding guard) ===
    # sazon_seed_version = schema/data version of THIS seeder (bump on breaking changes)
    sazon_meta_keys = {
        "sazon_seed_version": "1.0",
        "sazon_seeded_at": datetime.utcnow().isoformat(),
        "sazon_tenant_slug": TENANT_SLUG,
        "sazon_tenant_name": TENANT_NAME,
        "sazon_admin_user": SASKIA_USER,
        # Onboarding guard: lets the welcome modal / dashboard know that
        # *some* demo data is loaded. Future feature flags can be added
        # here (e.g. "sazon_loaded_charts", "sazon_loaded_reports").
        "sazon_loaded": "true",
    }
    for k, v in sazon_meta_keys.items():
        existing = session.execute(
            select(AppMeta).where(AppMeta.key == k)
        ).scalar_one_or_none()
        if existing is None:
            session.add(AppMeta(key=k, value=str(v), updated_at=datetime.utcnow().isoformat()))
        else:
            existing.value = str(v)
            existing.updated_at = datetime.utcnow().isoformat()

    # === 30. Bank transactions (a few recent ones) ===
    # Idempotency: the dedup query uses (posted_at, description) as the
    # natural key. Both must be deterministic. seed_anchor_date is a
    # `date` (not datetime) — when compared to the DateTime `posted_at`
    # column, SQLAlchemy coerces to datetime, but the conversion can
    # differ between drivers (midnight UTC vs local tz). To make it
    # 100% stable, we explicitly store posted_at as a midnight datetime.
    bank_tx_data = [
        # (date, amount, type, description, account, balance_gs)
        (seed_anchor_date - timedelta(days=60), -1_200_000, "transfer", "Pago a Distribuidora El Molino", "Itaú", 2_500_000),
        (seed_anchor_date - timedelta(days=45), -650_000, "transfer", "Pago a Lácteos Paraguay", "Itaú", 1_850_000),
        (seed_anchor_date - timedelta(days=30), 3_500_000, "deposit", "Cierre de caja 30 días", "Itaú", 5_350_000),
        (seed_anchor_date - timedelta(days=20), -280_000, "debit", "Servicios ANDE", "Itaú", 5_070_000),
        (seed_anchor_date - timedelta(days=15), 2_800_000, "deposit", "Cierre quincena", "Itaú", 7_870_000),
        (seed_anchor_date - timedelta(days=10), -450_000, "transfer", "Pago a Dulcería Santa Rita", "Itaú", 7_420_000),
        (seed_anchor_date - timedelta(days=5), -180_000, "debit", "Essap", "Itaú", 7_240_000),
        (seed_anchor_date - timedelta(days=2), 1_800_000, "deposit", "Cierre de caja 2 días", "Itaú", 9_040_000),
    ]
    for tx_date, amount, tx_type, desc, account, balance in bank_tx_data:
        # Normalize to midnight datetime so the dedup comparison is stable
        # regardless of tz coercion. seed_anchor_date is a `date`;
        # `BankTransaction.posted_at` is DateTime.
        tx_posted_at = datetime.combine(tx_date, datetime.min.time())
        existing = session.execute(
            select(BankTransaction).where(
                BankTransaction.posted_at == tx_posted_at,
                BankTransaction.description == desc,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                BankTransaction(
                    posted_at=tx_posted_at,
                    currency="PYG",
                    amount=amount,
                    balance_after=balance,
                    counterparty_name=desc.split(" a ")[1] if " a " in desc else None,
                    description=desc,
                    reference=None,
                    category=tx_type,
                    source="manual",
                    account_holder=account,
                    reconciled=False,
                )
            )
    # Don't count bank tx in the main report — keep it light

    session.commit()
    logger.info(f"seed_sazon complete: {report.as_dict()}")
    return report


def _delete_sazon_data(session: Session) -> None:
    """Delete all rows from the tables we manage. Used when overwrite=True."""
    # Order matters: respect FKs.
    # Wrap each deletion in try/except so a missing-table error (live DB
    # schema drift) doesn't abort the whole seed.
    for model in (
        # Reverse-dependency tables first
        PedidoEvent,
        PedidoLine,
        Pedido,
        CustomerAddress,
        Customer,
        TagLink,
        Tag,
        Sale,  # Sale has no FK from sales to other tables; this clears sales
        StockMovement,
        WasteLog,
        ShoppingListItem,
        ProductionCompletion,
        ProductionPlanTemplate,
        FreezerTemperatureLog,
        BankTransaction,
        MarketBenchmark,
        # Recipe / product
        RecipeLine,
        Product,
        Recipe,
        # Inventory
        IngredientPriceEvent,
        IngredientVariant,
        Ingredient,
        # Catalog tables
        ImportBatch,
        PriceHistory,
        # Settings
        MessageTemplate,
        DateRangePreset,
        MarginTier,
        PaymentMethod,
        StockStatusConfig,
        StorageKeyword,
        StorageType,
        Category,
        DeliveryZone,
        # Compliance + suppliers
        ComplianceInfo,
        Supplier,
        # Tenants + users (don't delete ALL — only seeded ones)
        SettingsKV,
    ):
        try:
            if model is SettingsKV:
                # Only delete sazon-related keys
                session.execute(
                    delete(SettingsKV).where(SettingsKV.key.like("branding.%") | SettingsKV.key.like("ops.%"))
                )
            elif model in (Customer,):
                # Only delete seeded customers (have an email)
                session.execute(delete(Customer).where(Customer.email.like("%@example.com")))
            elif model is User:
                # Only delete seeded users
                session.execute(delete(User).where(User.username.in_([SASKIA_USER, "lucia", "diego"])))
            elif model is Tenant:
                session.execute(delete(Tenant).where(Tenant.slug == TENANT_SLUG))
            else:
                session.execute(delete(model))
        except Exception as e:  # noqa: BLE001 — defensive default
            logger.warning(f"Could not wipe {model.__name__}: {e}")
            session.rollback()
    # Audit log
    try:
        session.execute(delete(AuditLog).where(AuditLog.action == "seed.complete"))
    except Exception as e:  # noqa: BLE001 — defensive default
        logger.warning(f"Could not wipe audit log: {e}")
        session.rollback()
    session.commit()


__all__ = [
    "CATEGORIES_PRODUCT",
    "CATEGORIES_RECIPE",
    "PAYMENT_METHODS",
    "MARGIN_TIERS",
    "STOCK_STATUSES",
    "STORAGE_TYPES",
    "STORAGE_KEYWORDS",
    "DATE_PRESETS",
    "MESSAGE_TEMPLATES",
    "DELIVERY_ZONES",
    "SUPPLIERS",
    "INGREDIENTS",
    "RECIPES",
    "RECIPE_LINES",
    "PRODUCTS",
    "CUSTOMERS",
    "PEDIDOS",
    "BENCHMARKS",
    "WASTE_LOG",
    "SazonReport",
    "seed_sazon",
    "SASKIA_USER",
    "SASKIA_PASSWORD",
    "TENANT_SLUG",
    "TENANT_NAME",
]
