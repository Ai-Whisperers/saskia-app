"""replace_placeholders.py — substitute ![placeholder] with real PNG refs in user-guide/*.md.

Each section file maps to one or more screenshots (we already have them in
docs/user-guide/screenshots/). This is a one-shot mapping; new screenshots
replaces previous ones by filename.
"""
from __future__ import annotations
import re
from pathlib import Path

UG_DIR = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/docs/user-guide")
SHOTS = UG_DIR / "screenshots"

# Section file → list of (placeholder_alt_text, screenshot_filename, caption)
MAPPING = [
    ("00-quickstart.md", [
        ("![Pantalla de login — placeholder screenshot]",
         "00-login.png", "Pantalla de inicio de sesión (login)."),
        ("![Pantalla de inicio — placeholder screenshot]",
         "00-dashboard.png", "Pantalla principal al iniciar sesión."),
    ]),
    ("01-dashboard.md", [
        ("![Pantalla de inicio — placeholder screenshot]",
         "00-dashboard.png", "Inicio: resumen del día + avisos."),
    ]),
    ("02-ventas.md", [
        ("![Pantalla de ventas — placeholder screenshot]",
         "01-ventas-pos.png", "Pantalla principal de Ventas — Quick-sell (columna)."),
        ("![Formulario de nueva venta — placeholder screenshot]",
         "01-ventas-pos.png", "Misma pantalla, sección «Nueva venta» (centro)."),
    ]),
    ("03-inventario.md", [
        ("![Pantalla de inventario — placeholder screenshot]",
         "12-inventario.png", "Pantalla principal de Inventario."),
        ("![Formulario de ingrediente nuevo — placeholder screenshot]",
         "13-inventario-nuevo.png", "Formulario para agregar ingrediente."),
    ]),
    ("04-productos.md", [
        ("![Pantalla de productos — placeholder screenshot]",
         "08-productos.png", "Listado de Productos."),
        ("![Formulario de producto nuevo — placeholder screenshot]",
         "09-productos-nuevo.png", "Formulario para crear producto."),
    ]),
    ("05-recetas.md", [
        ("![Pantalla de recetas — placeholder screenshot]",
         "10-recetas.png", "Listado de Recetas."),
        ("![Formulario de receta nueva — placeholder screenshot]",
         "11-recetas-nueva.png", "Formulario para crear receta."),
    ]),
    ("06-clientes.md", [
        ("![Pantalla de clientes — placeholder screenshot]",
         "17-clientes.png", "Listado de Clientes."),
    ]),
    ("07-merma.md", [
        ("![Pantalla de merma — placeholder screenshot]",
         "14-merma.png", "Pantalla de Merma / desperdicio."),
    ]),
    ("08-produccion.md", [
        ("![Pantalla de producción — placeholder screenshot]",
         "05-produccion.png", "Plan de producción del día."),
    ]),
    ("09-reportes.md", [
        ("![Pantalla de reportes — placeholder screenshot]",
         "16-reportes-diario.png", "Reporte diario de ventas."),
    ]),
    ("10-auditoria.md", [
        ("![Pantalla de auditoría — placeholder screenshot]",
         "19-auditoria.png", "Log de auditoría."),
    ]),
    ("11-configuracion.md", [
        ("![Pantalla de configuración — placeholder screenshot]",
         "20-settings.png", "Configuración general."),
    ]),
    ("12-ops.md", [
        ("![Pantalla de ops — placeholder screenshot]",
         "21-ops.png", "Estado operativo (sólo Iván)."),
    ]),
    ("13-reponer.md", [
        ("![Pantalla de reponer — placeholder screenshot]",
         "15-reorder.png", "Pantalla principal de Reposición."),
    ]),
    ("14-cierre.md", [
        ("![Pantalla de cierre — placeholder screenshot]",
         "07-eod-checklist.png", "Cierre diario (EOD) — checklist de 10 ítems."),
    ]),
    ("15-excel.md", [
        ("![Pantalla de Excel — placeholder screenshot]",
         "22-excel.png", "Pantalla de Excel (importar / exportar)."),
    ]),
]


def replace_in_file(path: Path, items: list[tuple[str, str, str]]) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0
    for placeholder, screenshot, caption in items:
        if placeholder in text:
            replacement = f"![{caption}](screenshots/{screenshot})"
            text = text.replace(placeholder, replacement, 1)
            n += 1
    if n:
        path.write_text(text, encoding="utf-8")
    return n


def main():
    total = 0
    for fname, items in MAPPING:
        path = UG_DIR / fname
        if not path.exists():
            print(f"  {fname}: MISSING")
            continue
        n = replace_in_file(path, items)
        print(f"  {fname}: replaced {n}/{len(items)} placeholders")
        total += n
    print(f"\nTotal placeholders replaced: {total}")


if __name__ == "__main__":
    main()