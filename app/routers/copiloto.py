"""app/routers/copiloto.py — Fase 3: copiloto IA fase 0 (read-only).

GET  /copiloto      → página chat (chips de preguntas sugeridas)
POST /copiloto/ask  → JSON {question} → answer() (nunca muta)
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.copilot import answer
from app.rms.dependencies import get_session
from app.services.template_render import render

router = APIRouter(prefix="/copiloto", dependencies=[Depends(require_login)])

_CHIPS = [
    "¿Cómo fueron las ventas?",
    "¿A quién le debo cobrar fiado?",
    "¿Qué conviene preparar mañana?",
    "¿Producto con peor margen?",
    "¿Hora más ocupada?",
    "¿Qué tiro que no se vende?",
]


@router.get("", response_class=HTMLResponse)
def page(request: Request) -> HTMLResponse:
    from app.rms.llm import available

    return render(
        request,
        "copiloto.html",
        {"chips": _CHIPS, "llm_available": available()},
    )


@router.post("/ask")
async def ask(request: Request, session: Session = Depends(get_session)) -> JSONResponse:
    # FIX-1 (2026-10-12, found by auto-generated route smoke test):
    # await request.json() raises JSONDecodeError on an empty body. The
    # downstream question-extraction would correctly return 400 "pregunta_vacia"
    # if we got that far, so handle the parse failure the same way.
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "json_invalido"}, status_code=400)
    question = str((body or {}).get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "pregunta_vacia"}, status_code=400)
    if len(question) > 500:
        question = question[:500]
    return JSONResponse(answer(question, session))
