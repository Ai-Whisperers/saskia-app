/* Phase 29: Live time tracker
 *
 * Auto-updates elements with [data-relative-time] attribute
 * to show relative time ("hace 2 min") that updates every minute.
 *
 * Usage:
 *   <span data-relative-time="{{ pedido.created_at }}">cargando…</span>
 *   <time data-relative-time="{{ evento.fecha }}" data-format="smart">...</time>
 */

(function() {
    'use strict';

    if (!window.DateFormat) {
        console.warn('DateFormat not loaded; relative times will not update');
        return;
    }

    const LiveTime = {
        // All tracked elements
        elements: new Set(),
        // Update interval (ms)
        interval: 60000, // 1 minute

        init() {
            this.refresh();
            this.start();
        },

        // Find and register all [data-relative-time] elements
        refresh() {
            const found = document.querySelectorAll('[data-relative-time]');
            found.forEach(el => this.elements.add(el));
        },

        // Start auto-update loop
        start() {
            setInterval(() => this.update(), this.interval);
        },

        // Update all elements
        update() {
            this.elements.forEach(el => {
                if (!document.body.contains(el)) {
                    this.elements.delete(el);
                    return;
                }
                this.updateElement(el);
            });
        },

        // Update single element
        updateElement(el) {
            const timestamp = el.getAttribute('data-relative-time');
            const format = el.getAttribute('data-format') || 'relative';

            if (!timestamp) return;

            let result;
            switch (format) {
                case 'short':
                    result = window.DateFormat.short(timestamp);
                    break;
                case 'dateTime':
                    result = window.DateFormat.dateTime(timestamp);
                    break;
                case 'smart':
                    result = window.DateFormat.smart(timestamp);
                    break;
                case 'time':
                    result = window.DateFormat.time(timestamp);
                    break;
                default:
                    result = window.DateFormat.relative(timestamp);
            }

            // Use title for full datetime on hover
            const fullDate = window.DateFormat.dateTime(timestamp);
            el.setAttribute('title', fullDate);

            // Update text (preserve innerHTML if it has children like icons)
            if (el.children.length === 0) {
                el.textContent = result;
            } else {
                // Find a text-only child node and update that
                const textNode = Array.from(el.childNodes)
                    .find(n => n.nodeType === Node.TEXT_NODE);
                if (textNode) {
                    textNode.textContent = result;
                }
            }
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => LiveTime.init());
    } else {
        LiveTime.init();
    }

    // Re-scan DOM after page navigations (for SPAs or HTMX)
    const observer = new MutationObserver(() => LiveTime.refresh());
    observer.observe(document.body, { childList: true, subtree: true });

    window.LiveTime = LiveTime;
})();