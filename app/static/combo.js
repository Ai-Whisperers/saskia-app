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
    }

    _wire() {
      var self = this;
      this.input.addEventListener("input", function () {
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
      });
      this.input.addEventListener("keydown", function (e) {
        if (self._handleKey(e)) return;
      });
      this.input.addEventListener("focus", function () {
        if (self.matches.length === 0 && self.input.value.trim().length >= self.opts.minChars) {
          self._fetch(self.input.value.trim());
        } else if (self.opts.minChars === 0 && self.matches.length === 0) {
          self._fetch("");
        }
      });
      this.input.addEventListener("blur", function () {
        // delay so clicks on results register first
        setTimeout(function () { self._hide(); }, 200);
      });
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
        return this.opts.buildRow(item, idx);
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
        self.results.appendChild(row);
      });
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
      if (typeof this.opts.source === "function") {
        promise = Promise.resolve().then(function () { return self.opts.source(q); });
      } else {
        var url = this.opts.source + (this.opts.source.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q);
        promise = fetch(url).then(function (r) { return r.json(); });
      }
      promise.then(function (data) {
        if (token !== self.lastFetchToken) return;
        var items = (data && data.results) ? data.results : [];
        self._render(items);
      }).catch(function () { self._hide(); });
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
