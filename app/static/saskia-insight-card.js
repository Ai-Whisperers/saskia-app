/* app/static/saskia-insight-card.js — <saskia-insight-card> actionable insight tile.

Wraps the metric_card macro pattern but adds:
- Primary action button that can navigate or perform an action
- Dismiss button that calls API and removes the card
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
  id               (required) Unique insight identifier for dismissal
  title            (required) Card title (1 line)
  detail           (required) 1-sentence detail text
  action-text      (required) Button label
  action-href      (required) Where to navigate on action click
  severity         "warn" | "danger" | "success" | "neutral"
  icon             Icon sprite name (rendered via <svg><use>)

Events:
  Dismiss: calls POST /api/insights/{id}/dismiss (requires csrf_token)
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
      
      // Dismiss button
      var dismissBtn = el('button', { 
        class: 'metric-card__dismiss-btn', 
        type: 'button',
        title: 'Descartar por hoy'
      });
      dismissBtn.innerHTML = '<svg aria-hidden="true"><use href="#icon-close"/></svg>';
      dismissBtn.onclick = this._handleDismiss.bind(this);
      labelRow.appendChild(dismissBtn);
      
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

    _handleDismiss(event) {
      event.preventDefault();
      event.stopPropagation();
      
      var id = this.getAttribute('id');
      if (!id) return;

      // Find CSRF token from the form (usually in a hidden input)
      var csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
      if (!csrfToken) {
        console.error('CSRF token not found for insight dismissal');
        return;
      }

      // Call API to dismiss
      fetch('/api/insights/' + encodeURIComponent(id) + '/dismiss', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'csrf_token=' + encodeURIComponent(csrfToken)
      })
      .then(response => {
        if (response.ok) {
          // Remove the card from DOM
          this.style.opacity = '0';
          setTimeout(() => {
            this.remove();
          }, 300);
        } else {
          console.error('Failed to dismiss insight:', response.status);
        }
      })
      .catch(error => {
        console.error('Error dismissing insight:', error);
      });
    }
  }

  customElements.define('saskia-insight-card', SASKIAInsightCard);
})();