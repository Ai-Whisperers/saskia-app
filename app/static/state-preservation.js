/* Phase 22: Cross-page state preservation utility

Preserves filters, search queries, view preferences across page visits.
Uses localStorage with cookie fallback for key state.
*/

// State preservation namespace
const StatePreservation = {
    // Keys for different state types
    keys: {
        filters: 'saskia-filters',
        search: 'saskia-search', 
        views: 'saskia-views',
        drafts: 'saskia-drafts',
        preferences: 'saskia-prefs'
    },

    // Get state from localStorage with fallback
    get: function(key, defaultValue = null) {
        try {
            const stored = localStorage.getItem(this.keys[key]);
            return stored ? JSON.parse(stored) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    },

    // Save state to localStorage
    set: function(key, value) {
        try {
            localStorage.setItem(this.keys[key], JSON.stringify(value));
        } catch (e) {
            console.warn('Failed to save state:', e);
        }
    },

    // Clear specific state
    clear: function(key) {
        localStorage.removeItem(this.keys[key]);
    },

    // Get filter state for a specific page
    getFilters: function(page) {
        const allFilters = this.get('filters', {});
        return allFilters[page] || {};
    },

    // Save filter state for a specific page
    setFilters: function(page, filters) {
        const allFilters = this.get('filters', {});
        allFilters[page] = filters;
        this.set('filters', allFilters);
    },

    // Get search query for a page
    getSearch: function(page) {
        const allSearch = this.get('search', {});
        return allSearch[page] || '';
    },

    // Save search query for a page
    setSearch: function(page, query) {
        const allSearch = this.get('search', {});
        allSearch[page] = query;
        this.set('search', allSearch);
    },

    // Get view preferences (sorting, filters, etc.)
    getViews: function(page) {
        const allViews = this.get('views', {});
        return allViews[page] || {};
    },

    // Save view preferences
    setViews: function(page, views) {
        const allViews = this.get('views', {});
        allViews[page] = views;
        this.set('views', allViews);
    },

    // Auto-save form data
    saveFormData: function(formId, data) {
        const drafts = this.get('drafts', {});
        drafts[formId] = {
            data: data,
            timestamp: new Date().toISOString()
        };
        this.set('drafts', drafts);
    },

    // Get saved form data
    getFormData: function(formId) {
        const drafts = this.get('drafts', {});
        const draft = drafts[formId];
        if (draft) {
            // Auto-delete old drafts (older than 24 hours)
            const age = new Date() - new Date(draft.timestamp);
            if (age > 24 * 60 * 60 * 1000) {
                delete drafts[formId];
                this.set('drafts', drafts);
                return null;
            }
            return draft.data;
        }
        return null;
    },

    // Clear old drafts
    clearOldDrafts: function() {
        const drafts = this.get('drafts', {});
        const now = new Date();
        let changed = false;
        
        for (const [formId, draft] of Object.entries(drafts)) {
            const age = now - new Date(draft.timestamp);
            if (age > 24 * 60 * 60 * 1000) {
                delete drafts[formId];
                changed = true;
            }
        }
        
        if (changed) {
            this.set('drafts', drafts);
        }
    }
};

// Global state preservation functions
window.StatePreservation = StatePreservation;

// Auto-clear old drafts on page load
document.addEventListener('DOMContentLoaded', function() {
    StatePreservation.clearOldDrafts();
});

// Auto-save inputs with data-saskia-state attribute
document.addEventListener('input', function(e) {
    const input = e.target;
    if (input.hasAttribute('data-saskia-state')) {
        const page = input.dataset.saskiaPage || window.location.pathname;
        const stateKey = input.dataset.saskiaState || input.name || input.id;
        
        const filters = StatePreservation.getFilters(page);
        filters[stateKey] = input.value;
        StatePreservation.setFilters(page, filters);
    }
});

// Auto-save selects with data-saskia-state
document.addEventListener('change', function(e) {
    const select = e.target;
    if (select.hasAttribute('data-saskia-state')) {
        const page = select.dataset.saskiaPage || window.location.pathname;
        const stateKey = select.dataset.saskiaState || select.name || select.id;
        
        const filters = StatePreservation.getFilters(page);
        filters[stateKey] = select.value;
        StatePreservation.setFilters(page, filters);
    }
});

// Auto-save form data on submit
document.addEventListener('submit', function(e) {
    const form = e.target;
    if (form.hasAttribute('data-saskia-autosave')) {
        const formData = new FormData(form);
        const data = {};
        for (let [key, value] of formData.entries()) {
            data[key] = value;
        }
        StatePreservation.saveFormData(form.id || form.name || 'form', data);
    }
});

// Restore saved form data
function restoreFormData(formId) {
    const data = StatePreservation.getFormData(formId);
    if (data) {
        const form = document.getElementById(formId);
        if (form) {
            for (const [key, value] of Object.entries(data)) {
                const input = form.querySelector(`[name="${key}"], [id="${key}"]`);
                if (input) {
                    input.value = value;
                }
            }
        }
    }
}

// Export restore function
window.restoreFormData = restoreFormData;