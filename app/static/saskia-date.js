/* app/static/saskia-date.js — <saskia-date> Spanish-locale date picker.

Replaces native <input type="date"> with a Spanish calendar (lun-dom,
enero-diciembre) that displays dd/mm/yyyy and emits change events with
ISO YYYY-MM-DD. Keyboard accessible, WCAG AA focus contrast, custom
element with Shadow DOM for style isolation.

Usage:
  <saskia-date name="promised_date" value="2026-09-28" min="2026-09-27"
                 required></saskia-date>

Attributes:
  value       ISO date string YYYY-MM-DD (or empty)
  min, max    ISO date strings (range)
  name        Form field name (creates a hidden input)
  required    Adds required attribute to the hidden input
  placeholder Display text when empty (default "dd/mm/yyyy")

Events:
  change      { value: 'YYYY-MM-DD' | null, display: 'dd/mm/yyyy' }
*/

(function () {
  'use strict';

  var MONTHS_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                   'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var DAYS_ES = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'];
  var DAYS_FULL_ES = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

  // Pad to 2 digits
  function pad2(n) { return n < 10 ? '0' + n : '' + n; }

  // ISO date string validation
  function isValidISO(s) {
    if (typeof s !== 'string') return false;
    return /^\d{4}-\d{2}-\d{2}$/.test(s);
  }

  // Parse ISO date → { y, m, d } (local time, m is 0-11)
  function parseISO(iso) {
    if (!isValidISO(iso)) return null;
    var parts = iso.split('-');
    return {
      y: parseInt(parts[0], 10),
      m: parseInt(parts[1], 10) - 1,
      d: parseInt(parts[2], 10)
    };
  }

  // Format {y,m,d} → ISO
  function toISO(y, m, d) {
    return y + '-' + pad2(m + 1) + '-' + pad2(d);
  }

  // Display format dd/mm/yyyy
  function formatDisplay(y, m, d) {
    return pad2(d) + '/' + pad2(m + 1) + '/' + y;
  }

  // Days in month
  function daysInMonth(y, m) {
    return new Date(y, m + 1, 0).getDate();
  }

  class SaskiaDate extends HTMLElement {
    static get observedAttributes() {
      return ['value', 'min', 'max', 'placeholder', 'required', 'name'];
    }

    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._open = false;
      this._cursor = new Date();
      this._cursor.setHours(0, 0, 0, 0);
      this._selected = null;
      this._minISO = null;
      this._maxISO = null;
      this._placeholder = 'dd/mm/yyyy';
    }

    connectedCallback() {
      this._readAttrs();
      this._render();
      this._attachListeners();
      // Initialize cursor to value's month if set
      if (this._selected) {
        this._cursor = new Date(this._selected.y, this._selected.m, 1);
      }
    }

    attributeChangedCallback(name) {
      if (this.isConnected) {
        this._readAttrs();
        this._render();
      }
    }

    _readAttrs() {
      var v = this.getAttribute('value');
      if (isValidISO(v)) {
        this._selected = parseISO(v);
      } else {
        this._selected = null;
      }
      this._minISO = isValidISO(this.getAttribute('min')) ? this.getAttribute('min') : null;
      this._maxISO = isValidISO(this.getAttribute('max')) ? this.getAttribute('max') : null;
      this._placeholder = this.getAttribute('placeholder') || 'dd/mm/yyyy';
    }

    _isDisabled(y, m, d) {
      var iso = toISO(y, m, d);
      if (this._minISO && iso < this._minISO) return true;
      if (this._maxISO && iso > this._maxISO) return true;
      return false;
    }

    _render() {
      var cy = this._cursor.getFullYear();
      var cm = this._cursor.getMonth();
      var today = new Date();
      today.setHours(0, 0, 0, 0);
      var todayISO = toISO(today.getFullYear(), today.getMonth(), today.getDate());

      var displayText = this._selected
        ? formatDisplay(this._selected.y, this._selected.m, this._selected.d)
        : this._placeholder;

      var hiddenValue = this._selected ? toISO(this._selected.y, this._selected.m, this._selected.d) : '';

      // Build calendar grid: 6 rows × 7 cols
      var firstDay = new Date(cy, cm, 1).getDay(); // 0=Sun
      // Convert to Monday-first: (firstDay + 6) % 7
      var startOffset = (firstDay + 6) % 7;
      var daysCount = daysInMonth(cy, cm);

      var cells = [];
      for (var i = 0; i < 42; i++) {
        var dayNum = i - startOffset + 1;
        if (dayNum < 1 || dayNum > daysCount) {
          cells.push('<td class="empty"></td>');
          continue;
        }
        var iso = toISO(cy, cm, dayNum);
        var disabled = this._isDisabled(cy, cm, dayNum);
        var isSelected = this._selected && this._selected.y === cy && this._selected.m === cm && this._selected.d === dayNum;
        var isToday = iso === todayISO;
        var cls = ['day'];
        if (disabled) cls.push('disabled');
        if (isSelected) cls.push('selected');
        if (isToday) cls.push('today');
        var attr = disabled ? ' aria-disabled="true"' : '';
        cells.push('<td class="' + cls.join(' ') + '"' + attr + ' data-iso="' + iso + '" tabindex="-1">' + dayNum + '</td>');
      }

      // Weekday header
      var head = DAYS_ES.map(function (d) { return '<th scope="col" aria-label="' + d + '">' + d + '</th>'; }).join('');

      var popover = this._open ? this._renderPopover(cy, cm, head, cells) : '';

      var name = this.getAttribute('name') || '';
      var required = this.hasAttribute('required');

      this.shadowRoot.innerHTML =
        '<style>' + this._css() + '</style>' +
        '<div class="root">' +
          '<input type="text" class="display" value="' + displayText + '" ' +
            'readonly placeholder="' + this._placeholder + '" ' +
            'aria-label="Fecha" aria-haspopup="dialog" ' +
            (this._selected ? '' : 'placeholder="' + this._placeholder + '" ') +
          '/>' +
          '<button type="button" class="toggle" aria-label="Abrir calendario">📅</button>' +
          '<input type="hidden" name="' + name + '" value="' + hiddenValue + '"' +
            (required ? ' required' : '') + '/>' +
          popover +
        '</div>';
    }

    _renderPopover(cy, cm, head, cells) {
      var prevDisabled = this._minISO && toISO(cy, cm - 1, 1) < this._minISO.replace(/-\d{2}$/, '-01');
      var nextDisabled = this._maxISO && toISO(cy, cm + 1, 1) > this._maxISO.replace(/-\d{2}$/, '-28');
      return (
        '<div class="popover" role="dialog" aria-label="Calendario">' +
          '<div class="popover-head">' +
            '<button type="button" class="nav prev" data-nav="prev"' + (prevDisabled ? ' disabled' : '') + ' aria-label="Mes anterior">‹</button>' +
            '<span class="month-name">' + MONTHS_ES[cm] + ' ' + cy + '</span>' +
            '<button type="button" class="nav next" data-nav="next"' + (nextDisabled ? ' disabled' : '') + ' aria-label="Mes siguiente">›</button>' +
          '</div>' +
          '<table role="grid" class="grid">' +
            '<thead><tr>' + head + '</tr></thead>' +
            '<tbody>' +
              [0, 1, 2, 3, 4, 5].map(function (row) {
                return '<tr>' + cells.slice(row * 7, (row + 1) * 7).join('') + '</tr>';
              }).join('') +
            '</tbody>' +
          '</table>' +
          '<div class="popover-foot">' +
            '<button type="button" class="today-btn" data-action="today">Hoy</button>' +
            '<button type="button" class="clear-btn" data-action="clear">Limpiar</button>' +
          '</div>' +
        '</div>'
      );
    }

    _css() {
      return [
        ':host { display: inline-block; position: relative; font: inherit; }',
        '.root { position: relative; display: inline-flex; align-items: stretch; }',
        '.display { padding: .375rem .75rem; border: 1px solid var(--border, #ccc); border-radius: 4px;',
        '           background: var(--card, #fff); color: var(--fg, #111); font: inherit; min-width: 8rem;',
        '           cursor: pointer; user-select: none; }',
        '.display:focus, .toggle:focus { outline: 2px solid var(--accent, #2563eb); outline-offset: 2px; }',
        '.toggle { border: 1px solid var(--border, #ccc); border-left: none; background: var(--card, #fff);',
        '          padding: 0 .5rem; cursor: pointer; border-radius: 0 4px 4px 0; }',
        '.popover { position: absolute; top: 100%; left: 0; margin-top: 4px; z-index: 50;',
        '           background: var(--card, #fff); color: var(--fg, #111); border: 1px solid var(--border, #ccc);',
        '           border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,.15); padding: .75rem; min-width: 18rem; }',
        '.popover-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: .5rem; }',
        '.month-name { font-weight: 600; }',
        '.nav { background: none; border: 1px solid var(--border, #ccc); border-radius: 4px;',
        '       width: 2rem; height: 2rem; cursor: pointer; font-size: 1.2rem; }',
        '.nav[disabled] { opacity: .4; cursor: not-allowed; }',
        '.grid { width: 100%; border-collapse: collapse; }',
        '.grid th { font-weight: 600; padding: .25rem 0; font-size: .8rem; color: var(--muted, #555);',
        '          text-align: center; }',
        '.grid td { padding: .35rem; text-align: center; border-radius: 4px; cursor: pointer;',
        '          font-size: .9rem; }',
        '.grid td.empty { cursor: default; }',
        '.grid td.day:hover:not(.disabled):not(.empty) { background: var(--accent-bg, #e0e7ff); }',
        '.grid td.day.today { font-weight: 700; outline: 1px solid var(--accent, #2563eb); }',
        '.grid td.day.selected { background: var(--accent, #2563eb); color: #fff; }',
        '.grid td.day.disabled { opacity: .3; cursor: not-allowed; }',
        '.popover-foot { display: flex; gap: .5rem; margin-top: .75rem; justify-content: space-between; }',
        '.today-btn, .clear-btn { background: none; border: 1px solid var(--border, #ccc); padding: .25rem .75rem;',
        '                         border-radius: 4px; cursor: pointer; font: inherit; }',
        '.today-btn:hover, .clear-btn:hover { background: var(--accent-bg, #e0e7ff); }'
      ].join('\n');
    }

    _attachListeners() {
      var self = this;
      this.shadowRoot.addEventListener('click', function (e) {
        var dayCell = e.target.closest('td.day:not(.disabled):not(.empty)');
        if (dayCell) {
          var iso = dayCell.getAttribute('data-iso');
          self._setValue(iso);
          return;
        }
        if (e.target.closest('.toggle') || e.target.classList.contains('display')) {
          self._open = !self._open;
          self._render();
          return;
        }
        if (e.target.matches('[data-nav="prev"]')) {
          self._cursor = new Date(self._cursor.getFullYear(), self._cursor.getMonth() - 1, 1);
          self._render();
          return;
        }
        if (e.target.matches('[data-nav="next"]')) {
          self._cursor = new Date(self._cursor.getFullYear(), self._cursor.getMonth() + 1, 1);
          self._render();
          return;
        }
        if (e.target.matches('[data-action="today"]')) {
          var today = new Date();
          self._setValue(toISO(today.getFullYear(), today.getMonth(), today.getDate()));
          return;
        }
        if (e.target.matches('[data-action="clear"]')) {
          self._setValue(null);
          return;
        }
      });

      this.shadowRoot.addEventListener('keydown', function (e) {
        if (!self._open) return;
        if (e.key === 'Escape') { self._open = false; self._render(); }
      });

      // Close popover when clicking outside
      document.addEventListener('click', function (e) {
        if (!self._open) return;
        if (!self.contains(e.target) && !self.shadowRoot.contains(e.target)) {
          self._open = false;
          self._render();
        }
      });
    }

    _setValue(iso) {
      var prev = this.getAttribute('value');
      if (iso === null) {
        this.removeAttribute('value');
        this._selected = null;
      } else {
        this.setAttribute('value', iso);
        this._selected = parseISO(iso);
      }
      this._open = false;
      this._render();
      if (prev !== iso) {
        this.dispatchEvent(new CustomEvent('change', {
          bubbles: true,
          detail: {
            value: iso,
            display: this._selected ? formatDisplay(this._selected.y, this._selected.m, this._selected.d) : ''
          }
        }));
      }
    }

    get value() { return this.getAttribute('value') || null; }
    set value(v) {
      if (v === null || v === '') {
        this.removeAttribute('value');
      } else {
        this.setAttribute('value', v);
      }
      this._readAttrs();
      this._render();
    }
  }

  if (!customElements.get('saskia-date')) {
    customElements.define('saskia-date', SaskiaDate);
  }
})();
