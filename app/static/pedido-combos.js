/**
 * pedido-combos.js — Combobox pickers for /pedidos/nuevo
 *
 * Two comboboxes:
 *  1) Customer: type 2+ chars → live-search; pick a result to set customer_id
 *     + autofill phone; free-form text creates a new customer at submit time.
 *  2) Product: each line has its own product combobox; typing filters,
 *     picking sets line_product_id + auto-fills price.
 *
 * Both comboboxes fall back gracefully to plain text inputs if JS is disabled.
 */
(function () {
  "use strict";

  // ─────────────────────────────────────────────────────────────────────
  // Customer combobox
  // ─────────────────────────────────────────────────────────────────────
  var customerInput = document.getElementById("customer_picker_input");
  var customerHidden = document.getElementById("customer_id");
  var customerPhoneInput = document.getElementById("customer_phone");
  var customerResults = document.getElementById("customer_picker_results");
  var customerPickedHint = document.getElementById("customer_picked_hint");
  var lastQuery = "";
  var customerQueryTimer = null;
  var customerSuggestions = [];

  function setCustomerHint(name, id, lifetimeLabel, phone) {
    if (!name) {
      customerPickedHint.dataset.empty = "true";
      customerPickedHint.innerHTML =
        '<em class="muted">Ninguno — se crea al guardar</em>';
      return;
    }
    var lifetime = lifetimeLabel
      ? ' <small style="color: var(--color-accent);">· ' + lifetimeLabel + " lifetime</small>"
      : "";
    var idNote = id
      ? ' <small style="color: var(--color-text-muted);">#' + id + "</small>"
      : ' <small style="color: var(--color-success);">Nuevo</small>';
    customerPickedHint.dataset.empty = "false";
    customerPickedHint.innerHTML =
      '<strong>' + escapeHtml(name) + "</strong>" + idNote + lifetime;
  }

  function renderCustomerResults(rows) {
    customerResults.innerHTML = "";
    if (!rows || rows.length === 0) {
      if (lastQuery.length >= 2) {
        customerResults.innerHTML =
          '<div class="empty-search">No hay coincidencias — seguí escribiendo para crear uno nuevo.</div>';
        customerResults.hidden = false;
      } else {
        customerResults.hidden = true;
      }
      return;
    }
    rows.forEach(function (c) {
      var div = document.createElement("div");
      div.className = "customer-combobox-result";
      div.dataset.id = c.id;
      div.dataset.name = c.name;
      div.dataset.phone = c.phone || "";
      div.dataset.lifetime = c.lifetime_label || "";
      div.setAttribute("role", "option");
      div.tabIndex = 0;
      div.innerHTML =
        '<span class="customer-combobox-result-main">' + escapeHtml(c.name) + "</span>" +
        '<span class="customer-combobox-result-sub">' +
        escapeHtml(c.phone || "") +
        (c.cedula ? " · CI " + escapeHtml(c.cedula) : "") +
        "</span>" +
        '<span class="customer-combobox-result-stats">' +
        (c.lifetime_label || "") +
        (c.tier ? " · " + c.tier : "") +
        "</span>";
      div.addEventListener("click", function () { pickCustomer(c); });
      div.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); pickCustomer(c); }
      });
      customerResults.appendChild(div);
    });
    customerResults.hidden = false;
  }

  function pickCustomer(c) {
    customerInput.value = c.name;
    customerHidden.value = c.id || "";
    if (c.phone && !customerPhoneInput.value) {
      customerPhoneInput.value = c.phone;
    }
    setCustomerHint(c.name, c.id || null, c.lifetime_label || "");
    customerResults.hidden = true;
    customerInput.classList.remove("is-selected");
    customerInput.focus();
    // Move cursor to end
    var len = customerInput.value.length;
    if (typeof customerInput.setSelectionRange === "function") {
      customerInput.setSelectionRange(len, len);
    }
  }

  function clearCustomerSelection() {
    customerHidden.value = "";
    setCustomerHint("", null, "");
  }

  if (customerInput) {
    customerInput.addEventListener("input", function () {
      var q = customerInput.value.trim();
      customerHidden.value = ""; // typing unlinks the existing selection
      if (q.length < 2) {
        customerResults.hidden = true;
        customerResults.innerHTML = "";
        setCustomerHint(q || "", null, ""); // empty = muted hint
        return;
      }
      lastQuery = q;
      clearTimeout(customerQueryTimer);
      customerQueryTimer = setTimeout(function () {
        fetch("/customers/api/search?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            customerSuggestions = data.results || [];
            renderCustomerResults(customerSuggestions);
          })
          .catch(function () {
            customerResults.hidden = true;
          });
      }, 200);
    });

    // Free-form name typed but not picked: leave customer_id empty;
    // backend will create a new Customer row.
    customerInput.addEventListener("blur", function () {
      // small delay so a click on a result registers first
      setTimeout(function () {
        if (customerHidden.value === "" && customerInput.value.trim() !== "") {
          setCustomerHint(customerInput.value.trim(), null, "");
        }
        customerResults.hidden = true;
      }, 200);
    });

    customerInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        customerResults.hidden = true;
      }
    });

    // Click outside closes
    document.addEventListener("click", function (e) {
      if (
        e.target !== customerInput &&
        !customerResults.contains(e.target)
      ) {
        customerResults.hidden = true;
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Product combobox (per line)
  // ─────────────────────────────────────────────────────────────────────
  function attachProductCombobox(row) {
    var input = row.querySelector(".product-combobox-input");
    var hidden = row.querySelector('input[name="line_product_id"]');
    var results = row.querySelector(".product-combobox-results");
    var qtyInput = row.querySelector('input[name="line_qty"]');
    var priceInput = row.querySelector('input[name="line_unit_price_gs"]');
    if (!input || !hidden || !results) return;

    var timer = null;
    var activeIndex = -1;
    var currentMatches = [];

    function hide() {
      results.hidden = true;
      results.innerHTML = "";
      activeIndex = -1;
      currentMatches = [];
    }

    function render(matches) {
      results.innerHTML = "";
      if (!matches || matches.length === 0) {
        results.innerHTML =
          '<div class="empty-search">Sin resultados.</div>';
        results.hidden = false;
        return;
      }
      matches.forEach(function (p, idx) {
        var div = document.createElement("div");
        div.className = "product-combobox-result";
        if (idx === 0) div.classList.add("is-active");
        div.dataset.id = p.id;
        div.dataset.name = p.name;
        div.dataset.price = p.sale_price_gs;
        div.setAttribute("role", "option");
        div.innerHTML =
          '<span class="pname">' + escapeHtml(p.name) +
          (p.portion_label ? ' <span class="portion">' + escapeHtml(p.portion_label) + "</span>" : "") +
          "</span>" +
          '<span class="pprice">Gs. ' +
          Number(p.sale_price_gs).toLocaleString("es-PY") +
          "</span>";
        div.addEventListener("mouseenter", function () {
          activeIndex = idx;
          updateActive();
        });
        div.addEventListener("click", function () { pickProduct(p); });
        results.appendChild(div);
      });
      activeIndex = 0;
      results.hidden = false;
    }

    function updateActive() {
      Array.from(results.children).forEach(function (c, idx) {
        if (idx === activeIndex) c.classList.add("is-active");
        else c.classList.remove("is-active");
      });
    }

    function pickProduct(p) {
      input.value = p.name;
      hidden.value = p.id;
      input.classList.add("is-selected");
      if (priceInput && p.sale_price_gs) {
        priceInput.value = p.sale_price_gs;
      }
      if (qtyInput && Number(qtyInput.value) < 1) {
        qtyInput.value = 1;
      }
      hide();
    }

    input.addEventListener("input", function () {
      var q = input.value.trim();
      // If user is typing a new value, clear the selection
      if (hidden.value && input.value !== input.dataset.selectedName) {
        hidden.value = "";
        input.classList.remove("is-selected");
      }
      clearTimeout(timer);
      timer = setTimeout(function () {
        var url = "/productos/api/search?q=" + encodeURIComponent(q);
        fetch(url)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            currentMatches = data.results || [];
            render(currentMatches);
          })
          .catch(function () { hide(); });
      }, 150);
    });

    input.addEventListener("keydown", function (e) {
      if (results.hidden) return;
      var max = currentMatches.length - 1;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIndex = Math.min(max, activeIndex + 1);
        updateActive();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(0, activeIndex - 1);
        updateActive();
      } else if (e.key === "Enter") {
        if (activeIndex >= 0 && currentMatches[activeIndex]) {
          e.preventDefault();
          pickProduct(currentMatches[activeIndex]);
        }
      } else if (e.key === "Escape") {
        hide();
      }
    });

    input.addEventListener("blur", function () {
      setTimeout(function () {
        if (!hidden.value && currentMatches.length === 0) {
          hide();
        }
      }, 250);
    });

    // Initial: hide until focus
    input.addEventListener("focus", function () {
      if (results.innerHTML === "" && currentMatches.length === 0) {
        // Trigger initial fetch to populate suggestions
        input.dispatchEvent(new Event("input"));
      }
    });

    // Stash selected name so re-typing clears selection
    Object.defineProperty(input, "dataset", {
      value: input.dataset,
      writable: true,
    });
  }

  // Attach to existing rows + new rows
  document.querySelectorAll("#lines-body .line-row").forEach(attachProductCombobox);
  var tmpl = document.getElementById("line-row-template");
  var body = document.getElementById("lines-body");
  var addBtn = document.getElementById("add-line-btn");
  if (addBtn && tmpl && body) {
    addBtn.addEventListener("click", function () {
      var clone = tmpl.content.cloneNode(true);
      body.appendChild(clone);
      // Attach combobox to the newly added row
      var newRow = body.lastElementChild;
      attachProductCombobox(newRow);
    });
  }

  // ─────────────────────────────────────────────────────────────────────
  // Submit-side validation: refuse empty product picks
  // ─────────────────────────────────────────────────────────────────────
  var form = document.getElementById("pedido-form");
  if (form) {
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
          var firstInput = firstRow.querySelector(".product-combobox-input");
          if (firstInput) firstInput.focus();
        }
        alert(
          "Necesitás seleccionar al menos un producto. Las líneas vacías se ignoran automáticamente — agregá un producto o usá «Quitar»."
        );
      }
    });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Expose the removeLine handler for inline onclick=
  window.removeLine = function (btn) {
    var row = btn.closest("tr");
    if (!row) return;
    var body = document.getElementById("lines-body");
    if (body && body.querySelectorAll(".line-row").length > 1) {
      row.remove();
    } else {
      // Last row — clear instead of removing.
      row.querySelector('input[name="line_product_id"]').value = "";
      row.querySelector('.product-combobox-input').value = "";
      row.querySelector('.product-combobox-input').classList.remove("is-selected");
      row.querySelector('input[name="line_qty"]').value = "1";
      row.querySelector('input[name="line_unit_price_gs"]').value = "0";
    }
  };
})();
