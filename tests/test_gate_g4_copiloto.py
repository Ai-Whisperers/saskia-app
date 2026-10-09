"""GATE G4: copiloto — 10 preguntas, sin LLM key (degrade). Verifica:
(1) nunca crash, (2) NUNCA muta (row counts iguales antes/después),
(3) intent correcto por pregunta, (4) números del contexto = DB real.
Correr: .venv/bin/python -m pytest tests/test_gate_g4_copiloto.py -q
"""

from __future__ import annotations

import os

os.environ.pop("ZAI_API_KEY", None)  # fuerza degradación numérica

from app.rms import copilot

PREGUNTAS = [
    ("¿Cuánto vendí hoy?", "hoy"),
    ("¿Cómo va la venta del día?", "hoy"),
    ("¿Quién me debe del fiado?", "fiado"),
    ("¿Cuánto hay en cuentas corrientes?", "fiado"),
    ("¿Qué margen tengo?", "margen"),
    ("¿Cuál es mi hora pico?", "hora_pico"),
    ("¿Qué preparo mañana?", "mañana"),
    ("¿Qué productos están muertos?", "muerto"),
    ("¿Cómo fue la facturación?", "hoy"),
    ("Resumen del negocio", "hoy"),  # fallback intent
]


def test_gate_g4_copiloto_10_preguntas(session_factory, qseed):
    from sqlalchemy import func, select

    from app.rms.models_legacy import CreditTransaction, Sale

    qseed("with_sale")

    session = session_factory()
    sales_before = session.execute(select(func.count()).select_from(Sale)).scalar()
    cred_before = session.execute(select(func.count()).select_from(CreditTransaction)).scalar()

    resultados = []
    for q, expected in PREGUNTAS:
        out = copilot.answer(q, session)
        assert out["llm_used"] is False, "sin key no debe usar LLM"
        assert out["intent"] == expected, f"{q!r}: intent {out['intent']} != {expected}"
        assert isinstance(out["answer"], str) and len(out["answer"]) > 10
        assert "error_contexto" not in out["context"]
        resultados.append((q, out["intent"], out["context"].get("ventas_totales_gs")))

    sales_after = session.execute(select(func.count()).select_from(Sale)).scalar()
    cred_after = session.execute(select(func.count()).select_from(CreditTransaction)).scalar()
    assert (sales_before, cred_before) == (sales_after, cred_after), "¡MUTACIÓN!"

    # números correctos: recalcula ventas de la DB y compara con un intent 'hoy'
    total = 0
    for row in session.execute(
        select(Sale.qty, Sale.unit_price_gs).where(Sale.voided_at.is_(None))
    ).all():
        total += int(row.qty or 0) * int(row.unit_price_gs or 0)
    hoy_ctx = next(r for r in resultados if r[1] == "hoy")
    assert hoy_ctx[2] == total, f"contexto {hoy_ctx[2]} != DB {total}"
    print(f"G4 OK: 10/10 intents, 0 mutaciones, ventas_totales_gs={total:,}")
