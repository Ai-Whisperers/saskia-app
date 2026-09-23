/**
 * combo-rows.js — Global row-builder functions for the combobox.
 *
 * Each row builder returns an HTML string for one search result.
 * window-level because the auto-init in combo.js calls them by name.
 *
 * Add new builders here when adding new comboboxes that need richer display.
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

  function fmtGs(n) {
    if (!n || n === 0) return "";
    return "Gs. " + Number(n).toLocaleString("es-PY");
  }

  /**
   * Ingredient row: name · unit · current stock
   * Used in merma + future inventory-picker contexts.
   */
  window.ingredientRowLabel = function (item) {
    var warnClass = item.stock_qty < item.min_stock_qty ? ' combo-row-warn' : '';
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) +
      ' <small class="combo-row-sub">(' + escapeHtml(item.unit || "") + ")" +
      "</small>" + "</span>" +
      '<span class="combo-row-meta' + warnClass + '">' +
      (item.stock_qty != null
        ? Number(item.stock_qty).toFixed(1) + " " + escapeHtml(item.unit || "")
        : "") +
      (item.purchase_price_gs
        ? ' · ' + escapeHtml(fmtGs(item.purchase_price_gs))
        : "") +
      "</span>"
    );
  };

  /**
   * Customer row: name + phone (Pi-style)
   */
  window.customerRowLabel = function (item) {
    var phone = item.phone ? " · " + escapeHtml(item.phone) : "";
    var cedula = item.cedula ? " · CI " + escapeHtml(item.cedula) : "";
    var lifetime = item.lifetime_label
      ? ' · <span class="combo-row-accent">' + escapeHtml(item.lifetime_label) + "</span>"
      : "";
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) + "</span>" +
      '<span class="combo-row-sub">' + phone + cedula + lifetime + "</span>"
    );
  };

  /**
   * Product row: name + price
   */
  window.productRowLabel = function (item) {
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) +
      (item.portion_label ? ' <small class="combo-row-sub">' + escapeHtml(item.portion_label) + "</small>" : "") +
      "</span>" +
      '<span class="combo-row-meta combo-row-accent">' +
      escapeHtml(fmtGs(item.sale_price_gs)) + "</span>"
    );
  };

  /**
   * Product row: name + price
   */
  window.productRowLabel = function (item, isCreateOption) {
    var label = item.name || "Producto sin nombre";
    if (item.sale_price_gs) {
      label += " - " + escapeHtml(window.saskia_gs(item.sale_price_gs));
    }
    if (isCreateOption) {
      return '<div class="combo-row combo-row-create">+ Crear: ' + label + '</div>';
    }
    return '<div class="combo-row">' + label + '</div>';
  };
  
  /**
   * Recipe row: name + yield + cost
   */
  window.recipeRowLabel = function (item) {
    var yield_ = item.yield_qty ? " rinde " + escapeHtml(String(item.yield_qty)) +
      " " + escapeHtml(item.yield_unit || "") : "";
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) + "</span>" +
      '<span class="combo-row-sub">' + yield_ + "</span>"
    );
  };

  /**
   * Category row: just name, with "Crear" for new items
   */
  window.categoryRowLabel = function (item, isCreateOption) {
    if (isCreateOption) {
      return (
        '<span class="combo-row-main combo-row-create">' +
        '+ Crear: ' + escapeHtml(item.name) + "</span>" +
        '<span class="combo-row-sub"> nueva categoría</span>'
      );
    }
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) + "</span>"
    );
  };

  /**
   * Generic fallback (used when no row builder specified)
   */
  window.genericRowLabel = function (item) {
    return '<span class="combo-row-main">' + escapeHtml(JSON.stringify(item)) + "</span>";
  };

  /**
   * Recipe search row: name + yield description
   * Used in merma form for recipe selection with combo
   */
  window.recipeSearchRowLabel = function (item) {
    if (!item) return '';
    
    var yieldText = item.yield_qty && item.yield_unit 
      ? " rinde " + escapeHtml(String(item.yield_qty)) + " " + escapeHtml(item.yield_unit)
      : "";
    
    return (
      '<span class="combo-row-main">' + escapeHtml(item.name) + "</span>" +
      '<span class="combo-row-sub">' + yieldText + "</span>"
    );
  };
})();
