/* Phase 35: Auto-save form drafts to localStorage
 *
 * Automatically saves form state to localStorage and restores on load.
 * Useful for long forms to prevent data loss.
 *
 * Usage: <form data-autosave="my-form-key">
 */

(function() {
    'use strict';

    const AutoSave = {
        // Default save delay (ms)
        debounceMs: 800,

        init() {
            this._onInput = this._debounce(this._onInput.bind(this), this.debounceMs);

            const forms = document.querySelectorAll('form[data-autosave]');
            forms.forEach(form => this._setupForm(form));
        },

        _setupForm(form) {
            const key = form.getAttribute('data-autosave');
            if (!key) return;

            // Restore on load
            this._restoreForm(form, key);

            // Save on input
            form.addEventListener('input', (e) => {
                this._onInput(form, key);
            });
            form.addEventListener('change', (e) => {
                this._onInput(form, key);
            });

            // Clear on successful submit
            form.addEventListener('submit', () => {
                this._clear(key);
            });
        },

        _onInput(form, key) {
            const data = this._serialize(form);
            try {
                localStorage.setItem(key, JSON.stringify({
                    data,
                    savedAt: Date.now()
                }));
            } catch (e) {
                console.warn('AutoSave: localStorage failed', e);
            }
        },

        _serialize(form) {
            const data = {};
            const fields = form.querySelectorAll('input, select, textarea');
            fields.forEach(field => {
                if (!field.name) return;
                if (field.type === 'checkbox') {
                    data[field.name] = field.checked;
                } else if (field.type === 'radio') {
                    if (field.checked) data[field.name] = field.value;
                } else if (field.tagName === 'SELECT' && field.multiple) {
                    data[field.name] = Array.from(field.selectedOptions).map(o => o.value);
                } else {
                    data[field.name] = field.value;
                }
            });
            return data;
        },

        _restoreForm(form, key) {
            try {
                const stored = localStorage.getItem(key);
                if (!stored) return;

                const { data, savedAt } = JSON.parse(stored);

                // Skip if older than 24 hours
                if (Date.now() - savedAt > 24 * 60 * 60 * 1000) {
                    localStorage.removeItem(key);
                    return;
                }

                const fields = form.querySelectorAll('input, select, textarea');
                let restored = 0;
                fields.forEach(field => {
                    if (!field.name || !(field.name in data)) return;
                    const value = data[field.name];

                    if (field.type === 'checkbox') {
                        field.checked = value === true;
                        if (field.checked) restored++;
                    } else if (field.type === 'radio') {
                        if (field.value === value) {
                            field.checked = true;
                            restored++;
                        }
                    } else if (field.tagName === 'SELECT' && field.multiple && Array.isArray(value)) {
                        Array.from(field.options).forEach(opt => {
                            opt.selected = value.includes(opt.value);
                            if (opt.selected) restored++;
                        });
                    } else {
                        field.value = value;
                        if (value) restored++;
                    }
                });

                if (restored > 0) {
                    this._showRestoreNotice(form, key);
                }
            } catch (e) {
                console.warn('AutoSave: restore failed', e);
            }
        },

        _showRestoreNotice(form, key) {
            const notice = document.createElement('div');
            notice.className = 'autosave-notice';
            notice.style.cssText = 'padding:8px 12px;background:var(--color-bg-elevated,#f0f9ff);border:1px solid var(--color-primary,#3b82f6);border-radius:4px;margin-bottom:1rem;display:flex;align-items:center;gap:8px;font-size:0.875rem;';
            notice.innerHTML = `
                <span>📝 Se restauró borrador guardado</span>
                <button type="button" class="btn btn-sm btn-ghost"
                        data-discard-autosave="${key}"
                        style="margin-left:auto;">
                    Descartar borrador
                </button>
            `;

            form.parentElement.insertBefore(notice, form);

            notice.querySelector('[data-discard-autosave]').addEventListener('click', () => {
                this._clear(key);
                notice.remove();
                form.reset();
            });
        },

        _clear(key) {
            try {
                localStorage.removeItem(key);
            } catch (e) {
                // ignore
            }
        },

        _debounce(fn, ms) {
            let timer = null;
            return function(...args) {
                if (timer) clearTimeout(timer);
                timer = setTimeout(() => fn.apply(this, args), ms);
            };
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => AutoSave.init());
    } else {
        AutoSave.init();
    }

    window.AutoSave = AutoSave;
})();