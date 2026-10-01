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

  /**
   * Customer row (clientes). Three stacked lines so the cashier can
   * scan name, phone, email and tier at a glance.
   *
   * T-2026-10-01: previously this returned a single cramped line
   * "Name 0982515138" with no spacing. Replaced with a 3-line layout:
   *   Line 1: Name (bold) + tier badge (right) when set
   *   Line 2: phone (📞) + CI/RUC (🪪)
   *   Line 3: email (✉) when set, dietary chip (⚠) when restricted
   *           + lifetime spend chip on the right (₲)
   *
   * The dropdown stays scannable at a glance — operators no longer
   * have to squint at squished text or open the customer card to
   * see what phone/email belong to whom.
   */
  function customerRowLabel(row) {
    if (!row) return '';
    const name = row.name || row.label || '';

    // --- Line 1: name + tier badge ---
    const tierRaw = (row.tier || '').toString().toLowerCase();
    const tierLabel = {
      bronze: '🥉',
      silver: '🥈',
      gold: '🥇',
      platinum: '💎',
    }[tierRaw] || '';
    const tierName = tierRaw ? tierRaw.charAt(0).toUpperCase() + tierRaw.slice(1) : '';
    const tierChip = tierRaw
      ? `<span class="combo-row-tier combo-row-tier--${escapeHtml(tierRaw)}" aria-label="Tier ${escapeHtml(tierName)}">${
          tierLabel ? tierLabel + ' ' : ''
        }${escapeHtml(tierName)}</span>`
      : '';

    // --- Line 2: phone + CI/RUC ---
    const phoneStr = row.phone ? '📞 ' + escapeHtml(row.phone) : '';
    const cedulaStr = row.cedula ? '🪪 ' + escapeHtml(row.cedula) : '';
    const line2 = [phoneStr, cedulaStr].filter(Boolean).join(' &nbsp;·&nbsp; ');
    const line2Html = line2
      ? `<span class="combo-row-line combo-row-line--contact">${line2}</span>`
      : '';

    // --- Line 3: email + dietary + lifetime ---
    const emailStr = row.email
      ? '<span class="combo-row-line-part">✉ ' + escapeHtml(row.email) + '</span>'
      : '';
    const dietaryArr = Array.isArray(row.dietary_restrictions) ? row.dietary_restrictions : [];
    const dietaryStr = dietaryArr.length
      ? '<span class="combo-row-chip combo-row-chip--warn" title="Restricciones: ' +
        escapeHtml(dietaryArr.join(', ')) +
        '">⚠ ' + escapeHtml(dietaryArr.length + ' restricción' + (dietaryArr.length === 1 ? '' : 'es')) + '</span>'
      : '';
    const lifetimeStr = row.lifetime_label
      ? '<span class="combo-row-line-part combo-row-line-part--meta">₲ ' + escapeHtml(row.lifetime_label) + '</span>'
      : '';
    const leftLine3 = [emailStr, dietaryStr].filter(Boolean).join(' ');
    const rightLine3 = lifetimeStr;
    const line3Parts = [];
    if (leftLine3) line3Parts.push(leftLine3);
    if (rightLine3) line3Parts.push(rightLine3);
    const line3Html = line3Parts.length
      ? `<span class="combo-row-line combo-row-line--meta">${line3Parts.join(' &nbsp;')}</span>`
      : '';

    return (
      '<span class="combo-row combo-row--customer">' +
      '<span class="combo-row-main">' +
      '<span class="combo-row-line combo-row-line--name">' + escapeHtml(name) + '</span>' +
      line2Html +
      line3Html +
      '</span>' +
      tierChip +
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