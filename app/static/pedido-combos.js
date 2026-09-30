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
  // P3 delivery: fetch a customer's saved addresses and autofill the form.
  window.loadCustomerAddresses = function (customerId) {
    var addrInput = document.getElementById("address_text");
    var zoneInput = document.querySelector('input[name="delivery_zone_id"]'); // hidden combo field
    var zoneCombo = document.getElementById("delivery_zone_combo");
    var wsEl = document.getElementById("delivery_window_start");
    var weEl = document.getElementById("delivery_window_end");
    var saveRow = document.getElementById("save-address-row");
    fetch("/pedidos/api/customer/" + customerId + "/addresses")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        // Preferred zone → set the zone combo (fires its change so cost recalcs)
        if (data.preferred_zone_id && zoneInput) {
          zoneInput.value = String(data.preferred_zone_id);
          if (zoneCombo && zoneCombo.dispatchEvent) {
            zoneCombo.dispatchEvent(new Event("saskia-combo-external-set"));
          }
        }
        // Single saved address → autofill; multiple → offer a quick chooser
        var addrs = data.addresses || [];
        if (addrs.length === 1 && addrInput && !addrInput.value) {
          addrInput.value = addrs[0].address_text;
        } else if (addrs.length > 1 && addrInput) {
          var chooser = document.createElement("select");
          chooser.id = "address_quick_pick";
          chooser.className = "input";
          chooser.style.marginTop = "var(--space-2)";
          chooser.innerHTML = '<option value="">— direcciones guardadas —</option>' +
            addrs.map(function (a) {
              return '<option value="' + a.id + '">' +
                escapeHtml(a.label) + ": " + escapeHtml(a.address_text) + "</option>";
            }).join("");
          chooser.addEventListener("change", function () {
            var picked = addrs.filter(function (a) {
              return String(a.id) === chooser.value;
            })[0];
            if (picked) {
              addrInput.value = picked.address_text;
              if (picked.zone_id && zoneInput) {
                zoneInput.value = String(picked.zone_id);
              }
            }
          });
          addrInput.parentElement.appendChild(chooser);
        }
        // Customer already has saved addresses → hide save-row (they're covered);
        // new customer with address typed → show it. Flag first so the
        // address input listener doesn't re-show it a beat later.
        if (saveRow) {
          saveRow.dataset.customerHasAddresses = addrs.length > 0 ? "1" : "0";
          saveRow.hidden = addrs.length > 0;
        }
      })
      .catch(function () { /* non-fatal */ });
  };

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
        // P3 delivery: autofill address book + preferred zone for known customers
        if (item && item.id && typeof loadCustomerAddresses === "function") {
          loadCustomerAddresses(item.id);
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
