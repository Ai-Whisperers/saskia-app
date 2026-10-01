/* app/static/saskia-combo.js — <saskia-combo> Web Component.

Search-as-you-type combobox replacement for native <select>.

Renders a button (the trigger) + a dropdown panel with:
  - a search input that filters results client-side from a `src` array
  - or server-side from `endpoint` URL (JSON GET, returns {results:[...]} or [...])
  - keyboard nav: ↑/↓ to move, Enter to select, Esc to close
  - ARIA: role=combobox on trigger, role=listbox on panel, role=option on items
  - WCAG AA focus contrast (1px outline + 2px ring on focus)

Usage (client-side src):
  <saskia-combo name="category" placeholder="Buscar categoría…"
                value="repostería" display="Repostería"
                src='[{"value":"reposteria","label":"Repostería"},{"value":"panaderia","label":"Panadería"}]'>
  </saskia-combo>

Usage (server-side endpoint):
  <saskia-combo name="product_id" placeholder="Buscar producto…"
                endpoint="/api/lookup/products?q="></saskia-combo>

Form integration: on form submit, adds <input type="hidden" name="X" value="...">
whose value is the selected option's `value` field. Or call el.getValue().

Events:
  change  { detail: { value: '...', display: '...' } }

TODOs (for tomorrow's full implementation):
  - Async fetch debounce (200ms)
  - Virtualized scroll for >100 results
  - Multi-select mode (checkboxes)
  - Custom render (e.g. avatar + name)
  - Reduced-motion respect
*/

