/**
 * combo.js — Reusable async combobox component for Saskia.
 *
 * Usage (vanilla, no framework):
 *
 *   <div class="saskia-combo"
 *        data-source="/api/search?param=id"
 *        data-min-chars="2"
 *        data-display="name"
 *        data-value="id">
 *     <input type="text" class="combo-input"
 *            placeholder="Buscar…"
 *            autocomplete="off">
 *     <input type="hidden" name="thing_id" value="">
 *     <div class="combo-results" role="listbox" hidden></div>
 *   </div>
 *
 * Or as a JS class:
 *
 *   const c = new SaskiaCombo(rootEl, {
 *     source: '/customers/api/search',
 *     displayField: 'name',
 *     valueField: 'id',
 *     onSelect: (item) => { ... },
 *     buildLabel: (item) => `${item.name} — ${item.phone}`,
 *   });
 *
 * Features:
 *  - Live search with debounce
 *  - Keyboard nav: ArrowUp/Down, Enter, Escape
 *  - Click-outside closes dropdown
 *  - Multiple items per page (server returns `results: [...]`)
 *  - Free-form text mode (allow non-matching text to be the value)
 *  - Auto-creates visual "picked" state with green-on-success styling
 *  - Custom result-row builder for richer display
 *
 * Loaded by: pedidos (combobox for customer + product line), this file is
 * a generalization ready for ventas, merma, receta_form, etc.
 */
