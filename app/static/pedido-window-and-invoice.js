/**
 * pedido-window-and-invoice.js — Phase 13 (2026-10-01) delivery UX glue.
 *
 * Wires:
 *   1. Ventana preferida radios — show/hide the window/scheduled
 *      fields based on the selected preference.
 *   2. Invoice profile dropdown — picking a profile autofills the
 *      legacy RUC + Razón social inputs + sets the hidden profile id.
 *   3. Address picker — when the cashier picks a saved address (via
 *      the datalist or the JS combo change), the structured form
 *      fields get prefilled too (calle/piso/barrio/etc).
 *
 * Loaded via <script defer> from app/templates/pedidos_nuevo.html.
 * Idempotent — safe to load multiple times (no-op on second init).
 */
(function () {
  "use strict";

  if (window.__saskiaPhase13Wired) return;
  window.__saskiaPhase13Wired = true;

  // ── 1. Ventana preferida radios ──────────────────────────────────
  function wireVentanaRadios() {
    const radios = document.querySelectorAll(
      'input[name="delivery_preference"]'
    );
    if (!radios.length) return;
    const windowFields = document.getElementById("ventana-window-fields");
    const scheduledFields = document.getElementById(
      "ventana-scheduled-fields"
    );
    function sync() {
      const v = document.querySelector(
        'input[name="delivery_preference"]:checked'
      );
      const value = v ? v.value : "asap";
      if (windowFields) {
        windowFields.hidden = value !== "window" && value !== "scheduled";
      }
      if (scheduledFields) {
        scheduledFields.hidden = value !== "scheduled";
      }
    }
    radios.forEach((r) => r.addEventListener("change", sync));
    sync();
  }

  // ── 2. Invoice profile dropdown ───────────────────────────────────
  function wireInvoiceProfile() {
    const sel = document.getElementById("customer_invoice_profile_select");
    if (!sel) return;
    const idField = document.getElementById("customer_invoice_profile_id");
    const rucEl = document.getElementById("invoice_ruc");
    const nameEl = document.getElementById("invoice_name");
    sel.addEventListener("change", function () {
      const opt = sel.selectedOptions[0];
      if (!opt || !opt.value) {
        // "use manual RUC" — clear the hidden id, leave the inputs
        // alone so the cashier can keep typing
        if (idField) idField.value = "";
        return;
      }
      if (idField) idField.value = opt.value;
      if (rucEl && opt.dataset.ruc) rucEl.value = opt.dataset.ruc;
      if (nameEl && opt.dataset.razon) nameEl.value = opt.dataset.razon;
    });
  }

  // ── 3. Address picker → structured form prefill ──────────────────
  // The datalist-based picker exposes the chosen address in
  // `customer-addresses` (value=address_text, visible text=alias+address).
  // The combo change event from pedido-combos.js sets a global var we
  // can read here; otherwise we look up the saved-address list in the
  // prefill JSON and match by address_text.
  function wireAddressPickerStructured() {
    const addrInput = document.getElementById("address_text");
    if (!addrInput) return;
    let prefill = window.CUSTOMER_PREFILL || {};
    if (!prefill.available_addresses || !prefill.available_addresses.length) {
      // try reading the <script id="customer-prefill"> JSON
      const tag = document.getElementById("customer-prefill");
      if (tag && tag.textContent) {
        try { prefill = JSON.parse(tag.textContent); } catch (e) { prefill = {}; }
      }
    }
    function applyStructured(addr) {
      if (!addr) return;
      function set(name, value) {
        const el = document.getElementById("address_" + name);
        if (el && value) el.value = value;
      }
      set("calle_principal", addr.calle_principal);
      set("calle_secundaria", addr.calle_secundaria);
      set("numero", addr.numero);
      set("edificio", addr.edificio);
      set("piso", addr.piso);
      set("unidad", addr.unidad);
      set("barrio", addr.barrio);
      set("ciudad", addr.ciudad);
      set("departamento", addr.departamento);
      set("codigo_postal", addr.codigo_postal);
      set("recipient_name", addr.recipient_name);
      set("delivery_instructions", addr.delivery_instructions);
      if (addr.address_kind) {
        const k = document.getElementById("address_kind");
        if (k) k.value = addr.address_kind;
      }
      // Also record which saved address was picked (FK to customer_address)
      const idField = document.getElementById("customer_address_id");
      if (idField && addr.id) idField.value = addr.id;
    }
    function onChange() {
      const text = addrInput.value || "";
      const match = (prefill.available_addresses || []).find(
        (a) => (a.address_text || "").trim() === text.trim()
      );
      applyStructured(match);
    }
    addrInput.addEventListener("change", onChange);
    addrInput.addEventListener("blur", onChange);
  }

  // ── 4. Initial paint: pre-select default invoice profile ─────────
  function preselectDefaultProfile() {
    const sel = document.getElementById("customer_invoice_profile_select");
    if (!sel) return;
    let prefill = window.CUSTOMER_PREFILL || {};
    if (!prefill.invoice_profiles) {
      const tag = document.getElementById("customer-prefill");
      if (tag && tag.textContent) {
        try { prefill = JSON.parse(tag.textContent); } catch (e) { prefill = {}; }
      }
    }
    const profiles = prefill.invoice_profiles || [];
    if (!profiles.length) return;
    // Pick the is_default=true row, else the first row.
    const target =
      profiles.find((p) => p.is_default) || profiles[0];
    if (!target) return;
    const opt = Array.from(sel.options).find((o) => o.value == target.id);
    if (opt) {
      opt.selected = true;
      // fire the change handler so idField/ruc/name are set
      sel.dispatchEvent(new Event("change"));
    }
  }

  function init() {
    wireVentanaRadios();
    wireInvoiceProfile();
    wireAddressPickerStructured();
    preselectDefaultProfile();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();