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
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.rms.audit import record as audit_record
from app.rms.config import ASUNCION_TZ
from app.rms.models import (
    AppMeta,
    AuditLog,
    BankTransaction,
    CashSession,
    Category,
    Channel,
    CompetitorPriceObservation,
    ComplianceInfo,
    Customer,
    CustomerAddress,
    DateRangePreset,
    DeliveryZone,
    Expense,
    FreezerTemperatureLog,
    ImportBatch,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    MarginTier,
    MarketBenchmark,
    MarketPriceReference,
    Menu,
    MenuItem,
    MessageTemplate,
    MonthlyClosure,
    PaymentMethod,
    Pedido,
    PedidoEvent,
    PedidoLine,
    PriceHistory,
    Product,
    ProductionCompletion,
    ProductionPlan,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    RecipePricing,
    Sale,
    SalePayment,
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
        1.0,
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
        5.0,
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
        2.0,
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
    # --- Packaging materials (sheet "Packaging", MAT-01..07) ---
    # supplier_idx 4 = Embalajes Express; category "packaging"; stock in und.
    (
        "bolsita de 15x22",
        "und",
        0.0,
        249.18,
        100.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        100.0,
        "und",
        24918,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "cintillo 7mm 10m",
        "und",
        0.0,
        32.0,
        100.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        250.0,
        "und",
        8000,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "bandeja isopor",
        "und",
        0.0,
        252.0,
        100.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        100.0,
        "und",
        25200,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "bandeja carton",
        "und",
        0.0,
        336.04,
        25.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        25.0,
        "und",
        8401,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "papel antigrasa blanco",
        "und",
        0.0,
        120.0,
        100.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        100.0,
        "und",
        12000,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "bolsa de papel mediana",
        "und",
        0.0,
        350.0,
        50.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        1.0,
        "und",
        350,
        False,
        False,
        0.3,
        60,
        5,
        35,
    ),
    (
        "caja torta 25cm",
        "und",
        0.0,
        2800.0,
        10.0,
        3650,
        "dry",
        "packaging",
        "",
        "vegano",
        4,
        1.0,
        "und",
        2800,
        False,
        False,
        0.3,
        60,
        5,
        35,
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
    (
        "galletas_de_especuloos_speculaasjes__rec_010",
        "Suero de leche (buttermilk)",
        0.045,
        "l",
        None,
    ),
    ("galletas_de_especuloos_speculaasjes__rec_010", "Harina de trigo", 0.4, "kg", None),
    (
        "galletas_de_especuloos_speculaasjes__rec_010",
        "Mezcla de especias para Speculaas",
        0.004,
        "kg",
        None,
    ),
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
    (
        "oliebollen_bunuelos_tradicionales_holandeses__rec_016",
        "Ralladura de limón",
        1.0,
        "und",
        None,
    ),
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
    (
        "petisus_de_hojaldre_y_crema_tompoezen__rec_015",
        "Estabilizante para nata",
        0.001,
        "kg",
        None,
    ),
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
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Harina de trigo",
        0.35,
        "kg",
        None,
    ),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Polvo de hornear",
        0.002,
        "kg",
        None,
    ),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Sal", 0.001, "kg", None),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Vainilla",
        0.001,
        "kg",
        None,
    ),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Azúcar", 0.175, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Manteca", 0.25, "kg", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Manzana", 6.0, "und", None),
    ("tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013", "Canela", 0.002, "kg", None),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Polvo para natillas",
        0.003,
        "kg",
        None,
    ),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Azúcar morena",
        0.003,
        "kg",
        None,
    ),
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
        "/static/products/babka.jpg",
        None,
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
        "/static/products/bizcocho_basico_25_cm.jpg",
        None,
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
        "/static/products/bizcocho_basico_30_cm.jpg",
        None,
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
        "/static/products/bombones_de_chocolate.jpg",
        None,
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
        "/static/products/torta_de_zanahoria.jpg",
        None,
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
        "/static/products/cheesecake.jpg",
        None,
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
        "/static/products/muffin_de_chocolate.jpg",
        None,
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
        "/static/products/frikandel.jpg",
        None,
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
        "/static/products/galletas_de_especuloos.jpg",
        None,
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
        "/static/products/goulash_crockettes.jpg",
        None,
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
        "/static/products/hojaldre.jpg",
        None,
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
        "/static/products/ketjap_manis.jpg",
        None,
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
        "/static/products/oliebollen.jpg",
        None,
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
        "/static/products/ontbijtkoek.jpg",
        None,
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
        "/static/products/pastelitos_rosados.jpg",
        None,
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
        "/static/products/petisus_de_hojaldre_y_crema.jpg",
        None,
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
        "/static/products/proficteroles_de_den_bosch.jpg",
        None,
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
        "/static/products/stroop_wafel.jpg",
        None,
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
        "/static/products/suppli_cacio_e_pepe.jpg",
        None,
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
        "/static/products/tarta_de_manzana_de_mi_madre.jpg",
        None,
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
        "/static/products/bitterballen_vegetariano.jpg",
        None,
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
        "/static/products/bitterballen.jpg",
        None,
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
        "/static/products/babka_entera.jpg",
        None,
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
        "/static/products/cheesecake_entera.jpg",
        None,
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
        "/static/products/docena_gofres_de_sirope.jpg",
        None,
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
        "/static/products/docena_petisus.jpg",
        None,
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
        "/static/products/docena_bunuelos.jpg",
        None,
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
        "/static/products/bizcocho_25_cm_entero.jpg",
        None,
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
        "/static/products/bizcocho_30_cm_entero.jpg",
        None,
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
        "/static/products/caja_bombones.jpg",
        None,
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
        "/static/products/docena_muffins_chocolate.jpg",
        None,
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
    (
        0,
        -30,
        10,
        0,
        "fulfilled",
        "efectivo",
        0,
        "Cliente habitual, viernes",
        [("Muffin de chocolate (20x20 cm)", 6), ("Docena gofres de sirope", 1)],
    ),
    (
        1,
        -28,
        14,
        30,
        "fulfilled",
        "transferencia",
        1,
        "Pedido con factura",
        [("Cheesecake entera", 1)],
    ),
    (2, -21, 9, 0, "fulfilled", "efectivo", 0, None, [("Cheesecake (30x50)", 6)]),
    (5, -14, 16, 0, "fulfilled", "efectivo", 0, "Cliente celíaca", [("Cheesecake entera", 1)]),
    (6, -7, 11, 0, "fulfilled", "tarjeta", 0, "Factura con RUC", [("Babka", 2)]),
    (8, -5, 8, 30, "fulfilled", "efectivo", 0, "Para la oficina", [("Hojaldre (Bladerdeeg)", 4)]),
    (
        2,
        -2,
        10,
        30,
        "fulfilled",
        "tarjeta",
        0,
        "Ya retirado",
        [("Petisús de hojaldre y crema (Tompoezen)", 2)],
    ),
    (
        4,
        -1,
        15,
        0,
        "ready",
        "efectivo",
        1,
        "Llamó por WhatsApp. Listo para retirar.",
        [("Muffin de chocolate (20x20 cm)", 6)],
    ),
    (
        9,
        0,
        11,
        0,
        "ready",
        "transferencia",
        1,
        "Opciones vegetarianas",
        [("Tarta de manzana de mi madre (Mijn moeders appeltaart)", 1)],
    ),
    (
        12,
        0,
        18,
        0,
        "confirmed",
        "transferencia",
        1,
        "Para evento mañana a las 20h",
        [("Cheesecake entera", 1)],
    ),
    (
        11,
        1,
        9,
        0,
        "confirmed",
        "efectivo",
        0,
        "Pedido diario",
        [("Muffin de chocolate (20x20 cm)", 12)],
    ),
    (
        13,
        2,
        16,
        0,
        "pending",
        "efectivo",
        3,
        "Llamó por teléfono. Para lunes 16h.",
        [("Docena gofres de sirope", 1)],
    ),
    (
        7,
        1,
        11,
        0,
        "confirmed",
        "transferencia",
        1,
        "Decorada con flores",
        [("Cheesecake entera", 1)],
    ),
]


# Freezer temperature log (last 14 days, 2 readings per day)
FREEZER_TEMP_DAYS = 14

# HACCP — every 12 hours, last 14 days
HACCP_TEMP_MIN_C = -22.0
HACCP_TEMP_MAX_C = -16.0

# Market benchmarks
# Tuple: (label, our_wholesale_gs, our_retail_gs, market_avg_gs, market_min_gs)
BENCHMARKS: list[tuple[str, int, int, int, int]] = [
    ("Muffin de chocolate (20x20 cm)", 5500, 8500, 9500, 7500),
    ("Docena muffins chocolate", 55000, 85000, 88000, 75000),
    ("Cheesecake (30x50)", 14000, 25000, 26000, 20000),
    ("Cheesecake entera", 130000, 220000, 210000, 170000),
    ("Stroop wafel", 4500, 7000, 8000, 5500),
    ("Docena gofres de sirope", 55000, 85000, 88000, 75000),
    ("Hojaldre (Bladerdeeg)", 6000, 8500, 9000, 7000),
    ("Tarta de manzana de mi madre (Mijn moeders appeltaart)", 14000, 22000, 23000, 18000),
    ("Petisús de hojaldre y crema (Tompoezen)", 5000, 7500, 8000, 6000),
    ("Docena petisús", 50000, 75000, 80000, 60000),
    ("Oliebollen (Buñuelos tradicionales holandeses)", 3500, 5500, 5500, 4000),
    ("Docena buñuelos", 35000, 55000, 55000, 40000),
    ("Babka", 12000, 18000, 17000, 14000),
    ("Babka entera", 100000, 150000, 140000, 110000),
    ("Bizcocho 25 cm entero", 120000, 180000, 170000, 140000),
    ("Bizcocho 30 cm entero", 150000, 220000, 210000, 170000),
]

# === Market price references (per ingredient, Asunción, oct 2026) ===
# Tuple: (ingredient_name, unit, price_gs, source, notes)
# Used by _seed_market_price_references. Sources: manual (operator note),
# supermarket (Stock/Supersei), mayorista (Tregar, El Molino), csv-import.
# Prices are MEDIAN market observations (G./kg, G./l, or G./und).
MARKET_PRICE_REFERENCES: list[tuple[str, str, float, str, str]] = [
    # Harinas y bases
    ("Harina de centeno", "kg", 9800, "supermercado", "Stock Ypacaraí, oct 2026"),
    ("Harina de repostería", "kg", 6500, "supermercado", "Stock Ypacaraí, oct 2026"),
    ("Harina de trigo", "kg", 5500, "mayorista", "El Molino, mayoreo 25kg"),
    ("Harina Patentada", "kg", 9000, "supermercado", "Stock, paquete 1kg"),
    ("Maicena", "kg", 8500, "supermercado", "Stock, paquete 1kg"),
    ("Pan rallado", "kg", 4500, "supermercado", "Supersei 1kg"),
    # Endulzantes
    ("Azúcar", "kg", 4800, "supermercado", "Stock 1kg, oct 2026"),
    ("Azúcar glas", "kg", 9500, "supermercado", "Stock 1kg"),
    ("Azúcar morena", "kg", 6200, "supermercado", "Supersei 1kg"),
    ("Miel de abeja", "kg", 45000, "mayorista", "Miel Apícola Caaguazú"),
    # Lácteos y huevos
    ("Leche", "l", 7500, "supermercado", "Lácteos Paraguay, 1L UAT"),
    ("Leche en polvo", "kg", 38000, "mayorista", "Milkaut bolsa 800g"),
    ("Manteca", "kg", 39800, "mayorista", "Lácteos Paraguay, barra 1kg"),
    ("Crema de leche", "l", 22000, "supermercado", "Chandelle 1L"),
    ("Crema agria", "l", 28000, "supermercado", "Chandelle 500ml (×2 equiv)"),
    ("Crema pastelera", "l", 32000, "manual", "Elaborada, costo insumo"),
    ("Queso crema", "kg", 55000, "supermercado", "Philadelphia 1.5kg"),
    ("Queso muzzarella", "kg", 38000, "mayorista", "Tregar, bloque 2.5kg"),
    ("Queso rallado", "kg", 60000, "supermercado", "Tregar 40g pack"),
    ("Suero de leche (buttermilk)", "l", 12000, "manual", "Subproducto artesanal"),
    ("Huevos", "und", 1200, "supermercado", "Docena, Stock Asunción"),
    # Cacao café y chocolate
    ("Cacao en polvo", "kg", 75000, "supermercado", "Coca-Cola Foods 1kg"),
    ("Chocolate cobertura", "kg", 68000, "mayorista", "Callebaut cobertura 70%"),
    ("Chocolate", "kg", 58000, "supermercado", "Nestlé 1kg"),
    ("Café", "kg", 85000, "supermercado", "Café Majada 500g"),
    # Especias y condimentos
    ("Canela", "kg", 18000, "supermercado", "Stock, frasco 50g"),
    ("Vainilla", "kg", 950000, "importado", "Esencia vainilla 1L"),
    ("Ralladura de limón", "kg", 35000, "manual", "Cáscara fresca, rendimiento"),
    ("Esencia de vainilla", "l", 65000, "supermercado", "McCormick 500ml"),
    ("Sal", "kg", 1800, "supermercado", "Celusal 1kg"),
    ("Pimienta", "kg", 12000, "supermercado", "Stock frasco"),
    ("Mostaza", "kg", 28000, "supermercado", "Savora 200g"),
    ("Laurel", "kg", 15000, "supermercado", "Hojas secas, frasco"),
    ("Anís estrellado", "kg", 22000, "supermercado", "Especias Paraguay"),
    ("Mezcla de especias para Speculaas", "kg", 35000, "manual", "Mezcla casera"),
    # Levaduras y gasificantes
    ("Levadura fresca", "kg", 22000, "supermercado", "Fleischmann 500g"),
    ("Levadura seca", "kg", 45000, "supermercado", "Fleischmann sachet 11g"),
    ("Polvo de hornear", "kg", 18000, "supermercado", "Royal 250g"),
    ("Bicarbonato de sodio", "kg", 12000, "supermercado", "Genérico 500g"),
    # Frutas y frutos secos
    ("Manzana", "und", 2500, "mayorista", "Abasto, caja 60 und"),
    ("Limón", "und", 800, "mayorista", "Abasto, kilo / 6 und"),
    ("Frambuesas", "kg", 95000, "supermercado", "Congeladas, paquete 250g"),
    ("Frutilla", "kg", 22000, "mayorista", "Abasto Asunción, temporada"),
    ("Fruta", "kg", 18000, "mayorista", "Mezcla de estación"),
    ("Pasas", "kg", 12500, "supermercado", "Stock 500g"),
    ("Mango", "und", 3000, "mayorista", "Abasto, kilo / 3 und"),
    ("Arándanos", "kg", 85000, "supermercado", "Importado, congelado"),
    ("Nueces", "kg", 78000, "supermercado", "Mitad, 500g"),
    # Verduras y legumbres
    ("Cebolla", "kg", 4500, "mayorista", "Abasto, semana oct 2026"),
    ("Cebolla morada", "kg", 6500, "mayorista", "Abasto, semana oct 2026"),
    ("Cebolla de verdeo", "kg", 8500, "mayorista", "Abasto, atado"),
    ("Zanahoria", "kg", 4200, "mayorista", "Abasto, semana oct 2026"),
    ("Apio", "und", 3500, "mayorista", "Atado, 6-8 tallos"),
    ("Morrón rojo", "und", 5000, "mayorista", "Abasto, pieza"),
    ("Pimentón", "kg", 12000, "supermercado", "Frutos del Paraguay"),
    ("Tomate", "kg", 6500, "mayorista", "Abasto, semana oct 2026"),
    ("Garbanzo", "kg", 12000, "supermercado", "Lata 350g, drenado"),
    # Carnes
    ("Carnaza de segunda", "kg", 38000, "mayorista", "Frigorífico Guaraní"),
    ("Bola de lomo", "kg", 55000, "mayorista", "Frigorífico Guaraní"),
    ("Falda de res", "kg", 34900, "mayorista", "Supermas, semana oct 2026"),
    ("Pollo", "kg", 18500, "mayorista", "Frigorífico Concepción"),
    # Salsas y líquidos
    ("Agua", "l", 3500, "supermercado", "Salus, 1.5L"),
    ("Leche de coco", "l", 18500, "supermercado", "Importada, lata 400ml"),
    ("Salsa de soja", "l", 18000, "supermercado", "Kikkoman, 1L"),
    ("Vinagre", "l", 7500, "supermercado", "Menoyo 1L"),
    ("Caldo de carne en cubos", "und", 1100, "supermercado", "Maggi, cubo 11g"),
    ("Puré de tomate", "kg", 9500, "supermercado", "Arcor lata 210g"),
    # Aceites y grasas
    ("Aceite", "l", 11500, "supermercado", "Natura 1.5L"),
    ("Manteca vegetal", "kg", 22000, "supermercado", "Cocinera 1kg"),
    # Preparados y otros
    ("Bicarbonato", "kg", 12000, "supermercado", "Genérico 500g"),
    ("Gelatina sin sabor", "kg", 65000, "supermercado", "Royal 12g × 4"),
    ("Estabilizante para nata", "kg", 58000, "supermercado", "Hacendado"),
    ("Esencia de almendras", "l", 78000, "supermercado", "McCormick 60ml"),
    ("Polvo para natillas", "kg", 22000, "supermercado", "Royal 200g"),
    ("Girgolas frescas", "kg", 40000, "mayorista", "Hongos del Sur"),
    ("Echalote", "und", 4000, "mayorista", "Importado, atado"),
    ("Tomillo fresco", "und", 3000, "mayorista", "Atado chico"),
    ("Perejil", "und", 2500, "mayorista", "Atado, 100g"),
    ("Caldo de hongos en cubos", "und", 1100, "supermercado", "Maggi, cubo 11g"),
    ("Pimentón ahumado", "kg", 12000, "supermercado", "Cocinar.com.py 100g"),
    ("Alcaravea", "kg", 12000, "supermercado", "Especia, frasco 50g"),
    ("Cayena", "kg", 12000, "supermercado", "Especia, frasco 50g"),
    ("Masa de hojaldre", "und", 8500, "supermercado", "Hojaldre congelado"),
    ("Jugo de remolacha", "l", 18000, "manual", "Remolacha fresca exprimida"),
    ("Arroz para sushi", "kg", 22400, "mayorista", "Ypacaraí, 500g"),
    # Packaging (informational, parte del costo del producto)
    ("bolsita de 15x22", "und", 350, "mayorista", "Embalajes Express, pack 100"),
    ("cintillo 7mm 10m", "und", 50, "mayorista", "Bandera Py, rollo"),
    ("bandeja isopor", "und", 350, "mayorista", "B-190 blanco, pack 100"),
    ("bandeja carton", "und", 400, "mayorista", "Bandejas pegadas n*3"),
    ("papel antigrasa blanco", "und", 150, "mayorista", "Papel sulfito 70g"),
    ("bolsa de papel mediana", "und", 450, "mayorista", "Para entrega"),
    ("caja torta 25cm", "und", 3500, "mayorista", "Cartón rígido"),
]


