// Users page — modal helpers and button wiring.
// Loaded by users.html via <script src="/static/users.js?v={{ asset_version() }}"></script>.

(function () {
  function $(id) { return document.getElementById(id); }

  function openModal() {
    var m = $('nuevo-usuario-modal');
    if (m && m.showModal) m.showModal();
  }

  function closeModal() {
    var m = $('nuevo-usuario-modal');
    if (m && m.close) m.close();
  }

  function closeEditModal() {
    var m = $('editar-usuario-modal');
    if (m && m.close) m.close();
  }

  function closeDeleteModal() {
    var m = $('eliminar-usuario-modal');
    if (m && m.close) m.close();
  }

  // Exposed to inline onclick="editUser(...)" / onclick="deleteUser(...)" handlers in the table.
  window.editUser = function (id, username, role, isActive) {
    $('edit-user-id').value = id;
    $('edit-username').value = username;
    $('edit-role').value = role;
    $('edit-is-active').checked = !!isActive;
    $('edit-password').value = '';
    $('edit-user-form').action = '/users/' + id + '/editar';
    var m = $('editar-usuario-modal');
    if (m && m.showModal) m.showModal();
  };

  window.deleteUser = function (id, username) {
    $('delete-user-id').value = id;
    $('delete-user-message').textContent =
      '¿Estás seguro de que deseas eliminar al usuario "' + username + '"? Esta acción no se puede deshacer.';
    $('delete-user-form').action = '/users/' + id + '/eliminar';
    var m = $('eliminar-usuario-modal');
    if (m && m.showModal) m.showModal();
  };

  document.addEventListener('DOMContentLoaded', function () {
    var nuevoBtn = $('nuevo-usuario-btn');
    if (nuevoBtn) nuevoBtn.addEventListener('click', openModal);

    // Close modals on backdrop click
    ['nuevo-usuario-modal', 'editar-usuario-modal', 'eliminar-usuario-modal'].forEach(function (id) {
      var el = $(id);
      if (!el) return;
      el.addEventListener('click', function (e) {
        if (e.target === this) this.close();
      });
    });
  });
})();
