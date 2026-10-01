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

  // Shared handler bag picked up by change events (see lines ~97/99) and
  // set up later in setupCustomerCombo(). Initialised as an empty object
  // so dereferences before the assignment (or on pages where the
  // combo never finishes upgrading) don't crash with
  // `Cannot read properties of undefined`. Pre-existing bug fixed
  // 2026-10-01 alongside the new /pedidos/nuevo customer-create panel,
  // which calls these handlers directly.
  window.customerPickHandlers = window.customerPickHandlers || {};

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
        // Single saved address → autofill; multiple → offer a quick chooser.
        // T-2026-10-01: idempotent — remove any previously-injected chooser
        // (this function is called from multiple paths: onSelect, the
        // delegated change listener, firePicked, and pedido-prefill.js's
        // renderAddressPicker) and dedupe any address_quick_pick elements
        // that may have piled up before this fix.
        var addrs = data.addresses || [];
        addrInput.parentElement.querySelectorAll("#address_quick_pick").forEach(function (el) { el.remove(); });
        addrInput.parentElement.querySelectorAll("#address-picker").forEach(function (el) { el.remove(); });
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
    // PRO-PED-UX (2026-09-30): la clase .saskia-customer-combo no existe en
    // ningún template — el hook nunca matcheaba y seleccionar cliente no
    // prellenaba teléfono/hint/RUC. El combo real es <saskia-combo name="customer_id">.
    var root = document.querySelector(".saskia-customer-combo") ||
               document.querySelector('saskia-combo[name="customer_id"]');
    if (!root) return;
    // T-2026-10-01: dedupe guard — a single user-pick previously fired
    // both cfg.onSelect AND the delegated change listener (which called
    // firePicked), which called loadCustomerAddresses twice → two address
    // choosers stacked. Track whether onSelect handled the event so the
    // delegated listener can early-return.
    var _pickHandled = false;
    var _markHandled = function () { _pickHandled = true; setTimeout(function () { _pickHandled = false; }, 50); };
    // Attach per-instance opts al elemento ya definido (upgrade-safe).
    // Además: escuchar el evento change que el elemento ya emite — path
    // principal, funciona incluso si attach llega tarde al upgrade.
    root.addEventListener("change", function (ev) {
      if (_pickHandled) return;
      var d = ev.detail || {};
      if (d.value && root._selectedItem) {
        _markHandled();
        window.customerPickHandlers.firePicked(root._selectedItem);
      } else if (!d.value) {
        _markHandled();
        window.customerPickHandlers.fireCleared();
      }
    });
    var hidden = document.getElementById("customer_id");

    // ── handlers compartidos (cfg.onSelect + change-event delegado) ──
    var phoneInput = document.getElementById("customer_phone");
    var pickedHint = document.getElementById("customer_picked_hint");
    var input = root.querySelector(".combo-input");

    function fireCustomerPicked(item) {
      // Prefill contact + facturación from the customer record. Fill-if-empty
      // for phone; overwrite for RUC/razón social.
      if (item && item.phone && phoneInput && !phoneInput.value) {
        phoneInput.value = item.phone;
      }
      var rucInput = document.getElementById("invoice_ruc");
      var nameInput = document.getElementById("invoice_name");
      if (item && rucInput) {
        var ruc = item.invoice_ruc || item.cedula || "";
        if (ruc) rucInput.value = ruc;
      }
      if (item && nameInput && item.invoice_name) {
        nameInput.value = item.invoice_name;
      }
      // P3 dietary: red alert for restrictions
      var alertEl = document.getElementById("dietary-alert");
      var alertBody = document.getElementById("dietary-alert-body");
      if (alertEl && alertBody) {
        var restrictions = (item && item.dietary_restrictions) || [];
        if (restrictions.length) {
          var askAlways = item && item.dietary_confirm_always;
          alertBody.innerHTML =
            "<strong>" + restrictions.map(escapeHtml).join(", ") + "</strong>" +
            (askAlways
              ? ' <em>— preguntar siempre antes de sustituir</em>'
              : ' <em>— verificar cada pedido</em>');
          alertEl.hidden = false;
        } else {
          alertBody.innerHTML = "";
          alertEl.hidden = true;
        }
      }
      // P3 delivery: autofill address book + preferred zone
      // T-2026-10-01: removed — fireCustomerPicked (called from cfg.onSelect
      // at line 206) already calls loadCustomerAddresses. Keeping this
      // caused two address-pickers to stack on every customer pick.
      // if (item && item.id && typeof loadCustomerAddresses === "function") {
      //   loadCustomerAddresses(item.id);
      // }
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
    }
    function fireCustomerCleared() {
      if (pickedHint) {
        pickedHint.dataset.empty = "true";
        pickedHint.innerHTML = '<em class="muted">Ninguno — se crea al guardar</em>';
      }
      var alertEl = document.getElementById("dietary-alert");
      if (alertEl) alertEl.hidden = true;
    }
    window.customerPickHandlers.firePicked = fireCustomerPicked;
    window.customerPickHandlers.fireCleared = fireCustomerCleared;
    var combo = window.SaskiaCombo.attach(root, {
      source: function (q) {
        var url = "/clientes/api/search?q=" + encodeURIComponent(q || "");
        return fetch(url).then(function (r) { return r.json(); });
      },
      displayField: "name",
      valueField: "id",
      minChars: 2,
      buildRow: function (item) {
        return window.customerRowLabel(item);
      },
      onSelect: function (item) {
        if (window.customerPickHandlers.firePicked) window.customerPickHandlers.firePicked(item);
        // Prefill contact + facturación from the customer record. Fill-if-empty
        // for phone (operator may have typed one already); overwrite for RUC/
        // razón social (customer record is the source of truth, form starts blank).
        if (item && item.phone && phoneInput && !phoneInput.value) {
          phoneInput.value = item.phone;
        }
        var rucInput = document.getElementById("invoice_ruc");
        var nameInput = document.getElementById("invoice_name");
        if (item && rucInput) {
          var ruc = item.invoice_ruc || item.cedula || "";
          if (ruc) rucInput.value = ruc;
        }
        if (item && nameInput && item.invoice_name) {
          nameInput.value = item.invoice_name;
        }
        // P3 dietary: red alert for restrictions + confirm-always note
        var alertEl = document.getElementById("dietary-alert");
        var alertBody = document.getElementById("dietary-alert-body");
        if (alertEl && alertBody) {
          var restrictions = (item && item.dietary_restrictions) || [];
          if (restrictions.length) {
            var askAlways = item && item.dietary_confirm_always;
            alertBody.innerHTML =
              "<strong>" + restrictions.map(escapeHtml).join(", ") + "</strong>" +
              (askAlways
                ? ' <em>— preguntar siempre antes de sustituir</em>'
                : ' <em>— verificar cada pedido</em>');
            alertEl.hidden = false;
          } else {
            alertBody.innerHTML = "";
            alertEl.hidden = true;
          }
        }
        // P3 delivery: autofill address book + preferred zone for known customers
      // T-2026-10-01: this is now the ONLY place loadCustomerAddresses is
      // called from cfg.onSelect (fireCustomerPicked used to also call it,
      // which caused stacking). Kept here because onSelect runs before
      // firePicked for the customer-combo path and we want the address
      // fetch to start as soon as the pick happens.
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
        if (window.customerPickHandlers.fireCleared) window.customerPickHandlers.fireCleared();
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

    var combo = window.SaskiaCombo.attach(root, {
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
  // T-2026-10-01: live inventory forecast warning + delivery min preview
  //                + submit-button lock + idempotency key
  // ─────────────────────────────────────────────────────────────────────
  function setupT2026Oct01() {
    setupInventoryForecastWarning();
    setupDeliveryMinPreview();
    setupSubmitLockAndIdempotency();
  }

  // Per-line: when product OR qty changes, ping /produccion/api/forecast
  // and surface a yellow "Pediste N pero el plan dice M" warning if the
  // requested qty exceeds the production plan's qty_to_produce for that
  // date. Operator can still submit — this is a nudge, not a block.
  function setupInventoryForecastWarning() {
    var dateEl = document.getElementById("promised_date");
    var body = document.getElementById("lines-body");
    if (!dateEl || !body) return;

    // Debounce per product+qty to avoid hitting the API on every keystroke
    var debounceByRow = new WeakMap();
    function scheduleCheck(row) {
      clearTimeout(debounceByRow.get(row));
      var t = setTimeout(function () { checkRow(row); }, 250);
      debounceByRow.set(row, t);
    }

    function checkRow(row) {
      var hidden = row.querySelector('input[name="line_product_id"]');
      var qtyEl = row.querySelector('input[name="line_qty"]');
      var productId = hidden && Number(hidden.value);
      var qty = qtyEl && Number(qtyEl.value);
      var metaRow = row.nextElementSibling;
      var warnEl = metaRow && metaRow.querySelector(".line-stock-warning");

      // Hide the warning when inputs are incomplete or invalid
      if (!productId || !qty || qty <= 0) {
        if (metaRow) metaRow.hidden = true;
        if (warnEl) warnEl.textContent = "";
        return;
      }

      var forDate = (dateEl.value || "").trim();
      if (!forDate) {
        if (metaRow) metaRow.hidden = true;
        if (warnEl) warnEl.textContent = "";
        return;
      }

      fetch(
        "/produccion/api/forecast?for_date=" + encodeURIComponent(forDate) +
        "&product_id=" + encodeURIComponent(productId),
        { credentials: "same-origin" }
      )
        .then(function (r) {
          if (!r.ok) throw new Error("forecast " + r.status);
          return r.json();
        })
        .then(function (data) {
          var rows = (data && data.rows) || [];
          // /api/forecast filters server-side, but fall back to client filter
          var row = rows.filter(function (x) { return x.product_id === productId; })[0];
          if (!row) {
            if (metaRow) metaRow.hidden = true;
            if (warnEl) warnEl.textContent = "";
            return;
          }
          var planQty = Number(row.qty_to_produce) || 0;
          if (qty > planQty && planQty > 0) {
            if (metaRow) metaRow.hidden = false;
            if (warnEl) {
              warnEl.textContent =
                "⚠ Pediste " + qty + " pero el plan de " + forDate +
                " dice " + planQty + ". ¿Vas a hornear de más o aceptar el faltante?";
            }
          } else if (planQty === 0) {
            // Plan has no forecast for this product on that day
            if (metaRow) metaRow.hidden = false;
            if (warnEl) {
              warnEl.textContent =
                "⚠ No hay plan de producción para este producto el " + forDate +
                ". Verificá con cocina antes de prometerlo.";
            }
          } else {
            if (metaRow) metaRow.hidden = true;
            if (warnEl) warnEl.textContent = "";
          }
        })
        .catch(function () {
          // Forecast API failed — silently skip the warning
          if (metaRow) metaRow.hidden = true;
          if (warnEl) warnEl.textContent = "";
        });
    }

    // Wire change listeners: any product combo `change` or qty `input` re-checks.
    body.addEventListener("change", function (e) {
      var row = e.target.closest && e.target.closest(".line-row");
      if (row) scheduleCheck(row);
    });
    body.addEventListener("input", function (e) {
      var row = e.target.closest && e.target.closest(".line-row");
      if (row && e.target.matches('input[name="line_qty"]')) scheduleCheck(row);
    });
    // Re-check all rows when the promised_date changes
    dateEl.addEventListener("change", function () {
      body.querySelectorAll(".line-row").forEach(scheduleCheck);
    });

    // Initial check for the default row
    var firstRow = body.querySelector(".line-row");
    if (firstRow) scheduleCheck(firstRow);
  }

  // T-2026-10-01: inline preview of min_order_gs vs the live cart total.
  // Renders below the delivery-zone combo. Updates on every line change
  // and on every zone change.
  function setupDeliveryMinPreview() {
    var preview = document.getElementById("delivery-min-preview");
    var previewText = document.getElementById("delivery-min-preview-text");
    var body = document.getElementById("lines-body");
    if (!preview || !previewText) return;

    var zones = [];
    var dataEl = document.getElementById("delivery-zones-data");
    if (dataEl) {
      try { zones = JSON.parse(dataEl.textContent || "[]"); } catch (_) { zones = []; }
    }

    function cartTotalGs() {
      if (!body) return 0;
      var total = 0;
      body.querySelectorAll(".line-row").forEach(function (row) {
        var qty = Number((row.querySelector('input[name="line_qty"]') || {}).value) || 0;
        var price = Number((row.querySelector('input[name="line_unit_price_gs"]') || {}).value) || 0;
        if (qty > 0 && price > 0) total += qty * price;
      });
      return Math.round(total);
    }

    function fmt(n) { return "Gs. " + Number(n).toLocaleString("es-PY"); }

    function render() {
      var zoneId = Number(((document.querySelector("input[name='delivery_zone_id']") || {}).value) || 0);
      var zone = zones.filter(function (z) { return z.id === zoneId; })[0];
      if (!zone || !zone.min_order_gs) {
        preview.style.display = "none";
        previewText.textContent = "";
        preview.dataset.minGs = "0";
        return;
      }
      var total = cartTotalGs();
      preview.dataset.minGs = String(zone.min_order_gs);
      preview.style.display = "block";
      if (total >= zone.min_order_gs) {
        preview.style.background = "#e8f5e9";
        preview.style.border = "1px solid #a5d6a7";
        preview.style.color = "#1b5e20";
        previewText.innerHTML =
          "✓ Pedido " + fmt(total) + " supera el mínimo de " +
          "<strong>" + fmt(zone.min_order_gs) + "</strong> para la zona <strong>" +
          zone.name + "</strong>.";
      } else {
        var gap = zone.min_order_gs - total;
        preview.style.background = "#fff7e6";
        preview.style.border = "1px solid #f0c674";
        preview.style.color = "#7a4f01";
        previewText.innerHTML =
          "⚠ Faltan <strong>" + fmt(gap) + "</strong> para el mínimo de delivery " +
          "(" + fmt(zone.min_order_gs) + " — zona " + zone.name + ").";
      }
    }

    // Re-render when lines change
    if (body) {
      body.addEventListener("input", render);
      body.addEventListener("change", render);
    }
    // Re-render when the zone combo changes
    document.addEventListener("change", function (e) {
      if (e.target && e.target.name === "delivery_zone_id") render();
    });
    // Initial render
    render();
  }

  // T-2026-10-01: submit-side hardening — disable the button on submit
  // and generate a client-side idempotency key so duplicate requests
  // (network stutter, double-click) collapse server-side into the
  // existing pedido.
  function setupSubmitLockAndIdempotency() {
    var form = document.getElementById("pedido-form");
    var keyEl = document.getElementById("idempotency-key-input");
    var submitBtn = document.getElementById("submit-btn");
    if (!form || !keyEl || !submitBtn) return;

    function uuidv4() {
      // RFC4122 v4 — works without crypto.randomUUID on older browsers
      if (window.crypto && typeof window.crypto.randomUUID === "function") {
        return window.crypto.randomUUID();
      }
      var bytes = new Uint8Array(16);
      if (window.crypto && window.crypto.getRandomValues) {
        window.crypto.getRandomValues(bytes);
      } else {
        for (var i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
      }
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      var hex = Array.from(bytes).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
      return (
        hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) +
        "-" + hex.slice(16, 20) + "-" + hex.slice(20)
      );
    }

    form.addEventListener("submit", function () {
      // Lazy-generate on the first submit attempt (not on page load)
      if (!keyEl.value) keyEl.value = uuidv4();
      // Lock the button so a network stutter can't fire a second POST
      submitBtn.disabled = true;
      var oldHtml = submitBtn.innerHTML;
      submitBtn.innerHTML =
        '<span class="spinner"></span> Creando…';
      // Re-enable after 8s as a safety net — if the redirect never lands
      // the operator can retry. The idempotency key prevents dupes.
      setTimeout(function () {
        if (submitBtn.disabled) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = oldHtml;
        }
      }, 8000);
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Bootstrap
  // ─────────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    setupCustomerCombo();
    setupAddLineButton();
    setupSubmitGate();
    setupT2026Oct01();

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
