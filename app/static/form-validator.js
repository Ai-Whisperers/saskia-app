/* Phase 32: Inline form validation
 *
 * Auto-applies validation styles and aria-invalid to form fields
 * based on HTML5 constraint validation API.
 *
 * Usage: Just add data-validate="true" to any <form>
 */

(function() {
    'use strict';

    const FormValidator = {
        init() {
            this._onSubmit = this._onSubmit.bind(this);
            this._onBlur = this._onBlur.bind(this);
            this._onInput = this._onInput.bind(this);

            const forms = document.querySelectorAll('form[data-validate="true"]');
            forms.forEach(form => {
                form.addEventListener('submit', this._onSubmit);
                form.addEventListener('blur', this._onBlur, true);
                form.addEventListener('input', this._onInput);
            });
        },

        _onSubmit(event) {
            const form = event.target;
            const fields = form.querySelectorAll('input, select, textarea');

            fields.forEach(field => {
                this._validateField(field);
            });
        },

        _onBlur(event) {
            const field = event.target;
            if (this._isFormField(field)) {
                this._validateField(field);
            }
        },

        _onInput(event) {
            const field = event.target;
            if (field.classList.contains('is-invalid')) {
                this._validateField(field);
            }
        },

        _isFormField(el) {
            return el.matches('input, select, textarea') &&
                   !el.disabled &&
                   !el.readOnly;
        },

        _validateField(field) {
            if (!field.checkValidity()) {
                this._markInvalid(field, field.validationMessage);
            } else {
                this._markValid(field);
            }
        },

        _markInvalid(field, message) {
            field.classList.remove('is-valid');
            field.classList.add('is-invalid');
            field.setAttribute('aria-invalid', 'true');

            let feedback = field.parentElement.querySelector('.invalid-feedback[data-for="' + field.id + '"]');
            if (!feedback && field.id) {
                feedback = field.parentElement.querySelector('.invalid-feedback:not([data-for])');
                if (feedback) feedback.setAttribute('data-for', field.id);
            }
            if (feedback && message) {
                feedback.textContent = message;
                feedback.style.display = 'block';
            }
        },

        _markValid(field) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
            field.setAttribute('aria-invalid', 'false');

            const feedback = field.parentElement.querySelector('.invalid-feedback');
            if (feedback) {
                feedback.textContent = '';
                feedback.style.display = 'none';
            }
        },

        validate(form) {
            if (!form) return true;
            const fields = form.querySelectorAll('input, select, textarea');
            let valid = true;
            fields.forEach(field => {
                if (!this._validateField(field)) valid = false;
            });
            return valid;
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => FormValidator.init());
    } else {
        FormValidator.init();
    }

    window.FormValidator = FormValidator;
})();