/* Phase 27: Date formatting utility
 *
 * Consistent date formatting across the app.
 * Handles relative dates ("hace 2 horas"), Paraguayan formats, etc.
 */

(function() {
    'use strict';

    const DateFormat = {
        // Format as DD/MM/YYYY (Paraguayan standard)
        short: function(date) {
            if (!date) return '';
            const d = this._toDate(date);
            if (!d) return '';
            const day = String(d.getDate()).padStart(2, '0');
            const month = String(d.getMonth() + 1).padStart(2, '0');
            return `${day}/${month}/${d.getFullYear()}`;
        },

        // Format as DD/MM/YYYY HH:mm
        dateTime: function(date) {
            if (!date) return '';
            const d = this._toDate(date);
            if (!d) return '';
            const datePart = this.short(d);
            const time = this.time(d);
            return `${datePart} ${time}`;
        },

        // Format as HH:mm
        time: function(date) {
            if (!date) return '';
            const d = this._toDate(date);
            if (!d) return '';
            const hours = String(d.getHours()).padStart(2, '0');
            const mins = String(d.getMinutes()).padStart(2, '0');
            return `${hours}:${mins}`;
        },

        // Relative time: "hace 2 horas", "en 3 días"
        relative: function(date) {
            if (!date) return '';
            const d = this._toDate(date);
            if (!d) return '';

            const now = new Date();
            const diffMs = d.getTime() - now.getTime();
            const diffSec = Math.round(diffMs / 1000);
            const absSec = Math.abs(diffSec);

            // Less than a minute
            if (absSec < 60) {
                return diffSec < 0 ? 'recién' : 'en un momento';
            }

            const diffMin = Math.round(diffSec / 60);
            const absMin = Math.abs(diffMin);

            // Less than an hour
            if (absMin < 60) {
                return diffMin < 0
                    ? `hace ${absMin} min`
                    : `en ${absMin} min`;
            }

            const diffHour = Math.round(diffMin / 60);
            const absHour = Math.abs(diffHour);

            // Less than a day
            if (absHour < 24) {
                return diffHour < 0
                    ? `hace ${absHour} hora${absHour !== 1 ? 's' : ''}`
                    : `en ${absHour} hora${absHour !== 1 ? 's' : ''}`;
            }

            const diffDay = Math.round(diffHour / 24);
            const absDay = Math.abs(diffDay);

            // Less than a week
            if (absDay < 7) {
                return diffDay < 0
                    ? `hace ${absDay} día${absDay !== 1 ? 's' : ''}`
                    : `en ${absDay} día${absDay !== 1 ? 's' : ''}`;
            }

            // Less than a month
            if (absDay < 30) {
                const weeks = Math.round(absDay / 7);
                return diffDay < 0
                    ? `hace ${weeks} semana${weeks !== 1 ? 's' : ''}`
                    : `en ${weeks} semana${weeks !== 1 ? 's' : ''}`;
            }

            // Fall back to short date
            return this.short(d);
        },

        // Smart: relative if recent, else short date
        smart: function(date) {
            if (!date) return '';
            const d = this._toDate(date);
            if (!d) return '';

            const now = new Date();
            const diffDays = Math.abs((d - now) / (1000 * 60 * 60 * 24));

            if (diffDays < 7) {
                return this.relative(d);
            }
            return this.short(d);
        },

        // Day name in Spanish
        dayName: function(date) {
            const days = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
            const d = this._toDate(date);
            if (!d) return '';
            return days[d.getDay()];
        },

        // Month name in Spanish
        monthName: function(date) {
            const months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
            const d = this._toDate(date);
            if (!d) return '';
            return months[d.getMonth()];
        },

        // Convert any input to Date
        _toDate: function(input) {
            if (input instanceof Date) return input;
            if (typeof input === 'string' || typeof input === 'number') {
                const d = new Date(input);
                return isNaN(d.getTime()) ? null : d;
            }
            return null;
        }
    };

    window.DateFormat = DateFormat;
})();