"""app/routers/copiloto.py — Fase 3: copiloto IA fase 0 (read-only).

GET  /copiloto      → página chat (chips de preguntas sugeridas)
POST /copiloto/ask  → JSON {question} → answer() (nunca muta)
"""

from __future__ import annotations

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
    body = await request.json()
    question = str((body or {}).get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "pregunta_vacia"}, status_code=400)
    if len(question) > 500:
        question = question[:500]
    return JSONResponse(answer(question, session))
