/**
 * pedido-prefill.js — phase 3 smart autofill for /pedidos/nuevo
 *
 * Reads a JSON blob from `<script id="customer-prefill">` (rendered by
 * the server when ?customer_id=N is passed) and patches the form fields
 * on initial render. When the user picks a different customer via the
 * combo, this script fetches /pedidos/api/customer-defaults/<id> and
 * patches the form again.
 *
 * Idempotent: only fills fields that exist on the page. Leaves the
 * existing values alone if the smart default is null/empty (so the
 * operator's manual edits aren't clobbered).
 *
 * Depends on:
 *   - window.customerPickHandlers (set up in pedido-combos.js)
 *   - the field IDs on pedidos_nuevo.html (customer_phone, invoice_ruc,
 *     invoice_name, address_text, delivery_window_start,
 *     delivery_window_end, promised_date, promised_time, channel,
 *     payment_intent, save_address, address_label, notes)
 */

(function () {
  "use strict";

  // ---- Field ID map (single source of truth for autofill) ----
  const FIELD_IDS = {
    phone: "customer_phone",
    invoice_ruc: "invoice_ruc",
    invoice_name: "invoice_name",
    address_text: "address_text",
    delivery_window_start: "delivery_window_start",
    delivery_window_end: "delivery_window_end",
    promised_date: "promised_date",
    promised_time: "promised_time",
    channel: "channel",
    payment_intent: "payment_intent",
    save_address: "save_address",
    address_label: "address_label",
    notes: "notes",
  };

  /**
   * Apply a prefill dict to the form. Only patches fields that exist
   * and only when the prefill value is non-empty. If `force=true`,
   * overwrite the field even if it already has a value (used when the
   * user explicitly picks a customer and we want to repopulate).
   */
  function applyPrefill(prefill, force) {
    if (!prefill || typeof prefill !== "object") return;
    Object.entries(FIELD_IDS).forEach(([key, id]) => {
      const el = document.getElementById(id);
      if (!el) return;
      const value = prefill[key];
      if (value === null || value === undefined || value === "") return;
      if (!force && el.value && el.value !== el.defaultValue) {
        // Don't overwrite a manually-edited field unless forced
        return;
      }
      if (el.type === "checkbox") {
        el.checked = !!value;
      } else if (el.tagName === "SELECT") {
        // Try to set the option that matches; if not found, set value attr
        const optionExists = Array.from(el.options).some(
          (o) => o.value === String(value)
        );
        if (optionExists) {
          el.value = String(value);
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        el.value = value;
      }
    });

    // Delivery zone — special: it's a saskia-combo (web component) so
    // we have to use its setValue API, not the native value setter.
    if (prefill.delivery_zone_id) {
      const combo = document.querySelector("saskia-combo#delivery_zone_combo");
      if (combo && typeof combo.setValue === "function") {
        combo.setValue(String(prefill.delivery_zone_id));
      }
    }

    // Show the "Pedir de nuevo" banner if a clone is suggested
    showCloneBanner(prefill);
  }

  /**
   * Inject a small banner above the items table when a previous pedido
   * is being cloned, so the operator knows what's about to happen.
   */
  function showCloneBanner(prefill) {
    let banner = document.getElementById("prefill-clone-banner");
    const shouldShow =
      prefill.last_pedido_summary && Array.isArray(prefill.clone_lines) && prefill.clone_lines.length > 0;

    if (!shouldShow) {
      if (banner) banner.remove();
      return;
    }
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "prefill-clone-banner";
      banner.className = "prefill-clone-banner";
      banner.style.cssText =
        "background:#fff7e6;border:1px solid #f0c674;padding:8px 12px;border-radius:6px;margin:10px 0;font-size:14px;";
      const itemsTable = document.querySelector("#items-table, .items-table, table tbody");
      const insertTarget = itemsTable
        ? itemsTable.closest("section") || itemsTable.parentElement
        : document.body;
      insertTarget.prepend(banner);
    }
    banner.textContent =
      "📋 Pedir de nuevo — clonando " +
      prefill.clone_lines.length +
      " ítem(s) del pedido " +
      prefill.last_pedido_summary +
      ". Revisá antes de guardar.";
  }

  /**
   * Render the cloned lines as additional pedido-line rows in the items
   * table. This is "best effort" — the operator can edit/delete any
   * row. We append rows to whatever container the template uses.
   */
  function injectClonedLines(cloneLines) {
    if (!Array.isArray(cloneLines) || cloneLines.length === 0) return;
    // Defer to the next tick so pedido-combos.js has time to wire up
    setTimeout(() => {
      const btn = document.getElementById("add-line-btn");
      if (!btn) return;
      cloneLines.forEach((line) => {
        // Click the "Agregar ítem" button to create a fresh row,
        // then patch the new row's product + qty + price.
        btn.click();
        // Find the most recently added row (last in tbody / last form group)
        const rows = document.querySelectorAll(
          "[data-line-row], .line-row, .pedido-line"
        );
        const lastRow = rows[rows.length - 1];
        if (!lastRow) return;
        const productSelect = lastRow.querySelector(
          "select[name='line_product_id'], select.line-product"
        );
        const qtyInput = lastRow.querySelector(
          "input[name='line_qty'], input.line-qty"
        );
        const priceInput = lastRow.querySelector(
          "input[name='line_unit_price_gs'], input.line-price"
        );
        if (productSelect && line.product_id) {
          productSelect.value = line.product_id;
          productSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (qtyInput && line.qty) {
          qtyInput.value = line.qty;
        }
        if (priceInput && line.unit_price_gs) {
          priceInput.value = line.unit_price_gs;
        }
      });
    }, 50);
  }

  // ---- Boot ----
  function boot() {
    // 1. Read the server-rendered prefill JSON and apply it.
    const prefillEl = document.getElementById("customer-prefill");
    if (prefillEl) {
      try {
        const prefill = JSON.parse(prefillEl.textContent || "{}");
        applyPrefill(prefill, true);
        if (prefill.clone_lines && prefill.clone_lines.length > 0) {
          injectClonedLines(prefill.clone_lines);
        }
      } catch (err) {
        console.warn("pedido-prefill: failed to parse customer-prefill JSON", err);
      }
    }

    // 2. Wire a change handler so when the user picks a different
    // customer from the combo, we re-fetch and re-apply defaults.
    const customerInput = document.getElementById("customer_picker_input");
    if (customerInput) {
      customerInput.addEventListener("change", async () => {
        const newId = customerInput.value || customerInput.dataset.value;
        if (!newId) return;
        try {
          const r = await fetch(
            `/pedidos/api/customer-defaults/${encodeURIComponent(newId)}`,
            { credentials: "same-origin" }
          );
          if (!r.ok) return;
          const prefill = await r.json();
          applyPrefill(prefill, true);
          // Don't auto-inject cloned lines on a manual re-pick — only on
          // the initial Pedir de nuevo flow. The operator can click
          // "Pedir de nuevo" on the detail page if they want it.
        } catch (err) {
          console.warn("pedido-prefill: failed to fetch defaults", err);
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
