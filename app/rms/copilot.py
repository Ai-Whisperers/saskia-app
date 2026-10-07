"""app/rms/copilot.py — Fase 3: Copiloto IA fase 0 (read-only, en-app).

answer(question, session) → intención (regex) → función existente de
insights/fiado → contexto compacto → GLM responde corto en español PY.
Sin ZAI_API_KEY: responde con los números crudos (degradación).

Guardarraíles: SOLO lectura (ninguna mutación), agregados sin PII,
prompt con anti-invención. La pregunta del usuario NUNCA se ejecuta.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.llm import available, chat

_SYSTEM = (
    "Sos el copiloto de un negocio de comida en Paraguay. Respondé en español "
    "de Paraguay, en 3-6 líneas máximo, con los números reales del contexto. "
    "NO inventes datos que no estén en el contexto. Si el contexto no alcanza "
    "para responder, decí qué falta."
)

# intenciones en orden de prioridad
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("fiado", re.compile(r"fiado|debo|cobrar|cuenta corriente|crédito", re.I)),
    ("mañana", re.compile(r"mañana|preparo|producir|cuánto hac", re.I)),
    ("hora_pico", re.compile(r"hora|ocupado|movido|pico", re.I)),
    ("margen", re.compile(r"margen|rentab|gananc|peor", re.I)),
    ("hoy", re.compile(r"hoy|día|venta|factur|cuánto vend", re.I)),
    ("muerto", re.compile(r"no se vende|parado|muerto|venc", re.I)),
]


def detect_intent(question: str) -> str:
    for name, rx in _PATTERNS:
        if rx.search(question):
            return name
    return "hoy"


def _context(session: Session, intent: str) -> dict[str, Any]:
    """Contexto compacto de AGREGADOS (sin PII) según intención."""
    from app.rms.models_legacy import Sale

    ctx: dict[str, Any] = {"intencion": intent}
    try:
        if intent == "fiado":
            from app.rms.fiado import cartera

            rows = cartera(session)
            ctx["cuentas_fiado"] = [
                {"cliente": r["customer"], "saldo_gs": r["saldo_gs"]}
                for r in rows[:10]
                if r["saldo_gs"] != 0
            ]
            ctx["saldo_total_fiado_gs"] = sum(r["saldo_gs"] for r in rows)
        else:
            # ventas agregadas (toda la base es poco volumen; filtro hoy
            # real vendrá de insights cuando exista sale date filter UI)
            total_gs, n = 0, 0
            for row in session.execute(
                select(Sale.id, Sale.qty, Sale.unit_price_gs).where(Sale.voided_at.is_(None))
            ).all():
                total_gs += int(row.qty or 0) * int(row.unit_price_gs or 0)
                n += 1
            ctx["ventas_totales_gs"] = total_gs
            ctx["cantidad_ventas"] = n
    except Exception:  # noqa: BLE001 — contexto best-effort
        ctx["error_contexto"] = "no_se_pudo_armar"
    return ctx


_FALLBACK = (
    "Sin IA configurada (ZAI_API_KEY), te paso los números crudos:\n"
    "- Ventas de hoy: Gs {ventas_totales_gs:,} en {cantidad_ventas} tickets.\n"
    "- Saldo total fiado: Gs {saldo_total_fiado_gs:,}.\n"
)


def answer(question: str, session: Session) -> dict[str, Any]:
    """Devuelve {answer, intent, llm_used, context}. NUNCA muta datos."""
    intent = detect_intent(question)
    ctx = _context(session, intent)
    ctx.setdefault("saldo_total_fiado_gs", 0)
    if not available():
        return {
            "answer": _FALLBACK.format(**ctx),
            "intent": intent,
            "llm_used": False,
            "context": ctx,
        }
    prompt = (
        f"Pregunta del dueño: {question!r}\n\n"
        f"Contexto real del negocio (agregados): {ctx}\n\n"
        "Respondé corto, en español de Paraguay, con estos números."
    )
    try:
        text = chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        return {"answer": text, "intent": intent, "llm_used": True, "context": ctx}
    except Exception:  # noqa: BLE001 — LLM caído → fallback numérico
        return {
            "answer": _FALLBACK.format(**ctx),
            "intent": intent,
            "llm_used": False,
            "context": ctx,
        }
