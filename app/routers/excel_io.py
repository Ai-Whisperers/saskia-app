"""app/routers/excel_io.py — Excel import + export UI endpoints.

Per dev plan §9 Task 6 + v2 §6 (Excel I/O).

Endpoints:
- GET  /excel                    — page listing recent import batches
- POST /excel/importar?mode=...  — upload .xlsx, import into DB
                                   mode=PATCH (default) | FULL
- GET  /excel/exportar           — download current DB state as .xlsx (FULL)
- GET  /excel/plantilla          — download PATCH plantilla (.xlsx)
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.models import ImportBatch
from app.services.template_render import render

router = APIRouter(prefix="/excel", dependencies=[Depends(require_login)])

# Mode whitelist — anything else raises 422.
VALID_MODES = ("PATCH", "FULL")


def _resolve_mode(mode: str | None) -> str:
    """Validate mode query param. None or empty → PATCH (safer default).

    Raises HTTPException(422) on invalid value.
    """
    if mode is None or mode == "":
        return "PATCH"
    normalized = mode.upper()
    if normalized not in VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"mode inválido: {mode!r}; esperado uno de {VALID_MODES}",
        )
    return normalized


@router.get("", response_class=HTMLResponse)
async def excel_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Excel page: list recent import batches + import/export buttons."""
    batches = session.scalars(
        select(ImportBatch).order_by(ImportBatch.imported_at.desc()).limit(10)
    ).all()
    last_import = None
    if batches:
        b = batches[0]
        raw = b.row_counts_json
        if isinstance(raw, str):
            try:
                counts = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                counts = {}
        else:
            counts = raw or {}
        last_import = {
            "filename": b.source_filename,
            "imported_at_str": b.imported_at.strftime("%d/%m/%Y %H:%M"),
            "mode": counts.get("mode", "FULL"),
            "ingredients": counts.get("ingredients", 0),
            "recipes": counts.get("recipes", 0),
            "lines": counts.get("lines", 0),
            "products": counts.get("products", 0),
            "customers": counts.get("customers", 0),
            "warnings": counts.get("warnings", []),
        }

    return render(request, "excel.html", {"last_import": last_import})


@router.post("/importar")
async def excel_import(
    request: Request,
    session: Session = Depends(get_session),
    mode: str = Query(default="PATCH", description="PATCH (default) | FULL"),
) -> RedirectResponse:
    """Import an uploaded .xlsx file.

    `mode=PATCH` (default) updates existing rows by natural key — Productos
    by name or sku, Clientes by phone (creating new ones), Ingredientes and
    Recetas by name. No data is destroyed.

    `mode=FULL` is the legacy additive import — appends rows to existing tables.
    """
    resolved_mode = _resolve_mode(mode)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename"):
        raise HTTPException(status_code=400, detail="Subí un archivo .xlsx")
    filename = getattr(file, "filename", "") or ""
    if not filename or not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo tiene que ser .xlsx")

    # Save uploaded file to a secure temp location
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    # Use a per-request temp dir so concurrent imports don't clash
    with tempfile.TemporaryDirectory(prefix="saskia-import-") as tmp_dir:
        save_path = Path(tmp_dir) / filename
        save_path.write_bytes(content)
        try:
            from app.services.import_xlsx import from_file

            from_file(session, save_path, mode=resolved_mode)  # type: ignore[arg-type]
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Redirect back to /excel with the last batch shown
    return RedirectResponse(url="/excel", status_code=303)


@router.get("/exportar")
async def excel_export(request: Request, session: Session = Depends(get_session)) -> FileResponse:
    """Export current DB state to a HEREBUS-format .xlsx."""
    from app.services.export_xlsx import to_file

    # Use a temp file so concurrent exports don't overwrite each other
    fd, tmp_path_str = tempfile.mkstemp(prefix="saskia-export-", suffix=".xlsx")
    os.close(fd)  # let openpyxl open it
    tmp_path = Path(tmp_path_str)
    try:
        written = to_file(session, tmp_path)
        # FileResponse will read + delete via the temp file pattern
        return FileResponse(
            path=str(written),
            filename="saskia-rms-export.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        # Clean up temp file on failure
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


@router.get("/plantilla")
async def excel_plantilla(
    session: Session = Depends(get_session),
) -> Response:
    """Download a PATCH plantilla (.xlsx) pre-populated with current rows.

    The operator can edit it at home (Drive, Excel, Numbers, etc.) and
    re-upload via POST /excel/importar?mode=PATCH for incremental updates.

    Filename: saskia-import-YYYYMMDD.xlsx
    """
    from app.services.export_xlsx import patch_plantilla_bytes

    body = patch_plantilla_bytes(session)
    today = datetime.utcnow().strftime("%Y%m%d")
    filename = f"saskia-import-{today}.xlsx"
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
