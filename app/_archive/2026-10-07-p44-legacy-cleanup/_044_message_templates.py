from sqlalchemy import text

from app.rms.db import _bump_schema_version


def _migration_044_message_templates(conn: object):
    """Phase 6 — MessageTemplate table + seed common templates.

    Replaces hardcoded copy in pedidos.py, email notifications, etc.
    Operators can edit from /settings/templates without code deploy.

    Seed data matches the prior hardcoded copy in app/routers/pedidos.py
    and similar files. Body uses {placeholder} format() syntax — substitute
    at send time.

    Idempotent: INSERT OR IGNORE on (channel, key, locale) unique.
    """
    conn.dialect.name if hasattr(conn, "dialect") else "sqlite"
    text_type = "TEXT"

    conn.execute(
        text(
            f"""
        CREATE TABLE IF NOT EXISTS message_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel VARCHAR(16) NOT NULL,
            key VARCHAR(64) NOT NULL,
            subject VARCHAR(200),
            body {text_type} NOT NULL,
            locale VARCHAR(8) NOT NULL DEFAULT 'es-PY',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            notes {text_type},
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (channel, key, locale)
        )
        """
        )
    )

    # Seed default templates (Paraguayan Spanish, es-PY)
    defaults = [
        # WhatsApp — pedido ready for pickup
        {
            "channel": "whatsapp",
            "key": "pedido_listo",
            "subject": "🍽️ Tu pedido está listo para retirar",
            "body": "¡Hola {cliente}! Tu pedido #{pedido_id} está listo para retirar en {tienda}. Hora estimada: {hora_retiro}. Por favor, presentarse en el mostrador con este número. ¡Gracias!",
            "locale": "es-PY",
        },
        # WhatsApp — pedido delayed
        {
            "channel": "whatsapp",
            "key": "pedido_retrasado",
            "subject": "⏰ Tu pedido está demorado",
            "body": "Hola {cliente}, informamos que tu pedido #{pedido_id} está demorado debido a {razon}. Nuevo estimado: {nueva_hora}. Disculpe las molestias. ¿Desea cancelar? Responda SÍ o NO.",
            "locale": "es-PY",
        },
        # WhatsApp — pedido cancelled
        {
            "channel": "whatsapp",
            "key": "pedido_cancelado",
            "subject": "❌ Pedido cancelado",
            "body": "Hola {cliente}, tu pedido #{pedido_id} ha sido cancelado debido a {razon}. Si pagó online, el reintegro se procesará en 3-5 días hábiles. Por cualquier consulta, contáctenos.",
            "locale": "es-PY",
        },
        # Email — pedido ready for pickup
        {
            "channel": "email",
            "key": "pedido_listo",
            "subject": "Tu pedido #{pedido_id} está listo para retirar",
            "body": "<p>Estimado/a {cliente},</p><p>Tu pedido #{pedido_id} está listo para retirar en {tienda}.</p><p><strong>Hora estimada:</strong> {hora_retiro}</p><p>Por favor, presentarse en el mostrador con este número.</p><p>¡Gracias!</p>",
            "locale": "es-PY",
        },
        # Email — pedido delayed
        {
            "channel": "email",
            "key": "pedido_retrasado",
            "subject": "Tu pedido #{pedido_id} está demorado",
            "body": "<p>Estimado/a {cliente},</p><p>Informamos que tu pedido #{pedido_id} está demorado debido a {razon}.</p><p><strong>Nuevo estimado:</strong> {nueva_hora}</p><p>Disculpe las molestias.</p>",
            "locale": "es-PY",
        },
        # Email — pedido cancelled
        {
            "channel": "email",
            "key": "pedido_cancelado",
            "subject": "Tu pedido #{pedido_id} ha sido cancelado",
            "body": "<p>Estimado/a {cliente},</p><p>Tu pedido #{pedido_id} ha sido cancelado debido a {razon}.</p><p>Si pagó online, el reintegro se procesará en 3-5 días hábiles.</p><p>Por cualquier consulta, contáctenos.</p>",
            "locale": "es-PY",
        },
    ]

    for template in defaults:
        conn.execute(
            text(
                """
                INSERT OR IGNORE INTO message_template
                (channel, key, subject, body, locale, is_active, version)
                VALUES (:channel, :key, :subject, :body, :locale, 1, 1)
                """
            ),
            template,
        )

    _bump_schema_version(conn, 44)
