/* app/static/app-components.js — drawer, row-actions, stepper JS (no frameworks). */
(function () {
  'use strict';

  // ── A-11 drawer ───────────────────────────────────────────────────
  var UIDrawer = {
    _ensureShell: function () {
      if (document.getElementById('ui-drawer')) return;
      var bd = document.createElement('div');
      bd.className = 'drawer-backdrop'; bd.id = 'ui-drawer-backdrop';
      bd.addEventListener('click', function () { UIDrawer.close(); });
      var d = document.createElement('aside');
      d.className = 'drawer'; d.id = 'ui-drawer'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true');
      d.innerHTML = '<div class="drawer__header"><h2 class="drawer__title" id="ui-drawer-title"></h2>' +
        '<button type="button" class="btn btn-ghost" aria-label="Cerrar" data-drawer-close>✕</button></div>' +
        '<div class="drawer__body" id="ui-drawer-body"></div>' +
        '<div class="drawer__footer" id="ui-drawer-footer"></div>';
      document.body.appendChild(bd); document.body.appendChild(d);
      d.addEventListener('click', function (e) {
        if (e.target.closest('[data-drawer-close]')) UIDrawer.close();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') UIDrawer.close();
      });
    },
    open: function (title, bodyHtml, footerHtml) {
      this._ensureShell();
      document.getElementById('ui-drawer-title').textContent = title;
      document.getElementById('ui-drawer-body').innerHTML = bodyHtml;
      document.getElementById('ui-drawer-footer').innerHTML = footerHtml || '';
      document.getElementById('ui-drawer-backdrop').classList.add('is-open');
      document.getElementById('ui-drawer').classList.add('is-open');
      var first = document.querySelector('#ui-drawer-body input, #ui-drawer-body select, #ui-drawer-body button');
      if (first) first.focus();
    },
    close: function () {
      var b = document.getElementById('ui-drawer-backdrop'), d = document.getElementById('ui-drawer');
      if (b) b.classList.remove('is-open');
      if (d) d.classList.remove('is-open');
    }
  };
  window.UIDrawer = UIDrawer;

  // ── A-10 row-actions: close menus on outside click ────────────────
  document.addEventListener('click', function (e) {
    document.querySelectorAll('.row-actions__more[open]').forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute('open');
    });
  });

  // ── multi-filter popovers (inventario toolbar) ─────────────────────
function uncheckOthers(el) { /* radio "Todos" — native radios already exclusive */ }
document.addEventListener('click', function (e) {
  var pop = e.target.closest('.mf-pop');
  document.querySelectorAll('.mf-pop').forEach(function (p) {
    if (p !== pop) { var pn = p.querySelector('.mf-panel'); if (pn) pn.hidden = true; p.querySelector('.mf-btn').setAttribute('aria-expanded','false'); }
  });
  if (pop && e.target.closest('.mf-btn')) {
    var panel = pop.querySelector('.mf-panel');
    panel.hidden = !panel.hidden;
    pop.querySelector('.mf-btn').setAttribute('aria-expanded', String(!panel.hidden));
  }
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') document.querySelectorAll('.mf-panel').forEach(function (p) { p.hidden = true; });
});

// ── A-13 stepper: no JS needed (server-rendered state) ────────────

  // ── A-16 timer chips: auto-tick from data-start ───────────────────
  function tickTimers() {
    document.querySelectorAll('.timer-chip[data-start]').forEach(function (el) {
      var started = new Date(el.dataset.start + 'Z');
      if (isNaN(started)) return;
      var mins = Math.floor((Date.now() - started.getTime()) / 60000);
      var sev = mins > 30 ? 'danger' : mins > 15 ? 'warn' : 'ok';
      el.className = 'timer-chip is-' + sev;
      el.textContent = mins + ' min';
    });
  }
  if (document.querySelector('.timer-chip[data-start]')) {
    tickTimers(); setInterval(tickTimers, 30000);
  }
})();

// ── chip-toggle groups → hidden comma-joined field ──────────────────
document.addEventListener('change', function (e) {
  var t = e.target;
  if (t && t.dataset.allergen !== undefined) {
    var codes = Array.prototype.map.call(
      document.querySelectorAll('[data-allergen]:checked'),
      function (c) { return c.dataset.allergen; });
    document.getElementById('allergens').value = codes.join(',');
  }
  if (t && t.dataset.dietary !== undefined) {
    var dCodes = Array.prototype.map.call(
      document.querySelectorAll('[data-dietary]:checked'),
      function (c) { return c.dataset.dietary; });
    document.getElementById('dietary_tags').value = dCodes.join(',');
  }
});

