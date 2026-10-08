/* app/static/form-dirty.js — Shared unsaved-changes warning.

Usage in a form:
  <form id="my-form" data-saskia-dirty>
    ...
  </form>
  <script src="/static/form-dirty.js" defer></script>

The script auto-binds to all [data-saskia-dirty] forms. Listens for
any input event, sets a "dirty" flag, and prompts via beforeunload if
the user tries to navigate away. The flag is reset on submit.
*/

(function () {
  'use strict';

  function init() {
    var forms = document.querySelectorAll('form[data-saskia-dirty]');
    forms.forEach(function (form) {
      if (form.__saskiaDirtyBound) return;
      form.__saskiaDirtyBound = true;

      var dirty = false;

      form.addEventListener('input', function () {
        dirty = true;
      });
      form.addEventListener('change', function () {
        dirty = true;
      });

      form.addEventListener('submit', function () {
        dirty = false;
      });

      window.addEventListener('beforeunload', function (e) {
        if (dirty) {
          e.preventDefault();
          e.returnValue = '';  // required for Chrome
          return '';
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();