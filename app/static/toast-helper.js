/* Phase 22 / Sprint Day 6: Toast notification helper
 *
 * Simplifies showing saskia-toast notifications from any page.
 * Wraps the Web Component for ergonomic usage.
 */

(function() {
    'use strict';

    const Toast = {
        success: function(message, duration = 4000) {
            return this._show(message, 'success', duration);
        },

        error: function(message, duration = 6000) {
            return this._show(message, 'error', duration);
        },

        warning: function(message, duration = 5000) {
            return this._show(message, 'warning', duration);
        },

        info: function(message, duration = 4000) {
            return this._show(message, 'info', duration);
        },

        _show: function(message, kind, duration) {
            const stack = document.querySelector('saskia-toast-stack');
            if (!stack) {
                console.warn('saskia-toast-stack not found');
                return null;
            }

            // Create toast element
            const toast = document.createElement('saskia-toast');
            toast.setAttribute('kind', kind);
            toast.setAttribute('duration', String(duration));
            toast.textContent = message;

            // Add to stack
            stack.appendChild(toast);

            // Auto-remove after duration
            if (duration > 0) {
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.remove();
                    }
                }, duration);
            }

            return toast;
        },

        // Confirmation toast with action
        confirm: function(message, onConfirm, onCancel) {
            const stack = document.querySelector('saskia-toast-stack');
            if (!stack) return;

            const toast = document.createElement('saskia-toast');
            toast.setAttribute('kind', 'info');
            toast.setAttribute('duration', '0'); // persistent
            toast.innerHTML = `
                <div style="display:flex;align-items:center;gap:12px;">
                    <span>${message}</span>
                    <button class="btn btn-sm btn-primary" data-action="confirm">Sí</button>
                    <button class="btn btn-sm btn-ghost" data-action="cancel">No</button>
                </div>
            `;

            toast.querySelector('[data-action="confirm"]').addEventListener('click', () => {
                toast.remove();
                if (onConfirm) onConfirm();
            });

            toast.querySelector('[data-action="cancel"]').addEventListener('click', () => {
                toast.remove();
                if (onCancel) onCancel();
            });

            stack.appendChild(toast);
            return toast;
        }
    };

    window.Toast = Toast;
})();