// ── UIConfirmModal: Promise-based confirm() replacement ─────────────
window.UIConfirmModal = (function () {
  var _ensureShell = function () {
    if (document.getElementById('ui-confirm')) return;
    var bd = document.createElement('div');
    bd.className = 'confirm-backdrop'; bd.id = 'ui-confirm-backdrop';
    var d = document.createElement('aside');
    d.className = 'confirm-modal'; d.id = 'ui-confirm'; d.setAttribute('role', 'alertdialog');
    d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-labelledby', 'ui-confirm-title');
    d.setAttribute('aria-describedby', 'ui-confirm-body');
    d.innerHTML =
      '<div class="confirm-modal__header">' +
      '  <svg class="confirm-modal__icon" aria-hidden="true"><use href="#icon-warn"/></svg>' +
      '  <h2 class="confirm-modal__title" id="ui-confirm-title">Confirmar</h2>' +
      '</div>' +
      '<div class="confirm-modal__body" id="ui-confirm-body"></div>' +
      '<div class="confirm-modal__footer">' +
      '  <button type="button" class="btn btn-ghost" data-confirm-cancel>Cancelar</button>' +
      '  <button type="button" class="btn btn-danger" data-confirm-ok>Confirmar</button>' +
      '</div>';
    document.body.appendChild(bd); document.body.appendChild(d);
    bd.addEventListener('click', function () { _close(false); });
    d.addEventListener('click', function (e) {
      if (e.target.closest('[data-confirm-cancel]')) _close(false);
      if (e.target.closest('[data-confirm-ok]')) _close(true);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.getElementById('ui-confirm').open) _close(false);
      if (e.key === 'Enter' && document.getElementById('ui-confirm').open) _close(true);
    });
  };
  var _close = function (ok) {
    var d = document.getElementById('ui-confirm');
    var bd = document.getElementById('ui-confirm-backdrop');
    if (!d) return;
    d.classList.remove('open'); bd.classList.remove('open');
    d.open = false;
    var p = d._pending; d._pending = null;
    if (p) p(ok);
  };
  return {
    show: function (opts) {
      _ensureShell();
      opts = opts || {};
      var d = document.getElementById('ui-confirm');
      var bd = document.getElementById('ui-confirm-backdrop');
      document.getElementById('ui-confirm-title').textContent = opts.title || '¿Estás seguro?';
      document.getElementById('ui-confirm-body').textContent = opts.body || 'Esta acción no se puede deshacer.';
      var okBtn = d.querySelector('[data-confirm-ok]');
      okBtn.textContent = opts.confirmLabel || 'Confirmar';
      okBtn.className = opts.danger === false ? 'btn btn-primary' : 'btn btn-danger';
      d.classList.add('open'); bd.classList.add('open');
      d.open = true;
      setTimeout(function () { okBtn.focus(); }, 30);
      return new Promise(function (resolve) {
        d._pending = resolve;
      });
    },
    close: function (ok) { _close(ok); }
  };
})();

// ── UISortTable: client-side table sorting ────────────────────────────
// Sort a table by the numeric content of a single column (descending).
// Usage: window.UISortTable.sortByCell(colIndex, tableId)
// tableId defaults to 'stock-table' for the pedido_stock_preview screen.
window.UISortTable = {
  sortByCell: function (colIndex, tableId) {
    tableId = tableId || 'stock-table';
    var tbl = document.getElementById(tableId);
    if (!tbl) return;
    var tbody = tbl.querySelector('tbody');
    if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var _num = function (cell) {
      return parseFloat(cell.textContent.replace(/[^0-9.\-]/g, '')) || 0;
    };
    rows.sort(function (a, b) {
      return _num(b.cells[colIndex]) - _num(a.cells[colIndex]);
    });
    rows.forEach(function (r) { tbody.appendChild(r); });
  }
};

// ── UIDifficultyStars: star picker for recipe difficulty ───────────────
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('difficulty-stars');
    if (!container) return;
    var hidden = container.querySelector('input[type="hidden"][name="difficulty"]');
    var buttons = Array.prototype.slice.call(container.querySelectorAll('.star-btn'));
    var currentVal = parseInt(hidden && hidden.value, 10) || 0;

    function render(val) {
      buttons.forEach(function (btn) {
        var bv = parseInt(btn.getAttribute('data-value'), 10);
        btn.classList.toggle('star-filled', bv <= val);
      });
      hidden.value = val || '';
    }

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var val = parseInt(btn.getAttribute('data-value'), 10);
        render(val === currentVal ? 0 : val); // toggle off if same
        currentVal = parseInt(hidden.value, 10) || 0;
      });
      // keyboard: Enter/Space selects
      btn.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          btn.click();
        }
      });
    });

    render(currentVal);
  });
})();

// ── UIEscandalloEmpty: mark escandallo as empty when no ingredient rows ─
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    var summary = document.querySelector('.cost-summary');
    if (!summary) return;
    var table = document.getElementById('ingredient-lines-body') ||
                 document.querySelector('[id$="-body"]'); // any recipe-line tbody
    if (!table) return;
    var rows = table.querySelectorAll('tr[data-line-id], tr:not([data-line-id])');
    // count non-template rows: real rows have data-line-id or are <tr> with td input
    var realRows = Array.prototype.slice.call(table.querySelectorAll('tr'))
      .filter(function (r) { return r.querySelector('input[name$="_qty"]'); });
    if (realRows.length === 0) {
      summary.classList.add('is-empty');
    }
  });
})();
