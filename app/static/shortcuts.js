/* Keyboard shortcuts (Phase 4 polish)
 *
 * Usage:
 *   g + i → Inicio
 *   g + v → Ventas
 *   g + p → Productos
 *   g + r → Recetas
 *   g + n → Inventario
 *   g + e → EOD (Cierre)
 *   g + m → Merma
 *   g + s → Settings
 *   Cmd+K / Ctrl+K → Command palette (P1-B6)
 *   ?     → Show shortcut help modal
 *   Esc   → Close modal
 *
 * Disabled when typing in form fields.
 */
(function() {
  'use strict';

  // Map: <g><letter> → URL
  const NAV = {
    'i': '/',
    'v': '/ventas',
    'p': '/productos',
    'r': '/recetas',
    'n': '/inventario',
    'e': '/eod',
    'm': '/merma',
    's': '/settings',
    'a': '/auditoria',
    'o': '/ops/status',
    'x': '/excel',
    'l': '/reorder',
    't': '/reportes',
    'c': '/clientes',
  };

  // POS hotkeys (only fire on /ventas) — P1-B6 sub-bullet
  const POS_HOTKEYS = {
    'F2': () => {
      const sale = document.querySelector('[data-action="save-sale"]');
      if (sale) sale.click();
    },
    'F4': () => {
      const disc = document.querySelector('[data-action="apply-discount"]');
      if (disc) disc.click();
    },
  };

  // Production hotkeys (only fire on /produccion) — D.5
  // Cooks self-pace through shift execution: J/K navigate rows,
  // O opens the per-row override form, C toggles the close-day form.
  // H/L move one day back/forward; T jumps to today.
  // Mobile-aware: shortcuts only fire on viewports ≥768px (no keyboard
  // on phones, no accidental fires from input focus changes).
  const PROD_HOTKEYS = {
    'j': () => {
      // Move focus to the next production row's qty input
      const rows = Array.from(document.querySelectorAll('#shift-form .production-row'));
      if (rows.length === 0) return;
      const current = document.activeElement && document.activeElement.closest('.production-row');
      const idx = current ? rows.indexOf(current) : -1;
      const next = rows[Math.min(idx + 1, rows.length - 1)];
      if (next) {
        const input = next.querySelector('.progress-input');
        if (input) { input.focus(); input.select && input.select(); }
        next.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    },
    'k': () => {
      // Move focus to the previous production row's qty input
      const rows = Array.from(document.querySelectorAll('#shift-form .production-row'));
      if (rows.length === 0) return;
      const current = document.activeElement && document.activeElement.closest('.production-row');
      const idx = current ? rows.indexOf(current) : rows.length;
      const prev = rows[Math.max(idx - 1, 0)];
      if (prev) {
        const input = prev.querySelector('.progress-input');
        if (input) { input.focus(); input.select && input.select(); }
        prev.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    },
    'o': () => {
      // Open override form for the row currently focused (or first row)
      const active = document.activeElement && document.activeElement.closest('.production-row');
      const row = active || document.querySelector('#shift-form .production-row');
      if (!row) return;
      const productId = row.getAttribute('data-product-id');
      const forDate = document.querySelector('input[name="for_date"]')?.value;
      if (productId && forDate) {
        window.location.href = `/produccion/override?for_date=${forDate}&product_id=${productId}`;
      }
    },
    'c': () => {
      // Toggle the close-day form (only if not already closed)
      const closeBtn = document.querySelector('[data-action="toggle-close-day"]');
      if (closeBtn) closeBtn.click();
    },
    // PRODUCCION-V3 Phase 1: day navigation shortcuts.
    // H moves to the previous day, L to the next day, T to today.
    // These click the data-day-nav anchors in _components/day_nav.html
    // so the shift/filter state is preserved.
    'h': () => {
      const link = document.querySelector('[data-day-nav-prev]');
      if (link) link.click();
    },
    'l': () => {
      const link = document.querySelector('[data-day-nav-next]');
      if (link) link.click();
    },
    't': () => {
      const link = document.querySelector('[data-day-nav-today]');
      if (link) link.click();
    },
  };

  // Two-key state: waiting for second key after 'g'
  let prefix = null;
  let prefixTimer = null;
  const PREFIX_TIMEOUT_MS = 1500;

  function isEditable(el) {
    if (!el) return false;
    const tag = (el.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
  }

  function showShortcutHelp() {
    // Build a simple modal with the keyboard shortcuts
    let modal = document.getElementById('shortcut-help-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'shortcut-help-modal';
      modal.className = 'modal-backdrop';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'shortcut-help-title');
      modal.innerHTML = `
        <div class="modal-dialog">
          <div class="modal-header">
            <h2 id="shortcut-help-title">
              <svg class="icon" aria-hidden="true"><use href="#icon-help"/></svg>
              Atajos de teclado
            </h2>
            <button type="button" class="btn-ghost btn-icon" id="close-shortcuts" aria-label="Cerrar">
              <svg class="icon" aria-hidden="true"><use href="#icon-x"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <table class="table">
              <thead><tr><th>Atajo</th><th>Acción</th></tr></thead>
              <tbody>
                <tr><td><kbd>g</kbd> + <kbd>i</kbd></td><td>Ir a Inicio</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>v</kbd></td><td>Ir a Ventas</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>p</kbd></td><td>Ir a Productos</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>r</kbd></td><td>Ir a Recetas</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>n</kbd></td><td>Ir a Inventario</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>e</kbd></td><td>Ir a Cierre (EOD)</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>m</kbd></td><td>Ir a Merma</td></tr>
                <tr><td><kbd>g</kbd> + <kbd>s</kbd></td><td>Ir a Configuración</td></tr>
                <tr><td><kbd>⌘K</kbd> / <kbd>Ctrl+K</kbd></td><td>Paleta de comandos</td></tr>
                <tr><td><kbd>?</kbd></td><td>Mostrar este diálogo</td></tr>
                <tr><td><kbd>Esc</kbd></td><td>Cerrar diálogo</td></tr>
                <tr><td><kbd>F2</kbd></td><td>Registrar venta (en /ventas)</td></tr>
                <tr><td><kbd>F4</kbd></td><td>Aplicar descuento (en /ventas)</td></tr>
                <tr><td><kbd>J</kbd> / <kbd>K</kbd></td><td>Navegar filas de producción (en /produccion, desktop)</td></tr>
                <tr><td><kbd>O</kbd></td><td>Abrir override de la fila activa (en /produccion)</td></tr>
                <tr><td><kbd>C</kbd></td><td>Cerrar / abrir el día (en /produccion)</td></tr>
                <tr><td><kbd>H</kbd> / <kbd>L</kbd></td><td>Día anterior / siguiente (en /produccion)</td></tr>
                <tr><td><kbd>T</kbd></td><td>Ir a hoy (en /produccion)</td></tr>
              </tbody>
            </table>
            <p class="text-muted">
              <small>Los atajos se desactivan cuando estás escribiendo en un campo.</small>
            </p>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
      document.getElementById('close-shortcuts').addEventListener('click', closeShortcutHelp);
      modal.addEventListener('click', function(e) {
        if (e.target === modal) closeShortcutHelp();
      });
    }
  // Wire up the nav button if present (added in base.html Phase 5+).
    var navBtn = document.getElementById('open-shortcuts');
    if (navBtn && !navBtn._shortcutsWired) {
      navBtn.addEventListener('click', function(e) {
        e.preventDefault();
        showShortcutHelp();
      });
      navBtn._shortcutsWired = true;
    }
    // P1-B6: topbar search button opens the command palette too.
    var searchBtn = document.getElementById('global-search-btn');
    if (searchBtn && !searchBtn._paletteWired) {
      searchBtn.addEventListener('click', function(e) {
        e.preventDefault();
        openPalette();
      });
      searchBtn._paletteWired = true;
    }
    modal.style.display = 'flex';
    document.getElementById('close-shortcuts').focus();
  }

  function closeShortcutHelp() {
    const modal = document.getElementById('shortcut-help-modal');
    if (modal) modal.style.display = 'none';
  }

  document.addEventListener('keydown', function(e) {
    if (isEditable(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const key = e.key.toLowerCase();

    if (e.key === 'Escape') {
      closeShortcutHelp();
      return;
    }

    if (e.key === '?') {
      e.preventDefault();
      showShortcutHelp();
      return;
    }

    if (prefix === 'g') {
      prefix = null;
      clearTimeout(prefixTimer);
      const url = NAV[key];
      if (url) {
        e.preventDefault();
        window.location.href = url;
      }
      return;
    }

    if (key === 'g') {
      prefix = 'g';
      prefixTimer = setTimeout(() => { prefix = null; }, PREFIX_TIMEOUT_MS);
      return;
    }

    // POS hotkeys (F2/F4) only fire on /ventas — keeps other pages clean.
    if (window.location.pathname.startsWith('/ventas') && POS_HOTKEYS[e.key]) {
      e.preventDefault();
      POS_HOTKEYS[e.key]();
      return;
    }

    // T-2026-10-04 (D.5): Production hotkeys (J/K/O/C) only fire on
    // /produccion and only on viewports ≥768px (mobile users don't
    // have physical keyboards so the shortcut hint would just be
    // visual noise). Touch is detected by checking pointer:coarse
    // first, then falling back to width.
    if (window.location.pathname.startsWith('/produccion')
        && PROD_HOTKEYS[key]
        && !window.matchMedia('(pointer: coarse)').matches
        && window.innerWidth >= 768) {
      e.preventDefault();
      PROD_HOTKEYS[key]();
      return;
    }
  });

  // --- P1-B6 Command Palette (Cmd+K / Ctrl+K) ---
  // Fuzzy search through NAV. Opens a modal with a search input,
  // filters by label substring, navigate on Enter. Datalist-style.
  function buildPaletteItems() {
    const items = [];
    document.querySelectorAll('.sidebar .nav-item').forEach(a => {
      const text = (a.textContent || '').trim();
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#')) return;
      items.push({ label: text, route: href });
    });
    // Add create-actions from the FAB if present
    document.querySelectorAll('[data-palette-action]').forEach(el => {
      items.push({
        label: el.getAttribute('data-palette-action'),
        route: el.getAttribute('href') || el.getAttribute('data-route'),
        isAction: true,
      });
    });
    return items;
  }

  let paletteModal = null;
  let paletteInput = null;
  let paletteResults = null;
  let paletteActiveIdx = 0;
  let paletteItems = [];

  function getPaletteModal() {
    if (paletteModal) return paletteModal;
    paletteModal = document.createElement('div');
    paletteModal.id = 'cmd-k-palette';
    paletteModal.className = 'modal-backdrop';
    paletteModal.style.display = 'none';
    paletteModal.innerHTML = `
      <div class="modal-dialog" style="max-width:520px;margin-top:10vh;">
        <div style="padding:var(--space-3);">
          <input id="cmd-k-input" type="search" placeholder="Buscar página o acción..."
                 autocomplete="off" spellcheck="false"
                 style="width:100%;padding:var(--space-3);font-size:var(--text-md);
                        border:1px solid var(--color-border);border-radius:8px;
                        background:var(--color-surface);">
        </div>
        <div id="cmd-k-results" style="max-height:50vh;overflow:auto;padding:0 var(--space-3) var(--space-3);"></div>
        <div style="padding:var(--space-2) var(--space-3);font-size:var(--text-xs);color:var(--color-text-muted);border-top:1px solid var(--color-border);">
          <kbd>↑</kbd>/<kbd>↓</kbd> navegar &nbsp; <kbd>↵</kbd> ir &nbsp; <kbd>Esc</kbd> cerrar
        </div>
      </div>
    `;
    document.body.appendChild(paletteModal);
    paletteInput = document.getElementById('cmd-k-input');
    paletteResults = document.getElementById('cmd-k-results');

    paletteInput.addEventListener('input', renderPalette);
    paletteInput.addEventListener('keydown', function(ev) {
      if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        paletteActiveIdx = Math.min(paletteActiveIdx + 1, paletteItems.length - 1);
        renderPalette();
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
        paletteActiveIdx = Math.max(paletteActiveIdx - 1, 0);
        renderPalette();
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        const item = paletteItems[paletteActiveIdx];
        if (item && item.route) {
          window.location.href = item.route;
        }
      } else if (ev.key === 'Escape') {
        ev.preventDefault();
        closePalette();
      }
    });
    paletteModal.addEventListener('click', function(ev) {
      if (ev.target === paletteModal) closePalette();
    });
    return paletteModal;
  }

  function renderPalette() {
    const q = (paletteInput.value || '').toLowerCase();
    paletteItems = buildPaletteItems().filter(it => !q || it.label.toLowerCase().includes(q));
    paletteActiveIdx = 0;
    if (paletteItems.length === 0) {
      paletteResults.innerHTML = '<p style="text-align:center;color:var(--color-text-muted);padding:var(--space-3);">Sin resultados</p>';
      return;
    }
    paletteResults.innerHTML = paletteItems.map((it, i) => `
      <a href="${it.route || '#'}" data-idx="${i}"
         style="display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2) var(--space-3);
                border-radius:6px;text-decoration:none;color:inherit;
                ${i === paletteActiveIdx ? 'background:var(--color-surface-subtle);font-weight:600;' : ''}">
        <span>${it.label}</span>
        ${it.isAction ? '<span style="margin-left:auto;font-size:var(--text-xs);color:var(--color-text-muted);">acción</span>' : ''}
      </a>
    `).join('');
  }

  function openPalette() {
    getPaletteModal().style.display = 'flex';
    paletteInput.value = '';
    paletteItems = buildPaletteItems();
    renderPalette();
    setTimeout(() => paletteInput.focus(), 50);
  }

  function closePalette() {
    if (paletteModal) paletteModal.style.display = 'none';
  }

  // Cmd+K (mac) or Ctrl+K (everything else) — P1-B6
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (paletteModal && paletteModal.style.display === 'flex') {
        closePalette();
      } else {
        openPalette();
      }
      return;
    }
  });

  // PRODUCCION-V3 Phase 4: data-action delegation. Buttons with
  // data-action="open-adhoc-modal" / "open-adhoc-bulk" open the
  // <dialog> elements with matching IDs. Delegated at the document
  // level so the button HTML stays free of inline onclick=.
  document.addEventListener('click', function(e) {
    const target = e.target.closest('[data-action]');
    if (!target) return;
    const action = target.getAttribute('data-action');
    if (action === 'open-adhoc-modal') {
      const dlg = document.getElementById('adhoc-modal');
      if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
      else if (dlg) dlg.setAttribute('open', '');
    } else if (action === 'open-adhoc-bulk') {
      const dlg = document.getElementById('adhoc-bulk-modal');
      if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
      else if (dlg) dlg.setAttribute('open', '');
    }
  });
})();
