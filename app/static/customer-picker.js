/* app/static/customer-picker.js
 *
 * Vanilla-JS modal picker for the /ventas sale form.
 *
 * Backed by:
 *   GET  /clientes/api/search?q=...&limit=10  -> {"results": [...]}
 *   POST /clientes/api/create                 -> {"id": N, "customer": {...}}
 *
 * Reads/writes these DOM nodes (defined in _customer_picker.html):
 *   #customer_id                  hidden form field posted with /ventas/nueva
 *   #customer_picker_trigger      button that opens the modal
 *   #customer_picker_label       text inside the trigger button
 *   #customer_picker_hint         small hint shown after a pick
 *   #customer_picker_clear        "Quitar" button (resets selection)
 *   #customer_picker_modal        <dialog> element
 *   #customer_picker_search       search input
 *   #customer_picker_results      results container
 *   #customer_picker_new_btn      "+ Nuevo cliente" button
 *   #customer_picker_new_panel    sub-form panel for new customer
 *   #customer_picker_new_form     form for new customer
 *   #customer_picker_new_close    X to close the new-customer panel
 *   #cp_new_*                     new-customer form fields
 *   #cp_new_error                 error region in new-customer form
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  var trigger = $('customer_picker_trigger');
  var label = $('customer_picker_label');
  var hint = $('customer_picker_hint');
  var hidden = $('customer_id');
  var clearBtn = $('customer_picker_clear');
  var modal = $('customer_picker_modal');
  var closeBtn = $('customer_picker_close');
  var cancelBtn = $('customer_picker_cancel');
  var searchInput = $('customer_picker_search');
  var resultsEl = $('customer_picker_results');
  var newBtn = $('customer_picker_new_btn');
  var newPanel = $('customer_picker_new_panel');
  var newCloseBtn = $('customer_picker_new_close');
  var newCancelBtn = $('cp_new_cancel');
  var newForm = $('customer_picker_new_form');
  var newError = $('cp_new_error');
  var badge = $('customer_badge');
  var badgeName = $('customer_badge_name');

  if (!trigger || !modal || !hidden) {
    // Picker not on this page; bail silently.
    return;
  }

  var state = {
    selected: null,   // {id, name, hint, ...}
    lastQuery: '',
    inflight: null,   // AbortController for current search
    debounceTimer: null,
  };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderResults(items) {
    if (!items || items.length === 0) {
      resultsEl.innerHTML = '<p class="hint">No se encontraron clientes.</p>';
      return;
    }
    var html = items.map(function (c) {
      var subtitle = [
        c.phone ? escapeHtml(c.phone) : '',
        c.cedula ? ('CI/RUC ' + escapeHtml(c.cedula)) : '',
        c.email ? escapeHtml(c.email) : '',
      ].filter(Boolean).join(' · ');
      var stats = (c.n_sales != null ? c.n_sales + ' visitas' : '')
        + (c.lifetime_label ? ' · ' + escapeHtml(c.lifetime_label) : '');
      return ''
        + '<button type="button" class="customer-picker-result" '
        + 'data-id="' + c.id + '" data-name="' + escapeHtml(c.name) + '">'
        +   '<div class="customer-picker-result-main">'
        +     '<strong>' + escapeHtml(c.name) + '</strong>'
        +     (subtitle ? '<small>' + subtitle + '</small>' : '')
        +   '</div>'
        +   (stats ? '<small class="customer-picker-result-stats">' + stats + '</small>' : '')
        + '</button>';
    }).join('');
    resultsEl.innerHTML = html;
    // Wire up click handlers.
    Array.prototype.forEach.call(
      resultsEl.querySelectorAll('.customer-picker-result'),
      function (btn) {
        btn.addEventListener('click', function () {
          var id = parseInt(btn.getAttribute('data-id'), 10);
          var name = btn.getAttribute('data-name') || '';
          var match = (items || []).find(function (x) { return x.id === id; }) || null;
          pickCustomer(match || { id: id, name: name });
        });
      }
    );
  }

  function pickCustomer(c) {
    if (!c) return;
    state.selected = c;
    hidden.value = String(c.id);
    label.textContent = c.name || ('#' + c.id);
    hint.textContent = c.hint || (c.name + ' seleccionado');
    hint.hidden = false;
    if (badge) {
      badge.hidden = false;
      if (badgeName) badgeName.textContent = c.name || ('#' + c.id);
    }
    if (clearBtn) clearBtn.hidden = false;
    closeModal();
  }

  function clearSelection() {
    state.selected = null;
    hidden.value = '';
    label.textContent = 'Seleccionar cliente…';
    hint.hidden = true;
    hint.textContent = '';
    if (badge) {
      badge.hidden = true;
      if (badgeName) badgeName.textContent = '';
    }
    if (clearBtn) clearBtn.hidden = true;
  }

  function openModal() {
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }
    showSearchPanel();
    // Focus the search box so the cashier can type immediately.
    setTimeout(function () {
      if (searchInput) searchInput.focus();
      runSearch('');
    }, 0);
  }

  function closeModal() {
    if (typeof modal.close === 'function') {
      modal.close();
    } else {
      modal.removeAttribute('open');
    }
  }

  function showSearchPanel() {
    if (newPanel) newPanel.hidden = true;
    if (resultsEl) resultsEl.hidden = false;
  }

  function showNewPanel() {
    if (newError) {
      newError.hidden = true;
      newError.textContent = '';
    }
    if (newForm) newForm.reset();
    if (resultsEl) resultsEl.hidden = true;
    if (newPanel) newPanel.hidden = false;
    setTimeout(function () {
      var nameInput = $('cp_new_name');
      if (nameInput) nameInput.focus();
    }, 0);
  }

  function runSearch(q) {
    state.lastQuery = q;
    if (state.inflight) {
      try { state.inflight.abort(); } catch (e) {}
    }
    var ctrl = new AbortController();
    state.inflight = ctrl;
    var url = '/clientes/api/search?q=' + encodeURIComponent(q) + '&limit=10';
    fetch(url, { signal: ctrl.signal, headers: { 'Accept': 'application/json' } })
      .then(function (r) {
        if (!r.ok) throw new Error('search failed: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (state.lastQuery !== q) return; // stale
        renderResults((data && data.results) || []);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') return;
        resultsEl.innerHTML = '<p class="hint">Error al buscar clientes.</p>';
      });
  }

  function debouncedSearch(q) {
    if (state.debounceTimer) clearTimeout(state.debounceTimer);
    state.debounceTimer = setTimeout(function () { runSearch(q); }, 120);
  }

  // --- Wire up events ---

  if (trigger) trigger.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
  if (clearBtn) clearBtn.addEventListener('click', clearSelection);
  if (newBtn) newBtn.addEventListener('click', showNewPanel);
  if (newCloseBtn) newCloseBtn.addEventListener('click', showSearchPanel);
  if (newCancelBtn) newCancelBtn.addEventListener('click', showSearchPanel);

  if (searchInput) {
    searchInput.addEventListener('input', function (e) {
      debouncedSearch(e.target.value || '');
    });
  }

  if (newForm) {
    newForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (newError) {
        newError.hidden = true;
        newError.textContent = '';
      }
      var formData = new FormData(newForm);
      var payload = {};
      formData.forEach(function (v, k) { payload[k] = v; });
      if (!payload.name || !payload.name.trim()) {
        if (newError) {
          newError.hidden = false;
          newError.textContent = 'El nombre es obligatorio.';
        }
        var nameInput = $('cp_new_name');
        if (nameInput) nameInput.focus();
        return;
      }
      var submitBtn = newForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      fetch('/clientes/api/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          if (r.status === 422) {
            return r.json().then(function (body) {
              throw new Error((body && body.detail) || 'Datos inválidos.');
            });
          }
          if (!r.ok) {
            return r.text().then(function (t) {
              throw new Error(t || ('HTTP ' + r.status));
            });
          }
          return r.json();
        })
        .then(function (data) {
          pickCustomer({ id: data.id, name: payload.name, _isNew: true });
        })
        .catch(function (err) {
          if (newError) {
            newError.hidden = false;
            newError.textContent = (err && err.message) || 'No se pudo crear el cliente.';
          }
        })
        .then(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  }

  // Close dialog on backdrop click (the dialog itself receives the click
  // when the user clicks outside the inner form).
  if (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });
  }

  // Expose a tiny API for tests / programmatic selection.
  window.SaskiaCustomerPicker = {
    pick: pickCustomer,
    clear: clearSelection,
    open: openModal,
    close: closeModal,
    getSelected: function () { return state.selected; },
  };
})();
