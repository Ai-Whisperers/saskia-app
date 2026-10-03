/* Phase 34: IntersectionObserver lazy load
 *
 * Auto-applies IntersectionObserver to images with [data-lazy-src]
 * attribute. Useful for images added dynamically.
 *
 * Usage: <img data-lazy-src="/path/to/image.jpg" alt="...">
 */

(function() {
    'use strict';

    const LazyLoad = {
        observer: null,

        init() {
            // Native lazy loading check
            if ('loading' in HTMLImageElement.prototype) {
                this._applyNativeLazy();
            } else {
                this._setupObserver();
            }
        },

        _applyNativeLazy() {
            // Convert data-lazy-src to src + loading="lazy"
            const images = document.querySelectorAll('img[data-lazy-src]');
            images.forEach(img => {
                const src = img.getAttribute('data-lazy-src');
                if (src && !img.getAttribute('src')) {
                    img.setAttribute('src', src);
                    img.setAttribute('loading', 'lazy');
                    img.setAttribute('decoding', 'async');
                }
            });
        },

        _setupObserver() {
            if (!('IntersectionObserver' in window)) {
                this._applyNativeLazy();
                return;
            }

            this.observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        this._loadImage(img);
                        this.observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '200px',  // Start loading 200px before viewport
                threshold: 0.01
            });

            // Observe all lazy images
            const images = document.querySelectorAll('img[data-lazy-src]');
            images.forEach(img => this.observer.observe(img));

            // Also observe newly added images
            const mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(m => {
                    m.addedNodes.forEach(node => {
                        if (node.nodeType === 1) { // Element
                            if (node.matches && node.matches('img[data-lazy-src]')) {
                                this.observer.observe(node);
                            }
                            const nested = node.querySelectorAll
                                ? node.querySelectorAll('img[data-lazy-src]')
                                : [];
                            nested.forEach(img => this.observer.observe(img));
                        }
                    });
                });
            });
            mutationObserver.observe(document.body, { childList: true, subtree: true });
        },

        _loadImage(img) {
            const src = img.getAttribute('data-lazy-src');
            if (!src) return;

            img.src = src;
            img.removeAttribute('data-lazy-src');
        },

        // Public method to force-load all images
        loadAll() {
            const images = document.querySelectorAll('img[data-lazy-src]');
            images.forEach(img => this._loadImage(img));
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => LazyLoad.init());
    } else {
        LazyLoad.init();
    }

    window.LazyLoad = LazyLoad;
})();