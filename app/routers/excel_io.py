"""app/routers/excel_io.py — Excel import + export UI endpoints.

Per dev plan §9 Task 6.

Note: the actual import_xlsx / export_xlsx service code lands in Batch 4.
For Batch 2, we ship the UI shell + a placeholder route handler.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.services.template_render import render

router = APIRouter(prefix="/excel")


def get_session(request: Request) -> Session:
    return request.app.state.session_factory()


@router.get("", response_class=HTMLResponse)
async def excel_home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    """Excel page: list recent import batches + import/export buttons."""
    from sqlalchemy import select

    from app.rms.models import ImportBatch

    batches = session.scalars(
        select(ImportBatch).order_by(ImportBatch.imported_at.desc()).limit(10)
    ).all()
    last_import = None
    if batches:
        b = batches[0]
        last_import = {
            "filename": b.source_filename,
            "imported_at_str": b.imported_at.strftime("%d/%m/%Y %H:%M"),
            "ingredients": 0,
            "recipes": 0,
            "lines": 0,
            "products": 0,
            "warnings": [],
        }

    return render(request, "excel.html", {"last_import": last_import})


@router.post("/importar")
async def excel_import(
    request: Request,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Import an uploaded .xlsx file. (Stub — full implementation lands in Batch 4.)"""
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "filename"):
        raise HTTPException(status_code=400, detail="Subí un archivo .xlsx")
    filename = getattr(file, "filename", "")
    if not filename or not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo tiene que ser .xlsx")

    # Save uploaded file to temp location
    import os

    save_dir = "/tmp/saskia-imports"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # TODO (Batch 4): call app.services.import_xlsx.from_file(save_path)
    # For now, just record that we received it.
    raise HTTPException(
        status_code=501,
        detail=(
            f"Importar Excel no está implementado todavía (llega en Batch 4). "
            f"Archivo recibido: {filename} ({len(content)} bytes)."
        ),
    )


@router.get("/exportar")
async def excel_export(request: Request) -> FileResponse:
    """Export current data to .xlsx. (Stub — full implementation lands in Batch 4.)"""
    # TODO (Batch 4): call app.services.export_xlsx.to_file() and return FileResponse.
    raise HTTPException(
        status_code=501,
        detail="Exportar Excel no está implementado todavía (llega en Batch 4).",
    )


__all__ = ["router"]
