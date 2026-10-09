/**
 * saskia-tooltip — accessible Web Component for tooltips
 *
 * Usage: <saskia-tooltip text="Helpful text">Trigger</saskia-tooltip>
 *        <button saskia-tooltip="...">Button</button>
 */
class SaskiaTooltip extends HTMLElement {
    static get observedAttributes() {
        return ['text', 'position', 'delay'];
    }

    constructor() {
        super();
        this._tooltipEl = null;
        this._showTimeout = null;
        this._hideTimeout = null;
        this._boundShow = this._show.bind(this);
        this._boundHide = this._hide.bind(this);
    }

    connectedCallback() {
        // Make focusable
        if (!this.hasAttribute('tabindex')) {
            this.setAttribute('tabindex', '0');
        }

        // Set role
        if (!this.hasAttribute('role')) {
            // Buttons stay buttons; everything else gets tooltip role
            if (this.tagName !== 'BUTTON' && this.tagName !== 'A') {
                this.setAttribute('role', 'button');
            }
        }

        this.addEventListener('mouseenter', this._boundShow);
        this.addEventListener('mouseleave', this._boundHide);
        this.addEventListener('focus', this._boundShow);
        this.addEventListener('blur', this._boundHide);
        this.addEventListener('click', this._boundShow);
    }

    disconnectedCallback() {
        this.removeEventListener('mouseenter', this._boundShow);
        this.removeEventListener('mouseleave', this._boundHide);
        this.removeEventListener('focus', this._boundShow);
        this.removeEventListener('blur', this._boundHide);
        this.removeEventListener('click', this._boundShow);
        this._removeTooltip();
    }

    attributeChangedCallback(name, oldValue, newValue) {
        if (name === 'text' && this._tooltipEl) {
            this._tooltipEl.textContent = newValue;
        }
    }

    get text() {
        return this.getAttribute('text') || this.getAttribute('saskia-tooltip') || '';
    }

    get position() {
        return this.getAttribute('position') || 'top';
    }

    get delay() {
        return parseInt(this.getAttribute('delay') || '300', 10);
    }

    _show() {
        clearTimeout(this._hideTimeout);
        this._showTimeout = setTimeout(() => {
            this._createTooltip();
        }, this.delay);
    }

    _hide() {
        clearTimeout(this._showTimeout);
        this._hideTimeout = setTimeout(() => {
            this._removeTooltip();
        }, 100);
    }

    _createTooltip() {
        if (!this.text) return;
        if (this._tooltipEl) return;

        const tooltip = document.createElement('div');
        tooltip.className = `saskia-tooltip saskia-tooltip--${this.position}`;
        tooltip.setAttribute('role', 'tooltip');
        tooltip.textContent = this.text;
        document.body.appendChild(tooltip);

        // Position
        this._positionTooltip(tooltip);

        // Show with animation
        requestAnimationFrame(() => {
            tooltip.classList.add('saskia-tooltip--visible');
        });

        this._tooltipEl = tooltip;
    }

    _positionTooltip(tooltip) {
        const rect = this.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const scrollY = window.scrollY || window.pageYOffset;
        const scrollX = window.scrollX || window.pageXOffset;

        let top, left;

        switch (this.position) {
            case 'top':
                top = rect.top + scrollY - tooltipRect.height - 8;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
                break;
            case 'bottom':
                top = rect.bottom + scrollY + 8;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
                break;
            case 'left':
                top = rect.top + scrollY + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.left + scrollX - tooltipRect.width - 8;
                break;
            case 'right':
                top = rect.top + scrollY + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.right + scrollX + 8;
                break;
            default:
                top = rect.top + scrollY - tooltipRect.height - 8;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
        }

        // Viewport collision
        const margin = 8;
        const viewportWidth = window.innerWidth;
        if (left < margin) left = margin;
        if (left + tooltipRect.width > viewportWidth - margin) {
            left = viewportWidth - tooltipRect.width - margin;
        }

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    _removeTooltip() {
        if (this._tooltipEl) {
            this._tooltipEl.remove();
            this._tooltipEl = null;
        }
    }
}

customElements.define('saskia-tooltip', SaskiaTooltip);

// Auto-attach to elements with saskia-tooltip attribute
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[saskia-tooltip]').forEach(el => {
        if (el.tagName !== 'SASKIA-TOOLTIP' && !el.hasAttribute('saskia-tooltip-attached')) {
            el.setAttribute('saskia-tooltip-attached', '1');
            el.setAttribute('text', el.getAttribute('saskia-tooltip'));
            new SaskiaTooltip.call(el); // Attach behavior
        }
    });
});