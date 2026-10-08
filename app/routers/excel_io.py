"""app/routers/excel_io.py — Excel import + export UI endpoints.

Per dev plan §9 Task 6 + v2 §6 (Excel I/O).

Endpoints:
- GET  /excel                    — page listing recent import batches
- POST /excel/importar?mode=...  — upload .xlsx, import into DB
                                   mode=PATCH (default) | FULL
- GET  /excel/validar            — dry-run: validate file and return errors without writing
- GET  /excel/exportar           — download current DB state as .xlsx (FULL)
- GET  /excel/plantilla          — download PATCH plantilla (.xlsx)
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.dependencies import get_session
from app.rms.errors import BadRequest
from app.rms.models import ImportBatch
from app.rms.observability import record_audit
from app.services.template_render import render

router = APIRouter(prefix="/excel", dependencies=[Depends(require_login)])

VALID_MODES = ("PATCH", "FULL", "APPEND")


def _resolve_mode(mode: str | None) -> str:
    if mode is None or mode == "":
        return "PATCH"
    normalized = mode.upper()
    if normalized not in VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"mode inválido: {mode!r}; esperado uno de {VALID_MODES}",
        )
    return normalized


# ─── Home page ──────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
async def excel_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Excel page: list recent import batches + import/export buttons."""
    batches = session.scalars(
        select(ImportBatch).order_by(ImportBatch.imported_at.desc()).limit(20)
    ).all()

    import_history = []
    for b in batches:
        raw = b.row_counts_json
        if isinstance(raw, str):
            try:
                counts = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                counts = {}
        else:
            counts = raw or {}

        # Parse warnings
        warnings_raw = counts.get("warnings", [])
        if isinstance(warnings_raw, str):
            try:
                warnings_raw = json.loads(warnings_raw)
            except (json.JSONDecodeError, TypeError):
                warnings_raw = [warnings_raw] if warnings_raw else []

        import_history.append(
            {
                "id": b.id,
                "filename": b.source_filename,
                "imported_at_str": b.imported_at.strftime("%d/%m/%Y %H:%M")
                if b.imported_at
                else "",
                "mode": counts.get("mode", "FULL"),
                "ingredients": counts.get("ingredients", 0),
                "recipes": counts.get("recipes", 0),
                "lines": counts.get("lines", 0),
                "products": counts.get("products", 0),
                "customers": counts.get("customers", 0),
                "warnings": warnings_raw,
            }
        )

    return render(request, "excel.html", {"import_history": import_history})


# ─── Mode guidance ───────────────────────────────────────────────────────────


@router.get("/mode-guidance", response_class=HTMLResponse)
async def excel_mode_guidance(request: Request) -> HTMLResponse:
    """Explain the three import modes: FULL, PATCH, APPEND."""
    guidance = [
        {
            "mode": "PATCH",
            "label": "Actualizar por nombre (PATCH)",
            "summary": "Recomendado para mantener tus datos actualizados.",
            "how": "Compara por nombre (productos, ingredientes, recetas) o teléfono (clientes). "
            "Actualiza las celdas que editás en el archivo. No borra nada existente.",
            "use_case": "Editaste precios de productos en la планilla y querés subir los cambios.",
            "danger": "safe",
            "color": "#22c55e",
        },
        {
            "mode": "FULL",
            "label": "Reemplazar todo (FULL)",
            "summary": "Añade filas del archivo SIN pisar las anteriores. No recomendado para actualizaciones.",
            "how": "Añade todas las filas del archivo a las tablas existentes. "
            "Si ya existe un producto con el mismo nombre, se crea otro igual (duplicado).",
            "use_case": "Necesitás restaurar un backup completo sin perder datos previos.",
            "danger": "caution",
            "color": "#f59e0b",
        },
        {
            "mode": "APPEND",
            "label": "Solo añadir (APPEND)",
            "summary": "Añade filas únicamente — sin actualizar nada existente.",
            "how": "Toma cada fila del archivo y la inserta como nueva. "
            "Los datos existentes quedan intactos.",
            "use_case": "Cargaste clientes nuevos a la планilla y querés agregarlos sin tocar los existentes.",
            "danger": "safe",
            "color": "#22c55e",
        },
    ]
    return render(request, "excel_mode_guidance.html", {"guidance": guidance})


# ─── Pre-import validation (dry-run) ───────────────────────────────────────


