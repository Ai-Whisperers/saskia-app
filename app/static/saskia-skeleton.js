/* app/static/saskia-skeleton.js — <saskia-skeleton> placeholder component.

Renders shimmering placeholder boxes while data loads.
3 variants:
- 'line':   text-line placeholder (h: 1em, w: configurable)
- 'card':   card-sized placeholder (~180px tall)
- 'kpi':    KPI tile placeholder (matches metric_card dimensions)

Usage:
  <saskia-skeleton variant="line" width="60%"></saskia-skeleton>
  <saskia-skeleton variant="card"></saskia-skeleton>
  <saskia-skeleton variant="kpi" label="Cargando ventas"></saskia-skeleton>
  <saskia-skeleton-stack count="5" variant="line"></saskia-skeleton-stack>
*/

(function () {
  'use strict';

  class SaskiaSkeleton extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
    }
    static get observedAttributes() {
      return ['variant', 'width', 'height', 'label'];
    }
    connectedCallback() {
      this._render();
    }
    attributeChangedCallback() {
      this._render();
    }
    _render() {
      var variant = this.getAttribute('variant') || 'line';
      var width = this.getAttribute('width') || '100%';
      var height = this.getAttribute('height');
      var label = this.getAttribute('label') || '';
      var styles = this._styles(variant);
      var style = 'width:' + width + ';';
      if (height) style += 'height:' + height + ';';
      this.shadowRoot.innerHTML =
        '<style>' + styles + '</style>' +
        (label ? '<div class="label">' + this._esc(label) + '</div>' : '') +
        '<div class="sk sk-' + variant + '" style="' + style + '" role="presentation" aria-label="' + this._esc(label || 'Cargando…') + '" aria-busy="true"></div>';
    }
    _esc(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    _styles(variant) {
      return [
        ':host { display: block; }',
        '.sk {',
        '  background: linear-gradient(90deg,',
        '    var(--color-surface-subtle, #f1f5f9) 0%,',
        '    var(--color-surface, #fff) 50%,',
        '    var(--color-surface-subtle, #f1f5f9) 100%);',
        '  background-size: 200% 100%;',
        '  animation: sk-shimmer 1.4s ease-in-out infinite;',
        '  border-radius: 4px;',
        '}',
        '.sk-card { height: 180px; border-radius: 8px; border: 1px solid var(--color-border, #e2e8f0); }',
        '.sk-kpi { height: 88px; border-radius: 8px; border: 1px solid var(--color-border, #e2e8f0); padding: 1rem; }',
        '.label { font-size: 0.75rem; color: var(--color-text-muted, #64748b); margin-bottom: 0.25rem; }',
        '@keyframes sk-shimmer {',
        '  0% { background-position: 200% 0; }',
        '  100% { background-position: -200% 0; }',
        '}',
        '@media (prefers-reduced-motion: reduce) {',
        '  .sk { animation: none; background: var(--color-surface-subtle, #f1f5f9); }',
        '}'
      ].join('\n');
    }
  }

  class SaskiaSkeletonStack extends HTMLElement {
    constructor() {
      super();
      this._count = 5;
      this._variant = 'line';
      this.attachShadow({ mode: 'open' });
    }
    static get observedAttributes() {
      return ['count', 'variant', 'gap'];
    }
    connectedCallback() {
      this._render();
    }
    attributeChangedCallback(name, oldVal, newVal) {
      if (name === 'count') this._count = parseInt(newVal, 10) || 5;
      if (name === 'variant') this._variant = newVal || 'line';
      if (this.isConnected) this._render();
    }
    _render() {
      var variant = this.getAttribute('variant') || 'line';
      var count = parseInt(this.getAttribute('count'), 10) || 5;
      var gap = this.getAttribute('gap') || '0.5rem';
      var cards = '';
      for (var i = 0; i < count; i++) {
        var w;
        if (variant === 'kpi') {
          cards += '<saskia-skeleton variant="kpi" style="flex:1;min-width:180px"></saskia-skeleton>';
        } else if (variant === 'card') {
          cards += '<saskia-skeleton variant="card"></saskia-skeleton>';
        } else {
          // line: vary widths to look natural
          var widths = ['60%', '90%', '80%', '70%', '95%', '50%', '85%', '65%', '75%', '88%'];
          w = widths[i % widths.length];
          cards += '<saskia-skeleton variant="line" width="' + w + '"></saskia-skeleton>';
        }
      }
      var containerStyle = variant === 'kpi'
        ? 'display:flex;gap:' + gap + ';flex-wrap:wrap;align-items:flex-start;'
        : 'display:flex;flex-direction:column;gap:' + gap + ';';
      this.shadowRoot.innerHTML =
        '<style>:host { display: block; }</style>' +
        '<div style="' + containerStyle + '" role="presentation" aria-busy="true">' + cards + '</div>';
    }
  }

  if (!customElements.get('saskia-skeleton')) {
    customElements.define('saskia-skeleton', SaskiaSkeleton);
  }
  if (!customElements.get('saskia-skeleton-stack')) {
    customElements.define('saskia-skeleton-stack', SaskiaSkeletonStack);
  }
})();
