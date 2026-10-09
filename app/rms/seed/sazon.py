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
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
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
from app.rms.tagging.ensure import ensure_starter_tags, ensure_tag, tag_target
from app.rms.tagging.model import TagKind

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
    (
        "transferencia",
        "Transferencia bancaria",
        True,
        0.0,
        20,
        False,
        True,
        "Banco Itaú / Continental",
    ),
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
    (
        "villa_morra",
        "Villa Morra / Carmelitas",
        "VM, Carmelitas, Shopping",
        4.0,
        15000,
        60000,
        50,
        None,
    ),
    (
        "lambare",
        "Lambaré / Ñemby",
        "Lambaré, Ñemby, San Antonio",
        6.0,
        20000,
        80000,
        60,
        "Costo más alto por distancia",
    ),
]

# Channels (sale channels)
# P43 (2026-10-07): source codes from Channel enum + remove "phone"
# (legacy alias not in the enum; DB CHECK would reject any pedido.channel
# set to "phone"). Legacy phone-channel traffic now maps to
# Channel.OTHER.value, and "phone" prefix in seed labels stays a display
# string only — not a Channel.code.
from app.rms.models.channels import (
    Channel as ChannelEnum,  # the canonical enum; Channel (ORM model) stays imported above
)

CHANNELS: list[tuple[str, str, int, bool, str | None]] = [
    # (code, label, sort_order, is_default, notes)
    (ChannelEnum.MOSTRADOR.value, "Mostrador", 10, True, "Venta directa en mostrador"),
    (
        ChannelEnum.MOSTRADOR_ENCARGO.value,
        "Mostrador (encargo)",
        20,
        False,
        "Encargo recogido en mostrador",
    ),
    (ChannelEnum.WHATSAPP.value, "WhatsApp", 30, False, "Pedido recibido por WhatsApp"),
    (ChannelEnum.PEDIDOSYA.value, "PedidosYa", 40, False, "PedidosYa (delivery app)"),
    (ChannelEnum.MONCHIS.value, "Monchis", 50, False, "Monchis (delivery app)"),
    (
        ChannelEnum.OTHER.value,
        "Teléfono / Otro",
        60,
        False,
        "Llamada telefónica u otro canal no listado",
    ),
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
    (
        "Harina de centeno",
        "kg",
        1.5,
        25000,
        150.0,
        90,
        "dry",
        "harinas y bases",
        "gluten",
        "vegano",
        0,
        1.0,
        "kg",
        25000,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Harina de repostería",
        "kg",
        0.0,
        6500,
        0.5,
        90,
        "dry",
        "harinas y bases",
        "gluten",
        "vegano",
        0,
        1.0,
        "kg",
        6500,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Harina de trigo",
        "kg",
        5.0,
        3440,
        500.0,
        90,
        "dry",
        "harinas y bases",
        "gluten",
        "vegano",
        0,
        5.0,
        "kg",
        17200,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Harina Patentada",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "harinas y bases",
        "gluten",
        "vegano",
        0,
        1.0,
        "kg",
        0,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Maicena",
        "kg",
        0.0,
        8500,
        0.5,
        90,
        "dry",
        "harinas y bases",
        "",
        "vegetariano",
        0,
        1.0,
        "kg",
        8500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Pan rallado",
        "kg",
        0.0,
        3500,
        0.5,
        90,
        "dry",
        "harinas y bases",
        "gluten",
        "vegetariano",
        0,
        1.0,
        "kg",
        3500,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Azúcar",
        "kg",
        0.002,
        8000,
        0.5,
        90,
        "dry",
        "endulzantes",
        "",
        "vegano",
        3,
        1.0,
        "kg",
        8000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Azúcar glas",
        "kg",
        0.0,
        9500,
        0.5,
        90,
        "dry",
        "endulzantes",
        "",
        "vegano",
        3,
        1.0,
        "kg",
        9500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Azúcar morena",
        "kg",
        0.0,
        5800,
        0.5,
        90,
        "dry",
        "endulzantes",
        "",
        "vegano",
        3,
        1.0,
        "kg",
        5800,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Melaza",
        "kg",
        0.0,
        16500,
        0.5,
        90,
        "dry",
        "endulzantes",
        "",
        "vegetariano",
        3,
        1.0,
        "kg",
        16500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Miel",
        "kg",
        0.0,
        18500,
        0.5,
        90,
        "dry",
        "endulzantes",
        "",
        "vegetariano",
        3,
        1.0,
        "kg",
        18500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Crema agria",
        "kg",
        0.0,
        12500,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "kg",
        12500,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Crema de leche",
        "l",
        0.0,
        22750,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "l",
        22750,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Crema pastelera",
        "l",
        0.0,
        0,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "l",
        0,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Huevos",
        "und",
        0.0,
        617,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "huevo",
        "vegetariano",
        1,
        30.0,
        "und",
        18500,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Leche",
        "l",
        0.0,
        5700,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "l",
        5700,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Manteca",
        "kg",
        0.0,
        39800,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "kg",
        39800,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Queso muzzarella",
        "l",
        0.0,
        0,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "l",
        0,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Queso crema",
        "kg",
        0.0,
        108600,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.5,
        "kg",
        162900,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Suero de leche (buttermilk)",
        "l",
        0.0,
        0,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "l",
        0,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Leche condensada",
        "kg",
        0.0,
        18501,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        0.397,
        "kg",
        7345,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Leche en polvo",
        "kg",
        0.0,
        0,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        1.0,
        "kg",
        0,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
    (
        "Cacao en polvo",
        "kg",
        0.0,
        18500,
        0.5,
        90,
        "dry",
        "cacao café y chocolate",
        "",
        "vegetariano",
        3,
        1.0,
        "kg",
        18500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Café instantaneo",
        "kg",
        0.0,
        22500,
        0.5,
        90,
        "dry",
        "cacao café y chocolate",
        "",
        "vegetariano",
        3,
        1.0,
        "kg",
        22500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Chocolate",
        "kg",
        0.0,
        23500,
        0.5,
        90,
        "dry",
        "cacao café y chocolate",
        "",
        "vegetariano",
        3,
        1.0,
        "kg",
        23500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Laurel",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Vainilla",
        "kg",
        0.0,
        19000,
        0.5,
        90,
        "ambient",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        19000,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Ajo",
        "und",
        0.0,
        2500,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "und",
        2500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Anís estrellado",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Canela",
        "kg",
        0.0,
        200000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.025,
        "kg",
        5000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Especias mixtas",
        "kg",
        0.0,
        7800,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        7800,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Mezcla de especias para Speculaas",
        "kg",
        0.0,
        9500,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        9500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Jengibre",
        "kg",
        0.0,
        8500,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        8500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Jengibre molido",
        "kg",
        0.0,
        5000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        5000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Nuez moscada",
        "kg",
        0.0,
        8500,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "nueces",
        "vegetariano",
        2,
        1.0,
        "kg",
        8500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Ralladura de limón",
        "und",
        0.0,
        0,
        0.5,
        90,
        "fresh",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        1.0,
        "und",
        0,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Sal",
        "kg",
        0.0,
        7000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        0.5,
        "kg",
        3500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Perejil",
        "und",
        0.0,
        700,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        1.0,
        "und",
        700,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Cebolla en polvo",
        "kg",
        0.0,
        228000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.025,
        "kg",
        5700,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Ajo en polvo",
        "kg",
        0.0,
        268000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.025,
        "kg",
        6700,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Knorr",
        "kg",
        0.0,
        92982,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.057,
        "kg",
        5300,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Pimienta",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.057,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Mostaza",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "mostaza",
        "vegetariano",
        2,
        0.057,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Bicarbonato de sodio",
        "kg",
        0.0,
        4500,
        0.5,
        90,
        "dry",
        "levaduras y gasificantes",
        "",
        "vegetariano",
        0,
        1.0,
        "kg",
        4500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Levadura fresca",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "levaduras y gasificantes",
        "",
        "vegano",
        0,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Levadura seca",
        "kg",
        0.0,
        104000,
        0.5,
        90,
        "dry",
        "levaduras y gasificantes",
        "",
        "vegano",
        0,
        0.125,
        "kg",
        13000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Polvo de hornear",
        "kg",
        0.0,
        8500,
        0.5,
        90,
        "dry",
        "levaduras y gasificantes",
        "",
        "vegetariano",
        0,
        1.0,
        "kg",
        8500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Frambuesas",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Fruta",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "fresh",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.85,
        80,
        10,
        25,
    ),
    (
        "Nueces",
        "kg",
        0.0,
        28500,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        28500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Pasas",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Frutilla",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "fresh",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Mango",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Fruta Confitada",
        "kg",
        0.0,
        12500,
        0.5,
        10,
        "fresh",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        12500,
        False,
        False,
        0.85,
        80,
        10,
        25,
    ),
    (
        "Mburukuja",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Manzana",
        "und",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "frutas y frutos secos",
        "",
        "vegano",
        2,
        1.0,
        "und",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Cebolla",
        "kg",
        0.0,
        8150,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        8150,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Zanahoria",
        "kg",
        0.0,
        3500,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        3500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Garbanzo",
        "kg",
        0.0,
        29000,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegano",
        2,
        1.0,
        "kg",
        29000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Cebolla morada",
        "kg",
        0.0,
        0,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        0.057,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Panceta de cerdo",
        "kg",
        0.0,
        28500,
        0.5,
        7,
        "dry",
        "carnes",
        "",
        None,
        2,
        1.0,
        "kg",
        28500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Pechuga de pollo",
        "kg",
        0.0,
        20318,
        0.5,
        7,
        "dry",
        "carnes",
        "",
        None,
        2,
        1.132,
        "kg",
        23000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Bola de lomo",
        "kg",
        0.0,
        74000,
        0.5,
        7,
        "dry",
        "carnes",
        "",
        None,
        2,
        0.5,
        "kg",
        37000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Carnaza de segunda",
        "kg",
        0.0,
        40000,
        0.5,
        7,
        "dry",
        "carnes",
        "",
        None,
        2,
        1.0,
        "kg",
        40000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Agua",
        "l",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "salsas y líquidos",
        "",
        "vegetariano",
        0,
        1.0,
        "l",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Jugo de limón",
        "l",
        0.0,
        6800,
        0.5,
        90,
        "fresh",
        "salsas y líquidos",
        "",
        "vegetariano",
        0,
        1.0,
        "l",
        6800,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Jugo de remolacha",
        "l",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "salsas y líquidos",
        "",
        "vegetariano",
        0,
        1.0,
        "l",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Vinagre",
        "l",
        0.0,
        4500,
        0.5,
        90,
        "ambient",
        "salsas y líquidos",
        "",
        "vegano",
        0,
        1.0,
        "l",
        4500,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Ketjap manis",
        "l",
        0.0,
        18500,
        0.5,
        90,
        "ambient",
        "salsas y líquidos",
        "soja",
        "vegano",
        0,
        1.0,
        "l",
        18500,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Salsa de soja",
        "l",
        0.0,
        7500,
        0.5,
        90,
        "dry",
        "salsas y líquidos",
        "soja",
        "vegano",
        0,
        1.0,
        "l",
        7500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Nata para montar",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "salsas y líquidos",
        "leche",
        "vegetariano",
        0,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Aceite",
        "l",
        0.0,
        13500,
        0.5,
        90,
        "ambient",
        "aceites y grasas",
        "",
        "vegano",
        0,
        1.0,
        "l",
        13500,
        False,
        False,
        0.7,
        80,
        10,
        25,
    ),
    (
        "Estabilizante para nata",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "leche",
        "vegetariano",
        0,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Polvo para natillas",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        1.0,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Masa choux",
        "und",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        1.0,
        "und",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Masa de hojaldre",
        "und",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        1.0,
        "und",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Gelatina",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        0.057,
        "kg",
        0,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Cafe Espresso Molido",
        "kg",
        0.0,
        394737,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        0.057,
        "kg",
        22500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Galletas dulces (base cheesecake)",
        "kg",
        0.0,
        0,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "gluten",
        "vegetariano",
        0,
        1.0,
        "kg",
        0,
        False,
        True,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Gelatina sin sabor",
        "kg",
        0.0,
        242500,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        0.1,
        "kg",
        24250,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Caldo de carne en cubos",
        "und",
        0.0,
        697,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        None,
        0,
        12.0,
        "und",
        8360,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Morrón rojo",
        "und",
        0.0,
        5000,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "und",
        5000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Apio",
        "und",
        8.0,
        667,
        0.8,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "und",
        667,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Puré de tomate",
        "kg",
        0.0,
        30952,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        0.21,
        "kg",
        6500,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Pimentón ahumado",
        "kg",
        0.0,
        120000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        0.1,
        "kg",
        12000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Falda de res",
        "kg",
        0.0,
        34900,
        0.5,
        7,
        "dry",
        "carnes",
        "",
        None,
        2,
        1.0,
        "kg",
        34900,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Alcaravea",
        "kg",
        0.0,
        120000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.1,
        "kg",
        12000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Cayena",
        "kg",
        0.0,
        120000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegetariano",
        2,
        0.1,
        "kg",
        12000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Echalote",
        "und",
        0.0,
        4000,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "und",
        4000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Girgolas frescas",
        "kg",
        0.0,
        40000,
        0.5,
        10,
        "dry",
        "verduras y legumbres",
        "",
        "vegetariano",
        2,
        1.0,
        "kg",
        40000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Tomillo fresco",
        "und",
        0.0,
        3000,
        0.5,
        90,
        "dry",
        "especias y condimentos",
        "",
        "vegano",
        2,
        1.0,
        "und",
        3000,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Caldo de hongos en cubos",
        "und",
        0.0,
        697,
        0.5,
        90,
        "dry",
        "preparados y otros",
        "",
        "vegetariano",
        0,
        12.0,
        "und",
        8360,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Arroz para sushi",
        "kg",
        0.0,
        44800,
        0.5,
        90,
        "dry",
        "harinas y bases",
        "",
        "vegetariano",
        0,
        0.5,
        "kg",
        22400,
        False,
        False,
        0.45,
        70,
        10,
        25,
    ),
    (
        "Queso rallado",
        "kg",
        0.0,
        131250,
        0.5,
        14,
        "refrigerated",
        "lácteos y huevos",
        "leche",
        "vegetariano",
        1,
        0.04,
        "kg",
        5250,
        False,
        False,
        0.7,
        40,
        0,
        4,
    ),
]



# 20+ recipes
# Tuple: (name, yield_qty, yield_unit, prep_minutes, cook_minutes, difficulty 1-5, family, menu_tags, dietary_tags, notes, image_url)
RECIPES: list[tuple] = [
    (
        "babka__rec_017",
        10.0,
        "und",
        40,
        40,
        3,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-017). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-babka.jpg",
    ),
    (
        "bizcocho_basico_25_cm_basiscake__rec_011",
        12.0,
        "und",
        15,
        30,
        1,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-011). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-bizcocho_basico_25_cm.jpg",
    ),
    (
        "bizcocho_basico_30_cm_basiscake__rec_012",
        16.0,
        "und",
        15,
        30,
        1,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-012). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-bizcocho_basico_30_cm.jpg",
    ),
    (
        "bombones_de_chocolate__rec_018",
        20.0,
        "und",
        30,
        0,
        3,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-018). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-bombones_de_chocolate.jpg",
    ),
    (
        "torta_de_zanahoria_43x33x1_5_cm__rec_005",
        24.0,
        "und",
        20,
        40,
        2,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-005). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-torta_de_zanahoria.jpg",
    ),
    (
        "cheesecake_30x50__rec_002",
        170.0,
        "und",
        20,
        60,
        3,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-002). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-cheesecake.jpg",
    ),
    (
        "muffin_de_chocolate_20x20_cm__rec_001",
        12.0,
        "und",
        15,
        25,
        1,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-001). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-muffin_de_chocolate.jpg",
    ),
    (
        "frikandel_100_unidades__rec_022",
        100.0,
        "und",
        45,
        0,
        4,
        "",
        "",
        None,
        "Heredado del workbook (id REC-006). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-frikandel.jpg",
    ),
    (
        "galletas_de_especuloos_speculaasjes__rec_010",
        40.0,
        "und",
        30,
        14,
        2,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-010). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-galletas_de_especuloos.jpg",
    ),
    (
        "goulash_crockettes__rec_019",
        100.0,
        "und",
        45,
        0,
        4,
        "",
        "",
        None,
        "Heredado del workbook (id REC-019). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-goulash_crockettes.jpg",
    ),
    (
        "hojaldre_bladerdeeg__rec_008",
        8.0,
        "und",
        60,
        25,
        4,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-008). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-hojaldre.jpg",
    ),
    (
        "ketjap_manis_version_rapida__rec_007",
        250.0,
        "ml",
        5,
        45,
        1,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-007). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-ketjap_manis.jpg",
    ),
    (
        "oliebollen_bunuelos_tradicionales_holandeses__rec_016",
        24.0,
        "und",
        20,
        6,
        2,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-016). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-oliebollen.jpg",
    ),
    (
        "ontbijtkoek_700g_de_harina__rec_004",
        12.0,
        "und",
        15,
        60,
        1,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-004). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-ontbijtkoek.jpg",
    ),
    (
        "pastelitos_rosados_roze_koeken__rec_009",
        12.0,
        "und",
        45,
        22,
        3,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-009). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-pastelitos_rosados.jpg",
    ),
    (
        "petisus_de_hojaldre_y_crema_tompoezen__rec_015",
        12.0,
        "und",
        60,
        25,
        4,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-015). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-petisus_de_hojaldre_y_crema.jpg",
    ),
    (
        "proficteroles_de_den_bosch_bossche_bollen__rec_014",
        12.0,
        "und",
        60,
        25,
        4,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-014). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-proficteroles_de_den_bosch.jpg",
    ),
    (
        "stroop_wafel__rec_003",
        12.0,
        "und",
        20,
        12,
        2,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-003). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-stroop_wafel.jpg",
    ),
    (
        "suppli_cacio_e_pepe__rec_021",
        12.0,
        "und",
        30,
        6,
        3,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-021). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-suppli_cacio_e_pepe.jpg",
    ),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        12.0,
        "und",
        35,
        50,
        2,
        "",
        "",
        "vegetariano",
        "Heredado del workbook (id REC-013). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-tarta_de_manzana_de_mi_madre.jpg",
    ),
    (
        "bitterballen_vegetariano__rec_020",
        100.0,
        "und",
        45,
        0,
        4,
        "",
        "",
        None,
        "Heredado del workbook (id REC-020). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-bitterballen_vegetariano.jpg",
    ),
    (
        "bitterballen__rec_006",
        100.0,
        "und",
        45,
        0,
        4,
        "",
        "",
        None,
        "Heredado del workbook (id REC-006). Rinde estimada — el operador ajusta B4 después de hornear.",
        "/static/recipes/receta-bitterballen.jpg",
    ),
]



