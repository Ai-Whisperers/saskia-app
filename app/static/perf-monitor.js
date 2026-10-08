/* Phase 23: Performance monitoring utility
 *
 * Tracks key Web Vitals and sends to console.
 * Can be extended to POST to analytics endpoint.
 */

(function() {
    'use strict';

    const Performance = {
        _metrics: {},
        _observers: [],

        init: function() {
            if (!window.performance) return;

            // Track page load time
            window.addEventListener('load', () => {
                this._trackPageLoad();
                this._trackResources();
                this._trackNavigationTiming();
            });

            // Track Largest Contentful Paint
            this._trackLCP();

            // Track First Input Delay
            this._trackFID();

            // Track Cumulative Layout Shift
            this._trackCLS();
        },

        _trackPageLoad: function() {
            const timing = performance.getEntriesByType('navigation')[0];
            if (timing) {
                this._metrics.pageLoad = {
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.domContentLoadedEventStart,
                    loadComplete: timing.loadEventEnd - timing.loadEventStart,
                    totalTime: timing.loadEventEnd - timing.navigationStart
                };
            }
        },

        _trackResources: function() {
            const resources = performance.getEntriesByType('resource');
            const byType = {};

            resources.forEach(r => {
                const ext = r.name.split('.').pop().toLowerCase().split('?')[0];
                const type = this._getResourceType(r.name, ext);
                if (!byType[type]) byType[type] = { count: 0, totalSize: 0, totalTime: 0 };
                byType[type].count++;
                byType[type].totalSize += r.transferSize || 0;
                byType[type].totalTime += r.duration || 0;
            });

            this._metrics.resources = byType;
        },

        _getResourceType: function(url, ext) {
            if (url.includes('/static/') && ext === 'js') return 'js';
            if (url.includes('/static/') && ext === 'css') return 'css';
            if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'avif'].includes(ext)) return 'image';
            if (['woff', 'woff2', 'ttf'].includes(ext)) return 'font';
            return 'other';
        },

        _trackNavigationTiming: function() {
            const nav = performance.getEntriesByType('navigation')[0];
            if (!nav) return;

            this._metrics.timing = {
                dns: nav.domainLookupEnd - nav.domainLookupStart,
                tcp: nav.connectEnd - nav.connectStart,
                request: nav.responseStart - nav.requestStart,
                response: nav.responseEnd - nav.responseStart,
                dom: nav.domComplete - nav.domInteractive
            };
        },

        _trackLCP: function() {
            try {
                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    this._metrics.lcp = lastEntry.renderTime || lastEntry.loadTime;
                });
                observer.observe({ type: 'largest-contentful-paint', buffered: true });
                this._observers.push(observer);
            } catch (e) {
                // Not supported
            }
        },

        _trackFID: function() {
            try {
                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        this._metrics.fid = entry.processingStart - entry.startTime;
                    });
                });
                observer.observe({ type: 'first-input', buffered: true });
                this._observers.push(observer);
            } catch (e) {
                // Not supported
            }
        },

        _trackCLS: function() {
            try {
                let clsValue = 0;
                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    });
                    this._metrics.cls = clsValue;
                });
                observer.observe({ type: 'layout-shift', buffered: true });
                this._observers.push(observer);
            } catch (e) {
                // Not supported
            }
        },

        // Get all metrics
        getMetrics: function() {
            return this._metrics;
        },

        // Get specific metric
        getMetric: function(name) {
            return this._metrics[name];
        },

        // Mark a custom timing point
        mark: function(name) {
            if (performance.mark) {
                performance.mark(name);
            }
        },

        // Measure between two marks
        measure: function(name, startMark, endMark) {
            try {
                if (performance.measure) {
                    performance.measure(name, startMark, endMark);
                    const measure = performance.getEntriesByName(name)[0];
                    return measure ? measure.duration : null;
                }
            } catch (e) {
                return null;
            }
        },

        // Disconnect all observers
        disconnect: function() {
            this._observers.forEach(obs => obs.disconnect());
            this._observers = [];
        }
    };

    // Auto-init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Performance.init());
    } else {
        Performance.init();
    }

    // Expose globally for debugging
    window.Performance = Performance;
})();