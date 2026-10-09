# BACKLOG: ruff findings in held_sale (sibling commit `c266f6e2`)

**Detectado:** 2026-10-07 · **Cerrado:** 2026-10-07 (commit `b1f3e2c4` post-sibling)
**Severidad:** baja — bloqueante, sin bloquear
**Detectado por:** post-P40 sanity check de la sesión de Iván

## Estado actual

`app/rms/held_sales.py` (lanzado en `c266f6e2 feat(pos): hold-sale`) tenía
4 hallazgos de `ruff check`. Todos cerrados en `b1f3e2c4`:

1. ✅ **`I001` (auto-fix):** import sort + `noqa: F401` reposicionado —
   resuelto con `ruff check --fix --select I001,W292`.
2. ✅ **`W292` (auto-fix):** newline al final del archivo — mismo fix.
3. ✅ **`ANN202` (manual):** `_now_asuncion()` ahora anota `-> datetime`;
   se agregó `from datetime import datetime`.
4. ✅ **`S608` (manual, falso positivo):** el `UPDATE held_sale ... IN (...)`
   sigue usando `", ".join(":" + ...)` para los placeholders y los IDs
   como bound params. Es seguro (no es user input). Se documentó con
   `# noqa: S608 — bound params, see above` apuntando al comentario
   preexistente que justifica la decisión.

## Tests

`pytest tests/test_held_sales.py tests/test_held_sales_routes.py -q` →
**25/25 pasan** (incluye tests del auto-evict que ejercita la query del
hallazgo #4). Sin regresiones.

## Resultado de ruff

`ruff check app/rms/held_sales.py` → exit 0, "All checks passed!"

## Cierre

Este item queda cerrado. Si ruff aprende a validar `", ".join(":" + ...)` en
el futuro (probablemente nunca), se puede refactorizar a
`IN (SELECT id FROM UNNEST(:ids))` con array bind — pero no es prioritario.