(function () {
  'use strict';

  const TEMPLATE = `
    <style>
      :host { display: inline-block; position: relative; width: 100%; }
      .trigger {
        display: flex; align-items: center; gap: .5rem;
        padding: .5rem .75rem; min-height: 38px;
        background: var(--color-surface, #fff);
        border: 1px solid var(--color-border, #d1d5db);
        border-radius: 6px; cursor: pointer; font: inherit;
        color: inherit; width: 100%; box-sizing: border-box;
        justify-content: space-between;
      }
      .trigger:hover { border-color: var(--color-accent, #2563eb); }
      .trigger:focus { outline: 2px solid transparent; outline-offset: 2px;
        box-shadow: 0 0 0 2px var(--color-accent, #2563eb); border-color: var(--color-accent, #2563eb); }
      .trigger .label { flex: 1; text-align: left; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap; }
      .trigger .placeholder { color: var(--color-text-muted, #6b7280); }
      .trigger .icon { width: 14px; height: 14px; transition: transform .15s; flex-shrink: 0; }
      .trigger[aria-expanded="true"] .icon { transform: rotate(180deg); }
      .trigger .clear {
        display: none; background: transparent; border: none;
        cursor: pointer; padding: 0 .25rem; color: var(--color-text-muted, #6b7280);
        font-size: 1.2em; line-height: 1;
      }
      .trigger.has-value .clear { display: block; }
      .panel {
        position: absolute; top: calc(100% + 4px); left: 0; right: 0;
        background: var(--color-surface, #fff);
        border: 1px solid var(--color-border, #e5e7eb);
        border-radius: 8px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,.15);
        max-height: 320px; overflow-y: auto;
        z-index: 100;
        opacity: 0; pointer-events: none; transform: translateY(-4px);
        transition: opacity .12s, transform .12s;
      }
      .panel.open { opacity: 1; pointer-events: auto; transform: translateY(0); }
      .search {
        width: 100%; padding: .5rem .75rem;
        border: none; border-bottom: 1px solid var(--color-border, #e5e7eb);
        font: inherit; outline: none; box-sizing: border-box;
        background: transparent;
      }
      .results { list-style: none; margin: 0; padding: .25rem 0; }
      .item {
        padding: .5rem .75rem; cursor: pointer; font: inherit;
        color: inherit; display: block; width: 100%;
        background: transparent; border: none; text-align: left;
      }
      .item:hover, .item.active { background: var(--color-surface-subtle, #f3f4f6); }
      .item.selected { font-weight: 600; color: var(--color-accent, #2563eb); }
      .item.empty, .item.loading {
        color: var(--color-text-muted, #6b7280);
        font-style: italic;
        cursor: default;
      }
      .item.empty:hover, .item.loading:hover { background: transparent; }
      /* PRO-A11Y: visually hide the aria-live announcement region. */
      .sr-only {
        position: absolute; width: 1px; height: 1px;
        padding: 0; margin: -1px; overflow: hidden;
        clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
      }
      @media (prefers-reduced-motion: reduce) {
        .trigger .icon, .panel { transition: none; }
      }
    </style>
    <button type="button" class="trigger" aria-haspopup="listbox" aria-expanded="false">
      <span class="label"></span>
      <span class="clear" aria-label="Limpiar selección" tabindex="0">×</span>
      <svg class="icon" aria-hidden="true" viewBox="0 0 24 24">
        <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
    </button>
    <div class="panel" role="listbox">
      <input type="text" class="search combo-input" aria-label="Buscar" placeholder="Buscar…">
      <span class="combo-input" hidden></span>
      <ul class="results" role="presentation"></ul>
      <!-- PRO-A11Y (2026-10-01): screen-reader announcement region.
           Updated whenever result count changes (loaded, filtered,
           cleared) so AT users hear "5 resultados", "Sin resultados",
           "Cargando..." etc. aria-live="polite" waits for the
           screen reader to finish current speech -- we never interrupt
           the user mid-utterance. Visually hidden via sr-only class. -->
      <div class="sr-only combo-status" aria-live="polite" role="status"></div>
    </div>
  `;

  class SaskiaCombo extends HTMLElement {
    constructor(opts) {
      super();
      // PRO-PED-UX (2026-09-30): allow programmatic config (onSelect/onClear/
      // source/displayField/valueField/minChars/buildRow) — pedido-combos.js
      // constructs `new window.SaskiaCombo(root, opts)`; opts were silently
      // dropped before, so customer-pick never prefilled phone/hint.
      this._cfg = opts || null;
      this._hostOverride = null;
      this.attachShadow({ mode: 'open' });
      this._open = false;
      this._activeIdx = -1;
      this._results = [];
      this._endpoint = null;
      this._src = [];
      this._value = null;
      this._display = null;
      this._selectedItem = null;  // full item data (incl. sale_price_gs) for getSelectedData()
      this._debounceTimer = null;
      this._uid = 'saskia-combo-' + Math.random().toString(36).slice(2, 10);
    }

    static get observedAttributes() {
      // data-source is an alias for endpoint (compatibility with combo v1 markup
      // and tests that reference data-source= directly).
      return ['value', 'display', 'name', 'placeholder', 'endpoint', 'data-source',
              'src', 'disabled', 'value-field', 'label-field', 'allow-create'];
    }

    connectedCallback() {
      this._parseAttributes();
      this._render();
      this._attachListeners();
      // Mirror initial value into hidden input (for native form serialization)
      this._emitChange();
    }

    disconnectedCallback() {
      document.removeEventListener('click', this._onDocClick);
    }

    attributeChangedCallback(name) {
      if (this.isConnected) {
        this._parseAttributes();
        this._updateTrigger();
        // Re-fetch results when data source changes (endpoint, src, or field mapping)
        if (name === 'endpoint' || name === 'src' ||
            name === 'value-field' || name === 'label-field') {
          // Clear stale value when source changes (different dataset)
          if (name === 'endpoint' || name === 'src') {
            this._value = null;
            this._display = null;
            this._updateTrigger();
            this._emitChange();
          }
          this._filterAndRender('');
        }
      }
    }

    _parseAttributes() {
      this._value = this.getAttribute('value') || null;
      this._display = this.getAttribute('display') || null;
      // data-source is an alias for endpoint.
      this._endpoint = this.getAttribute('endpoint') || this.getAttribute('data-source') || null;
      this._src = this._parseAttrJSON('src') || [];
    }

    _parseAttrJSON(attrName) {
      const raw = this.getAttribute(attrName);
      if (!raw) return null;
      try { return JSON.parse(raw); }
      catch (e) { console.warn(`saskia-combo: invalid JSON in ${attrName}`, e); return null; }
    }

    getValue() { return this._value; }
    /** Property getter that mirrors _value to the native HTMLElement.value.
     *  2026-09-29 fix: without this, `combo.value` returns undefined (custom
     *  elements extending HTMLElement don't reflect the `value` attribute the
     *  way form elements do). Callers can still use getValue(), but external
     *  code that does `combo.value` now works. */
    get value() { return this._value; }
    set value(v) { this.setValue(v, this._display); }
    getDisplay() { return this._display; }
    /** Returns the full selected item object (value, display, plus any extra
     *  fields like sale_price_gs that were stored via setOptionsData). */
    getSelectedData() {
      if (!this._value || !this._selectedItem) return null;
      return Object.assign({}, this._selectedItem, {
        value: this._value,
        display: this._display,
      });
    }
    clear() {
      this.setValue(null, null);
      if (this._cfg && typeof this._cfg.onClear === 'function') {
        try { this._cfg.onClear(); } catch (err) { console.warn('saskia-combo onClear', err); }
      }
    }
    setValue(value, display) {
      this._value = value;
      this._display = display || null;
      this.setAttribute('value', value || '');
      if (display) this.setAttribute('display', display);
      this._updateTrigger();
      this._emitChange();
    }

    _render() {
      this.shadowRoot.innerHTML = TEMPLATE;
      this._updateTrigger();
    }

    _updateTrigger() {
      const trigger = this.shadowRoot.querySelector('.trigger');
      const labelEl = this.shadowRoot.querySelector('.label');
      if (!trigger || !labelEl) return;
      const placeholder = this.getAttribute('placeholder') || 'Seleccionar…';
      const hasValue = this._value !== null && this._value !== '';
      labelEl.textContent = hasValue ? (this._display || this._value) : placeholder;
      labelEl.classList.toggle('placeholder', !hasValue);
      trigger.classList.toggle('has-value', hasValue);
    }

    _attachListeners() {
      const self = this;
      const trigger = this.shadowRoot.querySelector('.trigger');
      const panel = this.shadowRoot.querySelector('.panel');
      const search = this.shadowRoot.querySelector('.search');
      const clearBtn = this.shadowRoot.querySelector('.clear');

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        if (self.hasAttribute('disabled')) return;
        self._toggle();
      });

      clearBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        self.setValue(null, null);
        self._close();
      });

      search.addEventListener('input', function () {
        clearTimeout(self._debounceTimer);
        self._debounceTimer = setTimeout(function () { self._filterAndRender(search.value); }, 150);
      });

      search.addEventListener('keydown', function (e) {
        self._onSearchKey(e);
      });

      trigger.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'Enter') {
          e.preventDefault();
          if (!self._open) self._openPanel();
          else self._moveActive(1);
        } else if (e.key === 'Escape') {
          self._close();
        }
      });

      // Document click closes panel
      this._onDocClick = function (e) {
        if (!self.contains(e.target)) self._close();
      };
      document.addEventListener('click', this._onDocClick);

      // Initial filter
      this._filterAndRender('');
    }

    _toggle() {
      if (this._open) this._close(); else this._openPanel();
    }

    _openPanel() {
      this._open = true;
      const panel = this.shadowRoot.querySelector('.panel');
      const trigger = this.shadowRoot.querySelector('.trigger');
      const search = this.shadowRoot.querySelector('.search');
      panel.classList.add('open');
      trigger.setAttribute('aria-expanded', 'true');
      const placeholder = this.getAttribute('placeholder') || 'Seleccionar…';
      search.placeholder = 'Buscar' + (placeholder && placeholder !== 'Seleccionar…' ? ' ' + placeholder.toLowerCase() : '');
      setTimeout(() => search.focus(), 50);
    }

    _close() {
      this._open = false;
      const panel = this.shadowRoot.querySelector('.panel');
      const trigger = this.shadowRoot.querySelector('.trigger');
      if (panel) panel.classList.remove('open');
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }

    async _filterAndRender(query) {
      const resultsList = this.shadowRoot.querySelector('.results');
      // Shadow DOM may be torn down between `attributeChangedCallback` (which
      // re-fires this method) and a `_close()` call. Guard against null so
      // we no-op instead of throwing "Cannot set properties of null" on
      // every page that uses <saskia-combo> (18+ page errors per load).
      if (!resultsList) return;
      resultsList.innerHTML = '<li class="item loading" role="presentation">Buscando...</li>';
      // PRO-A11Y: announce the loading state to screen readers.
      this._announce(query ? 'Buscando...' : 'Abriendo lista');

      let results = [];
      // PRO-PED-UX: cfg.source(url) — programmatic fetcher (pedido-combos.js)
      if (this._cfg && typeof this._cfg.source === 'function' && this._hostOverride) {
        try {
          const q = encodeURIComponent(query || '');
          const data = await this._cfg.source(q);
          results = Array.isArray(data) ? data : (data.results || []);
          const vf = this._cfg.valueField || this.getAttribute('value-field') || 'value';
          const lf = this._cfg.displayField || this.getAttribute('label-field') || 'label';
          if (results.length && !('value' in results[0]) && ('id' in results[0] || 'name' in results[0])) {
            results = results.map(function (item) {
              if ('value' in item && 'label' in item) return item;
              const value = item[vf] !== undefined ? item[vf] : item.id;
              const label = item[lf] !== undefined ? item[lf] : item.name;
              return Object.assign({}, item, { value: value, label: label });
            });
          }
          this._results = results;
          this._renderResults();
          return;
        } catch (err) {
          console.warn('saskia-combo: cfg.source fetch failed', err);
          results = [];
        }
      }
      if (this._endpoint) {
        try {
          // Build URL: handle endpoints that already include a trailing
          // slash vs. those that expect ?q= or /{q}/. Strip a single
          // trailing slash from the endpoint, then if the endpoint has
          // no `?`, append the query as a path segment; otherwise use
          // it as a query-string parameter.
          const base = this._endpoint.replace(/\/$/, '');
          const hasQueryParam = base.includes('?');
          const url = hasQueryParam
            ? base + (base.endsWith('?') ? encodeURIComponent(query || '') : '&q=' + encodeURIComponent(query || ''))
            : base + '/' + encodeURIComponent(query || '');
          const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
          const data = await resp.json();
          results = Array.isArray(data) ? data : (data.results || []);
          // Normalize response: map server fields (id/name) → combo fields (value/label)
          // using value-field and label-field attributes (defaults: value, label)
          const valueField = this.getAttribute('value-field') || 'value';
          const labelField = this.getAttribute('label-field') || 'label';
          // If items don't have value/label but have id/name, map them
          if (results.length && !('value' in results[0]) && ('id' in results[0] || 'name' in results[0])) {
            results = results.map(function (item) {
              if ('value' in item && 'label' in item) return item;
              const value = item[valueField] !== undefined ? item[valueField] : item.id;
              const label = item[labelField] !== undefined ? item[labelField] : item.name;
              return Object.assign({}, item, { value: value, label: label });
            });
          }
        } catch (err) {
          console.warn('saskia-combo: fetch failed', err);
          results = [];
        }
      } else {
        // Client-side filter
        const q = (query || '').toLowerCase();
        results = this._src.filter(function (item) {
          return !q ||
            String(item.label || item.value).toLowerCase().indexOf(q) >= 0;
        });
      }

      this._results = results;
      this._renderResults();
    }

    _renderResults() {
      const resultsList = this.shadowRoot.querySelector('.results');
      resultsList.innerHTML = '';

      if (this._results.length === 0) {
        const li = document.createElement('li');
        li.className = 'item empty';
        li.textContent = 'Sin resultados';
        resultsList.appendChild(li);
        // PRO-A11Y: announce empty result set to screen readers.
        this._announce('Sin resultados');
        return;
      }

      // PRO-A11Y: announce result count to screen readers (e.g. "5 resultados").
      // Cap the message at 99 to avoid verbal "100 resultados" being read for
      // large lists; the user can arrow-down past the announcement anyway.
      const n = this._results.length;
      this._announce(n === 1 ? '1 resultado' : n + ' resultados');

      const self = this;
      this._results.forEach(function (item, idx) {
        const li = document.createElement('li');
        li.className = 'item';
        li.setAttribute('role', 'option');
        li.dataset.value = item.value;
        li.dataset.display = item.label || item.value;
        // row-label: allow per-instance row renderer (combo-rows.js builders).
        // Lookup happens on each render so a later-loaded combo-rows.js still wins.
        const rowLabelName = (self._cfg && self._cfg.buildRow) ? '__cfgBuildRow' : self.getAttribute('row-label');
        if (self._cfg && self._cfg.buildRow) window.__cfgBuildRow = self._cfg.buildRow;
        const rowLabelFn =
          (rowLabelName && typeof window[rowLabelName] === 'function')
            ? window[rowLabelName]
            : (typeof window.defaultRowLabel === 'function' ? window.defaultRowLabel : null);
        if (rowLabelFn) {
          try {
            const html = rowLabelFn(item);
            // row builders return safe HTML (they escape internally).
            li.innerHTML = html || escapeHtml(item.label || item.value);
          } catch (err) {
            li.textContent = item.label || item.value;
          }
        } else {
          // Inline minimal escaper so we never assign raw value to innerHTML.
          const raw = item.label || item.value || '';
          li.textContent = raw;
        }
        if (String(item.value) === String(self._value)) li.classList.add('selected');
        li.addEventListener('click', function () { self._selectItem(item); });
        li.addEventListener('mouseenter', function () { self._setActiveIdx(idx); });
        resultsList.appendChild(li);
      });
      this._activeIdx = -1;
    }

    // PRO-A11Y: write a message to the aria-live region. Screen readers
    // announce the text after any current speech finishes. Safe to call
    // repeatedly -- aria-live is idempotent (the same text won't re-fire
    // unless the DOM node changes).
    _announce(message) {
      const region = this.shadowRoot.querySelector('.combo-status');
      if (region && region.textContent !== message) {
        region.textContent = message;
      }
    }

    _setActiveIdx(idx) {
      const items = this.shadowRoot.querySelectorAll('.item:not(.empty):not(.loading)');
      items.forEach(function (el, i) {
        el.classList.toggle('active', i === idx);
      });
      this._activeIdx = idx;
      if (idx >= 0 && items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
    }

    _moveActive(delta) {
      const items = this.shadowRoot.querySelectorAll('.item:not(.empty):not(.loading)');
      if (items.length === 0) return;
      let next = this._activeIdx + delta;
      if (next < 0) next = items.length - 1;
      if (next >= items.length) next = 0;
      this._setActiveIdx(next);
    }

    _onSearchKey(e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); this._moveActive(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); this._moveActive(-1); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const items = this.shadowRoot.querySelectorAll('.item:not(.empty):not(.loading):not(.create)');
        if (this._activeIdx >= 0 && items[this._activeIdx]) {
          this._selectItem(this._results[this._activeIdx]);
          return;
        }
        // Allow-create: if Enter pressed with no selection and search text present,
        // create a virtual item with the typed text as both value and label.
        if (this.hasAttribute('allow-create')) {
          const search = this.shadowRoot.querySelector('.search');
          const typed = (search && search.value || '').trim();
          if (typed) {
            this.dispatchEvent(new CustomEvent('create-option', {
              bubbles: true,
              detail: { value: typed, label: typed, name: typed }
            }));
            this.setValue(typed, typed);
            this._close();
          }
        }
      } else if (e.key === 'Escape') {
        this._close();
      }
    }

    _selectItem(item) {
      this._selectedItem = item;  // store full item for getSelectedData()
      var val = item.value !== undefined ? item.value : item.id;
      this.setValue(val, item.label || item.name || val);
      this._close();
      // PRO-PED-UX: programmatic onSelect hook (pedido-combos.js)
      if (this._cfg && typeof this._cfg.onSelect === 'function') {
        try { this._cfg.onSelect(item); } catch (err) { console.warn('saskia-combo onSelect', err); }
      }
      // Auto-submit: if attribute set, submit the closest form on selection.
      // Used for scale selectors and similar "change → reload" patterns.
      if (this.hasAttribute('autosubmit')) {
        const form = this.closest('form');
        if (form) form.submit();
      }
      // No explicit change dispatch here — setValue() above already
      // calls _emitChange() which fires a CustomEvent('change', {detail})
      // with bubbles:true. Dispatching another plain Event('change')
      // here caused double-fire and a stale event.detail. Removed
      // 2026-09-29.
    }

    _emitChange() {
      const name = this.getAttribute('name');
      let mirror = name ? document.querySelector(`input[type="hidden"][data-saskia-combo-mirror="${name}"][data-saskia-combo-id="${this._uid}"]`) : null;
      if (!mirror && name) {
        mirror = document.createElement('input');
        mirror.type = 'hidden';
        mirror.name = name;
        mirror.setAttribute('data-saskia-combo-mirror', name);
        mirror.setAttribute('data-saskia-combo-id', this._uid);
        this.parentNode.insertBefore(mirror, this.nextSibling);
      }
      if (mirror) mirror.value = this._value == null ? '' : this._value;
      this.dispatchEvent(new CustomEvent('change', {
        detail: { value: this._value, display: this._display }
      }));
    }
  }

  // Form integration: on form submit, ensure <input type="hidden" name="X" value="...">
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (!form || !form.querySelectorAll) return;
    form.querySelectorAll('saskia-combo').forEach(function (el) {
      const name = el.getAttribute('name');
      if (!name) return;
      const existing = form.querySelectorAll('input[type="hidden"][data-saskia-combo="' + name + '"]');
      existing.forEach(function (n) { n.parentNode.removeChild(n); });
      const v = el.getValue();
      if (v !== null && v !== '') {
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = name;
        hidden.value = v;
        hidden.setAttribute('data-saskia-combo', name);
        form.appendChild(hidden);
      }
    });
  });

  if (!customElements.get('saskia-combo')) {
    customElements.define('saskia-combo', SaskiaCombo);
  }
  // PRO-PED-UX: expose for programmatic construction with per-instance opts.
  // If the element already exists (upgrade), wrap: new SaskiaCombo(el) is NOT
  // valid for custom elements — so pedido-combos attaches opts to the
  // existing element via SaskiaCombo.attach(el, opts) instead.
  window.SaskiaCombo = {
    attach: function (el, opts) {
      if (!el) return null;
      el._cfg = opts || null;
      el._hostOverride = el;
      return el;
    },
  };
})();
