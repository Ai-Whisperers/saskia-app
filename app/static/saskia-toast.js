/* app/static/saskia-toast.js — <saskia-toast> global toast notifications.

Replaces ad-hoc flash messages with a single toast queue that:
- Stacks at top-right (or top-center on mobile)
- Auto-dismisses after `duration` ms (default 4000)
- Can be persistent (duration=0)
- Supports 4 severities: success, info, warn, error
- Has action buttons (e.g. "Deshacer")
- Dismissible by click
- ARIA: aria-live=polite for non-errors, assertive for errors

Usage:
  <saskia-toast-stack></saskia-toast-stack>
  <script>
    SaskiaToast.show({ message: 'Guardado', severity: 'success', action: {label: 'Deshacer', onclick: undo} });
  </script>
*/

(function () {
  'use strict';

  var SaskiaToast = {
    _stack: null,
    _ensureStack: function () {
      if (this._stack) return;
      var existing = document.querySelector('saskia-toast-stack');
      if (existing) {
        this._stack = existing;
        return;
      }
      var stack = document.createElement('saskia-toast-stack');
      document.body.appendChild(stack);
      this._stack = stack;
    },
    show: function (opts) {
      this._ensureStack();
      return this._stack._add(opts);
    },
    dismiss: function (id) {
      if (this._stack) this._stack._dismiss(id);
    },
    dismissAll: function () {
      if (this._stack) this._stack._dismissAll();
    }
  };
  window.SaskiaToast = SaskiaToast;

  class SaskiaToastStack extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._nextId = 1;
    }

    connectedCallback() {
      this._render();
    }

    _render() {
      this.shadowRoot.innerHTML =
        '<style>' + this._css() + '</style>' +
        '<div class="toast-stack" role="region" aria-label="Notificaciones"></div>';
    }

    _css() {
      return [
        ':host { position: fixed; top: 1rem; right: 1rem; z-index: 10000; max-width: 28rem; pointer-events: none; font: inherit; }',
        '@media (max-width: 640px) { :host { left: 1rem; right: 1rem; max-width: none; top: .5rem; } }',
        '.toast-stack { display: flex; flex-direction: column; gap: .5rem; }',
        '.toast {',
        '  display: flex; align-items: flex-start; gap: .75rem;',
        '  background: var(--card, #fff); color: var(--fg, #111);',
        '  border: 1px solid var(--border, #ccc); border-left-width: 4px;',
        '  border-radius: 6px; padding: .75rem 1rem;',
        '  box-shadow: 0 4px 12px rgba(0,0,0,.1);',
        '  pointer-events: auto;',
        '  animation: toast-in .25s ease-out;',
        '  min-width: 16rem;',
        '}',
        '.toast.is-leaving { animation: toast-out .2s ease-in forwards; }',
        '@keyframes toast-in { from { transform: translateX(110%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }',
        '@keyframes toast-out { to { transform: translateX(110%); opacity: 0; } }',
        '.toast.sev-success { border-left-color: #10b981; }',
        '.toast.sev-info { border-left-color: #2563eb; }',
        '.toast.sev-warn { border-left-color: #f59e0b; }',
        '.toast.sev-error { border-left-color: #dc2626; }',
        '.toast.sev-error { background: #fef2f2; }',
        '.toast .icon-wrap { flex-shrink: 0; }',
        '.toast.sev-success .icon-wrap { color: #10b981; }',
        '.toast.sev-info .icon-wrap { color: #2563eb; }',
        '.toast.sev-warn .icon-wrap { color: #f59e0b; }',
        '.toast.sev-error .icon-wrap { color: #dc2626; }',
        '.toast-body { flex: 1; }',
        '.toast-title { font-weight: 600; margin: 0; }',
        '.toast-message { margin: .25rem 0 0; font-size: .9rem; }',
        '.toast-actions { display: flex; gap: .5rem; margin-top: .5rem; }',
        '.toast-action {',
        '  background: none; border: 1px solid var(--border, #ccc);',
        '  padding: .25rem .75rem; border-radius: 4px; cursor: pointer;',
        '  font: inherit; font-size: .85rem;',
        '}',
        '.toast-action:hover { background: var(--accent-bg, #e0e7ff); }',
        '.toast-close {',
        '  background: none; border: none; cursor: pointer;',
        '  color: var(--muted-fg, #666); font-size: 1.25rem;',
        '  padding: 0 .25rem; line-height: 1;',
        '}',
        '.toast-close:hover { color: var(--fg, #111); }'
      ].join('\n');
    }

    _add(opts) {
      opts = opts || {};
      var sev = opts.severity || 'info';
      var id = this._nextId++;
      var duration = opts.duration === undefined ? 4000 : opts.duration;
      var title = opts.title || '';
      var message = opts.message || '';
      var actions = opts.actions || (opts.action ? [opts.action] : []);

      var toast = document.createElement('div');
      toast.className = 'toast sev-' + sev;
      toast.setAttribute('role', sev === 'error' ? 'alert' : 'status');
      toast.setAttribute('aria-live', sev === 'error' ? 'assertive' : 'polite');
      toast.dataset.toastId = id;

      var iconChar = { success: '✓', info: 'ℹ', warn: '⚠', error: '✕' }[sev] || 'ℹ';

      var html = '<div class="icon-wrap">' + iconChar + '</div>';
      html += '<div class="toast-body">';
      if (title) html += '<p class="toast-title">' + this._esc(title) + '</p>';
      if (message) html += '<p class="toast-message">' + this._esc(message) + '</p>';
      if (actions.length) {
        html += '<div class="toast-actions">';
        for (var i = 0; i < actions.length; i++) {
          var a = actions[i];
          html += '<button class="toast-action" data-action-idx="' + i + '">' + this._esc(a.label || '') + '</button>';
        }
        html += '</div>';
      }
      html += '</div>';
      html += '<button class="toast-close" aria-label="Cerrar">×</button>';
      toast.innerHTML = html;

      // Wire close button
      toast.querySelector('.toast-close').addEventListener('click', this._dismiss.bind(this, id));

      // Wire action buttons
      var actionBtns = toast.querySelectorAll('.toast-action');
      for (var j = 0; j < actionBtns.length; j++) {
        (function (btn, idx) {
          btn.addEventListener('click', function () {
            try {
              var a = actions[idx];
              if (a && typeof a.onclick === 'function') a.onclick();
            } catch (e) {
              console.error('Toast action error:', e);
            }
            SaskiaToast.dismiss(id);
          });
        })(actionBtns[j], j);
      }

      var stack = this.shadowRoot.querySelector('.toast-stack');
      stack.appendChild(toast);

      // Auto-dismiss
      if (duration > 0) {
        setTimeout(this._dismiss.bind(this, id), duration);
      }

      return id;
    }

    _esc(s) {
      if (s === null || s === undefined) return '';
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    _dismiss(id) {
      var toast = this.shadowRoot.querySelector('[data-toast-id="' + id + '"]');
      if (!toast) return;
      toast.classList.add('is-leaving');
      var self = this;
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 200);
    }

    _dismissAll() {
      var toasts = this.shadowRoot.querySelectorAll('.toast');
      for (var i = 0; i < toasts.length; i++) {
        var id = parseInt(toasts[i].dataset.toastId, 10);
        this._dismiss(id);
      }
    }
  }

  if (!customElements.get('saskia-toast-stack')) {
    customElements.define('saskia-toast-stack', SaskiaToastStack);
  }
})();