# Recipe lines: (recipe_name, ingredient_name, qty, line_unit, notes)
RECIPE_LINES: list[tuple[str, str, float, str, str | None]] = [
    # === babka__rec_017 ===
    ("babka__rec_017", "Harina de trigo", 0.35, "kg", None),
    ("babka__rec_017", "Sal", 0.007, "kg", None),
    ("babka__rec_017", "Azúcar", 0.06, "kg", None),
    ("babka__rec_017", "Levadura seca", 0.007, "kg", None),
    ("babka__rec_017", "Leche", 0.175, "l", None),
    ("babka__rec_017", "Huevos", 1.0, "und", None),
    ("babka__rec_017", "Manteca", 0.17, "kg", None),
    ("babka__rec_017", "Chocolate", 0.1, "kg", None),
    ("babka__rec_017", "Cacao en polvo", 0.03, "kg", None),
    ("babka__rec_017", "Azúcar glas", 0.05, "kg", None),
    ("babka__rec_017", "Agua", 0.04, "l", None),
    # === bizcocho_basico_25_cm_basiscake__rec_011 ===
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Azúcar", 0.2, "kg", None),
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Manteca", 0.2, "kg", None),
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Vainilla", 0.001, "kg", None),
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Huevos", 4.0, "und", None),
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Harina de trigo", 0.2, "kg", None),
    ("bizcocho_basico_25_cm_basiscake__rec_011", "Polvo de hornear", 0.002, "kg", None),
    # === bizcocho_basico_30_cm_basiscake__rec_012 ===
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Azúcar", 0.25, "kg", None),
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Manteca", 0.25, "kg", None),
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Vainilla", 0.001, "kg", None),
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Huevos", 5.0, "und", None),
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Harina de trigo", 0.25, "kg", None),
    ("bizcocho_basico_30_cm_basiscake__rec_012", "Polvo de hornear", 0.002, "kg", None),
    # === bombones_de_chocolate__rec_018 ===
    ("bombones_de_chocolate__rec_018", "Leche condensada", 0.397, "kg", None),
    ("bombones_de_chocolate__rec_018", "Cacao en polvo", 0.022, "kg", None),
    ("bombones_de_chocolate__rec_018", "Manteca", 0.014, "kg", None),
    ("bombones_de_chocolate__rec_018", "Sal", 0.001, "kg", None),
    # === torta_de_zanahoria_43x33x1_5_cm__rec_005 ===
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Harina de trigo", 0.372, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Azúcar", 0.266, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Azúcar morena", 0.306, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Jengibre molido", 0.004, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Canela", 0.007, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Sal", 0.005, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Bicarbonato de sodio", 0.009, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Nuez moscada", 0.001, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Huevos", 5.0, "und", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Vainilla", 0.009, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Aceite", 0.392, "l", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Pasas", 0.073, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Zanahoria", 0.332, "kg", None),
    ("torta_de_zanahoria_43x33x1_5_cm__rec_005", "Nueces", 0.166, "kg", None),
    # === cheesecake_30x50__rec_002 ===
    ("cheesecake_30x50__rec_002", "Queso crema", 1.5, "kg", None),
    ("cheesecake_30x50__rec_002", "Azúcar", 0.419, "kg", None),
    ("cheesecake_30x50__rec_002", "Huevos", 11.0, "und", None),
    ("cheesecake_30x50__rec_002", "Crema de leche", 0.95, "l", None),
    ("cheesecake_30x50__rec_002", "Harina de trigo", 0.07, "kg", None),
    ("cheesecake_30x50__rec_002", "Vainilla", 0.015, "l", None),
    ("cheesecake_30x50__rec_002", "Jugo de limón", 0.015, "l", None),
    ("cheesecake_30x50__rec_002", "Manteca", 0.02, "kg", None),
    # === muffin_de_chocolate_20x20_cm__rec_001 ===
    ("muffin_de_chocolate_20x20_cm__rec_001", "Harina de trigo", 0.333, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Cacao en polvo", 0.117, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Polvo de hornear", 0.005, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Bicarbonato de sodio", 0.005, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Café instantaneo", 0.003, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Sal", 0.017, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Azúcar morena", 0.458, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Leche", 0.167, "l", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Aceite", 0.25, "l", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Huevos", 167.0, "und", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Crema agria", 0.375, "l", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Vainilla", 0.025, "kg", None),
    ("muffin_de_chocolate_20x20_cm__rec_001", "Chocolate", 0.333, "kg", None),
    # === frikandel_100_unidades__rec_022 ===
    ("frikandel_100_unidades__rec_022", "Pechuga de pollo", 0.2, "kg", None),
    ("frikandel_100_unidades__rec_022", "Carnaza de segunda", 0.8, "kg", None),
    ("frikandel_100_unidades__rec_022", "Cebolla morada", 0.1, "kg", None),
    ("frikandel_100_unidades__rec_022", "Ajo", 0.01, "kg", None),
    ("frikandel_100_unidades__rec_022", "Huevos", 1.0, "und", None),
    ("frikandel_100_unidades__rec_022", "Pan rallado", 0.05, "kg", None),
    ("frikandel_100_unidades__rec_022", "Especias mixtas", 0.013, "kg", None),
    ("frikandel_100_unidades__rec_022", "Sal", 0.016, "kg", None),
    ("frikandel_100_unidades__rec_022", "Leche en polvo", 0.03, "kg", None),
    # === galletas_de_especuloos_speculaasjes__rec_010 ===
    ("galletas_de_especuloos_speculaasjes__rec_010", "Manteca", 0.19, "kg", None),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Azúcar morena", 0.205, "kg", None),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Suero de leche (buttermilk)", 0.045, "l", None),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Harina de trigo", 0.4, "kg", None),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Mezcla de especias para Speculaas", 0.004, "kg", None),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Bicarbonato de sodio", 0.002, "kg", None),
    # === goulash_crockettes__rec_019 ===
    ("goulash_crockettes__rec_019", "Aceite", 0.04, "l", None),
    ("goulash_crockettes__rec_019", "Morrón rojo", 1.0, "und", None),
    ("goulash_crockettes__rec_019", "Cebolla", 0.15, "kg", None),
    ("goulash_crockettes__rec_019", "Zanahoria", 0.1, "kg", None),
    ("goulash_crockettes__rec_019", "Apio", 2.0, "und", None),
    ("goulash_crockettes__rec_019", "Ajo", 4.0, "und", None),
    ("goulash_crockettes__rec_019", "Puré de tomate", 0.03, "kg", None),
    ("goulash_crockettes__rec_019", "Pimentón ahumado", 0.007, "kg", None),
    ("goulash_crockettes__rec_019", "Falda de res", 0.6, "kg", None),
    ("goulash_crockettes__rec_019", "Sal", 0.005, "kg", None),
    ("goulash_crockettes__rec_019", "Pimienta", 0.001, "kg", None),
    ("goulash_crockettes__rec_019", "Caldo de carne en cubos", 2.5, "und", None),
    ("goulash_crockettes__rec_019", "Alcaravea", 0.002, "kg", None),
    ("goulash_crockettes__rec_019", "Manteca", 0.08, "kg", None),
    ("goulash_crockettes__rec_019", "Harina de trigo", 0.1, "kg", None),
    ("goulash_crockettes__rec_019", "Gelatina sin sabor", 0.005, "kg", None),
    ("goulash_crockettes__rec_019", "Huevos", 2.0, "und", None),
    ("goulash_crockettes__rec_019", "Crema de leche", 0.05, "kg", None),
    ("goulash_crockettes__rec_019", "Cayena", 0.001, "kg", None),
    ("goulash_crockettes__rec_019", "Huevos", 2.0, "und", None),
    ("goulash_crockettes__rec_019", "Harina de trigo", 0.015, "kg", None),
    ("goulash_crockettes__rec_019", "Aceite", 0.5, "l", None),
    # === hojaldre_bladerdeeg__rec_008 ===
    ("hojaldre_bladerdeeg__rec_008", "Harina de trigo", 0.25, "kg", None),
    ("hojaldre_bladerdeeg__rec_008", "Agua", 0.14, "l", None),
    ("hojaldre_bladerdeeg__rec_008", "Sal", 0.005, "kg", None),
    ("hojaldre_bladerdeeg__rec_008", "Manteca", 0.25, "kg", None),
    # === ketjap_manis_version_rapida__rec_007 ===
    ("ketjap_manis_version_rapida__rec_007", "Salsa de soja", 0.24, "l", None),
    ("ketjap_manis_version_rapida__rec_007", "Azúcar morena", 0.24, "kg", None),
    ("ketjap_manis_version_rapida__rec_007", "Ajo", 0.01, "kg", None),
    ("ketjap_manis_version_rapida__rec_007", "Anís estrellado", 0.001, "kg", None),
    ("ketjap_manis_version_rapida__rec_007", "Jengibre", 0.01, "kg", None),
    # === oliebollen_bunuelos_tradicionales_holandeses__rec_016 ===
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Levadura fresca", 0.08, "kg", None),
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Leche", 1.0, "l", None),
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Harina de trigo", 1.0, "kg", None),
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Azúcar", 0.045, "kg", None),
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Ralladura de limón", 1.0, "und", None),
    ("oliebollen_bunuelos_tradicionales_holandeses__rec_016", "Sal", 0.02, "kg", None),
    # === ontbijtkoek_700g_de_harina__rec_004 ===
    ("ontbijtkoek_700g_de_harina__rec_004", "Harina de centeno", 0.7, "kg", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Melaza", 0.56, "kg", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Miel", 0.238, "kg", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Vinagre", 0.007, "l", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Mezcla de especias para Speculaas", 0.042, "kg", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Bicarbonato de sodio", 0.007, "kg", None),
    ("ontbijtkoek_700g_de_harina__rec_004", "Polvo de hornear", 0.014, "kg", None),
    # === pastelitos_rosados_roze_koeken__rec_009 ===
    ("pastelitos_rosados_roze_koeken__rec_009", "Manteca", 0.1, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Azúcar", 0.1, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Huevos", 2.0, "und", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Vainilla", 0.001, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Harina de trigo", 0.11, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Maicena", 0.02, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Polvo de hornear", 0.001, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Frambuesas", 0.1, "kg", None),
    ("pastelitos_rosados_roze_koeken__rec_009", "Azúcar glas", 0.2, "kg", None),
    # === petisus_de_hojaldre_y_crema_tompoezen__rec_015 ===
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Crema pastelera", 0.001, "l", None),
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Crema de leche", 0.4, "l", None),
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Azúcar", 0.045, "kg", None),
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Estabilizante para nata", 0.001, "kg", None),
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Azúcar glas", 0.125, "kg", None),
    ("petisus_de_hojaldre_y_crema_tompoezen__rec_015", "Agua", 0.002, "l", None),
    # === proficteroles_de_den_bosch_bossche_bollen__rec_014 ===
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Masa choux", 1.0, "und", None),
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Azúcar", 0.2, "kg", None),
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Cacao en polvo", 0.015, "kg", None),
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Agua", 0.1, "l", None),
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Chocolate", 0.225, "kg", None),
    ("proficteroles_de_den_bosch_bossche_bollen__rec_014", "Crema de leche", 0.75, "l", None),
    # === stroop_wafel__rec_003 ===
    ("stroop_wafel__rec_003", "Harina de trigo", 0.168, "kg", None),
    ("stroop_wafel__rec_003", "Azúcar", 0.04, "kg", None),
    ("stroop_wafel__rec_003", "Leche", 0.01, "l", None),
    ("stroop_wafel__rec_003", "Canela", 0.002, "kg", None),
    ("stroop_wafel__rec_003", "Manteca", 0.077, "kg", None),
    ("stroop_wafel__rec_003", "Vainilla", 0.002, "kg", None),
    ("stroop_wafel__rec_003", "Sal", 0.002, "kg", None),
    ("stroop_wafel__rec_003", "Levadura seca", 0.002, "kg", None),
    ("stroop_wafel__rec_003", "Huevos", 1.0, "unidad", None),
    ("stroop_wafel__rec_003", "Azúcar", 0.133, "kg", None),
    ("stroop_wafel__rec_003", "Crema de leche", 0.067, "kg", None),
    ("stroop_wafel__rec_003", "Manteca", 0.01, "kg", None),
    # === suppli_cacio_e_pepe__rec_021 ===
    ("suppli_cacio_e_pepe__rec_021", "Arroz para sushi", 0.275, "kg", None),
    ("suppli_cacio_e_pepe__rec_021", "Caldo de carne en cubos", 1.0, "und", None),
    ("suppli_cacio_e_pepe__rec_021", "Huevos", 1.0, "und", None),
    ("suppli_cacio_e_pepe__rec_021", "Queso rallado", 0.05, "kg", None),
    ("suppli_cacio_e_pepe__rec_021", "Pimienta", 0.005, "kg", None),
    ("suppli_cacio_e_pepe__rec_021", "Sal", 0.005, "kg", None),
    ("suppli_cacio_e_pepe__rec_021", "Pan rallado", 0.06, "kg", None),
    # === tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013 ===
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Harina de trigo", 0.35, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Polvo de hornear", 0.002, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Sal", 0.001, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Vainilla", 0.001, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Azúcar", 0.175, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Manteca", 0.25, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Manzana", 6.0, "und", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Canela", 0.002, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Polvo para natillas", 0.003, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Azúcar morena", 0.003, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Pasas", 0.06, "kg", None),
    # === bitterballen_vegetariano__rec_020 ===
    ("bitterballen_vegetariano__rec_020", "Manteca", 0.085, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Echalote", 2.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Ajo", 3.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Girgolas frescas", 0.3, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Tomillo fresco", 1.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Sal", 0.003, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Pimienta", 0.001, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Harina de trigo", 0.075, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Caldo de hongos en cubos", 2.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Huevos", 1.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Crema de leche", 0.03, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Huevos", 2.0, "und", None),
    ("bitterballen_vegetariano__rec_020", "Harina de trigo", 0.015, "kg", None),
    ("bitterballen_vegetariano__rec_020", "Pan rallado", 0.1, "kg", None),
    # === bitterballen__rec_006 ===
    ("bitterballen__rec_006", "Carnaza de segunda", 0.4, "kg", None),
    ("bitterballen__rec_006", "Bola de lomo", 0.4, "kg", None),
    ("bitterballen__rec_006", "Cebolla", 0.15, "kg", None),
    ("bitterballen__rec_006", "Ajo", 1.0, "und", None),
    ("bitterballen__rec_006", "Manteca", 0.04, "kg", None),
    ("bitterballen__rec_006", "Huevos", 2.0, "und", None),
    ("bitterballen__rec_006", "Mostaza", 0.015, "kg", None),
    ("bitterballen__rec_006", "Pimienta", 0.003, "kg", None),
    ("bitterballen__rec_006", "Sal", 0.012, "kg", None),
    ("bitterballen__rec_006", "Zanahoria", 0.06, "kg", None),
    ("bitterballen__rec_006", "Laurel", 0.001, "kg", None),
    ("bitterballen__rec_006", "Manteca", 0.08, "kg", None),
    ("bitterballen__rec_006", "Harina de trigo", 0.1, "kg", None),
    ("bitterballen__rec_006", "Mostaza", 0.005, "kg", None),
    ("bitterballen__rec_006", "Caldo de carne en cubos", 2.0, "und", None),
    ("bitterballen__rec_006", "Agua", 1.0, "l", None),
    ("bitterballen__rec_006", "Crema de leche", 0.05, "l", None),
    ("bitterballen__rec_006", "Huevos", 2.0, "und", None),
    ("bitterballen__rec_006", "Gelatina sin sabor", 0.004900000000000001, "kg", None),
    ("bitterballen__rec_006", "Perejil", 0.5, "und", None),
    ("bitterballen__rec_006", "Pan rallado", 0.1, "kg", None),
    ("bitterballen__rec_006", "Nuez moscada", 0.001, "kg", None),
]



# Products (40+).
# Tuple: (name, recipe_name, portion_label, sale_price_gs, category, sku, iva_rate, rspa_number, is_favorite, dietary_tags, image_url, notes)
PRODUCTS: list[tuple] = [
    (
        "Babka",
        "babka__rec_017",
        "1 unidad",
        12000,
        "Tortas",
        "TO001-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/babka.jpg",
    ),
    (
        "Bizcocho básico 25 cm (Basiscake)",
        "bizcocho_basico_25_cm_basiscake__rec_011",
        "1 unidad",
        14000,
        "Panadería",
        "PA002-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/bizcocho_basico_25_cm.jpg",
    ),
    (
        "Bizcocho básico 30 cm (Basiscake)",
        "bizcocho_basico_30_cm_basiscake__rec_012",
        "1 unidad",
        14000,
        "Panadería",
        "PA003-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/bizcocho_basico_30_cm.jpg",
    ),
    (
        "Bombones de chocolate",
        "bombones_de_chocolate__rec_018",
        "1 unidad",
        15000,
        "Especiales",
        "ES004-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/bombones_de_chocolate.jpg",
    ),
    (
        "Torta de zanahoria (43x33x1.5 cm)",
        "torta_de_zanahoria_43x33x1_5_cm__rec_005",
        "1 unidad",
        14000,
        "Tortas",
        "TO005-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/torta_de_zanahoria.jpg",
    ),
    (
        "Cheesecake (30x50)",
        "cheesecake_30x50__rec_002",
        "1 unidad",
        16000,
        "Tortas",
        "TO006-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/cheesecake.jpg",
    ),
    (
        "Muffin de chocolate (20x20 cm)",
        "muffin_de_chocolate_20x20_cm__rec_001",
        "1 unidad",
        8000,
        "Panadería",
        "PA007-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/muffin_de_chocolate.jpg",
    ),
    (
        "Frikandel (100 unidades)",
        "frikandel_100_unidades__rec_022",
        "1 unidad",
        3000,
        "Salados",
        "SA008-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/frikandel.jpg",
    ),
    (
        "Galletas de especuloos (Speculaasjes)",
        "galletas_de_especuloos_speculaasjes__rec_010",
        "1 unidad",
        3000,
        "Panadería",
        "PA009-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/galletas_de_especuloos.jpg",
    ),
    (
        "goulash crockettes",
        "goulash_crockettes__rec_019",
        "1 unidad",
        3000,
        "Salados",
        "SA010-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/goulash_crockettes.jpg",
    ),
    (
        "Hojaldre (Bladerdeeg)",
        "hojaldre_bladerdeeg__rec_008",
        "1 unidad",
        7000,
        "Pastelería",
        "PS011-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/hojaldre.jpg",
    ),
    (
        "Ketjap manis (versión rápida)",
        "ketjap_manis_version_rapida__rec_007",
        "1 unidad",
        12000,
        "Especiales",
        "ES012-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/ketjap_manis.jpg",
    ),
    (
        "Oliebollen (Buñuelos tradicionales holandeses)",
        "oliebollen_bunuelos_tradicionales_holandeses__rec_016",
        "1 unidad",
        4000,
        "Especiales",
        "ES013-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/oliebollen.jpg",
    ),
    (
        "Ontbijtkoek (700g de harina)",
        "ontbijtkoek_700g_de_harina__rec_004",
        "1 unidad",
        8000,
        "Panadería",
        "PA014-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/ontbijtkoek.jpg",
    ),
    (
        "Pastelitos rosados (Roze koeken)",
        "pastelitos_rosados_roze_koeken__rec_009",
        "1 unidad",
        5000,
        "Especiales",
        "ES015-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/pastelitos_rosados.jpg",
    ),
    (
        "Petisús de hojaldre y crema (Tompoezen)",
        "petisus_de_hojaldre_y_crema_tompoezen__rec_015",
        "1 unidad",
        7000,
        "Pastelería",
        "PS016-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/petisus_de_hojaldre_y_crema.jpg",
    ),
    (
        "Proficteroles de Den Bosch (Bossche bollen)",
        "proficteroles_de_den_bosch_bossche_bollen__rec_014",
        "1 unidad",
        9000,
        "Panadería",
        "PA017-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/proficteroles_de_den_bosch.jpg",
    ),
    (
        "Stroop wafel",
        "stroop_wafel__rec_003",
        "1 unidad",
        6000,
        "Pastelería",
        "PS018-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/stroop_wafel.jpg",
    ),
    (
        "suppli cacio e pepe",
        "suppli_cacio_e_pepe__rec_021",
        "1 unidad",
        4000,
        "Salados",
        "SA019-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/suppli_cacio_e_pepe.jpg",
    ),
    (
        "Tarta de manzana de mi madre (Mijn moeders appeltaart)",
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "1 unidad",
        22000,
        "Panadería",
        "PA020-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/tarta_de_manzana_de_mi_madre.jpg",
    ),
    (
        "bitterballen vegetariano",
        "bitterballen_vegetariano__rec_020",
        "1 unidad",
        3000,
        "Salados",
        "SA021-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/bitterballen_vegetariano.jpg",
    ),
    (
        "bitterballen",
        "bitterballen__rec_006",
        "1 unidad",
        3000,
        "Salados",
        "SA022-U",
        "10",
        None,
        True,
        None,
        None,
        "/static/products/bitterballen.jpg",
    ),
    (
        "Babka entera",
        "babka__rec_017",
        "Lote completo",
        110000,
        "Tortas",
        "TO023-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/babka_entera.jpg",
    ),
    (
        "Cheesecake entera",
        "cheesecake_30x50__rec_002",
        "Lote completo",
        140000,
        "Tortas",
        "TO024-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/cheesecake_entera.jpg",
    ),
    (
        "Docena gofres de sirope",
        "stroop_wafel__rec_003",
        "Lote completo",
        60000,
        "Pastelería",
        "PS025-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/docena_gofres_de_sirope.jpg",
    ),
    (
        "Docena petisús",
        "petisus_de_hojaldre_y_crema_tompoezen__rec_015",
        "Lote completo",
        60000,
        "Pastelería",
        "PS026-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/docena_petisus.jpg",
    ),
    (
        "Docena buñuelos",
        "oliebollen_bunuelos_tradicionales_holandeses__rec_016",
        "Lote completo",
        40000,
        "Especiales",
        "ES027-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/docena_bunuelos.jpg",
    ),
    (
        "Bizcocho 25 cm entero",
        "bizcocho_basico_25_cm_basiscake__rec_011",
        "Lote completo",
        130000,
        "Panadería",
        "PA028-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/bizcocho_25_cm_entero.jpg",
    ),
    (
        "Bizcocho 30 cm entero",
        "bizcocho_basico_30_cm_basiscake__rec_012",
        "Lote completo",
        160000,
        "Panadería",
        "PA029-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/bizcocho_30_cm_entero.jpg",
    ),
    (
        "Caja bombones",
        "bombones_de_chocolate__rec_018",
        "Lote completo",
        15000,
        "Especiales",
        "ES030-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/caja_bombones.jpg",
    ),
    (
        "Docena muffins chocolate",
        "muffin_de_chocolate_20x20_cm__rec_001",
        "Lote completo",
        75000,
        "Panadería",
        "PA031-L",
        "10",
        None,
        False,
        None,
        None,
        "/static/products/docena_muffins_chocolate.jpg",
    ),
    (
        "Venta libre",
        None,
        "1 unidad",
        0,
        "Especiales",
        "VAR-001",
        "10",
        None,
        False,
        None,
        None,
        "Venta libre — definí el precio en el carrito.",
    ),
]



# 15 customers with realistic Paraguayan data
# Tuple: (name, phone, email, cedula, notes, loyalty_points, zone, address,
#         birthday, how_found, preferred_channel, marketing_consent,
#         dietary_restrictions, dietary_preferences, dietary_confirm_always)
CUSTOMERS: list[tuple] = [
    (
        "Roberto Giménez",
        "+595 981 555-100",
        "rgimenez@example.com",
        "3.456.789",
        "Cliente habitual. Pide todos los viernes.",
        580,
        "Centro",
        "Av. España 567, casi Estados Unidos",
        "1985-03-15",
        "instagram",
        "whatsapp",
        True,
        None,
        None,
        False,
    ),
    (
        "María Eugenia Barrios",
        "+595 982 555-101",
        "mbarrios@example.com",
        "4.567.890",
        "Compra tortas para eventos. Encargos con 48h.",
        1240,
        "Villa Morra",
        "Av. Mariscal López 2345",
        "1978-11-22",
        "facebook",
        "whatsapp",
        True,
        "sin-nueces",
        None,
        False,
    ),
    (
        "Carlos Pereira",
        "+595 983 555-102",
        "cpereira@example.com",
        "5.678.901",
        "Pedidos para la oficina. Empanadas + café.",
        95,
        "Recoleta",
        "Brasil 345, Edif. Ana, Piso 4",
        None,
        "recomendacion",
        "mostrador",
        False,
        None,
        None,
        False,
    ),
    (
        "Ana Sosa",
        "+595 984 555-103",
        "asosa@example.com",
        "2.345.678",
        "Cliente nueva. Probó chipa guazú.",
        30,
        "Lambaré",
        "Ruta 1 Km 12, Lambaré",
        "1992-07-30",
        "google",
        "mostrador",
        True,
        None,
        "vegano",
        False,
    ),
    (
        "Diego Maldonado",
        "+595 985 555-104",
        None,
        "3.567.890",
        "Prefiere factura de dulce de leche.",
        220,
        "Centro",
        "Palma 456, casi 14 de Mayo",
        None,
        "cartel",
        "mostrador",
        False,
        None,
        None,
        False,
    ),
    (
        "Lucía Romero",
        "+595 986 555-105",
        "lromero@example.com",
        "4.678.901",
        "Madre con niño celíaco. Siempre pregunta por sin TACC.",
        410,
        "Sajonia",
        "Av. Argentina 678",
        "1988-04-10",
        "recomendacion",
        "whatsapp",
        True,
        "sin-gluten",
        "sin-gluten",
        True,
    ),
    (
        "Pedro Vázquez",
        "+595 987 555-106",
        "pvazquez@example.com",
        "5.789.012",
        "Hombre de negocio. Paga con tarjeta. Factura siempre.",
        680,
        "Villa Morra",
        "Av. Santa Teresa 1234",
        "1975-09-18",
        "instagram",
        "tarjeta",
        True,
        None,
        None,
        False,
    ),
    (
        "Sofía Candia",
        "+595 988 555-107",
        "scandia@example.com",
        "6.890.123",
        "Diseñadora gráfica. Encarga tortas decoradas.",
        320,
        "Recoleta",
        "Sajonia 890",
        "1990-12-05",
        "instagram",
        "whatsapp",
        True,
        "sin-lactosa",
        "sin-lactosa",
        False,
    ),
    (
        "Fernando Torres",
        "+595 981 555-108",
        "ftorres@example.com",
        "1.234.567",
        "Practicante. Celíaco. Solo compra sin TACC.",
        145,
        "Centro",
        "Iturbe 234",
        "2000-02-28",
        "google",
        "mostrador",
        True,
        "sin-gluten",
        "sin-gluten",
        True,
    ),
    (
        "Patricia Méndez",
        "+595 982 555-109",
        "pmendez@example.com",
        "2.345.679",
        "Madre vegana. Pide a menudo opciones veganas.",
        280,
        "Villa Morra",
        "Av. Brasil 567",
        "1983-08-14",
        "facebook",
        "whatsapp",
        True,
        "vegano",
        "vegano",
        False,
    ),
    (
        "Andrés Colmán",
        "+595 983 555-110",
        None,
        None,
        "Cliente ocasional. Sin preferencias especiales.",
        0,
        "Recoleta",
        None,
        None,
        "recomendacion",
        "efectivo",
        False,
        None,
        None,
        False,
    ),
    (
        "Laura Ortellado",
        "+595 984 555-111",
        "lortellado@example.com",
        "3.678.901",
        "Profesional joven. Pide café + medialuna a diario.",
        175,
        "Centro",
        "Independencia Nacional 345",
        "1995-05-20",
        "instagram",
        "mostrador",
        True,
        None,
        None,
        False,
    ),
    (
        "Mauro Cáceres",
        "+595 985 555-112",
        "mcaceres@example.com",
        "4.789.012",
        "Fiestero. Pide tortas grandes para eventos.",
        540,
        "Sajonia",
        "Av. Eusebio Ayala 2345",
        "1980-10-08",
        "cartel",
        "transferencia",
        True,
        None,
        None,
        False,
    ),
    (
        "Rosa Valdez",
        "+595 986 555-113",
        "rvaldez@example.com",
        "5.890.123",
        "Adulto mayor. Pide pan lactal todos los lunes.",
        980,
        "Centro",
        "México 567",
        "1955-06-25",
        "recomendacion",
        "efectivo",
        False,
        "sin-azucar",
        None,
        False,
    ),
    (
        "Julio Benítez",
        "+595 987 555-114",
        None,
        None,
        "Constructor. Pide facturas para el equipo.",
        60,
        "Lambaré",
        "Ruta 2 Km 18",
        "1970-01-12",
        "cartel",
        "efectivo",
        False,
        None,
        None,
        False,
    ),
]

# 12 pedidos across statuses
# Tuple: (customer_idx, days_from_now, hour, minute, status, payment_intent,
#         channel_idx (Channel enum), notes, line_items: list[(product_name, qty)])
# Channel: 0=MOSTRADOR, 1=WHATSAPP, 2=PEDIDOSYA, 3=PHONE
PEDIDOS: list[tuple] = [
    (0, -30, 10, 0, 'fulfilled', 'efectivo', 0, 'Cliente habitual, viernes', [('Muffin de chocolate (20x20 cm)', 6), ('Docena gofres de sirope', 1)]),
    (1, -28, 14, 30, 'fulfilled', 'transferencia', 1, 'Pedido con factura', [('Cheesecake entera', 1)]),
    (2, -21, 9, 0, 'fulfilled', 'efectivo', 0, None, [('Cheesecake (30x50)', 6)]),
    (5, -14, 16, 0, 'fulfilled', 'efectivo', 0, 'Cliente celíaca', [('Cheesecake entera', 1)]),
    (6, -7, 11, 0, 'fulfilled', 'tarjeta', 0, 'Factura con RUC', [('Babka', 2)]),
    (8, -5, 8, 30, 'fulfilled', 'efectivo', 0, 'Para la oficina', [('Hojaldre (Bladerdeeg)', 4)]),
    (2, -2, 10, 30, 'fulfilled', 'tarjeta', 0, 'Ya retirado', [('Petisús de hojaldre y crema (Tompoezen)', 2)]),
    (4, -1, 15, 0, 'ready', 'efectivo', 1, 'Llamó por WhatsApp. Listo para retirar.', [('Muffin de chocolate (20x20 cm)', 6)]),
    (9, 0, 11, 0, 'ready', 'transferencia', 1, 'Opciones vegetarianas', [('Tarta de manzana de mi madre (Mijn moeders appeltaart)', 1)]),
    (12, 0, 18, 0, 'confirmed', 'transferencia', 1, 'Para evento mañana a las 20h', [('Cheesecake entera', 1)]),
    (11, 1, 9, 0, 'confirmed', 'efectivo', 0, 'Pedido diario', [('Muffin de chocolate (20x20 cm)', 12)]),
    (13, 2, 16, 0, 'pending', 'efectivo', 3, 'Llamó por teléfono. Para lunes 16h.', [('Docena gofres de sirope', 1)]),
    (7, 1, 11, 0, 'confirmed', 'transferencia', 1, 'Decorada con flores', [('Cheesecake entera', 1)]),
]



# Freezer temperature log (last 14 days, 2 readings per day)
FREEZER_TEMP_DAYS = 14

# HACCP — every 12 hours, last 14 days
HACCP_TEMP_MIN_C = -22.0
HACCP_TEMP_MAX_C = -16.0

# Market benchmarks
# Tuple: (label, our_wholesale_gs, our_retail_gs, market_avg_gs, market_min_gs)
BENCHMARKS: list[tuple[str, int, int, int, int]] = [
    ('Muffin de chocolate (20x20 cm)', 5500, 8500, 9500, 7500),
    ('Docena muffins chocolate', 55000, 85000, 88000, 75000),
    ('Cheesecake (30x50)', 14000, 25000, 26000, 20000),
    ('Cheesecake entera', 130000, 220000, 210000, 170000),
    ('Stroop wafel', 4500, 7000, 8000, 5500),
    ('Docena gofres de sirope', 55000, 85000, 88000, 75000),
    ('Hojaldre (Bladerdeeg)', 6000, 8500, 9000, 7000),
    ('Tarta de manzana de mi madre (Mijn moeders appeltaart)', 14000, 22000, 23000, 18000),
    ('Petisús de hojaldre y crema (Tompoezen)', 5000, 7500, 8000, 6000),
    ('Docena petisús', 50000, 75000, 80000, 60000),
    ('Oliebollen (Buñuelos tradicionales holandeses)', 3500, 5500, 5500, 4000),
    ('Docena buñuelos', 35000, 55000, 55000, 40000),
    ('Babka', 12000, 18000, 17000, 14000),
    ('Babka entera', 100000, 150000, 140000, 110000),
    ('Bizcocho 25 cm entero', 120000, 180000, 170000, 140000),
    ('Bizcocho 30 cm entero', 150000, 220000, 210000, 170000),
]



# Waste log entries
# Tuple: (ingredient_name, qty, reason, days_ago, recorded_by, notes)
WASTE_LOG: list[tuple[str, float, str, int, str, str | None]] = [
    ('Leche', 0.5, 'vencimiento', 12, 'lucia', 'Caja próxima a vencer'),
    ('Manteca', 0.2, 'mal_estado', 5, 'lucia', 'Rancio'),
    ('Huevos', 6, 'rotura', 4, 'saskia', 'Caja rota al recibir del proveedor'),
    ('Harina de trigo', 0.5, 'derrame', 2, 'diego', 'Bolsa rota'),
    ('Queso crema', 0.3, 'vencimiento', 1, 'saskia', 'Una vez abierto dura poco'),
    ('Chocolate', 0.2, 'mal_estado', 15, 'lucia', 'Bolsa mal cerrada'),
    ('Leche condensada', 0.4, 'mal_estado', 20, 'saskia', 'Lata hinchada'),
]



# Initial stock movement records (one per ingredient: positive entry)
# This documents the seed's opening balance for audit purposes.

# Production plan template (weekly, every weekday gets a basic plan)
# Tuple: (weekday 0-6, product_idx_in_PRODUCTS, qty, notes)
PRODUCTION_TEMPLATES: list[tuple[int, int, float, str | None]] = [
    (0, 6, 24, 'Lunes base'),
    (0, 15, 12, None),
    (0, 0, 6, 'Lunes base'),
    (1, 6, 18, 'Martes'),
    (1, 17, 12, None),
    (1, 0, 8, None),
    (2, 6, 24, 'Miércoles'),
    (2, 17, 12, None),
    (2, 0, 8, None),
    (3, 6, 30, 'Jueves popular'),
    (3, 5, 18, None),
    (3, 19, 10, None),
    (4, 6, 36, 'Viernes — día pico'),
    (4, 5, 24, 'Viernes — día pico'),
    (4, 17, 12, None),
    (4, 15, 12, 'Petisú fin de semana'),
    (5, 6, 24, 'Sábado'),
    (5, 5, 18, None),
    (5, 12, 12, None),
    (6, 6, 18, 'Domingo'),
    (6, 0, 4, None),
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


def _ensure_tenant(
    session: Session, slug: str, name: str, color: str, currency: str
) -> tuple[Tenant, bool]:
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


def _ensure_user(
    session: Session, username: str, password: str, *, role: str = "admin"
) -> tuple[User, bool]:
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
    row = session.execute(select(AppMeta).where(AppMeta.key == "sazon_loaded")).scalar_one_or_none()
    return row is not None and (row.value or "").lower() in ("true", "1", "yes")


def sazon_meta(session: Session) -> dict[str, str]:
    """Return all 6 sazon_* AppMeta rows as a dict (empty if not seeded)."""
    rows = session.execute(select(AppMeta).where(AppMeta.key.in_(SAZON_META_KEYS))).scalars().all()
    return {r.key: r.value for r in rows if r.value is not None}


def seed_sazon(
    session: Session, *, overwrite: bool = False, days_of_history: int = 90
) -> SazonReport:
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
    seed_anchor_date = datetime.now(ASUNCION_TZ).date()

    if overwrite:
        _delete_sazon_data(session)

    # === 1. Tenants ===
    _sazon_tenant, was_created = _ensure_tenant(
        session, TENANT_SLUG, TENANT_NAME, TENANT_COLOR, TENANT_CURRENCY
    )
    if was_created:
        report.tenants += 1
    _default_tenant, _ = _ensure_tenant(session, DEFAULT_TENANT_SLUG, "Default", "#7b3f00", "Gs.")
    logger.info(f"seed: tenant '{TENANT_NAME}' (slug={TENANT_SLUG})")

    # === 2. Users ===
    _saskia_user, was_created = _ensure_user(session, SASKIA_USER, SASKIA_PASSWORD, role="admin")
    if was_created:
        report.users += 1
    for username, password, _full_name, _email in CASHIER_USERS:
        _u, was_created = _ensure_user(session, username, password, role="cashier")
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
        "ops.pickup_instructions": "Tocar timbre. Si está cerrado, llamar al "
        + BUSINESS_INFO["phone"]
        + ".",
    }
    for k, v in branding_settings.items():
        existing = session.execute(
            select(SettingsKV).where(SettingsKV.key == k)
        ).scalar_one_or_none()
        if existing is None:
            session.add(SettingsKV(key=k, value_json=v, updated_at=datetime.now(ASUNCION_TZ)))
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
            session.add(
                Category(name=name, scope="product", sort_order=sort_order, is_active=is_active)
            )
            report.categories += 1
    for name, sort_order, is_active in CATEGORIES_RECIPE:
        existing = session.execute(
            select(Category).where(Category.scope == "recipe_family", Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Category(
                    name=name, scope="recipe_family", sort_order=sort_order, is_active=is_active
                )
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
        existing = session.execute(
            select(MarginTier).where(MarginTier.code == code)
        ).scalar_one_or_none()
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
        existing = session.execute(
            select(StorageType).where(StorageType.code == code)
        ).scalar_one_or_none()
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
    existing_compliance = session.execute(
        select(ComplianceInfo).where(ComplianceInfo.id == 1)
    ).scalar_one_or_none()
    if existing_compliance is None:
        compliance_copy = dict(COMPLIANCE)
        compliance_copy["updated_at"] = datetime.now(ASUNCION_TZ)
        ci = ComplianceInfo(id=1, **compliance_copy)
        session.add(ci)
        report.compliance = 1
    logger.info("seed: compliance info (La Vaquita Holandesa S.A.)")

    # === 14. Suppliers ===
    supplier_objs: list[Supplier] = []
    for name, contact, phone, email, address, ruc, notes in SUPPLIERS:
        existing = session.execute(
            select(Supplier).where(Supplier.name == name)
        ).scalar_one_or_none()
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
            name,
            unit,
            stock_qty,
            price_gs,
            min_stock,
            shelf_days,
            storage,
            category,
            allergens,
            dietary_tags,
            supplier_idx,
            package_size,
            package_unit,
            package_price_gs,
            lot_required,
            may_contain_gluten,
            water_aw,
            humidity_max,
            temp_min,
            temp_max,
        ) = ing_tuple
        existing = session.execute(
            select(Ingredient).where(Ingredient.name == name)
        ).scalar_one_or_none()
        if existing is None:
            ing = Ingredient(
                name=name,
                unit=unit,
                stock_qty=stock_qty,
                purchase_price_gs=price_gs if price_gs > 0 else None,
                purchase_price_updated_at=datetime.now(ASUNCION_TZ),
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
                supplier_id=supplier_objs[supplier_idx].id
                if supplier_idx < len(supplier_objs)
                else None,
                temp_min_c=temp_min,
                temp_max_c=temp_max,
                humidity_max_pct=humidity_max,
                water_activity_aw=water_aw,
                lot_required=lot_required,
                may_contain_gluten=may_contain_gluten,
                opening_stock_qty=stock_qty,
                opening_stock_date=datetime.now(ASUNCION_TZ).date().isoformat(),
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
                    supplier_id=supplier_objs[supplier_idx].id
                    if supplier_idx < len(supplier_objs)
                    else None,
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
                            recorded_at=datetime.now(ASUNCION_TZ) - timedelta(days=days_ago),
                            source="restock",
                        )
                    )
                    report.ingredient_price_events += 1
        else:
            ingredient_objs_by_name[name] = existing
            report.skipped_existing["ingredients_existing"] = (
                report.skipped_existing.get("ingredients_existing", 0) + 1
            )
    logger.info(
        f"seed: {report.ingredients} ingredients + {report.ingredient_variants} variants + {report.ingredient_price_events} price events"
    )

    # === 16. Recipes + RecipeLines ===
    recipe_objs_by_name: dict[str, Recipe] = {}
    for recipe_tuple in RECIPES:
        name, yield_qty, yield_unit, prep, cook, diff, family, menu_tags, dietary, notes, image_url = (
            recipe_tuple
        )
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
                image_url=image_url,
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
            name,
            recipe_name,
            portion_label,
            sale_price,
            category,
            sku,
            iva_rate,
            rspa_number,
            is_favorite,
            dietary,
            image_url,
            notes,
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
    logger.info("seed: tags applied")

    # === 19. Customers + addresses ===
    customer_objs: list[Customer] = []
    for cust_tuple in CUSTOMERS:
        (
            name,
            phone,
            email,
            cedula,
            notes,
            loyalty,
            zone,
            address,
            birthday,
            how_found,
            pref_channel,
            marketing,
            diet_r,
            diet_p,
            diet_confirm,
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
                created_at=datetime.now(ASUNCION_TZ),
                updated_at=datetime.now(ASUNCION_TZ),
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
                    ciudad="Asunción"
                    if zone in ("Centro", "Recoleta", "Sajonia", "Villa Morra")
                    else "Lambaré",
                    pais="Paraguay",
                    address_kind="home",
                    sort_order=0,
                    is_active=True,
                    created_at=datetime.now(ASUNCION_TZ),
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
                    updated_at=datetime.now(ASUNCION_TZ),
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
        for prod_name in [
            'Muffin de chocolate (20x20 cm)',
            'Cheesecake (30x50)',
            'Petisús de hojaldre y crema (Tompoezen)',
            'Babka',
            'Stroop wafel',
            'Tarta de manzana de mi madre (Mijn moeders appeltaart)',
            'Babka entera',
            'Cheesecake entera',
        ]:
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
                        updated_at=datetime.now(ASUNCION_TZ) if days_ago > 0 else None,
                    )
                )
                report.production_completions += 1
    logger.info(f"seed: {report.production_completions} production completions (last 7 days)")

    # === 22. Pedidos + lines ===
    channel_codes = [c[0] for c in CHANNELS]
    for ped_tuple in PEDIDOS:
        cust_idx, days_ago, hour, minute, status, payment, channel_idx, notes, line_items = (
            ped_tuple
        )
        if cust_idx >= len(customer_objs):
            continue
        cust = customer_objs[cust_idx]
        promised_date = today + timedelta(days=days_ago)
        promised_dt = datetime.combine(promised_date, datetime.min.time()) + timedelta(
            hours=hour, minutes=minute
        )
        token = secrets.token_urlsafe(16)
        # Skip empty line items (e.g. "Café (no vendido)")
        valid_lines = [(pn, q) for pn, q in line_items if q > 0 and pn in product_objs_by_name]
        if not valid_lines:
            continue
        channel_code = (
            channel_codes[channel_idx]
            if channel_idx < len(channel_codes)
            else ChannelEnum.MOSTRADOR.value  # P43: enum fallback
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
                public_token_expires_at=datetime.now(ASUNCION_TZ) + timedelta(days=30),
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

        for _sale_idx_in_day in range(count):
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
            existing_sale = (
                session.execute(
                    select(Sale).where(
                        Sale.sold_at >= day_start,
                        Sale.sold_at < day_end,
                        Sale.product_id == product.id,
                        Sale.qty == qty,
                        Sale.customer_id == stable_customer_id,
                    )
                )
                .scalars()
                .first()
            )
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
                        session.execute(select(RecipeLine).where(RecipeLine.recipe_id == recipe.id))
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
    voided_dedup = (
        session.execute(
            select(Sale).where(
                Sale.product_id == first_product.id,
                Sale.qty == 2,
                Sale.notes == "Cliente cambió de opinión",
                Sale.voided_at.isnot(None),
            )
        )
        .scalars()
        .first()
    )
    if voided_dedup is None:
        voided = Sale(
            # Anchor to seed_anchor_date so dedup by (product_id, qty, notes,
            # voided_at IS NOT NULL) is stable across re-runs.
            sold_at=datetime.combine(seed_anchor_date - timedelta(days=2), datetime.min.time())
            + timedelta(hours=20),
            product_id=first_product.id,
            qty=2,
            unit_price_gs=first_product.sale_price_gs,
            notes="Cliente cambió de opinión",
            voided_at=datetime.combine(seed_anchor_date - timedelta(days=2), datetime.min.time())
            + timedelta(hours=21),
            void_reason="Cliente cambió de opinión",
            voided_by=SASKIA_USER,
            payment_method="efectivo",
        )
        session.add(voided)
        session.flush()
        report.sales += 1

    # One encargo (custom order) sale
    encargo_product = list(product_objs_by_name.values())[5]
    encargo_dedup = (
        session.execute(
            select(Sale).where(
                Sale.product_id == encargo_product.id,
                Sale.qty == 1,
                Sale.notes.like("Encargo:%"),
            )
        )
        .scalars()
        .first()
    )
    if encargo_dedup is None:
        encargo = Sale(
            # Anchor to seed_anchor_date for dedup stability.
            sold_at=datetime.combine(seed_anchor_date - timedelta(days=1), datetime.min.time())
            + timedelta(hours=22),
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
    for ing in ingredient_objs_by_name.values():
        # Idempotency: one initial StockMovement per ingredient (1:1 audit trail).
        existing_initial = (
            session.execute(
                select(StockMovement).where(
                    StockMovement.ingredient_id == ing.id,
                    StockMovement.movement_type == "initial",
                )
            )
            .scalars()
            .first()
        )
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
                    recorded_at=datetime.now(ASUNCION_TZ) - timedelta(days=days_ago),
                    recorded_by=by,
                    notes=notes,
                )
            )
            report.waste_log += 1
    logger.info(f"seed: {report.waste_log} waste log entries")

    # === 25. Shopping list (items to reorder) ===
    # Use Spanish ingredient names (the canonical names in the INGREDIENTS list).
    for ing_name in ["Harina de trigo", "Manteca", "Huevos", "Leche", "Azúcar"]:
        ing = ingredient_objs_by_name.get(ing_name)
        if not ing:
            continue
        existing = session.execute(
            select(ShoppingListItem).where(
                ShoppingListItem.ingredient_id == ing.id, not ShoppingListItem.purchased
            )
        ).scalar_one_or_none()
        if existing is None:
            qty_to_buy = (ing.min_stock_qty or 1.0) * 2
            session.add(
                ShoppingListItem(
                    ingredient_id=ing.id,
                    qty_to_buy=qty_to_buy,
                    unit=ing.unit,
                    purpose_text="Stock bajo — comprar antes del lunes",
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
                temp = rng.choice(
                    [
                        rng.uniform(-25, -22),  # too cold
                        rng.uniform(-15, -10),  # too warm
                    ]
                )
            existing = session.execute(
                select(FreezerTemperatureLog).where(FreezerTemperatureLog.recorded_at == ts)
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
        "sazon_seeded_at": datetime.now(ASUNCION_TZ).isoformat(),
        "sazon_tenant_slug": TENANT_SLUG,
        "sazon_tenant_name": TENANT_NAME,
        "sazon_admin_user": SASKIA_USER,
        # Onboarding guard: lets the welcome modal / dashboard know that
        # *some* demo data is loaded. Future feature flags can be added
        # here (e.g. "sazon_loaded_charts", "sazon_loaded_reports").
        "sazon_loaded": "true",
    }
    for k, v in sazon_meta_keys.items():
        existing = session.execute(select(AppMeta).where(AppMeta.key == k)).scalar_one_or_none()
        if existing is None:
            session.add(
                AppMeta(key=k, value=str(v), updated_at=datetime.now(ASUNCION_TZ).isoformat())
            )
        else:
            existing.value = str(v)
            existing.updated_at = datetime.now(ASUNCION_TZ).isoformat()

    # === 30. Bank transactions (a few recent ones) ===
    # Idempotency: the dedup query uses (posted_at, description) as the
    # natural key. Both must be deterministic. seed_anchor_date is a
    # `date` (not datetime) — when compared to the DateTime `posted_at`
    # column, SQLAlchemy coerces to datetime, but the conversion can
    # differ between drivers (midnight UTC vs local tz). To make it
    # 100% stable, we explicitly store posted_at as a midnight datetime.
    bank_tx_data = [
        # (date, amount, type, description, account, balance_gs)
        (
            seed_anchor_date - timedelta(days=60),
            -1_200_000,
            "transfer",
            "Pago a Distribuidora El Molino",
            "Itaú",
            2_500_000,
        ),
        (
            seed_anchor_date - timedelta(days=45),
            -650_000,
            "transfer",
            "Pago a Lácteos Paraguay",
            "Itaú",
            1_850_000,
        ),
        (
            seed_anchor_date - timedelta(days=30),
            3_500_000,
            "deposit",
            "Cierre de caja 30 días",
            "Itaú",
            5_350_000,
        ),
        (
            seed_anchor_date - timedelta(days=20),
            -280_000,
            "debit",
            "Servicios ANDE",
            "Itaú",
            5_070_000,
        ),
        (
            seed_anchor_date - timedelta(days=15),
            2_800_000,
            "deposit",
            "Cierre quincena",
            "Itaú",
            7_870_000,
        ),
        (
            seed_anchor_date - timedelta(days=10),
            -450_000,
            "transfer",
            "Pago a Dulcería Santa Rita",
            "Itaú",
            7_420_000,
        ),
        (seed_anchor_date - timedelta(days=5), -180_000, "debit", "Essap", "Itaú", 7_240_000),
        (
            seed_anchor_date - timedelta(days=2),
            1_800_000,
            "deposit",
            "Cierre de caja 2 días",
            "Itaú",
            9_040_000,
        ),
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
                    delete(SettingsKV).where(
                        SettingsKV.key.like("branding.%") | SettingsKV.key.like("ops.%")
                    )
                )
            elif model in (Customer,):
                # Only delete seeded customers (have an email)
                session.execute(delete(Customer).where(Customer.email.like("%@example.com")))
            elif model is User:
                # Only delete seeded users
                session.execute(
                    delete(User).where(User.username.in_([SASKIA_USER, "lucia", "diego"]))
                )
            elif model is Tenant:
                session.execute(delete(Tenant).where(Tenant.slug == TENANT_SLUG))
            else:
                session.execute(delete(model))
        except Exception as e:
            logger.warning(f"Could not wipe {model.__name__}: {e}")
            session.rollback()
    # Audit log
    try:
        session.execute(delete(AuditLog).where(AuditLog.action == "seed.complete"))
    except Exception as e:
        logger.warning(f"Could not wipe audit log: {e}")
        session.rollback()
    session.commit()


__all__ = [
    "BENCHMARKS",
    "CATEGORIES_PRODUCT",
    "CATEGORIES_RECIPE",
    "CUSTOMERS",
    "DATE_PRESETS",
    "DELIVERY_ZONES",
    "INGREDIENTS",
    "MARGIN_TIERS",
    "MESSAGE_TEMPLATES",
    "PAYMENT_METHODS",
    "PEDIDOS",
    "PRODUCTS",
    "RECIPES",
    "RECIPE_LINES",
    "SASKIA_PASSWORD",
    "SASKIA_USER",
    "STOCK_STATUSES",
    "STORAGE_KEYWORDS",
    "STORAGE_TYPES",
    "SUPPLIERS",
    "TENANT_NAME",
    "TENANT_SLUG",
    "WASTE_LOG",
    "SazonReport",
    "seed_sazon",
]
