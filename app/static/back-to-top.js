/* app/static/back-to-top.js — "Volver arriba" floating button.

Renders a fixed-position button in the bottom-right corner that becomes
visible once the user scrolls down. Click scrolls smoothly to top.

Usage:
  <button class="back-to-top" aria-label="Volver arriba" hidden>
    <svg class="icon" aria-hidden="true"><use href="#icon-up"/></svg>
  </button>

The button is self-managed: it shows/hides based on scroll position.
Reduced-motion users get an instant scroll.
*/

(function () {
  'use strict';

  function init() {
    var btn = document.querySelector('.back-to-top');
    if (!btn) return;
    btn.hidden = false;

    function onScroll() {
      var y = window.scrollY || document.documentElement.scrollTop;
      btn.classList.toggle('is-visible', y > 400);
    }
    window.addEventListener('scroll', onScroll, { passive: true });

    btn.addEventListener('click', function () {
      var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
    });

    onScroll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();