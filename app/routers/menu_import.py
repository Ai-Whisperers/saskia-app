"""app/routers/menu_import.py — Fase 3: importar carta por foto (OCR).

POST /menu-import/ocr          → upload multipart → preview JSON
                                 (NUNCA inserta directo — guardarraíl)
POST /menu-import/ocr/confirm  → filas confirmadas (checkboxes) →
                                 import_menu_csv inserta/actualiza
GET  /menu-import/ocr          → página con el form de upload

Sin ZAI_API_KEY configurada: /ocr devuelve 503 con mensaje claro.
Preview obligatorio: el confirm sólo procesa las filas que el
operador marcó en la tabla editable.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.csrf import verify_form_csrf
from app.rms.dependencies import get_session
from app.rms.menu_ocr import match_to_catalog, parse_menu_image
from app.rms.observability import record_audit
from app.rms.seed.menu_import import import_menu_csv
from app.services.template_render import render

router = APIRouter(prefix="/menu-import", dependencies=[Depends(require_login)])

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.get("/ocr", response_class=HTMLResponse)
def ocr_page(request: Request) -> HTMLResponse:
    from app.rms.llm import available

    return render(
        request,
        "menu_import_ocr.html",
        {"ocr_available": available(), "preview": None},
    )


@router.post("/ocr")
async def ocr_upload(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from app.rms.llm import LLMError, available

    if not available():
        return render(
            request,
            "menu_import_ocr.html",
            {"ocr_available": False, "error": "OCR no configurado (falta ZAI_API_KEY)."},
            status_code=503,
        )
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype not in _ALLOWED_MIME:
        return render(
            request,
            "menu_import_ocr.html",
            {"ocr_available": True, "error": "Formato no soportado (usá JPG/PNG/WebP/PDF)."},
        )
    raw = await file.read()
    try:
        lines = parse_menu_image(raw, mime=ctype)
    except LLMError as e:
        return render(
            request,
            "menu_import_ocr.html",
            {"ocr_available": True, "error": f"OCR falló: {e}"},
        )
    result = match_to_catalog(lines, session)
    return render(
        request,
        "menu_import_ocr.html",
        {
            "ocr_available": True,
            "preview": {
                "matched": [
                    {
                        "name": ln.name,
                        "price_gs": ln.price_gs,
                        "category": ln.category,
                        "product_id": ln.product_id,
                    }
                    for ln in result.matched
                ],
                "nuevos": [
                    {"name": ln.name, "price_gs": ln.price_gs, "category": ln.category}
                    for ln in result.nuevos
                ],
                "dudosos": [
                    {"name": ln.name, "price_gs": ln.price_gs, "category": ln.category}
                    for ln in result.dudosos
                ],
            },
        },
    )


@router.post("/ocr/confirm")
async def ocr_confirm(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    await verify_form_csrf(request)
    form = await request.form()
    # Filas confirmadas llegan como JSON en el campo rows (solo las
    # chequeadas, ya editadas por el operador en la tabla preview).
    raw_rows = form.get("rows") or "[]"
    try:
        confirmed = json.loads(str(raw_rows))
    except json.JSONDecodeError:
        confirmed = []
    if not isinstance(confirmed, list) or not confirmed:
        return RedirectResponse("/menu-import/ocr?flash=ocr_empty", status_code=303)
    # Convertir a CSV y reusar import_menu_csv (dry_run=False): misma
    # vía que la importación manual → mismas validaciones y audit.
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["nombre", "precio", "categoria"])
    for r in confirmed:
        if not isinstance(r, dict) or not str(r.get("name") or "").strip():
            continue
        w.writerow([r.get("name"), r.get("price_gs") or "", r.get("category") or ""])
    report = import_menu_csv(session, buf.getvalue(), dry_run=False)
    record_audit(
        request,
        session=session,
        action="menu_import_ocr",
        target_type="product",
        target_id=None,
        detail={"rows": len(report.rows)},
    )
    counts = report.counts
    return RedirectResponse(
        f"/menu-import/ocr?flash=ocr_ok&creados={counts.get('created', 0)}"
        f"&actualizados={counts.get('price_updated', 0)}",
        status_code=303,
    )
