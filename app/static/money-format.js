/* Phase 28: Money/Number formatting utility
 *
 * Consistent Guaraní (Gs.) formatting across the app.
 * Handles K/M abbreviations, sign, decimals, etc.
 */

(function() {
    'use strict';

    const MoneyFormat = {
        // Format as "Gs. 1.234.567" (default)
        guaranies: function(amount, options = {}) {
            if (amount === null || amount === undefined || isNaN(amount)) {
                return options.emptyPlaceholder || '—';
            }

            const num = Number(amount);
            const sign = num < 0 ? '-' : '';
            const absNum = Math.abs(num);

            // Format with thousand separators (dots in es-PY)
            const formatted = Math.round(absNum).toString()
                .replace(/\B(?=(\d{3})+(?!\d))/g, '.');

            if (options.prefix !== false) {
                return `${sign}Gs. ${formatted}`;
            }
            return `${sign}${formatted}`;
        },

        // Short format: "Gs. 1.2M", "Gs. 1.5K"
        short: function(amount) {
            if (amount === null || amount === undefined || isNaN(amount)) return '—';
            const num = Number(amount);
            const absNum = Math.abs(num);
            const sign = num < 0 ? '-' : '';

            if (absNum >= 1e9) {
                return `${sign}Gs. ${(absNum / 1e9).toFixed(1)}MM`;
            }
            if (absNum >= 1e6) {
                return `${sign}Gs. ${(absNum / 1e6).toFixed(1)}M`;
            }
            if (absNum >= 1e3) {
                return `${sign}Gs. ${(absNum / 1e3).toFixed(1)}K`;
            }
            return this.guaranies(num);
        },

        // Format percentage
        percent: function(value, decimals = 0) {
            if (value === null || value === undefined || isNaN(value)) return '—';
            return `${Number(value).toFixed(decimals)}%`;
        },

        // Format with sign (+/-) and color hint
        delta: function(amount) {
            if (amount === null || amount === undefined || isNaN(amount)) return '—';
            const num = Number(amount);
            if (num === 0) return '0';
            const sign = num > 0 ? '+' : '';
            return `${sign}${this.guaranies(num)}`;
        },

        // Format just the number with dots (no currency)
        number: function(amount) {
            if (amount === null || amount === undefined || isNaN(amount)) return '—';
            const num = Math.round(Number(amount));
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        },

        // Format quantity with units
        quantity: function(amount, unit = '') {
            if (amount === null || amount === undefined || isNaN(amount)) return '—';
            const num = Number(amount);
            // Show 2 decimals if needed, otherwise integer
            const formatted = num % 1 === 0
                ? num.toString()
                : num.toFixed(2);
            return unit ? `${formatted} ${unit}` : formatted;
        },

        // Compact for KPI cards
        kpi: function(amount) {
            if (amount === null || amount === undefined || isNaN(amount)) return '—';
            const num = Number(amount);
            const absNum = Math.abs(num);
            const sign = num < 0 ? '-' : '';

            if (absNum >= 1e9) {
                return `${sign}Gs. ${(absNum / 1e9).toFixed(1)}B`;
            }
            if (absNum >= 1e6) {
                return `${sign}Gs. ${(absNum / 1e6).toFixed(1)}M`;
            }
            if (absNum >= 1e3) {
                return `${sign}Gs. ${(absNum / 1e3).toFixed(0)}K`;
            }
            return `${sign}Gs. ${absNum}`;
        }
    };

    window.MoneyFormat = MoneyFormat;
})();