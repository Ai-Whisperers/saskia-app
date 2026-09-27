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
