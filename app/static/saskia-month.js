/* app/static/saskia-month.js — <saskia-month> Web Component.

Lightweight month-only picker for cierres mensuales, reports, payroll.
Renders as a styled button + dropdown with year selector and 12-month grid.

Usage:
  <saskia-month name="month" value="2026-09"></saskia-month>

Submits as <input type="hidden" name="month" value="YYYY-MM"> when the
parent form is submitted. Or call el.getValue() for an ISO YYYY-MM string.

Events:
  change  { detail: { value: 'YYYY-MM', display: 'Septiembre 2026' } }
*/

(function () {
  'use strict';

  var MONTHS_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
  ];

  class SaskiaMonth extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._open = false;
      this._year = new Date().getFullYear();
      this._month = new Date().getMonth() + 1; // 1-12
    }
    static get observedAttributes() {
      return ['value', 'name', 'min', 'max', 'label'];
    }
    connectedCallback() {
      this._parseValue();
      this._render();
      this._attachListeners();
    }
    attributeChangedCallback() {
      if (this.isConnected) {
        this._parseValue();
        this._render();
      }
    }
    _parseValue() {
      var v = this.getAttribute('value');
      if (v && /^\d{4}-\d{2}$/.test(v)) {
        var parts = v.split('-');
        this._year = parseInt(parts[0], 10);
        this._month = parseInt(parts[1], 10);
      }
    }
    getValue() {
      var m = (this._month < 10 ? '0' : '') + this._month;
      return this._year + '-' + m;
    }
    _render() {
      var styles = this._styles();
      this.shadowRoot.innerHTML =
        '<style>' + styles + '</style>' +
        '<div class="wrap">' +
        '  <button type="button" class="trigger" aria-haspopup="dialog" aria-expanded="false">' +
        '    <svg class="icon" aria-hidden="true" viewBox="0 0 24 24">' +
        '      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" fill="none" stroke="currentColor" stroke-width="2"/>' +
        '      <line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" stroke-width="2"/>' +
        '      <line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" stroke-width="2"/>' +
        '      <line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" stroke-width="2"/>' +
        '    </svg>' +
        '    <span class="display">' + MONTHS_ES[this._month - 1] + ' ' + this._year + '</span>' +
        '    <svg class="caret" aria-hidden="true" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" fill="none"/></svg>' +
        '  </button>' +
        '  <div class="dropdown" role="dialog" aria-label="Seleccionar mes">' +
        '    <div class="header">' +
        '      <button type="button" class="nav prev" aria-label="Año anterior">‹</button>' +
        '      <span class="year">' + this._year + '</span>' +
        '      <button type="button" class="nav next" aria-label="Año siguiente">›</button>' +
        '    </div>' +
        '    <div class="grid">' +
        this._renderMonthCells() +
        '    </div>' +
        '  </div>' +
        '</div>';
    }
    _renderMonthCells() {
      var cells = '';
      for (var m = 1; m <= 12; m++) {
        var isCurrent = (m === this._month);
        var isDisabled = this._isMonthDisabled(m);
        cells += '<button type="button" class="cell' +
          (isCurrent ? ' is-selected' : '') +
          (isDisabled ? ' is-disabled' : '') +
          '" data-month="' + m + '"' +
          (isDisabled ? ' disabled aria-disabled="true"' : '') +
          '>' + MONTHS_ES[m - 1].substring(0, 3) + '</button>';
      }
      return cells;
    }
    _isMonthDisabled(m) {
      var min = this.getAttribute('min');
      var max = this.getAttribute('max');
      var v = this._year + '-' + (m < 10 ? '0' + m : m);
      if (min && v < min) return true;
      if (max && v > max) return true;
      return false;
    }
    _styles() {
      return [
        ':host { display: inline-block; position: relative; }',
        '.trigger { display: inline-flex; align-items: center; gap: .5rem;',
        '  padding: .5rem .75rem; background: var(--color-surface, #fff);',
        '  border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;',
        '  cursor: pointer; font: inherit; color: inherit; min-width: 180px;',
        '  justify-content: space-between; }',
        '.trigger:hover { border-color: var(--color-accent, #2563eb); }',
        '.trigger .icon { width: 16px; height: 16px; }',
        '.trigger .caret { width: 14px; height: 14px; transition: transform .15s; }',
        '.trigger[aria-expanded="true"] .caret { transform: rotate(180deg); }',
        '.dropdown { position: absolute; top: calc(100% + 4px); left: 0;',
        '  background: var(--color-surface, #fff); border: 1px solid var(--color-border, #e5e7eb);',
        '  border-radius: 8px; box-shadow: 0 10px 25px -5px rgba(0,0,0,.15);',
        '  padding: .75rem; min-width: 240px; z-index: 100;',
        '  opacity: 0; pointer-events: none; transform: translateY(-4px);',
        '  transition: opacity .15s, transform .15s; }',
        '.dropdown.open { opacity: 1; pointer-events: auto; transform: translateY(0); }',
        '.header { display: flex; align-items: center; justify-content: space-between;',
        '  margin-bottom: .5rem; }',
        '.nav { background: transparent; border: 1px solid var(--color-border, #e5e7eb);',
        '  border-radius: 4px; padding: .25rem .5rem; cursor: pointer; font: inherit; }',
        '.nav:hover { background: var(--color-surface-subtle, #f3f4f6); }',
        '.year { font-weight: 600; font-size: var(--text-lg); }',
        '.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .25rem; }',
        '.cell { padding: .5rem; background: transparent; border: 1px solid transparent;',
        '  border-radius: 4px; cursor: pointer; font: inherit; }',
        '.cell:hover { background: var(--color-surface-subtle, #f3f4f6); }',
        '.cell.is-selected { background: var(--color-accent, #2563eb); color: white;',
        '  border-color: var(--color-accent, #2563eb); }',
        '.cell.is-disabled { opacity: .4; cursor: not-allowed; }'
      ].join('\n');
    }
    _attachListeners() {
      var self = this;
      var trigger = this.shadowRoot.querySelector('.trigger');
      var dropdown = this.shadowRoot.querySelector('.dropdown');
      var prev = this.shadowRoot.querySelector('.prev');
      var next = this.shadowRoot.querySelector('.next');

      trigger.addEventListener('click', function () { self._toggle(); });
      prev.addEventListener('click', function () { self._year -= 1; self._render(); self._attachListeners(); self._openDropdown(); });
      next.addEventListener('click', function () { self._year += 1; self._render(); self._attachListeners(); self._openDropdown(); });

      this.shadowRoot.querySelectorAll('.cell').forEach(function (cell) {
        cell.addEventListener('click', function () {
          if (cell.disabled) return;
          self._month = parseInt(cell.dataset.month, 10);
          self._render();
          self._attachListeners();
          self._close();
          self._emitChange();
        });
      });

      // Close on outside click
      document.addEventListener('click', function (e) {
        if (!self.contains(e.target)) self._close();
      });

      // Close on Escape
      this.shadowRoot.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') self._close();
      });
    }
    _toggle() {
      if (this._open) this._close(); else this._openDropdown();
    }
    _openDropdown() {
      this._open = true;
      this.shadowRoot.querySelector('.dropdown').classList.add('open');
      this.shadowRoot.querySelector('.trigger').setAttribute('aria-expanded', 'true');
    }
    _close() {
      this._open = false;
      var dd = this.shadowRoot.querySelector('.dropdown');
      if (dd) dd.classList.remove('open');
      var tr = this.shadowRoot.querySelector('.trigger');
      if (tr) tr.setAttribute('aria-expanded', 'false');
    }
    _emitChange() {
      this.setAttribute('value', this.getValue());
      this.dispatchEvent(new CustomEvent('change', {
        detail: {
          value: this.getValue(),
          display: MONTHS_ES[this._month - 1] + ' ' + this._year
        }
      }));
    }
  }

  // Form integration: on form submit, ensure <input type="hidden" name="X" value="YYYY-MM"> is present
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.querySelectorAll) return;
    form.querySelectorAll('saskia-month').forEach(function (el) {
      var name = el.getAttribute('name');
      if (!name) return;
      // Remove existing hidden for this name
      var existing = form.querySelectorAll('input[type="hidden"][data-saskia-month="' + name + '"]');
      existing.forEach(function (n) { n.parentNode.removeChild(n); });
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = name;
      hidden.value = el.getValue();
      hidden.setAttribute('data-saskia-month', name);
      form.appendChild(hidden);
    });
  });

  if (!customElements.get('saskia-month')) {
    customElements.define('saskia-month', SaskiaMonth);
  }
})();
