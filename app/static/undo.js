/* Phase 33: Undo functionality for destructive actions
 *
 * Intercepts form submissions marked as destructive and shows an
 * undo toast instead of immediately committing the action.
 *
 * Usage: Add data-undo="30" (seconds) to <form>
 */

(function() {
    'use strict';

    const Undo = {
        // Seconds to allow undo
        defaultDuration: 30,

        init() {
            document.addEventListener('submit', this._onSubmit.bind(this), true);
        },

        _onSubmit(event) {
            const form = event.target;
            if (!form.matches('form[data-undo]')) return;

            // Don't intercept GET forms
            if ((form.method || 'get').toLowerCase() === 'get') return;

            event.preventDefault();
            const duration = parseInt(form.getAttribute('data-undo'), 10) || this.defaultDuration;
            const undoLabel = form.getAttribute('data-undo-label') || 'Acción realizada';
            const actionUrl = form.action;
            const formData = new FormData(form);

            this._showUndoToast(undoLabel, duration, () => {
                // Commit by re-submitting
                this._commit(actionUrl, formData, form);
            });
        },

        _showUndoToast(message, duration, onComplete) {
            if (!window.Toast) {
                // No toast helper; just commit immediately
                setTimeout(onComplete, 0);
                return;
            }

            // Use existing toast component
            const toast = document.createElement('saskia-toast');
            toast.setAttribute('variant', 'warning');
            toast.setAttribute('duration', (duration * 1000).toString());
            toast.innerHTML = `
                <div style="display:flex;align-items:center;gap:12px;">
                    <span>${message}</span>
                    <button type="button" class="btn btn-sm btn-primary"
                            data-undo-action
                            style="margin-left:auto;">
                        Deshacer (${duration}s)
                    </button>
                </div>
            `;

            // Auto-commit after duration
            let committed = false;
            const commit = () => {
                if (committed) return;
                committed = true;
                onComplete();
                if (toast.parentNode) toast.remove();
            };

            const undo = () => {
                if (committed) return;
                committed = true;
                if (toast.parentNode) toast.remove();
                // Cancel — do nothing
            };

            toast.addEventListener('click', (e) => {
                if (e.target.matches('[data-undo-action]')) {
                    undo();
                }
            });

            toast.addEventListener('toast-close', commit);
            setTimeout(commit, duration * 1000);

            document.body.appendChild(toast);
        },

        async _commit(url, formData, form) {
            try {
                const response = await fetch(url, {
                    method: form.method || 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.ok) {
                    if (window.Toast) {
                        window.Toast.success('✓ Acción completada');
                    }
                    // Reload to reflect changes
                    setTimeout(() => window.location.reload(), 500);
                } else {
                    if (window.Toast) {
                        window.Toast.error('✗ Error en la acción');
                    }
                }
            } catch (err) {
                console.error('Undo commit failed:', err);
                if (window.Toast) {
                    window.Toast.error('✗ Error de red');
                }
            }
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Undo.init());
    } else {
        Undo.init();
    }

    window.Undo = Undo;
})();