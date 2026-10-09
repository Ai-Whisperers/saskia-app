/* Phase 31: Print area utility
 *
 * Print specific parts of a page instead of the whole thing.
 * Usage:
 *   <button data-print="#receipt">Imprimir</button>
 *   <button data-print data-print-hide=".no-print">Imprimir todo</button>
 */

(function() {
    'use strict';

    const PrintArea = {
        init() {
            document.addEventListener('click', this.handleClick.bind(this));
        },

        handleClick(event) {
            const btn = event.target.closest('[data-print]');
            if (!btn) return;

            event.preventDefault();
            const target = btn.getAttribute('data-print');
            const hideSelector = btn.getAttribute('data-print-hide');
            const title = btn.getAttribute('data-print-title');

            this.print(target, hideSelector, title);
        },

        print(target, hideSelector, customTitle) {
            if (target) {
                const element = document.querySelector(target);
                if (!element) {
                    console.warn(`Print target not found: ${target}`);
                    return;
                }

                // Create iframe for clean print
                const iframe = document.createElement('iframe');
                iframe.style.position = 'fixed';
                iframe.style.right = '-10000px';
                iframe.style.bottom = '0';
                iframe.style.width = '0';
                iframe.style.height = '0';
                iframe.style.border = '0';
                document.body.appendChild(iframe);

                const doc = iframe.contentDocument;
                doc.open();
                doc.write(this._buildHtml(element, customTitle));
                doc.close();

                iframe.contentWindow.focus();

                setTimeout(() => {
                    try {
                        iframe.contentWindow.print();
                    } catch (err) {
                        console.error('Print failed:', err);
                    }
                    setTimeout(() => document.body.removeChild(iframe), 1000);
                }, 250);
            } else {
                // Print entire page
                if (customTitle) {
                    document.title = customTitle;
                }
                window.print();
            }
        },

        _buildHtml(element, title) {
            // Clone element and stylesheets
            const styles = Array.from(document.styleSheets)
                .map(sheet => {
                    try {
                        return Array.from(sheet.cssRules || [])
                            .map(rule => rule.cssText)
                            .join('\n');
                    } catch (e) {
                        return '';
                    }
                })
                .join('\n');

            const pageTitle = title || document.title;

            return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>${this._escape(pageTitle)}</title>
<style>
${styles}
@media print {
  body { padding: 0; }
  @page { margin: 1cm; }
}
</style>
</head>
<body>
${element.outerHTML}
</body>
</html>`;
        },

        _escape(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => PrintArea.init());
    } else {
        PrintArea.init();
    }

    window.PrintArea = PrintArea;
})();