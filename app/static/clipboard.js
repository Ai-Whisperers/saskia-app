/* Phase 30: Copy to clipboard utility
 *
 * Replaces the need for tiny inline onclick handlers for copy actions.
 * Provides visual feedback and keyboard accessibility.
 *
 * Usage:
 *   <button data-copy="some text">Copy</button>
 *   <button data-copy-from="#element-id">Copy content of element</button>
 */

(function() {
    'use strict';

    const Clipboard = {
        init() {
            document.addEventListener('click', this.handleClick.bind(this));
        },

        handleClick(event) {
            const btn = event.target.closest('[data-copy], [data-copy-from]');
            if (!btn) return;

            event.preventDefault();
            let text = btn.getAttribute('data-copy');

            if (!text && btn.hasAttribute('data-copy-from')) {
                const target = document.querySelector(btn.getAttribute('data-copy-from'));
                if (!target) return;
                text = target.textContent || target.value || '';
            }

            if (!text) return;
            this.copy(text, btn);
        },

        async copy(text, btn) {
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                } else {
                    this._fallback(text);
                }
                this._showFeedback(btn, 'success');
            } catch (err) {
                console.error('Copy failed:', err);
                this._showFeedback(btn, 'error');
            }
        },

        _fallback(text) {
            // Old execCommand fallback
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
            } finally {
                document.body.removeChild(ta);
            }
        },

        _showFeedback(btn, type) {
            const original = btn.innerHTML;
            const originalClass = btn.className;
            const successMsg = btn.getAttribute('data-copy-success') || '✓ Copiado';
            const errorMsg = btn.getAttribute('data-copy-error') || '✗ Error';

            btn.classList.add(`copy-${type}`);
            btn.innerHTML = type === 'success' ? successMsg : errorMsg;
            btn.setAttribute('aria-live', 'polite');

            setTimeout(() => {
                btn.classList.remove(`copy-${type}`);
                btn.innerHTML = original;
                btn.className = originalClass;
            }, 1500);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Clipboard.init());
    } else {
        Clipboard.init();
    }

    window.Clipboard = Clipboard;
})();