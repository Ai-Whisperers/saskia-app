/* Phase 36: Number input steppers
 *
 * Adds +/- buttons to number inputs for touch/mouse users.
 * Usage: <input type="number" data-stepper min="0" step="1">
 */

(function() {
    'use strict';

    const Stepper = {
        init() {
            const inputs = document.querySelectorAll('input[type="number"][data-stepper]');
            inputs.forEach(input => this._enhance(input));
        },

        _enhance(input) {
            if (input.dataset.stepperReady) return;
            input.dataset.stepperReady = 'true';

            // Create wrapper
            const wrapper = document.createElement('div');
            wrapper.className = 'stepper';

            // Insert wrapper before input
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
            input.classList.add('stepper__input');

            // Create buttons
            const decBtn = this._createButton('-', () => this._step(input, -1));
            const incBtn = this._createButton('+', () => this._step(input, 1));

            wrapper.appendChild(decBtn);
            wrapper.appendChild(input);
            wrapper.appendChild(incBtn);

            // Update step from input attribute
            input.addEventListener('input', () => this._updateButtons(input, decBtn, incBtn));
            this._updateButtons(input, decBtn, incBtn);
        },

        _createButton(text, handler) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'stepper__btn';
            btn.textContent = text;
            btn.setAttribute('aria-label', text === '+' ? 'Aumentar' : 'Disminuir');
            btn.addEventListener('click', handler);
            return btn;
        },

        _step(input, direction) {
            const step = parseFloat(input.step) || 1;
            const min = parseFloat(input.min);
            const max = parseFloat(input.max);
            const current = parseFloat(input.value) || 0;

            let newValue = current + (step * direction);

            // Apply step alignment
            if (input.step && input.step !== 'any') {
                const base = parseFloat(input.min) || 0;
                newValue = base + Math.round((newValue - base) / step) * step;
                // Round to step's decimal places
                const decimals = (input.step.toString().split('.')[1] || '').length;
                newValue = parseFloat(newValue.toFixed(decimals));
            }

            // Clamp to bounds
            if (!isNaN(min) && newValue < min) newValue = min;
            if (!isNaN(max) && newValue > max) newValue = max;

            input.value = newValue;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        },

        _updateButtons(input, decBtn, incBtn) {
            const value = parseFloat(input.value);
            const min = parseFloat(input.min);
            const max = parseFloat(input.max);

            decBtn.disabled = !isNaN(min) && value <= min;
            incBtn.disabled = !isNaN(max) && value >= max;
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Stepper.init());
    } else {
        Stepper.init();
    }

    window.Stepper = Stepper;
})();