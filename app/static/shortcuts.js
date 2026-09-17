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
                <tr><td><kbd>?</kbd></td><td>Mostrar este diálogo</td></tr>
                <tr><td><kbd>Esc</kbd></td><td>Cerrar diálogo</td></tr>
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
  });
})();
