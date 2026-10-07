# BACKLOG: ruff findings in held_sale (sibling commit `c266f6e2`)

**Detectado:** 2026-10-07 · **Severidad:** baja — bloqueante, sin bloquear
**Detectado por:** post-P40 sanity check de la sesión de Iván

## Estado actual

`app/rms/held_sales.py` (lanzado en `c266f6e2 feat(pos): hold-sale`) tiene 4 hallazgos
de `ruff check`:

1. **`I001` (auto-fix):** `app/rms/held_sales.py:33` — bloque de imports desordenado
   (mezcla `from __future__` con stdlib y third-party). `# noqa: F401` también
   está mal puesto. 1 fix con `ruff check --fix`.
2. **`W292` (auto-fix):** `app/rms/held_sales.py:246` — falta newline al final
   del archivo. 1 fix con `ruff check --fix`.
3. **`ANN202` (manual):** `app/rms/held_sales.py:47` — `_now_asuncion()` no tiene
   anotación de retorno. Agregar `-> datetime` (el `to_asuncion().replace(
   tzinfo=None)` retorna un `datetime` naive).
4. **`S608` (manual, posiblemente falso positivo):** `app/rms/held_sales.py:116`
   — el `UPDATE held_sale ... WHERE id IN (...)` arma la `IN (...)` con
   `", ".join(":" + key for key in param_keys)` y los IDs van como bound params
   en el dict `params`. **Es seguro** (los IDs son ints propios, no user input),
   pero ruff no puede seguir la indirección. Opciones:
   (a) agregar `# noqa: S608` con justificación, o
   (b) refactorizar a `IN (SELECT id FROM UNNEST(...))` con un array bind, que
   ruff sí entiende como safe.

## Tests

`pytest tests/test_held_sales.py tests/test_held_sales_routes.py -q` →
**25/25 pasan** (incluye tests del auto-evict que ejercita la query del
hallazgo #4). El código funciona; esto es deuda de estilo, no bug.

## Recomendación

Cerrar con `ruff check --fix` (1 + 2) más la anotación de retorno (3) en el
próximo pass sobre held_sale. Para #4, dejar la `# noqa: S608` con la
justificación de 1 línea y abrir issue aparte si ruff aprende a validar
`", ".join(":" + ...)` (probablemente nunca).

## Contexto

Hold-sale (B-7 port desde `Hao0321/pos-pro`, MIT) es la próxima feature en
producción. Iván punted 2026-10-07. No bloquea a held_sale, pero CI puede
flaquear si la regla S608 sube a error.