@router.post("/validar")
async def excel_validate(
    request: Request,
    session: Session = Depends(get_session),
    mode: str = Form(default="PATCH"),
) -> HTMLResponse:
    """Dry-run: validate an uploaded .xlsx without writing to DB.

    Returns a list of errors (row, field, message) and warnings.
    """
    resolved_mode = _resolve_mode(mode)
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename"):
        raise HTTPException(status_code=400, detail="Subí un archivo .xlsx")
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo tiene que ser .xlsx")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    errors: list[dict] = []
    warnings: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="sazon-validate-") as tmp_dir:
        save_path = Path(tmp_dir) / filename
        save_path.write_bytes(content)
        try:
            from app.services.import_xlsx import DryRunResult, from_file

            result: DryRunResult = from_file(session, save_path, mode=resolved_mode, dry_run=True)  # type: ignore[arg-type]
            errors = result.errors
            warnings = result.warnings
        except FileNotFoundError as exc:
            raise BadRequest(
                "Sheet no encontrado.",
                context={"original_error": str(exc)},
            ) from exc
        except ValueError as exc:
            raise BadRequest(
                "Datos inválidos en el archivo Excel.",
                context={"original_error": str(exc)},
            ) from exc

    return render(
        request,
        "excel_validate.html",
        {
            "filename": filename,
            "mode": resolved_mode,
            "errors": errors,
            "warnings": warnings,
            "has_errors": bool(errors),
        },
    )


# ─── Actual import (with audit log) ─────────────────────────────────────────


@router.post("/importar")
async def excel_import(
    request: Request,
    session: Session = Depends(get_session),
    mode: str = Form(default="PATCH"),
) -> RedirectResponse:
    """Import an uploaded .xlsx file.

    `mode=PATCH` (default) updates existing rows by natural key.
    `mode=FULL` appends all rows from the file.
    `mode=APPEND` only inserts new rows (no updates).
    Results are logged to the audit log.
    """
    resolved_mode = _resolve_mode(mode)

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename"):
        raise HTTPException(status_code=400, detail="Subí un archivo .xlsx")
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo tiene que ser .xlsx")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    row_counts: dict = {}

    with tempfile.TemporaryDirectory(prefix="sazon-import-") as tmp_dir:
        save_path = Path(tmp_dir) / filename
        save_path.write_bytes(content)
        try:
            from app.services.import_xlsx import from_file

            result = from_file(session, save_path, mode=resolved_mode)  # type: ignore[arg-type]
            row_counts = result.row_counts()
        except FileNotFoundError as exc:
            raise BadRequest(
                "Archivo Excel no encontrado.",
                context={"original_error": str(exc)},
            ) from exc
        except ValueError as exc:
            raise BadRequest(
                "Datos inválidos al importar Excel.",
                context={"original_error": str(exc)},
            ) from exc
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail="El archivo tiene filas que ya existen (nombres duplicados). "
                "Usá modo PATCH para actualizar, o revisá los nombres.",
            ) from exc

    # Record import in audit log
    batch_id = row_counts.get("batch_id", 0)
    rows_imported = sum(
        v
        for k, v in row_counts.items()
        if k in {"ingredients", "recipes", "lines", "products", "customers", "sales"}
    )
    warnings_count = len(row_counts.get("warnings", []))
    record_audit(
        request,
        session=session,
        action="write.excel.import",
        target_type="excel",
        target_id=batch_id,
        detail={
            "filename": filename,
            "mode": resolved_mode,
            "rows_imported": int(rows_imported),
            "rows_failed": warnings_count,
        },
    )
    session.commit()
    return RedirectResponse(url="/excel", status_code=303)


# ─── Export ──────────────────────────────────────────────────────────────────


@router.get("/exportar")
async def excel_export(
    request: Request,
    period: str = Query(
        "current_month",
        pattern="^(current_month|last_month|30d|today|all)$",
    ),
    session: Session = Depends(get_session),
) -> FileResponse:
    """Export current DB state to a HEREBUS-format .xlsx.

    Default period is ``current_month`` so the most common reason to hit
    this button — month-end close — works with one click. Use ``?period=all``
    to get the full history (the previous behavior).
    """
    from app.services.export_xlsx import to_file

    fd, tmp_path_str = tempfile.mkstemp(prefix="sazon-export-", suffix=".xlsx")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        written = to_file(session, tmp_path, period=period)
        # Filename reflects the chosen period so operators can keep multiple
        # exports side-by-side without renaming.
        filename = {
            "current_month": "sazon-rms-export-mes-actual.xlsx",
            "last_month": "sazon-rms-export-mes-anterior.xlsx",
            "30d": "sazon-rms-export-30d.xlsx",
            "today": "sazon-rms-export-hoy.xlsx",
            "all": "sazon-rms-export-completo.xlsx",
        }[period]
        return FileResponse(
            path=str(written),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        try:
            tmp_path.unlink()  # noqa: ASYNC240
        except OSError as exc:
            # Temp file cleanup; if the OS already removed it, not an error.
            logger.debug("excel_io tmp cleanup skipped: {}", exc)
        raise


@router.get("/plantilla")
async def excel_plantilla(
    session: Session = Depends(get_session),
) -> Response:
    """Download a PATCH plantilla (.xlsx) pre-populated with current rows.

    Columns marked as [REQUIRED] or [OPTIONAL] in the header row.
    """
    from app.services.export_xlsx import patch_plantilla_bytes

    body = patch_plantilla_bytes(session)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"sazon-import-{today}.xlsx"
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