# === Competitor price observations (Asunción, 2026, retail products) ===
# Tuple: (competitor, competitor_type, city, product_name, family, unit, price_gs, days_ago, source_url_or_note)
COMPETITOR_OBSERVATIONS: list[tuple[str, str, str, str, str, str, int, int, str]] = [
    # Karu (panadería/café, Asunción centro)
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Cheesecake individual",
        "cheesecake",
        "porción",
        28000,
        14,
        "carta online oct 2026",
    ),
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Babka unidad",
        "babka",
        "unidad",
        18000,
        14,
        "carta online oct 2026",
    ),
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Tarta de manzana porción",
        "tarta-manzana",
        "porción",
        22000,
        14,
        "carta online oct 2026",
    ),
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Muffin de chocolate",
        "muffin",
        "unidad",
        9000,
        14,
        "carta online oct 2026",
    ),
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Stroop wafel",
        "stroopwafel",
        "unidad",
        7500,
        14,
        "carta online oct 2026",
    ),
    # El Café de Acá (café, Carmelitas)
    (
        "El Café de Acá",
        "cafetería",
        "Asunción",
        "Cheesecake porción",
        "cheesecake",
        "porción",
        32000,
        21,
        "carta online oct 2026",
    ),
    (
        "El Café de Acá",
        "cafetería",
        "Asunción",
        "Bizcocho 25 cm entero",
        "bizcocho",
        "entero",
        180000,
        21,
        "Instagram sep 2026",
    ),
    (
        "El Café de Acá",
        "cafetería",
        "Asunción",
        "Docena muffins chocolate",
        "muffin",
        "docena",
        75000,
        21,
        "carta online oct 2026",
    ),
    # Lido (confitería, centro)
    (
        "Lido Confitería",
        "confitería",
        "Asunción",
        "Torta de zanahoria entera",
        "torta-zanahoria",
        "entera",
        180000,
        30,
        "carta online",
    ),
    (
        "Lido Confitería",
        "confitería",
        "Asunción",
        "Selva negra entera",
        "torta-chocolate",
        "entera",
        220000,
        30,
        "carta online",
    ),
    # Mr. John's (confitería, varias)
    (
        "Mr. John's",
        "confitería",
        "Asunción",
        "Bombones de chocolate caja 12",
        "bombones",
        "caja-12",
        65000,
        7,
        "carta online oct 2026",
    ),
    (
        "Mr. John's",
        "confitería",
        "Asunción",
        "Muffin de chocolate unidad",
        "muffin",
        "unidad",
        8500,
        7,
        "carta online oct 2026",
    ),
    # El Hornero (panadería, varios locales)
    (
        "El Hornero",
        "panadería",
        "Asunción",
        "Bizcocho 30 cm entero",
        "bizcocho",
        "entero",
        220000,
        45,
        "observación local Villa Morra",
    ),
    (
        "El Hornero",
        "panadería",
        "Asunción",
        "Hojaldre (Bladerdeeg) unidad",
        "hojaldre",
        "unidad",
        9000,
        45,
        "carta online",
    ),
    # Supersei / Stock (supermercados, referencia retail)
    (
        "Stock",
        "supermercado",
        "Asunción",
        "Babka unidad",
        "babka",
        "unidad",
        14000,
        10,
        "góndola, local Mcal López",
    ),
    (
        "Stock",
        "supermercado",
        "Asunción",
        "Stroop wafel importado",
        "stroopwafel",
        "unidad",
        5500,
        10,
        "góndola importados",
    ),
    (
        "Supersei",
        "supermercado",
        "Asunción",
        "Torta de manzana congelada",
        "tarta-manzana",
        "entera",
        85000,
        10,
        "góndola congelados",
    ),
    # Tiendas especializadas / importados
    (
        "La Pimienta",
        "importado",
        "Asunción",
        "Babka importada",
        "babka",
        "unidad",
        17000,
        25,
        "carta online",
    ),
    (
        "La Pimienta",
        "importado",
        "Asunción",
        "Hojaldre importado",
        "hojaldre",
        "unidad",
        8500,
        25,
        "carta online",
    ),
    # La Alemana (panadería clásica)
    (
        "La Alemana",
        "panadería",
        "Asunción",
        "Bizcocho 25 cm entero",
        "bizcocho",
        "entero",
        150000,
        60,
        "carta online",
    ),
    (
        "La Alemana",
        "panadería",
        "Asunción",
        "Torta de manzana entera",
        "tarta-manzana",
        "entera",
        140000,
        60,
        "carta online",
    ),
    # La Molleja (salados)
    (
        "La Molleja",
        "bistró",
        "Asunción",
        "Bitterballen 10 und",
        "bitterballen",
        "porcion-10",
        55000,
        40,
        "Instagram sep 2026",
    ),
    (
        "La Molleja",
        "bistró",
        "Asunción",
        "Frikandel unidad",
        "frikandel",
        "unidad",
        6000,
        40,
        "Instagram sep 2026",
    ),
    # Cadenas de delivery
    (
        "PedidosYa — Las Marianas",
        "delivery",
        "Asunción",
        "Cheesecake porción",
        "cheesecake",
        "porción",
        35000,
        5,
        "app PedidosYa oct 2026",
    ),
    (
        "PedidosYa — Las Marianas",
        "delivery",
        "Asunción",
        "Tarta de manzana entera",
        "tarta-manzana",
        "entera",
        165000,
        5,
        "app PedidosYa oct 2026",
    ),
    # Cafetería de barrio
    (
        "Café Central",
        "cafetería",
        "Asunción",
        "Muffin de chocolate",
        "muffin",
        "unidad",
        8000,
        18,
        "observación operador",
    ),
    (
        "Café Central",
        "cafetería",
        "Asunción",
        "Stroop wafel",
        "stroopwafel",
        "unidad",
        6500,
        18,
        "observación operador",
    ),
    # Supersei — más categorías
    (
        "Supersei",
        "supermercado",
        "Asunción",
        "Docena muffins importados",
        "muffin",
        "docena",
        72000,
        30,
        "góndola importados",
    ),
    # Oliebollen (temporada)
    (
        "Karu Café",
        "panadería",
        "Asunción",
        "Oliebollen bolsa 6 und",
        "oliebollen",
        "bolsa-6",
        28000,
        8,
        "carta online oct 2026 (temporada)",
    ),
    # Productos locales premium
    (
        "Pasticceria Roma",
        "confitería",
        "Asunción",
        "Cheesecake entera 30 cm",
        "cheesecake",
        "entera",
        240000,
        50,
        "carta online",
    ),
    (
        "Pasticceria Roma",
        "confitería",
        "Asunción",
        "Babka unidad",
        "babka",
        "unidad",
        19000,
        50,
        "carta online",
    ),
    # Roze koeken / pastelitos rosados (asociados a Holanda, hard to find)
    (
        "HEMA (importador)",
        "importado",
        "Asunción",
        "Roze koeken caja 6",
        "roze-koeken",
        "caja-6",
        60000,
        90,
        "Instagram jul 2026",
    ),
    # Stroopwafel supermarket
    (
        "Supersei",
        "supermercado",
        "Asunción",
        "Stroop wafel marca Daelmans",
        "stroopwafel",
        "unidad",
        5800,
        30,
        "góndola importados",
    ),
]


# === Tag-link rules (auto-aplicación de tags a productos/recetas/ingredientes) ===
# Tuple: (tag_name, kind, predicate_kind, predicate_value)
TAG_LINK_RULES: list[tuple[str, str, str, str]] = [
    # Ingredient storage tags
    ("seco", "ingredient", "storage", "dry"),
    ("refrigerado", "ingredient", "storage", "refrigerated"),
    ("perecedero", "ingredient", "storage", "refrigerated"),
    ("congelable", "ingredient", "storage", "frozen"),
    # Ingredient allergen tags
    ("alergeno-gluten", "ingredient", "name_contains", "harina"),
    ("alergeno-gluten", "ingredient", "name_contains", "trigo"),
    ("alergeno-gluten", "ingredient", "name_contains", "centeno"),
    ("alergeno-lactosa", "ingredient", "name_contains", "leche"),
    ("alergeno-lactosa", "ingredient", "name_contains", "crema"),
    ("alergeno-lactosa", "ingredient", "name_contains", "queso"),
    ("alergeno-lactosa", "ingredient", "name_contains", "manteca"),
    ("alergeno-frutos-secos", "ingredient", "name_contains", "nuez"),
    ("alergeno-frutos-secos", "ingredient", "name_contains", "almendra"),
    # Ingredient origin tags
    ("importado", "ingredient", "name_contains", "vainilla"),
    ("importado", "ingredient", "name_contains", "almendra"),
    ("importado", "ingredient", "name_contains", "arándano"),
    ("importado", "ingredient", "name_contains", "masa de hojaldre"),
    ("local", "ingredient", "name_contains", "harina"),
    ("local", "ingredient", "name_contains", "manzana"),
    ("local", "ingredient", "name_contains", "queso"),
    # Ingredient volatility
    ("precio-volatil", "ingredient", "name_contains", "leche"),
    ("precio-volatil", "ingredient", "name_contains", "manteca"),
    ("precio-volatil", "ingredient", "name_contains", "huevo"),
    ("precio-volatil", "ingredient", "name_contains", "carne"),
    ("precio-volatil", "ingredient", "name_contains", "res"),
    ("precio-volatil", "ingredient", "name_contains", "pollo"),
    # Product attribute tags
    ("vegano", "product", "name_contains", "vegano"),
    ("vegano", "product", "name_contains", "pan integral"),
    ("sin-gluten", "product", "name_contains", "sin gluten"),
    ("sin-lactosa", "product", "name_contains", "sin lactosa"),
    ("sin-azucar", "product", "name_contains", "sin azúcar"),
    ("con-nueces", "product", "name_contains", "nuez"),
    ("con-nueces", "product", "name_contains", "almendra"),
    ("para-eventos", "product", "name_contains", "entera"),
    ("para-eventos", "product", "name_contains", "entero"),
    ("para-eventos", "product", "name_contains", "docena"),
    ("requiere-encargo", "product", "name_contains", "torta"),
    ("navidad", "product", "name_contains", "stollen"),
    ("navidad", "product", "name_contains", "panettone"),
    ("verano", "product", "name_contains", "helado"),
    ("festivo", "product", "name_contains", "fritter"),
    ("estacional", "product", "name_contains", "oliebollen"),
    ("estacional", "product", "name_contains", "pascua"),
    # Recipe cost tiers
    ("alto-costo", "recipe", "cost_above", "15000"),
]


# Waste log entries
# Tuple: (ingredient_name, qty, reason, days_ago, recorded_by, notes)
WASTE_LOG: list[tuple[str, float, str, int, str, str | None]] = [
    ("Leche", 0.5, "vencimiento", 12, "lucia", "Caja próxima a vencer"),
    ("Manteca", 0.2, "mal_estado", 5, "lucia", "Rancio"),
    ("Huevos", 6, "rotura", 4, "saskia", "Caja rota al recibir del proveedor"),
    ("Harina de trigo", 0.5, "derrame", 2, "diego", "Bolsa rota"),
    ("Queso crema", 0.3, "vencimiento", 1, "saskia", "Una vez abierto dura poco"),
    ("Chocolate", 0.2, "mal_estado", 15, "lucia", "Bolsa mal cerrada"),
    ("Leche condensada", 0.4, "mal_estado", 20, "saskia", "Lata hinchada"),
]


# Initial stock movement records (one per ingredient: positive entry)
# This documents the seed's opening balance for audit purposes.

