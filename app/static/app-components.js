/* app/static/app-components.js — drawer, row-actions, stepper JS (no frameworks). */
(function () {
  'use strict';

  // ── A-11 drawer ───────────────────────────────────────────────────
  var SaskiaDrawer = {
    _ensureShell: function () {
      if (document.getElementById('saskia-drawer')) return;
      var bd = document.createElement('div');
      bd.className = 'drawer-backdrop'; bd.id = 'saskia-drawer-backdrop';
      bd.addEventListener('click', function () { SaskiaDrawer.close(); });
      var d = document.createElement('aside');
      d.className = 'drawer'; d.id = 'saskia-drawer'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true');
      d.innerHTML = '<div class="drawer__header"><h2 class="drawer__title" id="saskia-drawer-title"></h2>' +
        '<button type="button" class="btn btn-ghost" aria-label="Cerrar" data-drawer-close>✕</button></div>' +
        '<div class="drawer__body" id="saskia-drawer-body"></div>' +
        '<div class="drawer__footer" id="saskia-drawer-footer"></div>';
      document.body.appendChild(bd); document.body.appendChild(d);
      d.addEventListener('click', function (e) {
        if (e.target.closest('[data-drawer-close]')) SaskiaDrawer.close();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') SaskiaDrawer.close();
      });
    },
    open: function (title, bodyHtml, footerHtml) {
      this._ensureShell();
      document.getElementById('saskia-drawer-title').textContent = title;
      document.getElementById('saskia-drawer-body').innerHTML = bodyHtml;
      document.getElementById('saskia-drawer-footer').innerHTML = footerHtml || '';
      document.getElementById('saskia-drawer-backdrop').classList.add('is-open');
      document.getElementById('saskia-drawer').classList.add('is-open');
      var first = document.querySelector('#saskia-drawer-body input, #saskia-drawer-body select, #saskia-drawer-body button');
      if (first) first.focus();
    },
    close: function () {
      var b = document.getElementById('saskia-drawer-backdrop'), d = document.getElementById('saskia-drawer');
      if (b) b.classList.remove('is-open');
      if (d) d.classList.remove('is-open');
    }
  };
  window.SaskiaDrawer = SaskiaDrawer;

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

// ── SaskiaConfirmModal: Promise-based confirm() replacement ─────────────
window.SaskiaConfirmModal = (function () {
  var _ensureShell = function () {
    if (document.getElementById('saskia-confirm')) return;
    var bd = document.createElement('div');
    bd.className = 'confirm-backdrop'; bd.id = 'saskia-confirm-backdrop';
    var d = document.createElement('aside');
    d.className = 'confirm-modal'; d.id = 'saskia-confirm'; d.setAttribute('role', 'alertdialog');
    d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-labelledby', 'saskia-confirm-title');
    d.setAttribute('aria-describedby', 'saskia-confirm-body');
    d.innerHTML =
      '<div class="confirm-modal__header">' +
      '  <svg class="confirm-modal__icon" aria-hidden="true"><use href="#icon-warn"/></svg>' +
      '  <h2 class="confirm-modal__title" id="saskia-confirm-title">Confirmar</h2>' +
      '</div>' +
      '<div class="confirm-modal__body" id="saskia-confirm-body"></div>' +
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
      if (e.key === 'Escape' && document.getElementById('saskia-confirm').open) _close(false);
      if (e.key === 'Enter' && document.getElementById('saskia-confirm').open) _close(true);
    });
  };
  var _close = function (ok) {
    var d = document.getElementById('saskia-confirm');
    var bd = document.getElementById('saskia-confirm-backdrop');
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
      var d = document.getElementById('saskia-confirm');
      var bd = document.getElementById('saskia-confirm-backdrop');
      document.getElementById('saskia-confirm-title').textContent = opts.title || '¿Estás seguro?';
      document.getElementById('saskia-confirm-body').textContent = opts.body || 'Esta acción no se puede deshacer.';
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

// ── SaskiaSortTable: client-side table sorting ────────────────────────────
// Sort a table by the numeric content of a single column (descending).
// Usage: window.SaskiaSortTable.sortByCell(colIndex, tableId)
// tableId defaults to 'stock-table' for the pedido_stock_preview screen.
window.SaskiaSortTable = {
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
