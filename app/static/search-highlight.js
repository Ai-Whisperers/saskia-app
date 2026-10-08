/* Phase 22 / Sprint Day 4: Search highlight utility
 *
 * Highlights search query matches in result text.
 * Used by pedidos, clientes, productos search results.
 */

(function() {
    'use strict';

    const SearchHighlight = {
        highlight: function(element, query) {
            if (!query || !element) return;
            // Remove old highlights
            this.clear(element);

            if (!query || query.length < 2) return;

            // Escape regex special chars
            const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${safeQuery})`, 'gi');

            // Walk text nodes only
            const walker = document.createTreeWalker(
                element,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: (node) => {
                        // Skip script, style, already-highlighted
                        if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
                        const parent = node.parentElement;
                        if (!parent) return NodeFilter.FILTER_REJECT;
                        const tag = parent.tagName;
                        if (['SCRIPT', 'STYLE', 'MARK'].includes(tag)) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        return NodeFilter.FILTER_ACCEPT;
                    }
                }
            );

            const matches = [];
            let node;
            while (node = walker.nextNode()) {
                matches.push(node);
            }

            matches.forEach(textNode => {
                const text = textNode.nodeValue;
                if (!regex.test(text)) return;

                const fragment = document.createDocumentFragment();
                let lastIdx = 0;
                regex.lastIndex = 0;
                let match;

                while ((match = regex.exec(text)) !== null) {
                    // Text before match
                    if (match.index > lastIdx) {
                        fragment.appendChild(
                            document.createTextNode(text.slice(lastIdx, match.index))
                        );
                    }
                    // The match itself
                    const mark = document.createElement('mark');
                    mark.className = 'search-highlight';
                    mark.textContent = match[0];
                    fragment.appendChild(mark);
                    lastIdx = regex.lastIndex;
                }

                // Remaining text
                if (lastIdx < text.length) {
                    fragment.appendChild(
                        document.createTextNode(text.slice(lastIdx))
                    );
                }

                textNode.parentNode.replaceChild(fragment, textNode);
            });
        },

        clear: function(element) {
            if (!element) return;
            const marks = element.querySelectorAll('mark.search-highlight');
            marks.forEach(mark => {
                const parent = mark.parentNode;
                parent.replaceChild(
                    document.createTextNode(mark.textContent),
                    mark
                );
                parent.normalize();
            });
        },

        // Auto-attach to search inputs
        init: function() {
            document.querySelectorAll('[data-search-highlight]').forEach(input => {
                const targetSelector = input.dataset.searchHighlight;
                const target = document.querySelector(targetSelector);
                if (!target) return;

                let debounceTimer;
                input.addEventListener('input', (e) => {
                    clearTimeout(debounceTimer);
                    debounceTimer = setTimeout(() => {
                        this.highlight(target, e.target.value.trim());
                    }, 200);
                });

                // Clear on Escape
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        input.value = '';
                        this.clear(target);
                    }
                });
            });
        }
    };

    // Auto-init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => SearchHighlight.init());
    } else {
        SearchHighlight.init();
    }

    window.SearchHighlight = SearchHighlight;
})();