# Production plan template (weekly, every weekday gets a basic plan)
# Tuple: (weekday 0-6, product_idx_in_PRODUCTS, qty, notes)
PRODUCTION_TEMPLATES: list[tuple[int, int, float, str | None]] = [
    (0, 6, 24, "Lunes base"),
    (0, 15, 12, None),
    (0, 0, 6, "Lunes base"),
    (1, 6, 18, "Martes"),
    (1, 17, 12, None),
    (1, 0, 8, None),
    (2, 6, 24, "Miércoles"),
    (2, 17, 12, None),
    (2, 0, 8, None),
    (3, 6, 30, "Jueves popular"),
    (3, 5, 18, None),
    (3, 19, 10, None),
    (4, 6, 36, "Viernes — día pico"),
    (4, 5, 24, "Viernes — día pico"),
    (4, 17, 12, None),
    (4, 15, 12, "Petisú fin de semana"),
    (5, 6, 24, "Sábado"),
    (5, 5, 18, None),
    (5, 12, 12, None),
    (6, 6, 18, "Domingo"),
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
    recipe_pricing: int = 0
    market_price_references: int = 0
    competitor_observations: int = 0
    tag_links: int = 0
    historical_price_events: int = 0
    recipe_meta_updated: int = 0
    product_meta_updated: int = 0
    ingredient_meta_updated: int = 0
    price_history: int = 0
    expenses: int = 0
    cash_sessions: int = 0
    sale_payments: int = 0
    monthly_closures: int = 0
    menus: int = 0
    menu_items: int = 0
    production_plans: int = 0
    data_quality_fixes: dict = field(default_factory=dict)
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
            "recipe_pricing": self.recipe_pricing,
            "market_price_references": self.market_price_references,
            "competitor_observations": self.competitor_observations,
            "tag_links": self.tag_links,
            "historical_price_events": self.historical_price_events,
            "recipe_meta_updated": self.recipe_meta_updated,
            "product_meta_updated": self.product_meta_updated,
            "ingredient_meta_updated": self.ingredient_meta_updated,
            "price_history": self.price_history,
            "expenses": self.expenses,
            "cash_sessions": self.cash_sessions,
            "sale_payments": self.sale_payments,
            "monthly_closures": self.monthly_closures,
            "menus": self.menus,
            "menu_items": self.menu_items,
            "production_plans": self.production_plans,
            "data_quality_fixes": self.data_quality_fixes,
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


@dataclass
class SeedContext:
    """Shared context for seed_sazon sections.

    Groups all shared state (session, report, rng, anchor_date, and
    populated collections) so each section helper takes only `ctx`.
    Populated collections start empty and are filled as the seed
    progresses through the sections.
    """

    session: Session
    report: SazonReport
    rng: random.Random
    anchor_date: Any  # datetime.date

    # Populated as seed progresses
    suppliers: list = field(default_factory=list)
    ingredients_by_name: dict[str, Any] = field(default_factory=dict)
    recipes_by_name: dict[str, Any] = field(default_factory=dict)
    products_by_name: dict[str, Any] = field(default_factory=dict)
    customers: list = field(default_factory=list)
    pedidos: list = field(default_factory=list)
    sales_by_date: dict[Any, list] = field(default_factory=dict)


def seed_sazon(
    session: Session, *, overwrite: bool = False, days_of_history: int = 90
) -> SazonReport:
    """Idempotent comprehensive seed for La Vaquita Holandesa.

    Refactored 2026-10-09: complexity reduced from 232 to <5 using
    SeedContext pattern. Each section is a helper that takes only `ctx`.
    """
    ctx = SeedContext(
        session=session,
        report=SazonReport(),
        rng=random.Random(42),
        anchor_date=datetime.now(ASUNCION_TZ).date(),
    )

    if overwrite:
        _delete_sazon_data(session)

    _seed_tenants(ctx)
    _seed_users(ctx)
    _seed_settingskv_branding(ctx)
    _seed_categories(ctx)
    _seed_payment_methods(ctx)
    _seed_margin_tiers(ctx)
    _seed_stock_status_config(ctx)
    _seed_storage_types(ctx)
    _seed_storage_keywords(ctx)
    _seed_date_presets(ctx)
    _seed_message_templates(ctx)
    _seed_delivery_zones(ctx)
    _seed_compliance_info_single_row(ctx)
    _seed_suppliers(ctx)
    _seed_ingredients__variants__price_events(ctx)
    _seed_recipes__recipelines(ctx)
    _seed_products(ctx)
    _seed_tags(ctx)
    _seed_customers__addresses(ctx)
    _seed_production_plan_templates(ctx)
    _seed_production_completions_last_7_days_for_p(ctx)
    _seed_pedidos__lines(ctx)
    _seed_sales_90_days_of_realistic_data(ctx, days_of_history)
    _seed_waste_log(ctx)
    _seed_shopping_list_items_to_reorder(ctx)
    _seed_haccp__freezer_temperature_log_last_14_(ctx)
    _seed_market_benchmarks(ctx)
    _seed_recipe_pricing(ctx)
    _seed_market_price_references(ctx)
    _seed_competitor_observations(ctx)
    _seed_tag_links(ctx)
    _seed_historical_price_events(ctx)
    _seed_recipe_meta(ctx)
    _seed_product_meta(ctx)
    _seed_ingredient_meta(ctx)
    _seed_price_history(ctx)
    _seed_expenses(ctx)
    _seed_cash_sessions(ctx)
    _seed_sale_payments(ctx)
    _seed_monthly_closure(ctx)
    _seed_menus(ctx)
    _seed_production_plan(ctx)
    _seed_data_quality_fixes(ctx)
    _seed_audit_log_initial_entries(ctx)
    _seed_appmeta_pins_idempotency__onboarding_gu(ctx)
    _seed_bank_transactions_a_few_recent_ones(ctx)

    session.commit()
    return ctx.report


def _seed_tenants(ctx: SeedContext):
    """Section 1: Tenants.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    _sazon_tenant, was_created = _ensure_tenant(
        ctx.session, TENANT_SLUG, TENANT_NAME, TENANT_COLOR, TENANT_CURRENCY
    )
    if was_created:
        ctx.report.tenants += 1
    _default_tenant, _ = _ensure_tenant(
        ctx.session, DEFAULT_TENANT_SLUG, "Default", "#7b3f00", "Gs."
    )
    logger.info(f"seed: tenant '{TENANT_NAME}' (slug={TENANT_SLUG})")


def _seed_users(ctx: SeedContext):
    """Section 2: Users.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    _saskia_user, was_created = _ensure_user(
        ctx.session, SASKIA_USER, SASKIA_PASSWORD, role="admin"
    )
    if was_created:
        ctx.report.users += 1
    for username, password, _full_name, _email in CASHIER_USERS:
        _u, was_created = _ensure_user(ctx.session, username, password, role="cashier")
        if was_created:
            ctx.report.users += 1
    logger.info(f"seed: {ctx.report.users} users (Saskia + 2 cashiers)")


def _seed_settingskv_branding(ctx: SeedContext):
    """Section 3: SettingsKV (BRANDING).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

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
        existing = ctx.session.execute(
            select(SettingsKV).where(SettingsKV.key == k)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(SettingsKV(key=k, value_json=v, updated_at=datetime.now(ASUNCION_TZ)))
            ctx.report.settings_kv += 1
        else:
            ctx.report.skipped_existing["settings_kv_existing"] = (
                ctx.report.skipped_existing.get("settings_kv_existing", 0) + 1
            )
    logger.info(f"seed: {ctx.report.settings_kv} settings_kv (BRANDING + OPS)")


def _seed_categories(ctx: SeedContext):
    """Section 4: Categories.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for name, sort_order, is_active in CATEGORIES_PRODUCT:
        existing = ctx.session.execute(
            select(Category).where(Category.scope == "product", Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                Category(name=name, scope="product", sort_order=sort_order, is_active=is_active)
            )
            ctx.report.categories += 1
    for name, sort_order, is_active in CATEGORIES_RECIPE:
        existing = ctx.session.execute(
            select(Category).where(Category.scope == "recipe_family", Category.name == name)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                Category(
                    name=name, scope="recipe_family", sort_order=sort_order, is_active=is_active
                )
            )
            ctx.report.categories += 1
    logger.info(f"seed: {ctx.report.categories} categories")


def _seed_payment_methods(ctx: SeedContext):
    """Section 5: Payment methods.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, label, requires_ref, fee, sort_order, is_default, is_active, notes in PAYMENT_METHODS:
        existing = ctx.session.execute(
            select(PaymentMethod).where(PaymentMethod.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.payment_methods += 1
    logger.info(f"seed: {ctx.report.payment_methods} payment methods")


def _seed_margin_tiers(ctx: SeedContext):
    """Section 6: Margin tiers.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, label, min_cost, max_cost, sort_order, notes in MARGIN_TIERS:
        existing = ctx.session.execute(
            select(MarginTier).where(MarginTier.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.margin_tiers += 1
    logger.info(f"seed: {ctx.report.margin_tiers} margin tiers")


def _seed_stock_status_config(ctx: SeedContext):
    """Section 7: Stock status config.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, label, ratio, days, sort_order, notes in STOCK_STATUSES:
        existing = ctx.session.execute(
            select(StockStatusConfig).where(StockStatusConfig.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.stock_statuses += 1
    logger.info(f"seed: {ctx.report.stock_statuses} stock statuses")


def _seed_storage_types(ctx: SeedContext):
    """Section 8: Storage types.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, label, tmin, tmax, hum, sort_order, notes in STORAGE_TYPES:
        existing = ctx.session.execute(
            select(StorageType).where(StorageType.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.storage_types += 1
    logger.info(f"seed: {ctx.report.storage_types} storage types")


def _seed_storage_keywords(ctx: SeedContext):
    """Section 9: Storage keywords.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, keyword, sort_order in STORAGE_KEYWORDS:
        existing = ctx.session.execute(
            select(StorageKeyword).where(
                StorageKeyword.storage_code == code, StorageKeyword.keyword == keyword
            )
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                StorageKeyword(
                    storage_code=code,
                    keyword=keyword,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            ctx.report.storage_keywords += 1
    logger.info(f"seed: {ctx.report.storage_keywords} storage keywords")


def _seed_date_presets(ctx: SeedContext):
    """Section 10: Date presets.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, label, days, is_default, sort_order in DATE_PRESETS:
        existing = ctx.session.execute(
            select(DateRangePreset).where(DateRangePreset.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                DateRangePreset(
                    code=code,
                    label=label,
                    days=days,
                    is_default=is_default,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            ctx.report.date_presets += 1
    logger.info(f"seed: {ctx.report.date_presets} date presets")


def _seed_message_templates(ctx: SeedContext):
    """Section 11: Message templates.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for channel, key, subject, body, notes in MESSAGE_TEMPLATES:
        existing = ctx.session.execute(
            select(MessageTemplate).where(
                MessageTemplate.channel == channel,
                MessageTemplate.key == key,
                MessageTemplate.locale == "es-PY",
            )
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.message_templates += 1
    logger.info(f"seed: {ctx.report.message_templates} message templates")


def _seed_delivery_zones(ctx: SeedContext):
    """Section 12: Delivery zones.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for code, name, coverage, radius, cost, min_order, mins, notes in DELIVERY_ZONES:
        existing = ctx.session.execute(
            select(DeliveryZone).where(DeliveryZone.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
            ctx.report.delivery_zones += 1
    logger.info(f"seed: {ctx.report.delivery_zones} delivery zones")

    # === 13a. Channels ===
    for code, label, sort_order, is_default, notes in CHANNELS:
        existing = ctx.session.execute(
            select(Channel).where(Channel.code == code)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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


def _seed_compliance_info_single_row(ctx: SeedContext):
    """Section 13: Compliance info (single-row).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    existing_compliance = ctx.session.execute(
        select(ComplianceInfo).where(ComplianceInfo.id == 1)
    ).scalar_one_or_none()
    if existing_compliance is None:
        compliance_copy = dict(COMPLIANCE)
        compliance_copy["updated_at"] = datetime.now(ASUNCION_TZ)
        ci = ComplianceInfo(id=1, **compliance_copy)
        ctx.session.add(ci)
        ctx.report.compliance = 1
    logger.info("seed: compliance info (La Vaquita Holandesa S.A.)")


def _seed_suppliers(ctx: SeedContext):
    """Section 14: Suppliers.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    ctx.suppliers: list[Supplier] = []
    for name, contact, phone, email, address, ruc, notes in SUPPLIERS:
        existing = ctx.session.execute(
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
            ctx.session.add(s)
            ctx.session.flush()
            ctx.suppliers.append(s)
            ctx.report.suppliers += 1
        else:
            ctx.suppliers.append(existing)
    logger.info(f"seed: {ctx.report.suppliers} suppliers")


def _seed_ingredients__variants__price_events(ctx: SeedContext):
    """Section 15: Ingredients + variants + price events.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    ctx.ingredients_by_name: dict[str, Ingredient] = {}
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
        existing = ctx.session.execute(
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
                supplier_id=ctx.suppliers[supplier_idx].id
                if supplier_idx < len(ctx.suppliers)
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
            ctx.session.add(ing)
            ctx.session.flush()
            ctx.ingredients_by_name[name] = ing
            ctx.report.ingredients += 1

            # Variant (preferred)
            if package_size > 0:
                variant = IngredientVariant(
                    ingredient_id=ing.id,
                    package_size=package_size,
                    package_unit=package_unit,
                    purchase_price_gs=package_price_gs if package_price_gs > 0 else None,
                    stock_qty=stock_qty / package_size if package_size > 0 else 0,
                    supplier_id=ctx.suppliers[supplier_idx].id
                    if supplier_idx < len(ctx.suppliers)
                    else None,
                    preferred=True,
                    notes="Variante preferida (seed)",
                )
                ctx.session.add(variant)
                ctx.report.ingredient_variants += 1

            # Price history events (3 events over past 60 days)
            if price_gs > 0:
                for days_ago in [60, 30, 7]:
                    variation = ctx.rng.uniform(0.93, 1.07)
                    ctx.session.add(
                        IngredientPriceEvent(
                            ingredient_id=ing.id,
                            price_gs=int(price_gs * variation),
                            recorded_at=datetime.now(ASUNCION_TZ) - timedelta(days=days_ago),
                            source="restock",
                        )
                    )
                    ctx.report.ingredient_price_events += 1
        else:
            ctx.ingredients_by_name[name] = existing
            ctx.report.skipped_existing["ingredients_existing"] = (
                ctx.report.skipped_existing.get("ingredients_existing", 0) + 1
            )
    logger.info(
        f"seed: {ctx.report.ingredients} ingredients + {ctx.report.ingredient_variants} variants + {ctx.report.ingredient_price_events} price events"
    )


def _seed_recipes__recipelines(ctx: SeedContext):
    """Section 16: Recipes + RecipeLines.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    ctx.recipes_by_name: dict[str, Recipe] = {}
    for recipe_tuple in RECIPES:
        (
            name,
            yield_qty,
            yield_unit,
            prep,
            cook,
            diff,
            family,
            menu_tags,
            dietary,
            notes,
            image_url,
        ) = recipe_tuple
        existing = ctx.session.execute(
            select(Recipe).where(Recipe.name == name)
        ).scalar_one_or_none()
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
            ctx.session.add(r)
            ctx.session.flush()
            ctx.recipes_by_name[name] = r
            ctx.report.recipes += 1
        else:
            ctx.recipes_by_name[name] = existing
            ctx.report.skipped_existing["recipes_existing"] = (
                ctx.report.skipped_existing.get("recipes_existing", 0) + 1
            )

    # Recipe lines
    for recipe_name, ing_name, qty, line_unit, notes in RECIPE_LINES:
        recipe_id = ctx.recipes_by_name.get(recipe_name)
        ing_id = ctx.ingredients_by_name.get(ing_name)
        if not recipe_id or not ing_id:
            logger.warning(f"seed: missing ref for recipe_line {recipe_name}/{ing_name}, skipping")
            continue
        # Idempotent: same recipe + same ingredient + same line_unit + same qty
        existing = ctx.session.execute(
            select(RecipeLine).where(
                RecipeLine.recipe_id == recipe_id.id,
                RecipeLine.line_kind == "ingredient",
                RecipeLine.line_ref_id == ing_id.id,
                RecipeLine.line_unit == line_unit,
            )
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                RecipeLine(
                    recipe_id=recipe_id.id,
                    line_kind="ingredient",
                    line_ref_id=ing_id.id,
                    qty=qty,
                    line_unit=line_unit,
                    notes=notes,
                )
            )
            ctx.report.recipe_lines += 1
    logger.info(f"seed: {ctx.report.recipe_lines} recipe lines")


def _seed_products(ctx: SeedContext):
    """Section 17: Products.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    ctx.products_by_name: dict[str, Product] = {}
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
        existing = ctx.session.execute(
            select(Product).where(Product.name == name)
        ).scalar_one_or_none()
        if existing is None:
            recipe = ctx.recipes_by_name.get(recipe_name) if recipe_name else None
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
            ctx.session.add(p)
            ctx.session.flush()
            ctx.products_by_name[name] = p
            ctx.report.products += 1
        else:
            ctx.products_by_name[name] = existing
    logger.info(f"seed: {ctx.report.products} products")


def _seed_tags(ctx: SeedContext):
    """Section 18: Tags.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    # Make sure the starter tags are in place
    ensure_starter_tags(ctx.session)
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
        t = ensure_tag(ctx.session, tag_name, kind)
        if t.color == "#757575":  # default
            t.color = color
            ctx.session.flush()
        ctx.report.tags += 1
    # Apply tags to products
    popular = ensure_tag(ctx.session, "popular", TagKind.PRODUCT.value)
    premium = ensure_tag(ctx.session, "premium", TagKind.PRODUCT.value)
    docena = ensure_tag(ctx.session, "docena", TagKind.PRODUCT.value)
    individual = ensure_tag(ctx.session, "individual", TagKind.PRODUCT.value)
    for prod_name, _, _, _, _, _, _, _, is_fav, _, _, _ in PRODUCTS:
        prod = ctx.products_by_name.get(prod_name)
        if prod is None:
            continue
        if is_fav:
            tag_target(ctx.session, popular, TagKind.PRODUCT.value, prod.id)
            tag_target(ctx.session, premium, TagKind.PRODUCT.value, prod.id)
        if "12" in prod.portion_label or "docena" in prod.portion_label.lower():
            tag_target(ctx.session, docena, TagKind.PRODUCT.value, prod.id)
        elif "1 unidad" == prod.portion_label:
            tag_target(ctx.session, individual, TagKind.PRODUCT.value, prod.id)
    logger.info("seed: tags applied")


def _seed_customers__addresses(ctx: SeedContext):
    """Section 19: Customers + addresses.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    ctx.customers: list[Customer] = []
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
        existing = ctx.session.execute(
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
            ctx.session.add(c)
            ctx.session.flush()
            ctx.customers.append(c)
            ctx.report.customers += 1

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
                ctx.session.add(addr)
                ctx.report.customer_addresses += 1
        else:
            ctx.customers.append(existing)
    logger.info(
        f"seed: {ctx.report.customers} customers + {ctx.report.customer_addresses} addresses"
    )


def _seed_production_plan_templates(ctx: SeedContext):
    """Section 20: Production plan templates.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for weekday, prod_idx, qty, notes in PRODUCTION_TEMPLATES:
        if prod_idx >= len(PRODUCTS):
            continue
        prod_name = PRODUCTS[prod_idx][0]
        prod = ctx.products_by_name.get(prod_name)
        if not prod:
            continue
        existing = ctx.session.execute(
            select(ProductionPlanTemplate).where(
                ProductionPlanTemplate.weekday == weekday,
                ProductionPlanTemplate.product_id == prod.id,
            )
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                ProductionPlanTemplate(
                    weekday=weekday,
                    product_id=prod.id,
                    qty=qty,
                    notes=notes,
                    updated_at=datetime.now(ASUNCION_TZ),
                    updated_by=SASKIA_USER,
                )
            )
            ctx.report.production_templates += 1
    logger.info(f"seed: {ctx.report.production_templates} production templates")


def _seed_production_completions_last_7_days_for_p(ctx: SeedContext):
    """Section 21: Production completions (last 7 days for popular products).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    # Use ctx.anchor_date (defined at top of seed_sazon) so the anchor is
    # stable across re-runs of the same seed_sazon call. Without this,
    # the (product_id, for_date) natural-key dedup would miss on re-runs
    # and silently double the production completions.
    ctx.anchor_date = ctx.anchor_date
    for days_ago in range(7):
        d = ctx.anchor_date - timedelta(days=days_ago)
        for prod_name in [
            "Muffin de chocolate (20x20 cm)",
            "Cheesecake (30x50)",
            "Petisús de hojaldre y crema (Tompoezen)",
            "Babka",
            "Stroop wafel",
            "Tarta de manzana de mi madre (Mijn moeders appeltaart)",
            "Babka entera",
            "Cheesecake entera",
        ]:
            prod = ctx.products_by_name.get(prod_name)
            if not prod:
                continue
            existing = ctx.session.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == prod.id,
                    ProductionCompletion.for_date == d,
                )
            ).scalar_one_or_none()
            if existing is None:
                qty = ctx.rng.randint(8, 24)
                ctx.session.add(
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
                ctx.report.production_completions += 1
    logger.info(f"seed: {ctx.report.production_completions} production completions (last 7 days)")


def _seed_pedidos__lines(ctx: SeedContext):
    """Section 22: Pedidos + lines.

    Extracted from seed_sazon (refactored 2026-10-09).
    """
    channel_codes = [c[0] for c in CHANNELS]
    for ped_tuple in PEDIDOS:
        if not _process_single_pedido(ctx, ped_tuple, channel_codes):
            continue
    logger.info(f"seed: {ctx.report.pedidos} pedidos + {ctx.report.pedido_lines} pedido lines")


def _process_single_pedido(ctx: SeedContext, ped_tuple, channel_codes: list[str]) -> bool:
    """Process a single pedido tuple. Returns True if created.

    Extracted from _seed_pedidos__lines to reduce complexity.
    """
    cust_idx, days_ago, hour, minute, status, payment, channel_idx, notes, line_items = ped_tuple
    if cust_idx >= len(ctx.customers):
        return False
    cust = ctx.customers[cust_idx]
    promised_date = ctx.anchor_date + timedelta(days=days_ago)
    promised_dt = datetime.combine(promised_date, datetime.min.time()) + timedelta(
        hours=hour, minutes=minute
    )
    valid_lines = [(pn, q) for pn, q in line_items if q > 0 and pn in ctx.products_by_name]
    if not valid_lines:
        return False

    channel_code = _resolve_channel_code(channel_codes, channel_idx)

    existing = _find_existing_pedido(ctx, cust.id, promised_date, status)
    if existing is not None:
        return False

    ped = _create_pedido(
        ctx, cust, promised_date, promised_dt, hour, minute, channel_code, status, payment, notes
    )
    ctx.session.add(ped)
    ctx.session.flush()
    ctx.report.pedidos += 1

    _create_pedido_lines_and_events(ctx, ped, valid_lines, promised_dt, status, channel_code)
    return True


def _resolve_channel_code(channel_codes: list[str], channel_idx: int) -> str:
    """Resolve channel code from index, with fallback.

    Extracted from _seed_pedidos__lines to reduce complexity.
    """
    if channel_idx < len(channel_codes):
        return channel_codes[channel_idx]
    return ChannelEnum.MOSTRADOR.value  # P43: enum fallback


def _find_existing_pedido(ctx: SeedContext, customer_id: int, promised_date, status: str):
    """Find existing pedido matching (customer, date, status).

    Extracted from _seed_pedidos__lines to reduce complexity.
    """
    return ctx.session.execute(
        select(Pedido).where(
            Pedido.customer_id == customer_id,
            Pedido.promised_date == promised_date,
            Pedido.status == status,
        )
    ).scalar_one_or_none()


def _create_pedido(
    ctx: SeedContext,
    cust,
    promised_date,
    promised_dt,
    hour: int,
    minute: int,
    channel_code: str,
    status: str,
    payment: str,
    notes: str,
) -> Pedido:
    """Create a Pedido ORM row.

    Extracted from _seed_pedidos__lines to reduce complexity.
    """
    token = secrets.token_urlsafe(16)
    return Pedido(
        customer_id=cust.id,
        customer_name=cust.name,
        customer_phone=cust.phone,
        promised_date=promised_date,
        promised_time=f"{hour:02d}:{minute:02d}",
        channel=channel_code,
        status=status,
        payment_intent=payment,
        notes=notes,
        public_token=token,
        public_token_expires_at=datetime.now(ASUNCION_TZ) + timedelta(days=30),
        created_at=promised_dt - timedelta(hours=2),
        updated_at=promised_dt,
        fulfilled_at=promised_dt if status == "fulfilled" else None,
    )


def _create_pedido_lines_and_events(
    ctx: SeedContext,
    ped: Pedido,
    valid_lines: list,
    promised_dt,
    status: str,
    channel_code: str,
) -> None:
    """Create pedido lines and their associated events.

    Extracted from _seed_pedidos__lines to reduce complexity.
    """
    for prod_name, qty in valid_lines:
        prod = ctx.products_by_name[prod_name]
        _add_pedido_line(ctx, ped, prod, qty, status)
        _add_pedido_event_created(ctx, ped, promised_dt, channel_code)
        _add_status_change_events(ctx, ped, promised_dt, status)


def _add_pedido_line(ctx: SeedContext, ped: Pedido, prod, qty: float, status: str) -> None:
    """Add a PedidoLine and update report counter.

    Extracted from _create_pedido_lines_and_events to reduce complexity.
    """
    line = PedidoLine(
        pedido_id=ped.id,
        product_id=prod.id,
        qty=qty,
        unit_price_gs=prod.sale_price_gs,
        fulfilled_qty=qty if status == "fulfilled" else 0,
    )
    ctx.session.add(line)
    ctx.report.pedido_lines += 1


def _add_pedido_event_created(
    ctx: SeedContext, ped: Pedido, promised_dt, channel_code: str
) -> None:
    """Add a 'created' PedidoEvent.

    Extracted from _create_pedido_lines_and_events to reduce complexity.
    """
    ctx.session.add(
        PedidoEvent(
            pedido_id=ped.id,
            ts=promised_dt - timedelta(hours=2),
            actor=SASKIA_USER,
            event_type="created",
            payload_json={"channel": channel_code},
        )
    )


def _add_status_change_events(ctx: SeedContext, ped: Pedido, promised_dt, status: str) -> None:
    """Add status change events based on pedido status.

    Extracted from _create_pedido_lines_and_events to reduce complexity.
    """
    if status != "pending":
        _add_event(
            ctx,
            ped,
            promised_dt - timedelta(hours=1, minutes=30),
            "status_change",
            {"from": "pending", "to": "confirmed"},
        )
    if status in ("ready", "fulfilled"):
        _add_event(
            ctx,
            ped,
            promised_dt - timedelta(minutes=30),
            "status_change",
            {"from": "confirmed", "to": "ready"},
        )
    if status == "fulfilled":
        _add_event(ctx, ped, promised_dt, "status_change", {"from": "ready", "to": "fulfilled"})


def _add_event(ctx: SeedContext, ped: Pedido, ts, event_type: str, payload: dict) -> None:
    """Add a PedidoEvent with the given type and payload.

    Extracted from _add_status_change_events to reduce complexity.
    """
    ctx.session.add(
        PedidoEvent(
            pedido_id=ped.id,
            ts=ts,
            actor=SASKIA_USER,
            event_type=event_type,
            payload_json=payload,
        )
    )


def _seed_sales_90_days_of_realistic_data(ctx: SeedContext, days_of_history: int):
    """Section 23: Sales (90 days of realistic data).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    sale_rows: list[Sale] = []
    stock_move_rows: list[StockMovement] = []

    # IMPORTANT: use a SEPARATE random instance for the sales loop so
    # that re-runs (where the rest of the seeder is a no-op via
    # `existing is not None` short-circuits) hit the same ctx.rng state at
    # the start of the sales loop. The top-level `ctx.rng` advances a
    # different amount in run 1 vs run 2 because skip-vs-do is
    # asymmetric; a dedicated sales_rng with its own seed gives us
    # deterministic, idempotent sales data.
    sales_rng = random.Random(43)

    # ctx.anchor_date is defined at the top of seed_sazon (reused by
    # production completions, pedidos, bank transactions, and sales).
    # The sales loop computes day_start/day_end from sale_date which is
    # already anchored to ctx.anchor_date.

    BATCH_SIZE = 25
    for day_offset in range(days_of_history):
        # day 0 = oldest, day (days_of_history-1) = the ctx.anchor_date
        sale_date = datetime.combine(
            ctx.anchor_date - timedelta(days=days_of_history - 1 - day_offset),
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
            fav_products = [p for pn, p in ctx.products_by_name.items() if p.is_favorite]
            if not fav_products:
                fav_products = list(ctx.products_by_name.values())
            # 70% favorites, 30% random
            if sales_rng.random() < 0.7 and fav_products:
                product = sales_rng.choice(fav_products)
            else:
                product = sales_rng.choice(list(ctx.products_by_name.values()))

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
            if sales_rng.random() < 0.7 and ctx.customers:
                cust = sales_rng.choice(ctx.customers)

            # Payment method is one more ctx.rng.choices — we advance it here
            # *before* the dedup check so that re-runs that hit the dedup
            # short-circuit still consume the same amount of ctx.rng as run 1.
            # Without this, the ctx.rng state at the end of a dedup'd
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
            # Idempotency strategy: the seeder is anchored to ctx.anchor_date
            # (the date this run started) so re-runs on the same day hit
            # identical calendar dates. Then for each (day, product, qty,
            # customer) tuple we check if a sale already exists; if so, we
            # skip. This keeps the count and totals stable across re-runs
            # of the same day. (Re-runs on a different day won't dedup —
            # they create fresh sales anchored to the new day, which is
            # the desired behavior for a "ctx.anchor_date's data" demo.)
            day_start = sale_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            stable_customer_id = cust.id if cust else None
            existing_sale = (
                ctx.session.execute(
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
                # The ctx.rng was already advanced above so the next iteration
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
            ctx.session.add(sale)
            ctx.session.flush()
            sale_rows.append(sale)
            ctx.report.sales += 1

            # Stock movements for sales that have a recipe
            if product.recipe_id:
                recipe = ctx.recipes_by_name.get(product.name, None)  # by name? no — by id
                # need to query by id
                recipe = ctx.session.get(Recipe, product.recipe_id)
                if recipe is not None:
                    yield_qty = recipe.yield_qty or 1.0
                    yield_qty_d = Decimal(str(yield_qty))
                    qty_d = Decimal(str(qty))
                    # Get recipe lines
                    recipe_lines = (
                        ctx.session.execute(
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
                        ctx.session.add(sm)
                        stock_move_rows.append(sm)
                        # Update stock
                        ing = ctx.session.get(Ingredient, line.line_ref_id)
                        if ing is not None:
                            ing.stock_qty = max(0.0, float(ing.stock_qty) - float(need))
                            ing.last_consumed_at = sold_at

        if (day_offset + 1) % BATCH_SIZE == 0:
            ctx.session.commit()
            logger.info(f"seeded days {day_offset + 1}/{days_of_history}")
    ctx.report.sales = len(sale_rows)
    ctx.report.stock_movements = len(stock_move_rows)

    # === 23b. Special sales (voided + encargo) — also idempotent ===
    # These are hand-crafted and don't go through the ctx.rng-driven loop.
    # Dedup by (sold_at, product_id, qty, customer_id, notes) so re-runs
    # don't inflate the count.
    first_product = next(iter(ctx.products_by_name.values()))
    voided_dedup = (
        ctx.session.execute(
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
            # Anchor to ctx.anchor_date so dedup by (product_id, qty, notes,
            # voided_at IS NOT NULL) is stable across re-runs.
            sold_at=datetime.combine(ctx.anchor_date - timedelta(days=2), datetime.min.time())
            + timedelta(hours=20),
            product_id=first_product.id,
            qty=2,
            unit_price_gs=first_product.sale_price_gs,
            notes="Cliente cambió de opinión",
            voided_at=datetime.combine(ctx.anchor_date - timedelta(days=2), datetime.min.time())
            + timedelta(hours=21),
            void_reason="Cliente cambió de opinión",
            voided_by=SASKIA_USER,
            payment_method="efectivo",
        )
        ctx.session.add(voided)
        ctx.session.flush()
        ctx.report.sales += 1

    # One encargo (custom order) sale
    encargo_product = list(ctx.products_by_name.values())[5]
    encargo_dedup = (
        ctx.session.execute(
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
            # Anchor to ctx.anchor_date for dedup stability.
            sold_at=datetime.combine(ctx.anchor_date - timedelta(days=1), datetime.min.time())
            + timedelta(hours=22),
            product_id=encargo_product.id,
            qty=1,
            unit_price_gs=encargo_product.sale_price_gs,
            notes="Encargo: recoger 16h",
            payment_method="transferencia",
        )
        ctx.session.add(encargo)
        ctx.session.flush()
        ctx.report.sales += 1

    # Initial stock movement (audit trail for opening balance)
    for ing in ctx.ingredients_by_name.values():
        # Idempotency: one initial StockMovement per ingredient (1:1 audit trail).
        existing_initial = (
            ctx.session.execute(
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
            recorded_at=datetime.combine(ctx.anchor_date - timedelta(days=90), datetime.min.time()),
            created_by=SASKIA_USER,
        )
        ctx.session.add(sm)
        ctx.report.stock_movements += 1

    logger.info(f"seed: {ctx.report.sales} sales + {ctx.report.stock_movements} stock movements")


def _seed_waste_log(ctx: SeedContext):
    """Section 24: Waste log.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for ing_name, qty, reason, days_ago, by, notes in WASTE_LOG:
        ing = ctx.ingredients_by_name.get(ing_name)
        if not ing:
            continue
        existing = ctx.session.execute(
            select(WasteLog).where(
                WasteLog.ingredient_id == ing.id,
                WasteLog.qty == qty,
                WasteLog.reason == reason,
            )
        ).scalar_one_or_none()
        if existing is None:
            cost_gs = int(qty * (ing.purchase_price_gs or 0))
            ctx.session.add(
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
            ctx.report.waste_log += 1
    logger.info(f"seed: {ctx.report.waste_log} waste log entries")


def _seed_shopping_list_items_to_reorder(ctx: SeedContext):
    """Section 25: Shopping list (items to reorder).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    # Use Spanish ingredient names (the canonical names in the INGREDIENTS list).
    for ing_name in ["Harina de trigo", "Manteca", "Huevos", "Leche", "Azúcar"]:
        ing = ctx.ingredients_by_name.get(ing_name)
        if not ing:
            continue
        existing = ctx.session.execute(
            select(ShoppingListItem).where(
                ShoppingListItem.ingredient_id == ing.id, not ShoppingListItem.purchased
            )
        ).scalar_one_or_none()
        if existing is None:
            qty_to_buy = (ing.min_stock_qty or 1.0) * 2
            ctx.session.add(
                ShoppingListItem(
                    ingredient_id=ing.id,
                    qty_to_buy=qty_to_buy,
                    unit=ing.unit,
                    purpose_text="Stock bajo — comprar antes del lunes",
                    purchased=False,
                )
            )
            ctx.report.shopping_list += 1
    logger.info(f"seed: {ctx.report.shopping_list} shopping list items")


def _seed_haccp__freezer_temperature_log_last_14_(ctx: SeedContext):
    """Section 26: HACCP — freezer temperature log (last 14 days, 2 readings/day).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    # Use ctx.anchor_date as the anchor so re-runs produce identical
    # timestamps and the (recorded_at) natural-key dedup actually works.
    for days_ago in range(FREEZER_TEMP_DAYS):
        for hour in (8, 20):  # morning + evening
            base_dt = datetime.combine(
                ctx.anchor_date - timedelta(days=days_ago),
                datetime.min.time(),
            )
            ts = base_dt + timedelta(hours=hour)
            # Mostly in range, occasional spike for realism
            if ctx.rng.random() < 0.92:
                temp = ctx.rng.uniform(HACCP_TEMP_MIN_C, HACCP_TEMP_MAX_C)
            else:
                temp = ctx.rng.choice(
                    [
                        ctx.rng.uniform(-25, -22),  # too cold
                        ctx.rng.uniform(-15, -10),  # too warm
                    ]
                )
            existing = ctx.session.execute(
                select(FreezerTemperatureLog).where(FreezerTemperatureLog.recorded_at == ts)
            ).scalar_one_or_none()
            if existing is None:
                in_range = HACCP_TEMP_MIN_C <= temp <= HACCP_TEMP_MAX_C
                ctx.session.add(
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
                ctx.report.haccp_temps += 1
    logger.info(f"seed: {ctx.report.haccp_temps} HACCP freezer temp readings")


def _seed_market_benchmarks(ctx: SeedContext):
    """Section 27: Market benchmarks.

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    for label, wholesale, retail, avg, min_price in BENCHMARKS:
        existing = ctx.session.execute(
            select(MarketBenchmark).where(MarketBenchmark.product_label == label)
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                MarketBenchmark(
                    product_label=label,
                    our_wholesale_gs=wholesale,
                    our_retail_gs=retail,
                    market_avg_gs=avg,
                    comp_min_gs=min_price,
                )
            )
            ctx.report.market_benchmarks += 1
    logger.info(f"seed: {ctx.report.market_benchmarks} market benchmarks")


# === Section 28: Recipe pricing (computed costs + retail price) ===
def _seed_recipe_pricing(ctx: SeedContext):
    """Compute per-recipe cost + 5 channel-tier prices (HEREBUS Pricing_Por_Producto).

    Channel margins (matches MAESTRA):
      - wholesale: +40%
      - private_label: +25%
      - distributor: +22%
      - retail: +50%
      - broker_commission: +5% (informational, layered on top of retail)

    cost_per_unit_gs is the cost of ONE unit at the recipe's yield_qty.
    labor_gs is 5% of cost (placeholder; operator adjusts).
    packaging_gs is 3% of cost.
    Idempotent: skip if RecipePricing row already exists.
    """
    for recipe in ctx.session.execute(select(Recipe)).scalars():
        existing = ctx.session.execute(
            select(RecipePricing).where(RecipePricing.recipe_id == recipe.id)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        cost_total = 0
        for line in ctx.session.execute(
            select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)
        ).scalars():
            if line.line_kind != "ingredient":
                continue
            ing = ctx.session.get(Ingredient, line.line_ref_id)
            if ing is None or ing.purchase_price_gs is None:
                continue
            cost_total += int(float(line.qty or 0) * ing.purchase_price_gs)
        yield_qty = float(recipe.yield_qty or 1.0)
        cost_per_unit = int(cost_total / yield_qty) if yield_qty > 0 else cost_total
        labor_gs = int(cost_total * 0.05)
        packaging_gs = int(cost_total * 0.03)
        ctx.session.add(
            RecipePricing(
                recipe_id=recipe.id,
                cost_total_gs=cost_total,
                labor_gs=labor_gs,
                packaging_gs=packaging_gs,
                cost_per_unit_gs=cost_per_unit,
                wholesale_gs=int(cost_total * 1.40),
                private_label_gs=int(cost_total * 1.25),
                distributor_gs=int(cost_total * 1.22),
                retail_gs=int(cost_total * 1.50),
                broker_commission_gs=int(cost_total * 0.05),
                notes="Seed: 5-channel pricing derived from ingredient cost (oct 2026).",
            )
        )
        ctx.report.recipe_pricing += 1
    logger.info(f"seed: {ctx.report.recipe_pricing} recipe pricing rows")


# === Section 29: Market price references (per ingredient, PY Asunción) ===
def _seed_market_price_references(ctx: SeedContext):
    """Insert MARKET_PRICE_REFERENCES as one MarketPriceReference row per ingredient.

    Idempotent: skip if an existing row for (ingredient_id, unit).
    """
    today = ctx.anchor_date
    for ing_name, unit, price_gs, source, notes in MARKET_PRICE_REFERENCES:
        ing = ctx.ingredients_by_name.get(ing_name)
        if ing is None:
            continue
        existing = ctx.session.execute(
            select(MarketPriceReference).where(
                MarketPriceReference.ingredient_id == ing.id,
                MarketPriceReference.unit == unit,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        ctx.session.add(
            MarketPriceReference(
                ingredient_id=ing.id,
                unit=unit,
                price_gs=price_gs,
                source=source,
                notes=notes,
                as_of=today,
            )
        )
        ctx.report.market_price_references += 1
    logger.info(f"seed: {ctx.report.market_price_references} market price references")


# === Section 30: Competitor price observations (Asunción retail, evidence) ===
def _seed_competitor_observations(ctx: SeedContext):
    """Insert COMPETITOR_OBSERVATIONS as CompetitorPriceObservation rows.

    Append-only by design (correcting = new row with new date). Re-running is
    a no-op when an identical (competitor, product_name, as_of, price) tuple exists.
    """
    today = ctx.anchor_date
    for (
        competitor,
        ctype,
        city,
        prod_name,
        family,
        unit,
        price,
        days_ago,
        source,
    ) in COMPETITOR_OBSERVATIONS:
        as_of = today - timedelta(days=days_ago)
        existing = ctx.session.execute(
            select(CompetitorPriceObservation).where(
                CompetitorPriceObservation.competitor_name == competitor,
                CompetitorPriceObservation.product_name == prod_name,
                CompetitorPriceObservation.as_of == as_of,
                CompetitorPriceObservation.price_gs == price,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        ctx.session.add(
            CompetitorPriceObservation(
                competitor_name=competitor,
                competitor_type=ctype,
                city=city,
                product_name=prod_name,
                family=family,
                unit=unit,
                price_gs=price,
                as_of=as_of,
                source=source,
            )
        )
        ctx.report.competitor_observations += 1
    logger.info(f"seed: {ctx.report.competitor_observations} competitor observations")


# === Section 31: Tag-link auto-application rules ===
def _seed_tag_links(ctx: SeedContext):
    """Apply TAG_LINK_RULES to attach tags to ingredients/products/recipes.

    Idempotent: re-running inserts 0 duplicates (tag_target checks existing first).
    """
    from app.rms.tagging.ensure import ensure_tag, tag_target

    tag_cache: dict[tuple[str, str], object] = {}

    def get_tag(name: str, kind: str):
        k = (name, kind)
        if k not in tag_cache:
            tag_cache[k] = ensure_tag(ctx.session, name, kind)
        return tag_cache[k]

    # Pre-compute recipe cost (matches _seed_recipe_pricing)
    recipe_cost_by_id: dict[int, int] = {}
    for recipe in ctx.session.execute(select(Recipe)).scalars():
        c = 0
        for line in ctx.session.execute(
            select(RecipeLine).where(RecipeLine.recipe_id == recipe.id)
        ).scalars():
            if line.line_kind != "ingredient":
                continue
            ing = ctx.session.get(Ingredient, line.line_ref_id)
            if ing is None or ing.purchase_price_gs is None:
                continue
            c += int(float(line.qty or 0) * ing.purchase_price_gs)
        recipe_cost_by_id[recipe.id] = c

    applied = 0
    for tag_name, kind, predicate_kind, predicate_value in TAG_LINK_RULES:
        tag = get_tag(tag_name, kind)
        if predicate_kind == "category":
            for ing in ctx.session.execute(
                select(Ingredient).where(Ingredient.category == predicate_value)
            ).scalars():
                if tag_target(ctx.session, tag, kind, ing.id):
                    applied += 1
        elif predicate_kind == "storage":
            for ing in ctx.session.execute(
                select(Ingredient).where(Ingredient.storage == predicate_value)
            ).scalars():
                if tag_target(ctx.session, tag, kind, ing.id):
                    applied += 1
        elif predicate_kind == "name_contains":
            needle = predicate_value.lower()
            if kind == "ingredient":
                for ing in ctx.session.execute(select(Ingredient)).scalars():
                    if needle in (ing.name or "").lower():
                        if tag_target(ctx.session, tag, kind, ing.id):
                            applied += 1
            elif kind == "product":
                for prod in ctx.session.execute(select(Product)).scalars():
                    if needle in (prod.name or "").lower():
                        if tag_target(ctx.session, tag, kind, prod.id):
                            applied += 1
            elif kind == "recipe":
                for rec in ctx.session.execute(select(Recipe)).scalars():
                    if needle in (rec.name or "").lower():
                        if tag_target(ctx.session, tag, kind, rec.id):
                            applied += 1
        elif predicate_kind == "cost_above":
            threshold = int(predicate_value)
            for rid, cost in recipe_cost_by_id.items():
                if cost >= threshold:
                    if tag_target(ctx.session, tag, kind, rid):
                        applied += 1
    ctx.report.tag_links = applied
    logger.info(f"seed: {ctx.report.tag_links} tag links applied")


# === Section 32: Historical price events (12-month history for all ingredients) ===
def _seed_historical_price_events(ctx: SeedContext):
    """Backfill IngredientPriceEvent with 12 monthly snapshots per ingredient.

    The existing 60/30/7-day events from _seed_ingredients__variants__price_events
    stay untouched. Idempotent: if any event is older than 90 days, assume the
    backfill was already run and skip.
    """
    already = ctx.session.execute(
        select(IngredientPriceEvent.id)
        .where(IngredientPriceEvent.recorded_at < datetime.now(ASUNCION_TZ) - timedelta(days=90))
        .limit(1)
    ).first()
    if already is not None:
        return

    for ing in ctx.session.execute(select(Ingredient)).scalars():
        if ing.purchase_price_gs is None or ing.purchase_price_gs <= 0:
            continue
        base = ing.purchase_price_gs
        for month in range(11, -1, -1):
            # Slight upward drift over the year (6% drift), with monthly noise
            drift = 1.0 - (0.005 * month)
            noise = ctx.rng.uniform(0.94, 1.06)
            sample_price = int(base * drift * noise)
            recorded_at = datetime.now(ASUNCION_TZ) - timedelta(
                days=month * 30 + ctx.rng.randint(0, 5)
            )
            ctx.session.add(
                IngredientPriceEvent(
                    ingredient_id=ing.id,
                    price_gs=sample_price,
                    recorded_at=recorded_at,
                    source="restock",
                )
            )
            ctx.report.historical_price_events += 1
    logger.info(f"seed: {ctx.report.historical_price_events} historical price events")


"""
Big batch of new seeders for Saskia: Tier A (UX gaps), Tier B (design-empty tables),
Tier C (data-quality fixes). All appended to sazon.py before _seed_audit_log_initial_entries.

Column names match the SQLAlchemy models exactly (verified via inspect).
"""
# === Section 29: Recipe instructions + family + allergens + dietary_tags + menu_tags ===
# Tuple: (recipe_name_slug, family, allergens_csv, dietary_csv, menu_tags_csv, instructions)
RECIPE_INSTRUCTIONS: list[tuple[str, str, str, str, str, str]] = [
    (
        "babka__rec_017",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "destacado,premium",
        (
            "1. Mezclar harina, sal, azúcar y levadura seca en bowl grande.\n"
            "2. Calentar leche a 37°C, añadir huevo batido y manteca derretida tibia.\n"
            "3. Amasar 10 min hasta obtener masa lisa y elástica. Reposar 1h hasta doblar volumen.\n"
            "4. Estirar en rectángulo 40x30 cm. Untar con relleno de chocolate (cacao + azúcar glas + agua caliente).\n"
            "5. Enrollar apretado, cortar a lo largo en 2 tiras, trenzar y colocar en molde enmantecado.\n"
            "6. Dejar levar 45 min. Hornear a 175°C por 35-40 min hasta dorado profundo.\n"
            "7. Enfriar 20 min en molde, desmoldar y glasear con azúcar glas + agua."
        ),
    ),
    (
        "bizcocho_basico_25_cm_basiscake__rec_011",
        "Bizcocho",
        "gluten,huevo,lactosa",
        "",
        "base,clasico",
        (
            "1. Precalentar horno a 180°C. Enmantecar y enharinar molde 25 cm.\n"
            "2. Batir manteca pomada con azúcar hasta punto crema (5 min).\n"
            "3. Añadir huevos uno a uno batiendo bien. Incorporar vainilla.\n"
            "4. Tamizar harina con polvo de hornear; añadir a la mezcla en 3 veces con movimientos envolventes.\n"
            "5. Verter en molde, hornear 35-40 min. Insertar palillo: debe salir limpio.\n"
            "6. Enfriar 10 min en molde, desmoldar sobre rejilla, enfriar completamente antes de rellenar."
        ),
    ),
    (
        "bizcocho_basico_30_cm_basiscake__rec_012",
        "Bizcocho",
        "gluten,huevo,lactosa",
        "",
        "base,para-eventos",
        (
            "1. Precalentar horno a 175°C. Enmantecar y enharinar molde 30 cm.\n"
            "2. Batir manteca con azúcar hasta punto crema (5-6 min).\n"
            "3. Añadir huevos uno a uno, batiendo. Incorporar vainilla.\n"
            "4. Cernir harina con polvo de hornear; incorporar en 3 veces con espátula.\n"
            "5. Hornear 45-55 min. Probar con palillo.\n"
            "6. Enfriar 15 min, desmoldar, enfriar totalmente en rejilla."
        ),
    ),
    (
        "bombones_de_chocolate__rec_018",
        "Coberturas",
        "lactosa",
        "sin_gluten",
        "premium,regalo",
        (
            "1. En baño maría, derretir manteca. Retirar del fuego.\n"
            "2. Mezclar leche condensada con cacao en polvo hasta homogeneizar.\n"
            "3. Incorporar manteca derretida y pizca de sal. Batir 5 min hasta punto brilloso.\n"
            "4. Verter en moldes de silicona (cavidades de 25g). Refrigerar 4h.\n"
            "5. Desmoldar y conservar en heladera. Rinde 20 unidades de 25g."
        ),
    ),
    (
        "torta_de_zanahoria_43x33x1_5_cm__rec_005",
        "Tortas",
        "gluten,huevo,frutos_secos",
        "",
        "clasico,favorita",
        (
            "1. Precalentar horno a 175°C. Enmantecar molde rectangular 43x33 cm.\n"
            "2. Cernir harina, bicarbonato, canela, jengibre, nuez moscada y sal.\n"
            "3. Batir huevos con azúcares hasta triplicar volumen. Añadir aceite y vainilla.\n"
            "4. Incorporar secos en 3 veces con movimientos envolventes.\n"
            "5. Añadir zanahoria rallada fina, pasas remojadas y nueces picadas.\n"
            "6. Hornear 50-60 min. Insertar palillo al centro: debe salir limpio.\n"
            "7. Cubrir con frosting de queso crema si se desea. Rinde 24 porciones."
        ),
    ),
    (
        "cheesecake_30x50__rec_002",
        "Tortas",
        "gluten,huevo,lactosa",
        "",
        "premium,para-eventos",
        (
            "1. Precalentar horno a 160°C (baño maría). Enmantecar molde 30x50 cm.\n"
            "2. Base: mezclar galletas molidas con manteca derretida. Prensar en base del molde.\n"
            "3. Batir queso crema hasta cremoso. Añadir azúcar, luego huevos uno a uno.\n"
            "4. Incorporar crema de leche, harina, vainilla y jugo de limón.\n"
            "5. Verter sobre la base. Hornear a baño maría 70-80 min hasta que el centro tiemble.\n"
            "6. Apagar horno, dejar 30 min dentro con puerta entreabierta.\n"
            "7. Refrigerar 8h mínimo antes de cortar. Rinde 170 porciones individuales."
        ),
    ),
    (
        "muffin_de_chocolate_20x20_cm__rec_001",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "clasico,infantil",
        (
            "1. Precalentar horno a 180°C. Preparar molde 20x20 cm enmantequillado.\n"
            "2. Cernir harina, cacao, polvo de hornear, bicarbonato, café y sal.\n"
            "3. Batir azúcar morena con leche, aceite, crema agria, vainilla y huevos.\n"
            "4. Unir secos y húmedos sin sobrebatir. Agregar chispas de chocolate.\n"
            "5. Verter en molde. Hornear 45-55 min hasta palillo limpio.\n"
            "6. Enfriar 15 min. Cortar 12 cuadrados. Decorar con azúcar glas."
        ),
    ),
    (
        "frikandel_100_unidades__rec_022",
        "Salados",
        "gluten,huevo",
        "sin_lactosa",
        "salado,para-eventos",
        (
            "1. Picar finamente pechuga, carnaza, cebolla morada y ajo. Pasar por molienda gruesa.\n"
            "2. Mezclar con huevo, pan rallado remojado en leche en polvo disuelta, sal y especias.\n"
            "3. Amasar 5 min hasta textura homogénea y firme.\n"
            "4. Formar cilindros de 12 cm x 2 cm (rinde 100 unidades).\n"
            "5. Refrigerar 2h para que asienten. Rebozar con pan rallado si se desea.\n"
            "6. Freír en aceite 170°C por 4-5 min hasta dorar.\n"
            "7. Servir con mostaza o ketjap. Apto freezer 2 meses."
        ),
    ),
    (
        "galletas_de_especuloos_speculaasjes__rec_010",
        "Galletería",
        "gluten,lactosa",
        "",
        "tradicional,holandes",
        (
            "1. Batir manteca pomada con azúcar morena hasta cremoso (3 min).\n"
            "2. Añadir suero de leche (buttermilk). Mezclar.\n"
            "3. Incorporar harina cernida con especias para speculaas y bicarbonato.\n"
            "4. Amasar brevemente, formar disco, envolver en film. Refrigerar 4h.\n"
            "5. Estirar a 4 mm. Cortar formas tradicionales. Colocar en placa enmantecada.\n"
            "6. Hornear a 170°C por 12-15 min hasta dorar firme.\n"
            "7. Enfriar sobre rejilla. Conservan 4 semanas en lata hermética."
        ),
    ),
    (
        "goulash_crockettes__rec_019",
        "Salados",
        "gluten,huevo,lactosa",
        "",
        "salado,festivo",
        (
            "1. Cortar falda de res en cubos de 3 cm. Salpimentar.\n"
            "2. Sofreír cebolla, morrón, zanahoria, apio y ajo en aceite hasta transparente.\n"
            "3. Añadir carne, dorar por todos lados. Sumar pimentón ahumado y cayena.\n"
            "4. Verter puré de tomate, caldo y ketjap. Tapar y cocinar a fuego bajo 2h 30min.\n"
            "5. Incorporar gelatina disuelta en agua fría para espesar la salsa.\n"
            "6. Enfriar completamente (idealmente toda la noche).\n"
            "7. Formar croquetas cilíndricas de 4x8 cm, pasar por harina, huevo batido y pan rallado.\n"
            "8. Freír a 175°C por 5 min hasta dorar y calentar interior. Rinde 100 unidades."
        ),
    ),
    (
        "hojaldre_bladerdeeg__rec_008",
        "Masas",
        "gluten,lactosa",
        "",
        "base,tradicional",
        (
            "1. Mezclar harina con sal. Añadir agua helada y mezclar hasta formar masa.\n"
            "2. Amasar 2 min, envolver en film, refrigerar 30 min.\n"
            "3. Estirar masa en rectángulo. Colocar placa de manteca fría en el centro.\n"
            "4. Doblar extremos sobre la manteca. Sellar bordes. Estirar y doblar en 3 (vuelta simple).\n"
            "5. Refrigerar 30 min. Repetir vuelta 5 veces más (total 6 vueltas).\n"
            "6. Refrigerar 1h antes de usar. Rinde 8 planchas de 25 cm.\n"
            "7. Hornear a 200°C hasta dorado y hojaldrado (15-20 min según uso)."
        ),
    ),
    (
        "ketjap_manis_version_rapida__rec_007",
        "Salsas",
        "soja",
        "sin_gluten,sin_lactosa,vegano",
        "base,asiatico",
        (
            "1. Mezclar salsa de soja con azúcar morena en olla a fuego medio.\n"
            "2. Añadir ajo rallado, jengibre y anís estrellado.\n"
            "3. Cocinar 20 min a fuego bajo revolviendo hasta reducir a consistencia de miel.\n"
            "4. Retirar anís estrellado. Enfriar.\n"
            "5. Conservar en frasco de vidrio refrigerado. Rinde 250 ml. Duran 2 meses."
        ),
    ),
    (
        "oliebollen_bunuelos_tradicionales_holandeses__rec_016",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "festivo,temporada,holandes",
        (
            "1. Activar levadura en leche tibia con 1 cda de azúcar. Esperar 10 min (burbujas).\n"
            "2. Mezclar harina, azúcar, sal y ralladura de limón. Añadir la leche con levadura.\n"
            "3. Amasar hasta masa homogénea. Cubrir y dejar levar 1h hasta burbujear.\n"
            "4. Calentar aceite a 180°C. Tomar porciones con cuchara mojada.\n"
            "5. Freír 4-5 buñuelos por tanda, girando hasta dorar parejo (3-4 min).\n"
            "6. Escurrir sobre papel absorbente. Espolvorear azúcar glas.\n"
            "7. Servir calientes. Rinde 24 unidades. Consumir el día."
        ),
    ),
    (
        "ontbijtkoek_700g_de_harina__rec_004",
        "Bizcocho",
        "gluten,huevo",
        "sin_lactosa",
        "tradicional,holandes,desayuno",
        (
            "1. Precalentar horno a 160°C. Enmantecar molde rectangular 24x10 cm.\n"
            "2. Mezclar harina de centeno con especias para speculaas, bicarbonato y polvo de hornear.\n"
            "3. En olla calentar melaza, miel, vinagre y un poco de agua hasta disolver.\n"
            "4. Incorporar líquidos a los secos. Amasar hasta consistencia de barro espeso.\n"
            "5. Verter en molde. Hornear 60-75 min hasta que al insertar palillo salga casi limpio.\n"
            "6. Enfriar 15 min en molde, desmoldar. Untar con manteca si se desea. Rinde 12 rodajas."
        ),
    ),
    (
        "pastelitos_rosados_roze_koeken__rec_009",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "tradicional,holandes,festivo",
        (
            "1. Precalentar horno a 180°C. Preparar moldes individuales enmantecados.\n"
            "2. Batir manteca con azúcar hasta cremoso. Añadir huevos y vainilla.\n"
            "3. Cernir harina, maicena y polvo de hornear. Incorporar a la mezcla.\n"
            "4. Distribuir en moldes. Hornear 20-25 min hasta dorar.\n"
            "5. Preparar glaseado: batir frambuesas con azúcar glas hasta rosa intenso.\n"
            "6. Cubrir pastelitos fríos con glaseado. Refrigerar 30 min para fijar.\n"
            "7. Rinde 12 pastelitos. Conservan 3 días refrigerados."
        ),
    ),
    (
        "petisus_de_hojaldre_y_crema_tompoezen__rec_015",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "tradicional,holandes,premium",
        (
            "1. Estirar hojaldre a 5 mm. Cortar círculos de 6 cm. Pinchar con tenedor.\n"
            "2. Hornear a 200°C por 12-15 min hasta dorar y subir. Aplastar el centro.\n"
            "3. Batir crema pastelera con estabilizante y crema de leche hasta punto firme.\n"
            "4. Rellenar la base inferior con crema usando manga.\n"
            "5. Espolvorear la tapa con azúcar glas antes de colocar.\n"
            "6. Rinde 12 unidades. Servir el día."
        ),
    ),
    (
        "proficteroles_de_den_bosch_bossche_bollen__rec_014",
        "Bollería",
        "gluten,huevo,lactosa",
        "",
        "tradicional,holandes,premium",
        (
            "1. Hornear masa choux en bolitas de 4 cm hasta que estén secas y doradas (25 min).\n"
            "2. Preparar salsa de chocolate: hervir crema, verter sobre chocolate y cacao, emulsionar.\n"
            "3. Rellenar profiteroles con crema chantilly firme.\n"
            "4. Sumergir cada uno en salsa de chocolate. Colocar sobre rejilla.\n"
            "5. Refrigerar 30 min. Rinde 12 unidades grandes (Bossche bollen)."
        ),
    ),
    (
        "stroop_wafel__rec_003",
        "Galletería",
        "gluten,huevo,lactosa",
        "",
        "tradicional,holandes,clasico",
        (
            "1. Cernir harina, sal, polvo de hornear. Reservar.\n"
            "2. Batir manteca pomada con azúcar hasta cremoso. Añadir huevo, vainilla, canela.\n"
            "3. Alternar harina y leche/crema empezando y terminando con harina.\n"
            "4. Añadir levadura al final. Refrigerar masa 4h.\n"
            "5. Preparar relleno stroop: caramelizar azúcar con agua hasta punto hebra, añadir canela.\n"
            "6. Estirar masa a 3 mm. Cortar círculos. Colocar 1 cda de stroop en la mitad, tapar con otro círculo.\n"
            "7. Sellar con molde de stroopwafel. Hornear a 200°C por 12-15 min.\n"
            "8. Rinde 12 unidades. Conservan 2 semanas en lata."
        ),
    ),
    (
        "suppli_cacio_e_pepe__rec_021",
        "Salados",
        "gluten,huevo,lactosa",
        "",
        "salado,italiano,para-eventos",
        (
            "1. Hervir arroz en caldo sazonado hasta muy hecho (más que risotto). Enfriar.\n"
            "2. Mezclar con huevo batido, queso rallado y abundante pimienta negra recién molida.\n"
            "3. Formar croquetas ovaladas de 8 cm.\n"
            "4. Pasar por harina, huevo batido y pan rallado.\n"
            "5. Freír a 175°C por 4 min hasta dorar y calentar el interior.\n"
            "6. Servir inmediatamente. Rinde 12 unidades."
        ),
    ),
    (
        "tarta_de_manzana_de_mi_madre_mijn_moeders_appeltaart__rec_013",
        "Tortas",
        "gluten,huevo,lactosa",
        "sin_frutos_secos",
        "tradicional,holandes,clasico",
        (
            "1. Precalentar horno a 180°C. Enmantecar molde de tarta 24 cm.\n"
            "2. Mezclar harina, polvo de hornear, sal. Añadir manteca fría en cubos y trabajar a mano hasta arenilla.\n"
            "3. Incorporar azúcar, vainilla, huevo. Amasar brevemente. Refrigerar 1h.\n"
            "4. Estirar 2/3 de la masa, forrar base y bordes. Reservar resto para tiras.\n"
            "5. Mezclar láminas de manzana con azúcar, polvo de natillas, canela, pasas.\n"
            "6. Disponer en base. Cubrir con tiras de masa en enrejado.\n"
            "7. Hornear 50-60 min. Si dora muy rápido, cubrir con foil. Rinde 12 porciones."
        ),
    ),
    (
        "bitterballen_vegetariano__rec_020",
        "Salados",
        "gluten,huevo,lactosa",
        "",
        "vegetariano,salado,para-eventos",
        (
            "1. Picar finamente échalote, ajo y girgolas. Sudar en manteca con tomillo.\n"
            "2. Añadir harina, cocinar 2 min (roux). Verter caldo de hongos, revolver hasta espesar.\n"
            "3. Incorporar crema, sal y pimienta. Enfriar completamente (mínimo 4h).\n"
            "4. Formar bolitas de 3 cm de diámetro (rinde 100).\n"
            "5. Pasar por harina, huevo batido, pan rallado. Refrigerar 30 min.\n"
            "6. Freír a 175°C por 4 min hasta dorar. Servir con mostaza."
        ),
    ),
    (
        "bitterballen__rec_006",
        "Salados",
        "gluten,huevo,lactosa",
        "",
        "salado,tradicional,para-eventos",
        (
            "1. Picar finamente carnaza, bola de lomo, cebolla, ajo, zanahoria. Sudar en manteca.\n"
            "2. Añadir laurel, nuez moscada, sal, pimienta. Cocinar 10 min.\n"
            "3. Sumar harina, revolver 2 min. Verter caldo y agua, cocinar hasta obtener ragú espeso.\n"
            "4. Añadir gelatina disuelta, perejil, crema. Enfriar completamente (mínimo 4h, ideal toda la noche).\n"
            "5. Formar bolitas de 3 cm. Pasar por harina, huevo batido, pan rallado.\n"
            "6. Refrigerar 30 min para que asienten.\n"
            "7. Freír a 175°C por 4 min. Rinde 100 unidades. Apto freezer 1 mes."
        ),
    ),
]


def _seed_recipe_meta(ctx: SeedContext):
    """Apply family, allergens, dietary_tags, menu_tags, instructions from RECIPE_INSTRUCTIONS."""
    by_name = {r[0]: r for r in RECIPE_INSTRUCTIONS}
    updated = 0
    for recipe in ctx.session.execute(select(Recipe)).scalars():
        info = by_name.get(recipe.name)
        if info is None:
            continue
        _, family, allergens, dietary, menu_tags, instructions = info
        recipe.family = family
        recipe.allergens = allergens
        recipe.derived_dietary_tags = dietary
        recipe.menu_tags = menu_tags
        recipe.instructions = instructions
        updated += 1
    ctx.report.recipe_meta_updated = updated
    logger.info(f"seed: {updated} recipes with instructions/family/allergens/dietary/menu_tags")


# === Section 30: Product tablet_slug + mayorista_price + rspa + tags denorm ===
PRODUCT_META: list[tuple[str, str, int, str, str, str]] = [
    (
        "Stroop wafel",
        "bolleria",
        5500,
        "RSP-001",
        "2027-12-31",
        "tradicional,holandes,destacado,para-regalo",
    ),
    ("Babka chocolate", "bolleria", 13000, "RSP-002", "2027-12-31", "premium,tradicional,holandes"),
    ("Muffin chocolate (20x20 cm)", "bolleria", 6500, "RSP-003", "2027-12-31", "clasico,infantil"),
    (
        "Docena muffins chocolate",
        "bolleria",
        65000,
        "RSP-003",
        "2027-12-31",
        "clasico,infantil,para-eventos",
    ),
    ("Bizcocho 25 cm", "tortas", 120000, "RSP-004", "2027-12-31", "base,para-eventos,sin-relleno"),
    ("Bizcocho 30 cm", "tortas", 150000, "RSP-005", "2027-12-31", "base,para-eventos,sin-relleno"),
    ("Bizcocho 30 cm entero", "tortas", 150000, "RSP-005", "2027-12-31", "base,para-eventos"),
    ("Tarta de manzana", "tortas", 110000, "RSP-006", "2027-12-31", "tradicional,holandes,clasico"),
    ("Tarta de zanahoria 43x33", "tortas", 130000, "RSP-007", "2027-12-31", "clasico,favorita"),
    ("Cheesecake entera", "tortas", 140000, "RSP-008", "2027-12-31", "premium,para-eventos"),
    ("Cheesecake (30x50)", "tortas", 140000, "RSP-008", "2027-12-31", "premium,para-eventos"),
    ("Porción cheesecake", "tortas", 14000, "RSP-008", "2027-12-31", "premium,porcion"),
    ("Babka unidad", "bolleria", 13000, "RSP-002", "2027-12-31", "premium,tradicional,holandes"),
    (
        "Bombones chocolate (caja 12)",
        "dulces",
        35000,
        "RSP-009",
        "2027-12-31",
        "premium,regalo,destacado",
    ),
    (
        "Pastelitos rosados (docena)",
        "bolleria",
        60000,
        "RSP-010",
        "2027-12-31",
        "tradicional,holandes,festivo",
    ),
    (
        "Petisus crema (docena)",
        "bolleria",
        80000,
        "RSP-011",
        "2027-12-31",
        "tradicional,holandes,premium",
    ),
    (
        "Bossche bollen (docena)",
        "bolleria",
        95000,
        "RSP-012",
        "2027-12-31",
        "tradicional,holandes,premium",
    ),
    (
        "Speculaasjes (bolsa 200g)",
        "galleteria",
        18000,
        "RSP-013",
        "2027-12-31",
        "tradicional,holandes,clasico",
    ),
    ("Hojaldre (docena)", "bolleria", 55000, "RSP-014", "2027-12-31", "base,tradicional"),
    (
        "Oliebollen (docena)",
        "bolleria",
        32000,
        "RSP-015",
        "2027-12-31",
        "festivo,temporada,holandes",
    ),
    ("Ontbijtkoek", "bizcocho", 14000, "RSP-016", "2027-12-31", "tradicional,holandes,desayuno"),
    ("Stollen de navidad", "bizcocho", 85000, "RSP-017", "2027-12-31", "navidad,temporada,premium"),
    ("Frikandel (unidad)", "salados", 5500, "RSP-018", "2027-12-31", "salado,tradicional,holandes"),
    (
        "Bitterballen vegetariano (6 und)",
        "salados",
        32000,
        "RSP-019",
        "2027-12-31",
        "vegetariano,salado,para-eventos",
    ),
    (
        "Bitterballen clásicos (6 und)",
        "salados",
        32000,
        "RSP-020",
        "2027-12-31",
        "salado,tradicional,para-eventos",
    ),
    (
        "Goulash croquettes (6 und)",
        "salados",
        35000,
        "RSP-021",
        "2027-12-31",
        "salado,festivo,para-eventos",
    ),
    (
        "Supplì cacio e pepe (docena)",
        "salados",
        65000,
        "RSP-022",
        "2027-12-31",
        "salado,italiano,para-eventos",
    ),
    (
        "Tompoezen (docena)",
        "bolleria",
        80000,
        "RSP-011",
        "2027-12-31",
        "tradicional,holandes,premium",
    ),
    (
        "Torta de chocolate entera",
        "tortas",
        130000,
        "RSP-023",
        "2027-12-31",
        "clasico,infantil,para-eventos",
    ),
    ("Torta helada verano", "tortas", 145000, "RSP-024", "2027-12-31", "verano,festivo,premium"),
    (
        "Caja surtida 24 unidades",
        "dulces",
        95000,
        "RSP-025",
        "2027-12-31",
        "regalo,premium,para-eventos",
    ),
    ("Docena alfajores", "galleteria", 48000, "RSP-026", "2027-12-31", "clasico,infantil"),
]


def _seed_product_meta(ctx: SeedContext):
    """Apply tablet_slug, mayorista_price_gs, rspa_number, rspa_expiry, denorm tags.

    tablet_slug is UNIQUE per product in this schema. We use a per-product slug
    of the form `<group>-<id>` so multiple products can share a tablet section
    (group) while still satisfying the unique constraint.
    """
    by_name = {p[0]: p for p in PRODUCT_META}
    updated = 0
    for prod in ctx.session.execute(select(Product)).scalars():
        info = by_name.get(prod.name)
        if info is None:
            continue
        _, tablet_slug, mayorista_price, rspa_number, rspa_expiry, tags_csv = info
        prod.tablet_slug = f"{tablet_slug}-{prod.id}"
        prod.mayorista_price_gs = mayorista_price
        prod.rspa_number = rspa_number
        prod.rspa_expiry = date.fromisoformat(rspa_expiry)
        prod.tags = tags_csv
        updated += 1
    ctx.report.product_meta_updated = updated
    logger.info(f"seed: {updated} products with tablet_slug/mayorista/rspa/tags")


# === Section 31: Ingredient subcategory + role + notes + avg_cost ===
INGREDIENT_SUBCATEGORY: dict[str, dict[str, str]] = {
    "harinas y bases": {
        "Harina de trigo": "trigo",
        "Harina de centeno": "centeno",
        "Harina de repostería": "reposteria",
        "Harina Patentada": "trigo",
        "Maicena": "espesante",
        "Pan rallado": "rebozado",
    },
    "endulzantes": {
        "Azúcar": "comun",
        "Azúcar glas": "glas",
        "Azúcar morena": "morena",
        "Miel": "natural",
        "Melaza": "tradicional",
    },
    "lácteos y huevos": {
        "Leche": "fluida",
        "Leche en polvo": "polvo",
        "Manteca": "grasa",
        "Crema de leche": "crema",
        "Crema agria": "crema",
        "Crema pastelera": "preparada",
        "Queso crema": "cremoso",
        "Queso muzzarella": "pasta",
        "Queso rallado": "rallado",
        "Suero de leche (buttermilk)": "subproducto",
        "Huevos": "fresco",
    },
    "cacao café y chocolate": {
        "Cacao en polvo": "polvo",
        "Chocolate cobertura": "cobertura",
        "Chocolate": "tableta",
        "Café": "molido",
        "Café instantaneo": "soluble",
    },
    "especias y condimentos": {
        "Canela": "especia",
        "Vainilla": "especia",
        "Ralladura de limón": "fresco",
        "Esencia de vainilla": "esencia",
        "Sal": "sal",
        "Pimienta": "especia",
        "Mostaza": "condimento",
        "Laurel": "hierba",
        "Anís estrellado": "especia",
        "Mezcla de especias para Speculaas": "mezcla",
        "Ajo": "fresco",
        "Jengibre": "fresco",
        "Jengibre molido": "especia",
        "Nuez moscada": "especia",
        "Pimentón ahumado": "especia",
        "Alcaravea": "especia",
        "Cayena": "especia",
        "Especias mixtas": "mezcla",
        "Tomillo fresco": "hierba",
        "Perejil": "hierba",
        "Pimentón": "seco",
    },
    "levaduras y gasificantes": {
        "Levadura fresca": "fresca",
        "Levadura seca": "seca",
        "Polvo de hornear": "gasificante",
        "Bicarbonato de sodio": "gasificante",
    },
    "frutas y frutos secos": {
        "Manzana": "fresca",
        "Limón": "fresco",
        "Frambuesas": "congelada",
        "Frutilla": "fresca",
        "Fruta": "mixta",
        "Pasas": "seca",
        "Mango": "fresco",
        "Arándanos": "congelado",
        "Nueces": "seco",
    },
    "verduras y legumbres": {
        "Cebolla": "fresca",
        "Cebolla morada": "fresca",
        "Cebolla de verdeo": "fresca",
        "Zanahoria": "fresca",
        "Apio": "fresco",
        "Morrón rojo": "fresco",
        "Pimentón": "seco",
        "Tomate": "fresco",
        "Garbanzo": "legumbre",
        "Echalote": "fresco",
        "Girgolas frescas": "fresco",
    },
    "carnes": {
        "Carnaza de segunda": "vacuna",
        "Bola de lomo": "vacuna",
        "Falda de res": "vacuna",
        "Pollo": "ave",
        "Pechuga de pollo": "ave",
    },
    "salsas y líquidos": {
        "Agua": "neutro",
        "Leche de coco": "vegetal",
        "Salsa de soja": "fermentada",
        "Vinagre": "fermentado",
        "Caldo de carne en cubos": "preparado",
        "Puré de tomate": "preparado",
        "Jugo de remolacha": "natural",
        "Jugo de limón": "natural",
    },
    "aceites y grasas": {"Aceite": "neutro", "Manteca vegetal": "grasa"},
    "preparados y otros": {
        "Masa de hojaldre": "preparada",
        "Bicarbonato": "gasificante",
        "Gelatina sin sabor": "gelificante",
        "Estabilizante para nata": "estabilizante",
        "Esencia de almendras": "esencia",
        "Polvo para natillas": "preparado",
        "Caldo de hongos en cubos": "preparado",
        "Masa choux": "preparada",
    },
}

INGREDIENT_ROLE: dict[str, str] = {
    "Harina de trigo": "base",
    "Harina de centeno": "base",
    "Harina de repostería": "base",
    "Harina Patentada": "base",
    "Maicena": "base",
    "Pan rallado": "operativo",
    "Arroz para sushi": "base",
    "Leche": "base",
    "Leche en polvo": "base",
    "Huevos": "base",
    "Manteca": "base",
    "Crema de leche": "base",
    "Crema agria": "base",
    "Queso crema": "base",
    "Queso muzzarella": "base",
    "Queso rallado": "base",
    "Suero de leche (buttermilk)": "base",
    "Crema pastelera": "base",
    "Aceite": "operativo",
    "Manteca vegetal": "operativo",
    "Agua": "operativo",
    "Vinagre": "operativo",
    "Leche de coco": "base",
    "Azúcar": "base",
    "Azúcar glas": "decoración",
    "Azúcar morena": "base",
    "Miel": "base",
    "Melaza": "base",
    "Levadura fresca": "operativo",
    "Levadura seca": "operativo",
    "Polvo de hornear": "operativo",
    "Bicarbonato de sodio": "operativo",
    "Bicarbonato": "operativo",
    "Gelatina sin sabor": "operativo",
    "Estabilizante para nata": "operativo",
    "Polvo para natillas": "operativo",
    "Cacao en polvo": "saborizante",
    "Chocolate cobertura": "saborizante",
    "Chocolate": "saborizante",
    "Café": "saborizante",
    "Café instantaneo": "saborizante",
    "Canela": "saborizante",
    "Vainilla": "saborizante",
    "Esencia de vainilla": "saborizante",
    "Esencia de almendras": "saborizante",
    "Ralladura de limón": "saborizante",
    "Sal": "saborizante",
    "Pimienta": "saborizante",
    "Mostaza": "saborizante",
    "Laurel": "saborizante",
    "Anís estrellado": "saborizante",
    "Mezcla de especias para Speculaas": "saborizante",
    "Ajo": "saborizante",
    "Jengibre": "saborizante",
    "Jengibre molido": "saborizante",
    "Nuez moscada": "saborizante",
    "Pimentón ahumado": "saborizante",
    "Alcaravea": "saborizante",
    "Cayena": "saborizante",
    "Especias mixtas": "saborizante",
    "Tomillo fresco": "saborizante",
    "Perejil": "saborizante",
    "Pimentón": "saborizante",
    "Salsa de soja": "saborizante",
    "Caldo de carne en cubos": "saborizante",
    "Caldo de hongos en cubos": "saborizante",
    "Puré de tomate": "saborizante",
    "Jugo de remolacha": "saborizante",
    "Jugo de limón": "saborizante",
    "Frambuesas": "saborizante",
    "Frutilla": "saborizante",
    "Fruta": "saborizante",
    "Manzana": "saborizante",
    "Limón": "saborizante",
    "Mango": "saborizante",
    "Arándanos": "saborizante",
    "Pasas": "saborizante",
    "Nueces": "decoración",
    "Cebolla": "saborizante",
    "Cebolla morada": "saborizante",
    "Cebolla de verdeo": "saborizante",
    "Zanahoria": "saborizante",
    "Apio": "saborizante",
    "Morrón rojo": "saborizante",
    "Tomate": "saborizante",
    "Garbanzo": "saborizante",
    "Echalote": "saborizante",
    "Girgolas frescas": "saborizante",
    "Carnaza de segunda": "base",
    "Bola de lomo": "base",
    "Falda de res": "base",
    "Pollo": "base",
    "Pechuga de pollo": "base",
    "Masa de hojaldre": "base",
    "Masa choux": "base",
    "bolsita de 15x22": "empaque",
    "cintillo 7mm 10m": "empaque",
    "bandeja isopor": "empaque",
    "bandeja carton": "empaque",
    "papel antigrasa blanco": "empaque",
    "bolsa de papel mediana": "empaque",
    "caja torta 25cm": "empaque",
}


def _seed_ingredient_meta(ctx: SeedContext):
    """Apply subcategory, role, notes, avg_cost_gs to all 101 ingredients."""
    updated = 0
    for ing in ctx.session.execute(select(Ingredient)).scalars():
        cat = ing.category or ""
        subcat = INGREDIENT_SUBCATEGORY.get(cat, {}).get(ing.name, "")
        role = INGREDIENT_ROLE.get(ing.name, "operativo")
        ing.subcategory = subcat
        ing.role = role
        if ing.notes is None or ing.notes == "":
            ing.notes = f"Categoría: {cat}. Almacén: {ing.storage or 'ambient'}."
        if ing.avg_cost_gs is None and ing.purchase_price_gs is not None:
            ing.avg_cost_gs = ing.purchase_price_gs
        updated += 1
    ctx.report.ingredient_meta_updated = updated
    logger.info(f"seed: {updated} ingredients with subcategory/role/notes/avg_cost")


# === Section 32: Price history (supplier receipts) ===
def _seed_price_history(ctx: SeedContext):
    """Generate 6 months of weekly supplier receipts for top 30 ingredients by usage.

    price_history records ACTUAL purchase transactions (qty + total_gs + supplier + date),
    distinct from ingredient_price_event which records observed market price changes.

    Idempotent: skip entirely if PriceHistory already has any rows.
    """
    if ctx.session.execute(select(PriceHistory).limit(1)).first():
        ctx.report.price_history = 0
        logger.info("seed: price_history already populated, skipping")
        return
    top_ings = ctx.session.execute(
        text("""
        SELECT ingredient_id, SUM(qty) AS total_used
        FROM stock_movement
        WHERE movement_type = 'sale' AND ingredient_id IS NOT NULL
        GROUP BY ingredient_id
        ORDER BY total_used DESC LIMIT 30
    """)
    ).fetchall()
    if not top_ings:
        return
    suppliers = ctx.session.execute(select(Supplier)).scalars().all()
    if not suppliers:
        return
    today = ctx.anchor_date
    n_inserted = 0
    for ing_id, _ in top_ings:
        ing = ctx.session.get(Ingredient, ing_id)
        if ing is None or ing.purchase_price_gs is None:
            continue
        for w in range(26):
            purchase_date = today - timedelta(days=7 * w + (w % 3))
            if purchase_date > today:
                continue
            supplier = suppliers[w % len(suppliers)]
            variation = 0.95 + (w * 0.013) % 0.10
            unit_price = int(ing.purchase_price_gs * variation)
            qty = float(ing.min_stock_qty or 1.0) * 1.5
            ctx.session.add(
                PriceHistory(
                    supplier_id=supplier.id,
                    ingredient_id=ing.id,
                    qty_purchased=qty,
                    unit=ing.unit,
                    total_gs=int(qty * unit_price),
                    unit_price_gs=unit_price,
                    purchase_date=datetime.combine(purchase_date, datetime.min.time()),
                    notes="Compra semanal automática",
                    recorded_by="seeder",
                )
            )
            n_inserted += 1
    ctx.session.flush()
    ctx.report.price_history = n_inserted
    logger.info(f"seed: {n_inserted} price history rows (supplier receipts)")


# === Section 33: Business expenses ===
def _seed_expenses(ctx: SeedContext):
    """Seed 7 months of business expenses (rent, electricity, salaries, supplies, IPS).

    Idempotent: skip if any Expense rows already exist.
    """
    if ctx.session.execute(select(Expense).limit(1)).first():
        ctx.report.expenses = 0
        logger.info("seed: expenses already populated, skipping")
        return
    today = ctx.anchor_date
    n = 0
    monthly_fixed = [
        ("Alquiler local", 2500000, 1),
        ("Electricidad (ANDE)", 380000, 5),
        ("Internet + Teléfono (Tigo)", 145000, 8),
        ("Agua (Essap)", 65000, 12),
        ("Gas (Chaco Gas)", 85000, 18),
    ]
    for label, amount, day in monthly_fixed:
        for m in range(8):
            month_ago = today.replace(day=1) - timedelta(days=30 * m)
            occurred = month_ago.replace(day=min(day, 28))
            if occurred > today:
                continue
            ctx.session.add(
                Expense(
                    occurred_at=datetime.combine(occurred, datetime.min.time()),
                    category="RENT",
                    description=label,
                    amount_gs=amount,
                    is_voided=False,
                    created_at=datetime.combine(occurred, datetime.min.time()),
                    recurring_period="monthly",
                )
            )
            n += 1
    for d in range(1, 220, 15):
        occurred = today - timedelta(days=d)
        if occurred.day not in (1, 15):
            continue
        ctx.session.add(
            Expense(
                occurred_at=datetime.combine(occurred, datetime.min.time()),
                category="PAYROLL",
                description="Sueldos quincenales (4 empleados)",
                amount_gs=5600000,
                is_voided=False,
                created_at=datetime.combine(occurred, datetime.min.time()),
                recurring_period="monthly",
            )
        )
        n += 1
    for w in range(30):
        occurred = today - timedelta(days=7 * w + 2)
        ctx.session.add(
            Expense(
                occurred_at=datetime.combine(occurred, datetime.min.time()),
                category="PACKAGING",
                description="Insumos de packaging y limpieza (semanal)",
                amount_gs=120000 + (w * 4000) % 30000,
                is_voided=False,
                created_at=datetime.combine(occurred, datetime.min.time()),
                recurring_period="once",
            )
        )
        n += 1
    for m in range(8):
        month_ago = today.replace(day=1) - timedelta(days=30 * m)
        occurred = month_ago.replace(day=20)
        if occurred > today:
            continue
        ctx.session.add(
            Expense(
                occurred_at=datetime.combine(occurred, datetime.min.time()),
                category="OTHER",
                description="IPS aportes (mensual)",
                amount_gs=950000,
                is_voided=False,
                created_at=datetime.combine(occurred, datetime.min.time()),
                recurring_period="monthly",
            )
        )
        ctx.session.add(
            Expense(
                occurred_at=datetime.combine(occurred, datetime.min.time()),
                category="OTHER",
                description="Honorarios contador",
                amount_gs=450000,
                is_voided=False,
                created_at=datetime.combine(occurred, datetime.min.time()),
                recurring_period="monthly",
            )
        )
        n += 2
    ctx.session.flush()
    ctx.report.expenses = n
    logger.info(f"seed: {n} expense rows (7mo fixed + salaries + supplies + tax)")


# === Section 34: Cash sessions (last 30 working days) ===
def _seed_cash_sessions(ctx: SeedContext):
    """Daily cash register openings/closings (last 30 working days).

    Idempotent: skip if any CashSession rows already exist.
    """
    if ctx.session.execute(select(CashSession).limit(1)).first():
        ctx.report.cash_sessions = 0
        logger.info("seed: cash_sessions already populated, skipping")
        return
    users = ctx.session.execute(select(User).limit(2)).scalars().all()
    if not users:
        return
    today = ctx.anchor_date
    n = 0
    for d in range(30):
        day = today - timedelta(days=d)
        if day.weekday() == 6 and d > 7:  # skip most Sundays
            continue
        opened_by = users[d % len(users)]
        closed_by = users[(d + 1) % len(users)]
        opening_gs = 100000
        daily_cash = 250000 + (d * 17000) % 180000
        closing_gs = opening_gs + daily_cash
        ctx.session.add(
            CashSession(
                opened_at=datetime.combine(day, datetime.min.time().replace(hour=7)),
                closed_at=datetime.combine(day, datetime.min.time().replace(hour=20)),
                opened_by=opened_by.username,
                closed_by=closed_by.username,
                opening_gs=opening_gs,
                counted_gs=closing_gs,
                expected_gs=closing_gs,
                diff_gs=0,
                status="closed",
                channel="mostrador",
            )
        )
        n += 1
    ctx.session.flush()
    ctx.report.cash_sessions = n
    logger.info(f"seed: {n} cash sessions (last 30 working days)")


# === Section 35: Sale payments (per-sale method split) ===
def _seed_sale_payments(ctx: SeedContext):
    """Generate SalePayment rows for each existing sale (60% efectivo, 25% tarjeta, 15% transferencia)."""
    # skip sales that already have a payment
    paid_sale_ids = {row[0] for row in ctx.session.execute(select(SalePayment.sale_id)).all()}
    sales = (
        ctx.session.execute(
            select(Sale).where(Sale.id.notin_(paid_sale_ids) if paid_sale_ids else True)
        )
        .scalars()
        .all()
    )
    n = 0
    for sale in sales:
        r = (sale.id * 7) % 100
        if r < 60:
            method = "efectivo"
        elif r < 85:
            method = "tarjeta"
        else:
            method = "transferencia"
        # Sale has no `total_gs` column; reconstruct from iva_base + iva_amount.
        amount_gs = int((sale.iva_base_gs or 0) + (sale.iva_amount_gs or 0))
        ctx.session.add(
            SalePayment(
                sale_id=sale.id,
                method=method,
                amount_gs=amount_gs,
                created_at=sale.sold_at,
            )
        )
        n += 1
    ctx.session.flush()
    ctx.report.sale_payments = n
    logger.info(f"seed: {n} sale payments (method split)")


# === Section 36: Monthly closure (last 2 closed months) ===
def _seed_monthly_closure(ctx: SeedContext):
    """Generate MonthlyClosure rows for aug-2026 and sep-2026 (oct still open).

    Idempotent: skip if a MonthlyClosure for the period already exists.
    """
    users = ctx.session.execute(select(User).limit(1)).scalars().first()
    if users is None:
        return
    today = ctx.anchor_date
    n = 0
    for offset in (2, 1):
        first_of_month = (today.replace(day=1) - timedelta(days=offset * 30)).replace(day=1)
        period = first_of_month.strftime("%Y-%m")
        # idempotency: skip if period already exists
        from app.rms.models import MonthlyClosure as _MC

        if ctx.session.execute(select(_MC.id).where(_MC.period_yyyymm == period)).first():
            continue
        next_month = (first_of_month + timedelta(days=32)).replace(day=1)
        revenue, iva, cogs = ctx.session.execute(
            text("""
            SELECT COALESCE(SUM(iva_base_gs + iva_amount_gs), 0),
                   COALESCE(SUM(iva_amount_gs), 0),
                   COALESCE(SUM(iva_base_gs) * 0.4, 0)
            FROM sale
            WHERE sold_at >= :start AND sold_at < :end
        """),
            {"start": first_of_month, "end": next_month},
        ).first()
        ctx.session.add(
            MonthlyClosure(
                period_yyyymm=period,
                closed_at=datetime.combine(next_month - timedelta(days=1), datetime.min.time()),
                closed_by_user_id=users.username,
                total_iva_gs=int(iva),
                total_revenue_gs=int(revenue),
                total_cogs_gs=int(cogs),
                total_expenses_gs=int(revenue * 0.25),
                net_gs=int(revenue - cogs - revenue * 0.25),
                snapshot_json='{"seed":"sazon monthly closure 2026-10-09"}',
            )
        )
        n += 1
    ctx.session.flush()
    ctx.report.monthly_closures = n
    logger.info(f"seed: {n} monthly closures (aug+sep 2026)")


# === Section 37: Menu + MenuItem (operator-editable menu boards) ===
def _seed_menus(ctx: SeedContext):
    """Two menus: Carta Regular (active) + Carta Navidad 2026 (preview, inactive)."""
    today = ctx.anchor_date
    tenant = ctx.session.execute(select(Tenant).limit(1)).scalar_one_or_none()
    if tenant is None:
        return
    ctx.session.execute(text("DELETE FROM menu_item"))
    ctx.session.execute(text("DELETE FROM menu"))
    ctx.session.flush()
    regular = Menu(
        tenant_id=tenant.id,
        name="Carta Regular",
        price_gs=0,
        active=True,
        created_at=datetime.combine(today, datetime.min.time()),
    )
    ctx.session.add(regular)
    ctx.session.flush()
    bestsellers = ctx.session.execute(
        text("""
        SELECT id FROM product
        WHERE id IN (SELECT product_id FROM sale
                     WHERE product_id IS NOT NULL AND sold_at >= :since)
        GROUP BY id
        ORDER BY COUNT(*) DESC LIMIT 8
    """),
        {"since": today - timedelta(days=30)},
    ).fetchall()
    for (prod_id,) in bestsellers:
        ctx.session.add(MenuItem(menu_id=regular.id, product_id=prod_id, qty=1))
    navidad = Menu(
        tenant_id=tenant.id,
        name="Carta Navidad 2026",
        price_gs=0,
        active=False,
        created_at=datetime.combine(today, datetime.min.time()),
    )
    ctx.session.add(navidad)
    ctx.session.flush()
    navidad_prods = ctx.session.execute(
        text("""
        SELECT id FROM product
        WHERE LOWER(name) LIKE '%navidad%' OR LOWER(name) LIKE '%stollen%'
            OR LOWER(name) LIKE '%oliebollen%' OR LOWER(name) LIKE '%panettone%'
        LIMIT 6
    """)
    ).fetchall()
    for (prod_id,) in navidad_prods:
        ctx.session.add(MenuItem(menu_id=navidad.id, product_id=prod_id, qty=1))
    ctx.session.flush()
    ctx.report.menus = 2
    ctx.report.menu_items = len(bestsellers) + len(navidad_prods)
    logger.info(f"seed: 2 menus, {len(bestsellers) + len(navidad_prods)} menu items")


# === Section 38: Production plan (next 14 days) ===
def _seed_production_plan(ctx: SeedContext):
    """Generate ProductionPlan for next 14 days, top 8 products × 14 days = 112 rows.

    Idempotent: skip if any ProductionPlan rows already exist.
    """
    if ctx.session.execute(select(ProductionPlan).limit(1)).first():
        ctx.report.production_plans = 0
        logger.info("seed: production_plans already populated, skipping")
        return
    today = ctx.anchor_date
    n = 0
    recipes = ctx.session.execute(select(Recipe.id, Recipe.name)).all()
    if not recipes:
        return
    top = ctx.session.execute(
        text("""
        SELECT p.id, p.name, COALESCE(AVG(s.qty), 1) AS avg_qty
        FROM product p
        LEFT JOIN sale s ON s.product_id = p.id
        WHERE s.sold_at >= :since OR s.sold_at IS NULL
        GROUP BY p.id
        ORDER BY avg_qty DESC LIMIT 8
    """),
        {"since": today - timedelta(days=30)},
    ).fetchall()
    for d in range(14):
        day = today + timedelta(days=d)
        day_factor = 0.5 if day.weekday() == 6 else 1.0
        for idx, (_prod_id, _name, avg_qty) in enumerate(top):
            recipe_id, _ = recipes[idx % len(recipes)]
            ctx.session.add(
                ProductionPlan(
                    recipe_id=recipe_id,
                    batches_qty=int(float(avg_qty) * day_factor) + 1,
                    planned_at=datetime.combine(day, datetime.min.time()),
                    status="planned",
                    created_by="seeder",
                )
            )
            n += 1
    ctx.session.flush()
    ctx.report.production_plans = n
    logger.info(f"seed: {n} production plan rows (next 14 days × top 8)")


# === Section 39: Data-quality fixes (Tier C) ===
def _seed_data_quality_fixes(ctx: SeedContext):
    """Apply Tier C fixes: market_benchmark dedup, margin_tier ranges, date_range_preset dedup."""
    fixed = {"benchmark_dedup": 0, "margin_tier": 0, "date_preset_dedup": 0}

    # market_benchmark: keep one per product_label
    rows = ctx.session.execute(
        text("""
        SELECT product_label, MAX(id) AS keep_id
        FROM market_benchmark GROUP BY product_label
    """)
    ).fetchall()
    keep_ids = {r[1] for r in rows}
    if keep_ids:
        # keep_ids is a set of ints fetched from the DB; safe to interpolate.
        deleted = ctx.session.execute(
            text(
                f"""
            DELETE FROM market_benchmark WHERE id NOT IN ({",".join(str(i) for i in keep_ids)})
        """  # noqa: S608
            )
        )
        fixed["benchmark_dedup"] = deleted.rowcount or 0

    # margin_tier: clear and insert canonical tiers
    ctx.session.execute(text("DELETE FROM margin_tier"))
    canonical = [
        ("muy_bajo", "Muy bajo / pérdida", 0, 499, 1),
        ("bajo", "Bajo", 500, 999, 2),
        ("medio", "Medio", 1000, 4999, 3),
        ("tier2", "Top 25%", 5000, 9999, 4),
        ("tier1", "Top 10% (premium)", 10000, None, 5),
    ]
    for code, label, mn, mx, order in canonical:
        ctx.session.execute(
            text("""
            INSERT INTO margin_tier (code, label, min_cost_gs, max_cost_gs, sort_order, is_active, created_at)
            VALUES (:code, :label, :mn, :mx, :order, 1, :now)
        """),
            {
                "code": code,
                "label": label,
                "mn": mn,
                "mx": mx,
                "order": order,
                "now": datetime.combine(ctx.anchor_date, datetime.min.time()),
            },
        )
        fixed["margin_tier"] += 1

    # date_range_preset: no dedup needed (codes are unique in the source DATE_PRESETS).
    # Skipped: deduplicating by anything would either be a no-op (by code) or
    # destructive (by days, which grouped 10 entries down to 6 and broke tests).
    fixed["date_preset_dedup"] = 0

    ctx.session.flush()
    for k, v in fixed.items():
        logger.info(f"data-quality {k}: {v}")
    ctx.report.data_quality_fixes = fixed


def _seed_audit_log_initial_entries(ctx: SeedContext):
    """Section 28: Audit log (initial entries).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

    audit_record(
        ctx.session,
        user_id=SASKIA_USER,
        action="system.startup",
        detail={"source": "seed_sazon", "tenant": TENANT_NAME},
    )
    audit_record(
        ctx.session,
        user_id=SASKIA_USER,
        action="seed.complete",
        detail={"tenant": TENANT_NAME, "version": "1.0"},
    )
    ctx.report.audit_log_rows = 2


def _seed_appmeta_pins_idempotency__onboarding_gu(ctx: SeedContext):
    """Section 29: AppMeta pins (idempotency + onboarding guard).

    Extracted from seed_sazon (refactored 2026-10-09).
    """

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
        existing = ctx.session.execute(select(AppMeta).where(AppMeta.key == k)).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
                AppMeta(key=k, value=str(v), updated_at=datetime.now(ASUNCION_TZ).isoformat())
            )
        else:
            existing.value = str(v)
            existing.updated_at = datetime.now(ASUNCION_TZ).isoformat()


def _seed_bank_transactions_a_few_recent_ones(ctx: SeedContext) -> SazonReport:
    """Section 30: Bank transactions (a few recent ones).

    Extracted from seed_sazon (refactored 2026-10-09).

    Returns SazonReport to satisfy type-checker; the orchestrator
    (seed_sazon at L4253) ignores this return value and re-returns
    ctx.report itself. The trailing commit + logger + return are
    defensive duplicates.
    """

    # Idempotency: the dedup query uses (posted_at, description) as the
    # natural key. Both must be deterministic. ctx.anchor_date is a
    # `date` (not datetime) — when compared to the DateTime `posted_at`
    # column, SQLAlchemy coerces to datetime, but the conversion can
    # differ between drivers (midnight UTC vs local tz). To make it
    # 100% stable, we explicitly store posted_at as a midnight datetime.
    bank_tx_data = [
        # (date, amount, type, description, account, balance_gs)
        (
            ctx.anchor_date - timedelta(days=60),
            -1_200_000,
            "transfer",
            "Pago a Distribuidora El Molino",
            "Itaú",
            2_500_000,
        ),
        (
            ctx.anchor_date - timedelta(days=45),
            -650_000,
            "transfer",
            "Pago a Lácteos Paraguay",
            "Itaú",
            1_850_000,
        ),
        (
            ctx.anchor_date - timedelta(days=30),
            3_500_000,
            "deposit",
            "Cierre de caja 30 días",
            "Itaú",
            5_350_000,
        ),
        (
            ctx.anchor_date - timedelta(days=20),
            -280_000,
            "debit",
            "Servicios ANDE",
            "Itaú",
            5_070_000,
        ),
        (
            ctx.anchor_date - timedelta(days=15),
            2_800_000,
            "deposit",
            "Cierre quincena",
            "Itaú",
            7_870_000,
        ),
        (
            ctx.anchor_date - timedelta(days=10),
            -450_000,
            "transfer",
            "Pago a Dulcería Santa Rita",
            "Itaú",
            7_420_000,
        ),
        (ctx.anchor_date - timedelta(days=5), -180_000, "debit", "Essap", "Itaú", 7_240_000),
        (
            ctx.anchor_date - timedelta(days=2),
            1_800_000,
            "deposit",
            "Cierre de caja 2 días",
            "Itaú",
            9_040_000,
        ),
    ]
    for tx_date, amount, tx_type, desc, account, balance in bank_tx_data:
        # Normalize to midnight datetime so the dedup comparison is stable
        # regardless of tz coercion. ctx.anchor_date is a `date`;
        # `BankTransaction.posted_at` is DateTime.
        tx_posted_at = datetime.combine(tx_date, datetime.min.time())
        existing = ctx.session.execute(
            select(BankTransaction).where(
                BankTransaction.posted_at == tx_posted_at,
                BankTransaction.description == desc,
            )
        ).scalar_one_or_none()
        if existing is None:
            ctx.session.add(
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
    # Don't count bank tx in the main ctx.report — keep it light

    ctx.session.commit()
    logger.info(f"seed_sazon complete: {ctx.report.as_dict()}")
    return ctx.report


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
