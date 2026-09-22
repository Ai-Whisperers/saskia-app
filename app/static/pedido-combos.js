/**
 * pedido-combos.js — pedido-specific bindings on top of the combo component.
 *
 * The reusable picker lives in /static/combo.js. This file:
 *  1) instantiates a SaskiaCombo for the customer field (with free-form auto-create)
 *  2) renders an "X / Y visitas" hint when an existing customer is picked
 *  3) wires the "Add line" button to clone a row and create one SaskiaCombo per row
 *  4) gates form submission: requires at least one row with a product selected
 *  5) graceful no-JS fallback handled in the template (form fields still
 *     POST customer_name + line_product_id as empty / hidden values).
 */
(function () {
  "use strict";

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ─────────────────────────────────────────────────────────────────────
  // Customer combobox
  // ─────────────────────────────────────────────────────────────────────
  function setupCustomerCombo() {
    var root = document.querySelector(".saskia-customer-combo");
    if (!root) return;
    var hidden = document.getElementById("customer_id");
    var phoneInput = document.getElementById("customer_phone");
    var pickedHint = document.getElementById("customer_picked_hint");
    var input = root.querySelector(".combo-input");

    var combo = new window.SaskiaCombo(root, {
      source: function (q) {
        var url = "/customers/api/search?q=" + encodeURIComponent(q || "");
        return fetch(url).then(function (r) { return r.json(); });
      },
      displayField: "name",
      valueField: "id",
      minChars: 2,
      buildRow: function (item) {
        return window.customerRowLabel(item);
      },
      onSelect: function (item) {
        if (item && item.phone && phoneInput && !phoneInput.value) {
          phoneInput.value = item.phone;
        }
        if (pickedHint) {
          pickedHint.dataset.empty = "false";
          pickedHint.innerHTML =
            '<strong>' + escapeHtml(item.name) + "</strong>" +
            (item.id
              ? ' <small style="color: var(--color-text-muted);">#' + item.id + "</small>"
              : ' <small style="color: var(--color-success);">Nuevo</small>') +
            (item.lifetime_label
              ? ' <small style="color: var(--color-accent);">· ' + escapeHtml(item.lifetime_label) + " lifetime</small>"
              : "");
        }
      },
      onClear: function () {
        if (pickedHint) {
          pickedHint.dataset.empty = "true";
          pickedHint.innerHTML = '<em class="muted">Ninguno — se crea al guardar</em>';
        }
      },
    });

    // Visible flag when free-form typed (no pick)
    if (input) {
      input.addEventListener("blur", function () {
        if (!hidden.value && input.value.trim() && pickedHint && pickedHint.dataset.empty === "true") {
          // Restate the hint with the typed name (so user sees what will be created)
          pickedHint.innerHTML =
            '<strong>' + escapeHtml(input.value.trim()) + '</strong>' +
            ' <small style="color: var(--color-success);">Nuevo</small>';
        }
      });
    }
  }

  // ─────────────────────────────────────────────────────────────────────
  // Product per-line combobox
  // ─────────────────────────────────────────────────────────────────────
  function attachProductCombo(row) {
    var root = row.querySelector(".saskia-product-combo");
    if (!root) return;
    var hidden = row.querySelector('input[name="line_product_id"]');
    var qtyInput = row.querySelector('input[name="line_qty"]');
    var priceInput = row.querySelector('input[name="line_unit_price_gs"]');

    var combo = new window.SaskiaCombo(root, {
      source: "/productos/api/search",
      displayField: "name",
      valueField: "id",
      minChars: 1,
      buildRow: function (item) {
        return window.productRowLabel(item);
      },
      onSelect: function (item) {
        if (item && priceInput && item.sale_price_gs) {
          priceInput.value = item.sale_price_gs;
        }
        if (item && qtyInput && Number(qtyInput.value) < 1) {
          qtyInput.value = 1;
        }
      },
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Line add / remove
  // ─────────────────────────────────────────────────────────────────────
  function setupAddLineButton() {
    var addBtn = document.getElementById("add-line-btn");
    var tmpl = document.getElementById("line-row-template");
    var body = document.getElementById("lines-body");
    if (!addBtn || !tmpl || !body) return;
    addBtn.addEventListener("click", function () {
      var clone = tmpl.content.cloneNode(true);
      body.appendChild(clone);
      var newRow = body.lastElementChild;
      attachProductCombo(newRow);
    });
    document.querySelectorAll("#lines-body .line-row").forEach(attachProductCombo);
  }

  // ─────────────────────────────────────────────────────────────────────
  // Submit-side validation: require at least one picked product
  // ─────────────────────────────────────────────────────────────────────
  function setupSubmitGate() {
    var form = document.getElementById("pedido-form");
    if (!form) return;
    form.addEventListener("submit", function (e) {
      var productIdInputs = form.querySelectorAll('input[name="line_product_id"]');
      var hasValid = false;
      productIdInputs.forEach(function (inp) {
        if (inp.value && Number(inp.value) > 0) hasValid = true;
      });
      if (!hasValid) {
        e.preventDefault();
        var firstRow = form.querySelector(".line-row");
        if (firstRow) {
          firstRow.scrollIntoView({ behavior: "smooth", block: "center" });
          var firstCombo = firstRow.querySelector(".combo-input");
          if (firstCombo) firstCombo.focus();
        }
        alert(
          "Necesitás seleccionar al menos un producto. Las líneas vacías se ignoran automáticamente — agregá un producto o usá «Quitar»."
        );
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Bootstrap
  // ─────────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    setupCustomerCombo();
    setupAddLineButton();
    setupSubmitGate();

    // Expose removeLine for inline onclick=
    window.removeLine = function (btn) {
      var row = btn.closest("tr");
      if (!row) return;
      var body = document.getElementById("lines-body");
      if (body && body.querySelectorAll(".line-row").length > 1) {
        row.remove();
      } else {
        // Last row — clear instead of removing.
        var hidden = row.querySelector('input[name="line_product_id"]');
        var input = row.querySelector(".combo-input");
        var qty = row.querySelector('input[name="line_qty"]');
        var price = row.querySelector('input[name="line_unit_price_gs"]');
        if (hidden) hidden.value = "";
        if (input) {
          input.value = "";
          input.classList.remove("is-selected");
        }
        if (qty) qty.value = "1";
        if (price) price.value = "0";
      }
    };
  });
})();
