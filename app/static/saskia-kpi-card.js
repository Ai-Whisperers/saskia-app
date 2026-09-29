/* app/static/saskia-kpi-card.js — <saskia-kpi-card> KPI tile with delta + severity.

Wraps the metric_card macro pattern but adds:
- Delta arrow (↑ +12% vs prior period, ↓ -5%, — 0%)
- Severity color (success/warn/danger/neutral)
- Optional icon (inline SVG name from icons.svg sprite)
- Optional href → renders as <a>
- ARIA: role="status" + aria-live="polite" for screen readers
- Spanish-first copy

Usage:
  <saskia-kpi-card label="Ventas de hoy"
                    value="Gs. 1.250.000"
                    delta="+12%"
                    delta-direction="up"
                    severity="success"
                    icon="icon-dollar"
                    href="/reportes/diario"></saskia-kpi-card>

Attributes:
  label              (required) Card title
  value              (required) Main value (string, render as-is)
  sub                Optional sublabel under value
  delta              Optional delta string (e.g. "+12%", "-5%", "0")
  delta-direction    "up" | "down" | "flat" — controls arrow + color
  delta-prior        Optional period label ("vs ayer", "vs semana")
  severity           "success" | "warn" | "danger" | "neutral"
  icon               Icon sprite name (rendered via <svg><use>)
  href               If set, renders the whole card as a link
  tooltip            Hover title
  compact            Boolean — reduces padding

Events: none (read-only display)
*/

(function () {
  'use strict';

  if (customElements.get('saskia-kpi-card')) return;

  var ARROW = {
    up: '↑',
    down: '↓',
    flat: '—'
  };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'class') node.className = attrs[k];
        else if (k === 'html') node.innerHTML = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      children.forEach(function (c) {
        if (typeof c === 'string') node.appendChild(document.createTextNode(c));
        else if (c) node.appendChild(c);
      });
    }
    return node;
  }

  class SASKIAKpiCard extends HTMLElement {
    connectedCallback() {
      if (this._rendered) return;
      this._rendered = true;
      this._render();
    }

    static get observedAttributes() {
      return ['label', 'value', 'sub', 'delta', 'delta-direction', 'delta-prior',
              'severity', 'icon', 'href', 'tooltip', 'compact'];
    }

    attributeChangedCallback() {
      if (this._rendered) this._render();
    }

    _render() {
      var label = this.getAttribute('label') || '';
      var value = this.getAttribute('value') || '';
      var sub = this.getAttribute('sub');
      var delta = this.getAttribute('delta');
      var deltaDir = this.getAttribute('delta-direction') || 'flat';
      var deltaPrior = this.getAttribute('delta-prior');
      var severity = this.getAttribute('severity') || 'neutral';
      var icon = this.getAttribute('icon');
      var href = this.getAttribute('href');
      var tooltip = this.getAttribute('tooltip');
      var compact = this.hasAttribute('compact');

      // Delta suppression rule (hat 40 — auditors / new users):
      // Never show delta arrow when delta is "0" / "+0" / "-0".
      // Reduces noise and avoids "↑ 0 ventas" confusion.
      var suppressDelta = !delta
        || delta.trim() === '0'
        || delta.trim() === '+0'
        || delta.trim() === '-0'
        || delta.trim() === '+0%'
        || delta.trim() === '-0%'
        || delta.trim() === '0%';

      // Resolve final severity from delta direction when not explicit
      var finalSev = severity;
      if (delta && !suppressDelta && severity === 'neutral') {
        if (deltaDir === 'up') finalSev = 'success';
        else if (deltaDir === 'down') finalSev = 'danger';
      }

      var sevClass = 'metric-card--sev-' + finalSev;
      var compactClass = compact ? ' metric-card--compact' : '';
      var wrapperClass = 'metric-card metric-card--kpi' + compactClass + ' ' + sevClass;

      // Clear children
      while (this.firstChild) this.removeChild(this.firstChild);

      // Build shadow-less inline rendering (style isolation via CSS vars)
      var card = el('div', { class: wrapperClass });
      if (tooltip) card.setAttribute('title', tooltip);

      // Header row: label + optional icon
      var labelRow = el('div', { class: 'metric-card__head' });
      if (icon) {
        var iconSvg = el('span', { class: 'metric-card__icon' });
        iconSvg.innerHTML = '<svg aria-hidden="true"><use href="/static/icons.svg#' + icon + '"></use></svg>';
        labelRow.appendChild(iconSvg);
      }
      labelRow.appendChild(el('span', { class: 'metric-card__label' }, [label]));
      card.appendChild(labelRow);

      // Value
      card.appendChild(el('div', { class: 'metric-card__value' }, [value]));

      // Delta row (suppressed when 0)
      if (delta && !suppressDelta) {
        var deltaRow = el('div', { class: 'metric-card__delta metric-card__delta--' + deltaDir });
        var arrow = el('span', { class: 'metric-card__delta-arrow', 'aria-hidden': 'true' }, [ARROW[deltaDir] || '—']);
        deltaRow.appendChild(arrow);
        deltaRow.appendChild(el('span', { class: 'metric-card__delta-text' }, [delta]));
        if (deltaPrior) {
          deltaRow.appendChild(el('span', { class: 'metric-card__delta-prior' }, [' ' + deltaPrior]));
        }
        deltaRow.setAttribute('aria-label', 'Cambio ' + deltaDir + ' ' + delta + (deltaPrior ? ' ' + deltaPrior : ''));
        card.appendChild(deltaRow);
      }

      // Sub
      if (sub) card.appendChild(el('div', { class: 'metric-card__sub' }, [sub]));

      // Optional href → wrap in <a>
      if (href) {
        var a = el('a', { class: 'metric-card__link', href: href, 'aria-label': label + ': ' + value });
        a.appendChild(card);
        this.appendChild(a);
      } else {
        this.appendChild(card);
      }

      // ARIA for screen readers
      this.setAttribute('role', 'status');
      this.setAttribute('aria-live', 'polite');
    }
  }

  customElements.define('saskia-kpi-card', SASKIAKpiCard);
})();
