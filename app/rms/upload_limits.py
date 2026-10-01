"""app/rms/upload_limits.py — size/type guard for file upload endpoints.

Phase 14 (security): three upload endpoints lacked size and MIME checks
(/reorder/upload-prices, /pedidos/{token}/comprobante,
/benchmarks/evidencia/importar). Without limits, an operator could
upload a 4 GB binary or an .exe that gets parsed as CSV and crashes
the worker.

Pattern::

    raw = form.get("csv")
    validate_upload(raw, allowed_types=("text/csv", "text/plain"), max_size=2 * 1024 * 1024)
    content = (await raw.read()).decode("utf-8-sig", errors="replace")

`validate_upload` raises HTTPException(415) on bad type and (413) on
oversize. The error message is in Spanish to match the rest of the
operator-facing API.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException, UploadFile


def validate_upload(
    raw: object,
    *,
    allowed_types: Iterable[str],
    max_size: int,
    field_name: str = "file",
) -> UploadFile:
    """Verify `raw` is an UploadFile with an allowed MIME and size <= max_size.

    Returns the same `raw` cast to UploadFile so the caller can use it.
    Raises HTTPException with the standard 415/413 codes so middleware
    and the SPA can surface the error in the right channel.
    """
    from starlette.datastructures import UploadFile as _UploadFile

    if not isinstance(raw, _UploadFile):
        raise HTTPException(
            status_code=400,
            detail=f"Subí un archivo en el campo '{field_name}'.",
        )

    if raw.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Tipo de archivo no permitido: {raw.content_type or 'desconocido'}. "
                f"Usá uno de: {', '.join(sorted(allowed_types))}."
            ),
        )

    # Read the whole body so we can reject BEFORE the caller parses it.
    # The FastAPI UploadFile stream is small enough for our endpoints
    # (CSVs are KB-MB). If max_size is ever bumped to GB we'd want a
    # streaming reader instead.
    raw.file.seek(0)
    content = raw.file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Archivo vacío.",
        )
    if len(content) > max_size:
        size_kb = len(content) // 1024
        max_kb = max_size // 1024
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande ({size_kb} KB). Máximo {max_kb} KB.",
        )
    # Rewind so the caller can read again.
    raw.file.seek(0)
    return raw


# Predefined limits for the three known upload sites. These are kept
# here so the policy lives in one place — the routers don't need to
# know magic numbers.

CSV_LIMIT_2MB = 2 * 1024 * 1024  # /reorder/upload-prices, /benchmarks/evidencia
RECEIPT_LIMIT_5MB = 5 * 1024 * 1024  # /pedidos/{token}/comprobante (images + PDFs)

CSV_MIME_TYPES = ("text/csv", "application/csv", "application/vnd.ms-excel", "text/plain")