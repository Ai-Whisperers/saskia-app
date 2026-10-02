/* app/static/saskia-insight-card.js — <saskia-insight-card> actionable insight tile.

Wraps the metric_card macro pattern but adds:
- Primary action button that can navigate or perform an action
- ARIA: role="alert" + aria-live="polite" for screen readers
- Spanish-first copy

Usage:
  <saskia-insight-card
    id="restock_urgent"
    title="Reposición urgente"
    detail="Harina con solo 2 días de stock"
    action-text="Reordenar"
    action-href="/reorder?ingredient=harina"
    severity="warn"
    icon="icon-reorder">
  </saskia-insight-card>

Attributes:
  id               (required) Unique insight identifier
  title            (required) Card title (1 line)
  detail           (required) 1-sentence detail text
  action-text      (required) Button label
  action-href      (required) Where to navigate on action click
  severity         "warn" | "danger" | "success" | "neutral"
  icon             Icon sprite name (rendered via <svg><use>)
*/

(function () {
  'use strict';

  if (customElements.get('saskia-insight-card')) return;

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

  class SASKIAInsightCard extends HTMLElement {
    connectedCallback() {
      if (this._rendered) return;
      this._rendered = true;
      this._render();
    }

    static get observedAttributes() {
      return ['id', 'title', 'detail', 'action-text', 'action-href', 'severity', 'icon'];
    }

    attributeChangedCallback() {
      if (this._rendered) this._render();
    }

    _render() {
      var id = this.getAttribute('id') || '';
      var title = this.getAttribute('title') || '';
      var detail = this.getAttribute('detail') || '';
      var actionText = this.getAttribute('action-text') || '';
      var actionHref = this.getAttribute('action-href') || '';
      var severity = this.getAttribute('severity') || 'neutral';
      var icon = this.getAttribute('icon');

      var sevClass = 'metric-card--sev-' + severity;
      var wrapperClass = 'metric-card metric-card--insight ' + sevClass;

      // Clear children
      while (this.firstChild) this.removeChild(this.firstChild);

      // Build shadow-less inline rendering (style isolation via CSS vars)
      var card = el('div', { class: wrapperClass });
      
      // Header row: label + optional icon
      var labelRow = el('div', { class: 'metric-card__head' });
      if (icon) {
        var iconSvg = el('span', { class: 'metric-card__icon' });
        iconSvg.innerHTML = '<svg aria-hidden="true"><use href="/static/icons.svg#' + icon + '"></use></svg>';
        labelRow.appendChild(iconSvg);
      }
      labelRow.appendChild(el('span', { class: 'metric-card__label' }, [title]));

      card.appendChild(labelRow);

      // Detail
      card.appendChild(el('div', { class: 'metric-card__detail' }, [detail]));

      // Action button
      var actionBtn = el('a', {
        class: 'metric-card__action btn btn-sm',
        href: actionHref,
        'aria-label': actionText + ': ' + detail
      }, [actionText]);
      card.appendChild(el('div', { class: 'metric-card__action-wrapper' }, [actionBtn]));

      this.appendChild(card);

      // ARIA for screen readers
      this.setAttribute('role', 'alert');
      this.setAttribute('aria-live', 'polite');
      this.setAttribute('data-insight-id', id);
    }
  }

  customElements.define('saskia-insight-card', SASKIAInsightCard);
})();