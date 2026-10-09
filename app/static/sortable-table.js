/* Phase 22: Sortable table component

Allows clicking table headers to sort by column. Works with all existing tables.
Adds visual indicators, keyboard support, and URL-based state preservation.
*/

(function() {
    'use strict';

    const SORT_ASC = 'asc';
    const SORT_DESC = 'desc';
    const SORT_NONE = '';

    // Get all sortable tables
    function init() {
        const tables = document.querySelectorAll('table.sortable, table[data-sortable]');
        tables.forEach(setupTable);
    }

    function setupTable(table) {
        // Skip if already initialized
        if (table.dataset.sortableInit === '1') return;
        table.dataset.sortableInit = '1';

        // Find thead
        const thead = table.tHead || table.querySelector('thead');
        if (!thead) return;

        // Setup each header
        const headers = thead.querySelectorAll('th');
        headers.forEach((th, index) => {
            // Skip if not sortable
            if (th.hasAttribute('data-no-sort')) return;
            if (th.classList.contains('no-sort')) return;
            if (!th.textContent.trim()) return;

            // Make sortable
            th.classList.add('sortable-header');
            th.setAttribute('role', 'button');
            th.setAttribute('tabindex', '0');
            th.setAttribute('aria-sort', 'none');
            th.setAttribute('data-sort-key', th.dataset.sortKey || th.textContent.trim());

            // Add sort indicator
            const indicator = document.createElement('span');
            indicator.className = 'sort-indicator';
            indicator.setAttribute('aria-hidden', 'true');
            indicator.textContent = '↕';
            th.appendChild(indicator);

            // Click handler
            th.addEventListener('click', () => sortTable(table, index));
            th.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    sortTable(table, index);
                }
            });
        });

        // Restore sort state from URL
        restoreSortState(table);
    }

    function sortTable(table, columnIndex) {
        const thead = table.tHead || table.querySelector('thead');
        const th = thead.querySelectorAll('th')[columnIndex];
        const tbody = table.tBodies[0];
        if (!tbody) return;

        // Determine new sort direction
        let newDir;
        const currentDir = th.getAttribute('aria-sort');
        if (currentDir === SORT_ASC) {
            newDir = SORT_DESC;
        } else if (currentDir === SORT_DESC) {
            newDir = SORT_NONE;
        } else {
            newDir = SORT_ASC;
        }

        // Reset all headers
        const allHeaders = thead.querySelectorAll('th');
        allHeaders.forEach(header => {
            header.setAttribute('aria-sort', 'none');
            header.classList.remove('sort-asc', 'sort-desc');
        });

        // If sort is none, restore original order
        if (newDir === SORT_NONE) {
            // Reset to original order
            const rows = Array.from(tbody.querySelectorAll('tr'));
            rows.sort((a, b) => {
                const aIdx = parseInt(a.dataset.originalIndex || '0', 10);
                const bIdx = parseInt(b.dataset.originalIndex || '0', 10);
                return aIdx - bIdx;
            });
            rows.forEach(row => tbody.appendChild(row));
            updateURL(null, null);
            return;
        }

        // Apply sort
        th.setAttribute('aria-sort', newDir);
        th.classList.add(newDir === SORT_ASC ? 'sort-asc' : 'sort-desc');

        // Get rows and sort
        const rows = Array.from(tbody.querySelectorAll('tr'));

        // Store original indices if not already stored
        rows.forEach((row, idx) => {
            if (!row.dataset.originalIndex) {
                row.dataset.originalIndex = idx;
            }
        });

        // Sort rows
        rows.sort((a, b) => {
            const aCell = a.cells[columnIndex];
            const bCell = b.cells[columnIndex];

            if (!aCell || !bCell) return 0;

            let aValue = getCellValue(aCell);
            let bValue = getCellValue(bCell);

            // Handle numeric values
            const aNum = parseFloat(aValue);
            const bNum = parseFloat(bValue);
            if (!isNaN(aNum) && !isNaN(bNum)) {
                aValue = aNum;
                bValue = bNum;
            }

            // Compare
            if (aValue < bValue) return newDir === SORT_ASC ? -1 : 1;
            if (aValue > bValue) return newDir === SORT_ASC ? 1 : -1;
            return 0;
        });

        // Reorder DOM
        rows.forEach(row => tbody.appendChild(row));

        // Update URL
        const sortKey = th.dataset.sortKey;
        updateURL(sortKey, newDir);
    }

    function getCellValue(cell) {
        // Get data-sort-value if present
        if (cell.dataset.sortValue !== undefined) {
            return cell.dataset.sortValue;
        }

        // Strip HTML and get text
        let text = cell.textContent || cell.innerText || '';
        return text.trim();
    }

    function updateURL(sortKey, direction) {
        if (!sortKey) {
            // Remove sort params
            const url = new URL(window.location.href);
            url.searchParams.delete('sort');
            url.searchParams.delete('dir');
            window.history.replaceState({}, '', url);
            return;
        }

        const url = new URL(window.location.href);
        url.searchParams.set('sort', sortKey);
        url.searchParams.set('dir', direction);
        window.history.replaceState({}, '', url);
    }

    function restoreSortState(table) {
        const url = new URL(window.location.href);
        const sortKey = url.searchParams.get('sort');
        const direction = url.searchParams.get('dir');

        if (!sortKey || !direction) return;

        // Find the matching header
        const headers = (table.tHead || table.querySelector('thead')).querySelectorAll('th');
        let targetHeader = null;
        let targetIndex = -1;

        headers.forEach((th, index) => {
            if (th.dataset.sortKey === sortKey) {
                targetHeader = th;
                targetIndex = index;
            }
        });

        if (targetHeader && targetIndex >= 0) {
            // Apply sort
            targetHeader.setAttribute('aria-sort', direction);
            targetHeader.classList.add(direction === SORT_ASC ? 'sort-asc' : 'sort-desc');
            // Re-sort the table
            const tbody = table.tBodies[0];
            if (tbody) {
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.forEach((row, idx) => {
                    if (!row.dataset.originalIndex) {
                        row.dataset.originalIndex = idx;
                    }
                });
                rows.sort((a, b) => {
                    const aCell = a.cells[targetIndex];
                    const bCell = b.cells[targetIndex];
                    if (!aCell || !bCell) return 0;
                    let aValue = getCellValue(aCell);
                    let bValue = getCellValue(bCell);
                    const aNum = parseFloat(aValue);
                    const bNum = parseFloat(bValue);
                    if (!isNaN(aNum) && !isNaN(bNum)) {
                        aValue = aNum;
                        bValue = bNum;
                    }
                    if (aValue < bValue) return direction === SORT_ASC ? -1 : 1;
                    if (aValue > bValue) return direction === SORT_ASC ? 1 : -1;
                    return 0;
                });
                rows.forEach(row => tbody.appendChild(row));
            }
        }
    }

    // Auto-initialize on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-initialize when new tables are added dynamically
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) {
                    if (node.tagName === 'TABLE' && (node.classList.contains('sortable') || node.hasAttribute('data-sortable'))) {
                        setupTable(node);
                    }
                    const tables = node.querySelectorAll && node.querySelectorAll('table.sortable, table[data-sortable]');
                    if (tables) {
                        tables.forEach(setupTable);
                    }
                }
            });
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Expose globally
    window.SortableTable = {
        init: init,
        sortBy: function(table, sortKey, direction) {
            const headers = (table.tHead || table.querySelector('thead')).querySelectorAll('th');
            headers.forEach((th, index) => {
                if (th.dataset.sortKey === sortKey) {
                    th.setAttribute('aria-sort', direction);
                    th.classList.add(direction === SORT_ASC ? 'sort-asc' : 'sort-desc');
                    sortTable(table, index);
                }
            });
        }
    };
})();