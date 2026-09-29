/**
 * combo-rows.js — row-label builders for saskia-combo.
 *
 * Each builder is a function that takes a row object from the combo's data
 * source and returns the HTML to render in the dropdown / chip. They are
 * attached to `window` so the combo component can look them up by name.
 *
 * Naming: combo consumers opt-in via the `row-label` attribute, e.g.
 *   <saskia-combo row-label="ingredientRowLabel" ...></saskia-combo>
 *
 * Conventions:
 *   - Builders receive the raw row object (server payload keys).
 *   - Builders return HTML strings (safe to set via innerHTML).
 *   - Keep payloads small: don't fetch full entities, just what's shown.
 *
 * Used by: recetas/nueva (ingredient + sub-recipe lines), inventario/nuevo
 * (category picker), merma (ingredient picker), pedidos/nuevo (customer +
 * product pickers).
 */
(function () {
  'use strict';

  /**
   * Generic default row: shows `label` (or `name`) and a subtle `sub` line.
   * The combo component uses this if no row-label is configured.
   */
  function defaultRowLabel(row) {
    if (!row) return '';
    const label = row.label || row.name || row.value || '';
    const sub = row.sub || row.hint || row.unit || row.detail || '';
    if (!sub) return escapeHtml(label);
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(label) +
      '</span><span class="combo-row-sub">' +
      escapeHtml(sub) +
      '</span></span>'
    );
  }

  /** Ingredient row (inventario). Shows name + unit + stock badge. */
  function ingredientRowLabel(row) {
    if (!row) return '';
    const name = row.name || row.label || '';
    const unit = row.unit || '';
    const stock = typeof row.stock_qty === 'number' ? row.stock_qty : null;
    const min = typeof row.min_stock_qty === 'number' ? row.min_stock_qty : 0;
    let badge = '';
    if (stock !== null) {
      const cls = stock <= 0 ? 'is-out' : stock <= min ? 'is-low' : 'is-ok';
      badge =
        '<span class="combo-row-badge combo-row-stock ' +
        cls +
        '">' +
        escapeHtml(formatStock(stock)) +
        (unit ? ' ' + escapeHtml(unit) : '') +
        '</span>';
    } else if (unit) {
      badge = '<span class="combo-row-badge">' + escapeHtml(unit) + '</span>';
    }
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(name) +
      '</span>' +
      badge +
      '</span>'
    );
  }

  /** Sub-recipe row (recetas lines). Shows recipe name + yield. */
  function recipeRowLabel(row) {
    if (!row) return '';
    const name = row.name || row.label || '';
    const yieldQty = row.yield_qty || row.yield || '';
    const yieldUnit = row.yield_unit || row.unit || '';
    const sub = yieldQty ? `Rinde ${yieldQty}${yieldUnit ? ' ' + yieldUnit : ''}` : '';
    return (
      '<span class="combo-row combo-row--recipe"><span class="combo-row-main">' +
      escapeHtml(name) +
      (sub
          ? '</span><span class="combo-row-sub">' + escapeHtml(sub) + '</span>'
          : '</span>') +
      '</span>'
    );
  }

  /** Back-compat alias used by recipe form line picker. */
  function recipeSearchRowLabel(row) {
    return recipeRowLabel(row);
  }

  /** Product row (productos). Shows name + sale price. */
  function productRowLabel(row) {
    if (!row) return '';
    const name = row.name || row.label || '';
    const price = row.sale_price_gs || row.price || '';
    const sub = price ? formatGs(price) : '';
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(name) +
      (sub
          ? '</span><span class="combo-row-sub">' + escapeHtml(sub) + '</span>'
          : '</span>') +
      '</span>'
    );
  }

  /** Customer row (clientes). Shows name + last visit / total spent. */
  function customerRowLabel(row) {
    if (!row) return '';
    const name = row.name || row.label || '';
    const sub = row.phone || row.ruc || row.alias || '';
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(name) +
      (sub
          ? '</span><span class="combo-row-sub">' + escapeHtml(sub) + '</span>'
          : '</span>') +
      '</span>'
    );
  }

  /**
   * Category row (recipe family / inventory category).
   * Highlighted when allow-create is set so the operator knows
   * typing will create a new category.
   */
  function categoryRowLabel(row) {
    if (!row) return '';
    if (row.__isNew) {
      return (
        '<span class="combo-row combo-row--new">' +
        '<span class="combo-row-main">Crear: <strong>' +
        escapeHtml(row.label || row.name || '') +
        '</strong></span>' +
        '<span class="combo-row-sub">nueva categoría</span>' +
        '</span>'
      );
    }
    const name = row.label || row.name || '';
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(name) +
      '</span></span>'
    );
  }

  /** Unit row (recetas lines). Shows the unit + optional display label. */
  function unitRowLabel(row) {
    if (!row) return '';
    const value = row.value || row.label || row.name || '';
    const display = row.display && row.display !== value ? ` (${row.display})` : '';
    return (
      '<span class="combo-row"><span class="combo-row-main">' +
      escapeHtml(value) +
      escapeHtml(display) +
      '</span></span>'
    );
  }

  // ── helpers ────────────────────────────────────────────────────────

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatStock(n) {
    if (n === null || n === undefined) return '';
    if (Number.isInteger(n)) return String(n);
    return n.toFixed(2).replace(/\.?0+$/, '');
  }

  function formatGs(value) {
    const n = Number(value);
    if (!isFinite(n)) return '';
    return 'Gs. ' + n.toLocaleString('es-PY');
  }

  // ── exports ────────────────────────────────────────────────────────

  const builders = {
    defaultRowLabel,
    ingredientRowLabel,
    recipeRowLabel,
    recipeSearchRowLabel,
    productRowLabel,
    customerRowLabel,
    categoryRowLabel,
    unitRowLabel,
  };
  Object.entries(builders).forEach(([k, fn]) => {
    window[k] = fn;
  });

  // Tell saskia-combo where to find the default row-label if none configured.
  document.addEventListener('saskia-combo:init', function (ev) {
    if (ev && ev.detail && ev.detail.combo && !ev.detail.combo._rowLabelFn) {
      ev.detail.combo._rowLabelFn = defaultRowLabel;
    }
  });
})();