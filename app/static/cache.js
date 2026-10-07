/* Phase 22 / Sprint Day 5: Simple client-side cache
 *
 * Provides TTL-based caching for API responses and DOM queries.
 * Reduces server load and improves perceived performance.
 */

(function() {
    'use strict';

    const Cache = {
        _store: new Map(),
        _timers: new Map(),

        set: function(key, value, ttlMs = 60000) {
            // Clear existing timer
            if (this._timers.has(key)) {
                clearTimeout(this._timers.get(key));
            }

            this._store.set(key, {
                value: value,
                expiresAt: Date.now() + ttlMs
            });

            // Set expiration timer
            const timer = setTimeout(() => {
                this.delete(key);
            }, ttlMs);

            this._timers.set(key, timer);
        },

        get: function(key) {
            const entry = this._store.get(key);
            if (!entry) return undefined;

            if (Date.now() > entry.expiresAt) {
                this.delete(key);
                return undefined;
            }

            return entry.value;
        },

        has: function(key) {
            return this.get(key) !== undefined;
        },

        delete: function(key) {
            this._store.delete(key);
            if (this._timers.has(key)) {
                clearTimeout(this._timers.get(key));
                this._timers.delete(key);
            }
        },

        clear: function() {
            this._timers.forEach(timer => clearTimeout(timer));
            this._timers.clear();
            this._store.clear();
        },

        size: function() {
            return this._store.size;
        },

        // Memoize function with TTL
        memoize: function(fn, ttlMs = 60000) {
            const cache = this;
            return function(...args) {
                const key = JSON.stringify(args);
                const cached = cache.get(key);
                if (cached !== undefined) {
                    return Promise.resolve(cached);
                }
                return Promise.resolve(fn.apply(this, args)).then(result => {
                    cache.set(key, result, ttlMs);
                    return result;
                });
            };
        }
    };

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        Cache.clear();
    });

    window.Cache = Cache;
})();