(function (global) {
  "use strict";

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Default label builder: returns the `displayField` value, or the whole
   * object as fallback.
   */
  function defaultLabel(item, displayField) {
    if (typeof item === "object" && displayField in item) return item[displayField];
    if (typeof item === "string") return item;
    return JSON.stringify(item);
  }

  class SaskiaCombo {
    /**
     * @param {Element} root - the .saskia-combo root element
     * @param {Object} opts:
     *   - source: URL or callable (q) => Promise<[items]>
     *   - displayField: key to display (default 'name')
     *   - valueField: key for value (default 'id')
     *   - input: optional input element override
     *   - hidden: optional hidden input override (must exist)
     *   - onSelect: (item) => void
     *   - onClear: () => void
     *   - minChars: min chars before searching (default 0)
     *   - debounceMs: ms (default 180)
     *   - allowFreeForm: keep typed value even if not a pick (default true)
     *   - buildRow: (item, idx) => HTMLString for result row
     *   - emptyMessage: HTML shown when 0 results
     */
    constructor(root, opts) {
      this.root = root;
      this.opts = Object.assign(
        {
          displayField: "name",
          valueField: "id",
          minChars: 0,
          debounceMs: 180,
          allowFreeForm: true,
          allowCreate: false,
          onCreate: null,
          buildRow: null,
          emptyMessage:
            '<div class="combo-empty">No hay coincidencias.</div>',
        },
        opts || {}
      );
      this.input =
        this.opts.input || root.querySelector(".combo-input");
      this.hidden =
        this.opts.hidden ||
        root.querySelector('input[type="hidden"]') ||
        root.querySelector('input[name$="_id"]');
      this.results =
        root.querySelector(".combo-results") ||
        root.querySelector(".combo-dropdown");
      if (!this.input || !this.results) {
        console.warn("[SaskiaCombo] missing input or results", root);
        return;
      }
      this.matches = [];
      this.activeIndex = -1;
      this.debounceTimer = null;
      this.lastFetchToken = 0;
      this._wire();
      this._applyInitialValue();
    }

    /**
     * On construction, if the hidden input already carries a value (e.g.
     * server-set filter state), reflect it in the visible input by looking
     * up the matching item so the user sees the friendly label, not an ID.
     */
    _applyInitialValue() {
      var self = this;
      if (!this.hidden || !this.hidden.value) return;
      var initialVal = this.hidden.value;
      var lookup = function (items) {
        for (var i = 0; i < items.length; i++) {
          var item = items[i];
          var v = typeof item === "object" ? item[self.opts.valueField] : item;
          if (String(v) === String(initialVal)) {
            var label = typeof item === "object"
              ? (item[self.opts.displayField] || JSON.stringify(item))
              : item;
            self.input.value = label;
            self.input.classList.add("is-selected");
            return true;
          }
        }
        return false;
      };
      // Static options live in the DOM — read them synchronously
      if (this.opts.source === "" || this.opts.source === "static") {
        lookup(this._readStaticOptions());
      }
      // URL-sourced combos wait for the first fetch to populate
      // (initialVal will be visible as soon as the first result arrives).
    }

    _wire() {
      var self = this;
      this._inputHandler = function () {
        var q = self.input.value.trim();
        // Free-form text + value cleared
        if (self.hidden) self.hidden.value = "";
        self.input.classList.remove("is-selected");
        if (self.opts.onClear) self.opts.onClear();
        if (q.length < self.opts.minChars) {
          self._hide();
          self._afterInput(q);
          return;
        }
        clearTimeout(self.debounceTimer);
        self.debounceTimer = setTimeout(function () {
          self._fetch(q);
        }, self.opts.debounceMs);
      };
      this._keyHandler = function (e) {
        if (self._handleKey(e)) return;
      };
      this._focusHandler = function () {
        if (self.matches.length === 0 && self.input.value.trim().length >= self.opts.minChars) {
          self._fetch(self.input.value.trim());
        } else if (self.opts.minChars === 0 && self.matches.length === 0) {
          self._fetch("");
        }
      };
      this._blurHandler = function () {
        // delay so clicks on results register first
        setTimeout(function () { self._hide(); }, 200);
      };
      
      this.input.addEventListener("input", this._inputHandler);
      this.input.addEventListener("keydown", this._keyHandler);
      this.input.addEventListener("focus", this._focusHandler);
      this.input.addEventListener("blur", this._blurHandler);
      document.addEventListener("click", function (e) {
        if (!self.root.contains(e.target)) self._hide();
      });
    }

    _afterInput(q) {
      // Hook for subclasses; default no-op.
    }

    _handleKey(e) {
      if (this.results.hidden) return;
      var max = this.matches.length - 1;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.activeIndex = Math.min(max, this.activeIndex + 1);
        this._updateActive();
        return true;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        this.activeIndex = Math.max(0, this.activeIndex - 1);
        this._updateActive();
        return true;
      }
      if (e.key === "Enter" && this.activeIndex >= 0) {
        e.preventDefault();
        this._pick(this.matches[this.activeIndex]);
        return true;
      }
      if (e.key === "Escape") {
        this._hide();
        return true;
      }
      return false;
    }

    _buildRow(item, idx) {
      if (this.opts.buildRow) {
        return this.opts.buildRow(item, idx, item._isCreate);
      }
      var label = defaultLabel(item, this.opts.displayField);
      return (
        '<span class="combo-row-label">' +
        escapeHtml(label) +
        "</span>"
      );
    }

    _render(matches) {
      this.matches = matches || [];
      this.results.innerHTML = "";
      if (!this.matches.length) {
        this.results.innerHTML = this.opts.emptyMessage;
        this.results.hidden = false;
        return;
      }
      var self = this;

      // If the hidden input already carries an initial value (server-set
      // filter state), find the matching row and refresh the visible
      // input with its display label. Avoids the user seeing a stale ID
      // sitting in a text input.
      if (this.hidden && this.hidden.value && !this.input.classList.contains("is-selected")) {
        var initialVal = String(this.hidden.value);
        for (var k = 0; k < this.matches.length; k++) {
          var it = this.matches[k];
          var vv = typeof it === "object" ? it[this.opts.valueField] : it;
          if (String(vv) === initialVal) {
            this.input.value = typeof it === "object"
              ? (it[this.opts.displayField] || JSON.stringify(it))
              : it;
            this.input.classList.add("is-selected");
            break;
          }
        }
      }

      // Build all rows in a DocumentFragment so the browser only reflows
      // once per render instead of once per row. Cuts visible jank on
      // large result sets (50+ items).
      var frag = document.createDocumentFragment();
      this.matches.forEach(function (item, idx) {
        var row = document.createElement("div");
        row.className = "combo-row";
        if (idx === 0) row.classList.add("is-active");
        row.setAttribute("role", "option");
        row.tabIndex = 0;
        row.innerHTML = self._buildRow(item, idx);
        row.addEventListener("mouseenter", function () {
          self.activeIndex = idx;
          self._updateActive();
        });
        row.addEventListener("mousedown", function (e) {
          // mousedown so blur doesn't fire first and hide
          e.preventDefault();
          self._pick(item);
        });
        row.addEventListener("keydown", function (e) {
          if (e.key === "Enter") {
            e.preventDefault();
            self._pick(item);
          }
        });
        frag.appendChild(row);
      });
      this.results.appendChild(frag);

      this.activeIndex = 0;
      this.results.hidden = false;
    }

    _updateActive() {
      Array.from(this.results.children).forEach(function (c, idx) {
        if (idx === this.activeIndex) c.classList.add("is-active");
        else c.classList.remove("is-active");
      }, this);
    }

    _hide() {
      this.results.hidden = true;
      this.results.innerHTML = "";
      this.activeIndex = -1;
    }

    _pick(item) {
      // Handle creation items
      if (item && item._isCreate) {
        this.input.value = item.name;
        if (this.hidden) {
          this.hidden.value = item.name; // Store the text value for creation
        }
        this.input.classList.add("is-selected");
        this.input.dataset.selectedName = item.name;
        this._hide();
        
        // Trigger a callback so parent can handle creation
        if (this.opts.onCreate) {
          this.opts.onCreate(item.name);
        }
        return;
      }
      
      // Normal pick behavior
      var value = item && typeof item === "object"
        ? item[this.opts.valueField]
        : item;
      this.input.value = defaultLabel(item, this.opts.displayField);
      if (this.hidden && this.opts.allowFreeForm) {
        this.hidden.value = value || "";
      }
      this.input.classList.add("is-selected");
      this.input.dataset.selectedName = this.input.value;
      this._hide();
      if (this.opts.onSelect) this.opts.onSelect(item);
    }

    _fetch(q) {
      var self = this;
      var token = ++this.lastFetchToken;
      var promise;

      // Caching layer — avoid redundant network calls for repeated queries
      // (e.g. opening the same combo twice, or re-typing the same search).
      // The cache is shared across ALL combo instances on the page so a
      // second combo pointing at the same endpoint never re-fetches the
      // same query. TTL is short (30s) so data stays reasonably fresh.
      var cacheKey = (typeof this.opts.source === "function") ? null
                     : this.opts.source + "::" + q;
      var sharedCache = SaskiaCombo._sharedCache;
      if (cacheKey && sharedCache && sharedCache.has(cacheKey)) {
        var entry = sharedCache.get(cacheKey);
        if (Date.now() - entry.ts < 30000) {
          if (token !== self.lastFetchToken) return;
          self._render(entry.data);
          return;
        } else {
          sharedCache.delete(cacheKey);
        }
      }

      if (typeof this.opts.source === "function") {
        promise = Promise.resolve().then(function () { return self.opts.source(q); });
      } else if (typeof this.opts.source === "string" && this.opts.source.indexOf("/") === 0) {
        // URL source — hit the network
        var url = this.opts.source + (this.opts.source.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q);
        promise = fetch(url).then(function (r) { return r.json(); });
      } else if (this.opts.source === "" || this.opts.source === "static") {
        // Static inline source — items live on the .combo-results div as
        // <div class="combo-row" data-value="..." data-display="..."> children.
        // We render them with no network call at all. Used for short,
        // never-changing lists (product categories, recipe multipliers, etc).
        promise = Promise.resolve({ results: this._readStaticOptions() });
      } else {
        // Unknown source — render empty
        promise = Promise.resolve({ results: [] });
      }
      promise.then(function (data) {
        if (token !== self.lastFetchToken) return;
        var items = (data && data.results) ? data.results : [];

        // Cache successful results for repeat queries across all combo instances
        if (cacheKey) {
          if (!SaskiaCombo._sharedCache) SaskiaCombo._sharedCache = new Map();
          SaskiaCombo._sharedCache.set(cacheKey, { ts: Date.now(), data: items });
        }

        // If allowCreate is enabled and input has value not in results, add create option
        if (self.opts.allowCreate && q && !items.some(item => item.name === q)) {
          items.push({
            name: q,
            isCreateOption: true,
            _isCreate: true
          });
        }

        self._render(items);
      }).catch(function () { self._hide(); });
    }

    /**
     * Read pre-defined option rows from a child <div class="combo-results">
     * container whose children carry `data-value` and `data-display` attrs.
     * Used for combos with a tiny static set of options (filters, multipliers).
     */
    _readStaticOptions() {
      var rows = this.results.querySelectorAll(":scope > .combo-static-option");
      var items = [];
      for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        items.push({
          value: r.getAttribute("data-value") || "",
          name: r.getAttribute("data-display") || r.textContent,
          _isStatic: true,
        });
      }
      return items;
    }

    setValue(item) {
      if (item) this._pick(item);
    }

    clear() {
      this.input.value = "";
      this.input.classList.remove("is-selected");
      if (this.hidden) this.hidden.value = "";
      this._hide();
    }
    
    destroy() {
      // Clean up event listeners and references. The shared combo cache
      // (`SaskiaCombo._sharedCache`) is intentionally NOT cleared here —
      // it persists for the lifetime of the page so later combos can hit it.
      // Use `SaskiaCombo.clearCache()` to flush manually if needed.
      this.input.removeEventListener("input", this._inputHandler);
      this.input.removeEventListener("keydown", this._keyHandler);
      this.input.removeEventListener("focus", this._focusHandler);
      this.input.removeEventListener("blur", this._blurHandler);
      if (this.root._saskiaCombo === this) {
        delete this.root._saskiaCombo;
      }
    }

    /**
     * Flush the app-wide combo result cache. Call after mutations that
     * invalidate a long-lived cache (e.g. after creating a new customer).
     */
    static clearCache() {
      if (SaskiaCombo._sharedCache) {
        SaskiaCombo._sharedCache.clear();
      }
    }
  }

  global.SaskiaCombo = SaskiaCombo;

  // Auto-init any .saskia-combo element with data-* attributes.
  document.addEventListener("DOMContentLoaded", function () {
    var combos = document.querySelectorAll(".saskia-combo[data-source]");
    Array.from(combos).forEach(function (el) {
      if (el._saskiaCombo) return; // already initialized
      el._saskiaCombo = new SaskiaCombo(el, {
        source: el.dataset.source,
        displayField: el.dataset.display || "name",
        valueField: el.dataset.value || "id",
        minChars: Number(el.dataset.minChars || 0),
        buildRow: el.dataset.rowBuilder ? window[el.dataset.rowBuilder] : null,
      });
    });
  });
})(window);
