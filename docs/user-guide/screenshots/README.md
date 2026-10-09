# User Guide Screenshots

> **Status:** placeholders. Real screenshots are captured by
> `scripts/capture_screenshots.py` (run from inside BWS-authenticated
> environment) and need to be manually added here.

## Required screenshots

For each section of the user guide, capture the corresponding page:

| Section | URL to capture | File |
|---|---|---|
| 00-quickstart | `/login` | `login.png` |
| 00-quickstart | `/` | `dashboard.png` |
| 01-dashboard | `/` | `dashboard.png` |
| 02-ventas | `/ventas` | `ventas.png` |
| 02-ventas (form) | `/ventas` (with form expanded) | `ventas-form.png` |
| 03-inventario | `/inventario` | `inventario.png` |
| 03-inventario (new) | `/inventario/nuevo` | `inventario-nuevo.png` |
| 04-productos | `/productos` | `productos.png` |
| 05-recetas | `/recetas` | `recetas.png` |
| 06-clientes | `/clientes` | `clientes.png` |
| 07-merma | `/merma` | `merma.png` |
| 08-produccion | `/produccion` | `produccion.png` |
| 09-reportes | `/reportes` | `reportes.png` |
| 09-reportes (IVA) | `/reportes/iva` | `reportes-iva.png` |
| 09-reportes (libro) | `/reportes/libro-ventas` | `reportes-libro.png` |
| 09-reportes (diario) | `/reportes/diario` | `reportes-diario.png` |
| 10-auditoria | `/auditoria` | `auditoria.png` |
| 11-configuracion | `/settings` | `settings.png` |
| 12-ops | `/ops/status` | `ops.png` |
| 13-reponer | `/reorder` | `reorder.png` |
| 14-cierre | `/eod` | `cierre.png` |
| 15-excel | `/excel` | `excel.png` |
| 15-excel (exportar) | `/excel/exportar` | `excel-exportar.png` |

## How to capture

1. Run `scripts/capture_screenshots.py` (logs in as `demo@sazon.app`).
2. Save raw HTML output to `/tmp/sazon_pages/`.
3. Use a headless browser (e.g. `playwright` or `chromium --headless`)
   to render HTML → PNG.
4. Drop PNGs into this directory.
5. Update the user-guide markdown to reference each image:

```markdown
![Dashboard principal](00-dashboard.png)
```

## Alternative (no headless browser)

If installing chromium fails, the guide is **still readable** without
screenshots — each section has detailed text descriptions of what the
operator sees. Screenshots are a nice-to-have enhancement.
