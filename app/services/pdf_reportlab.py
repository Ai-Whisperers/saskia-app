"""app/services/pdf_reportlab.py — Lazy import shim for reportlab.

PDF endpoints import reportlab inside the route function so the heavy
dependency isn't loaded on every request that doesn't need it. This
shim centralizes the import + the friendly error so endpoints don't
have to repeat the try/except.

Why not a top-level import in reportes.py? Reportlab pulls in a
~10MB tree of font support libs. Cold-start cost matters: serverless
deploys time out if the import happens at module load. Lazy imports
keep cold-start fast.
"""
from __future__ import annotations

from fastapi import HTTPException


def import_reportlab() -> dict:
    """Import reportlab and return the names this codebase uses.

    Raises a 503 (Service Unavailable) with a clear install hint if
    reportlab isn't installed. Without this, the missing import would
    surface as a 500 with a stack trace — confusing for operators who
    don't know the codebase.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "PDF generation requires the 'reportlab' package. "
                "Install it via `pip install reportlab>=4.0` or "
                "`uv sync` (it's in pyproject.toml dependencies). "
                f"Underlying error: {exc}"
            ),
        ) from exc
    return {
        "colors": colors,
        "A4": A4,
        "ParagraphStyle": ParagraphStyle,
        "getSampleStyleSheet": getSampleStyleSheet,
        "cm": cm,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


__all__ = ["import_reportlab"]
