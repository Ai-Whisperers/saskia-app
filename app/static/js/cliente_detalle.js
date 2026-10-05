/**
 * cliente_detalle.js — UX glue for /clientes/{id}
 *
 * T-2026-10-01:
 *   - Wires the suggestion-CTA <form class="js-suggestion-form"> so the
 *     operator gets instant feedback (button disable + spinner) when
 *     tapping "Aplicar sugerencia". Without this, the form falls
 *     through to a full page reload because the JS in customer_picker.js
 *     only fires for the POS customer card, not the detail page.
 *   - Adds a small download-link helper for the customer-export
 *     endpoint (#export-customer-csv) — purely cosmetic for now.
 *
 * Keep this file dependency-free (no jQuery, no framework). The base
 * layout already includes it via defer; the script attaches at
 * DOMContentLoaded so it runs after the template's DOM is parsed.
 */

(function () {
  "use strict";

  // ─── Suggestion CTA ────────────────────────────────────────────────────
  // Each suggestion renders as a <form class="js-suggestion-form">.
  // We intercept the submit so:
  //   1. the button shows a spinner (instant — never wait for server)
  //   2. the button is disabled (no double-tap)
  //   3. on next page load (the form POSTs normally), the ledger row
  //      is created with the correct `kind` (handler now reads both
  //      content-types — see customers.py:log_suggestion_applied).
  function bindSuggestionForms() {
    var forms = document.querySelectorAll("form.js-suggestion-form");
    if (!forms.length) return;
    forms.forEach(function (form) {
      // Guard against double-binding if the script ever runs twice
      if (form.__cliente_detalle_bound) return;
      form.__cliente_detalle_bound = true;
      form.addEventListener("submit", function () {
        var btn = form.querySelector("button[type=submit], button:not([type])");
        if (btn && !btn.disabled) {
          btn.disabled = true;
          // Cache the label so we can restore it if the redirect fails
          if (!btn.__original_html) btn.__original_html = btn.innerHTML;
          btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Aplicando…';
        }
        // Let the form POST through normally — the server now writes
        // a proper ledger row with the real kind.
      });
    });
  }

  // ─── CSV export helper ──────────────────────────────────────────────
  // The page already has the href baked in (#export-customer-csv);
  // this just adds a tiny "last downloaded" stamp to the link so the
  // operator knows the export landed. Purely cosmetic.
  function bindExportLink() {
    var link = document.getElementById("export-customer-csv");
    if (!link) return;
    link.addEventListener("click", function () {
      try {
        var stamp = new Date().toLocaleTimeString();
        link.setAttribute("data-last-downloaded", stamp);
        link.setAttribute("title", "Última descarga: " + stamp);
      } catch (e) {
        // localStorage / Intl may not be available in older browsers —
        // silently no-op
      }
    });
  }

  // ─── Suscripción one-click: confirm before submitting ────────────────
  // The form for active subscriptions posts to /pedidos/nuevo with a
  // pre-filled notes=[Suscripción] note. A stray click could create a
  // pedido the operator didn't intend. Use beforeunload for an explicit
  // confirmation.
  function bindSubscriptionForms() {
    var forms = document.querySelectorAll("form.js-subscription-form");
    if (!forms.length) return;
    forms.forEach(function (form) {
      if (form.__cliente_detalle_bound) return;
      form.__cliente_detalle_bound = true;
      form.addEventListener("submit", function (event) {
        // Skip confirmation if the user already checked the
        // "no volver a preguntar" checkbox in this session.
        try {
          if (window.sessionStorage && window.sessionStorage.getItem("sazon:susc-confirmed") === "1") {
            return;
          }
        } catch (e) {
          // sessionStorage may be disabled — fall through to confirm
        }
        var ok = window.confirm(
          "Vas a crear un pedido nuevo con la suscripción seleccionada.\n\n" +
          "¿Continuar?"
        );
        if (!ok) {
          event.preventDefault();
          event.stopPropagation();
        } else {
          try {
            if (window.sessionStorage) {
              window.sessionStorage.setItem("sazon:susc-confirmed", "1");
            }
          } catch (e) {
            // ignore
          }
        }
      });
    });
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  function init() {
    bindSuggestionForms();
    bindExportLink();
    bindSubscriptionForms();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();