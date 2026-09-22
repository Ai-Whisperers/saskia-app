/**
 * receta-combos.js — Recipe line picker for /recetas/nueva + /recetas/{id}/editar.
 *
 * Each recipe line has:
 *  - line_kind: 'ingredient' or 'sub_recipe' (small <select>)
 *  - line_target_id: hidden input backed by a combobox — searches
 *    the right endpoint based on the current kind.
 *
 * Sources:
 *   line_kind = 'ingredient' → /inventario/api/search
 *   line_kind = 'sub_recipe'  → /recetas/api/search
 *
 * Public API: window.RecetaCombos.attachLineTargetCombo(row)
 */
(function (global) {
  "use strict";

  function sourceFor(kind, recipeId) {
    if (kind === "sub_recipe") {
      return recipeId
        ? "/recetas/api/search?exclude_id=" + encodeURIComponent(recipeId)
        : "/recetas/api/search";
    }
    return "/inventario/api/search";
  }

  function rowBuilderFor(kind) {
    return kind === "sub_recipe" ? "recipeRowLabel" : "ingredientRowLabel";
  }

  function placeholderFor(kind) {
    return kind === "sub_recipe"
      ? "Buscar receta…"
      : "Buscar ingrediente…";
  }

  function attachLineTargetCombo(lineDiv) {
    var kindSel = lineDiv.querySelector("select.line-kind-select");
    var comboRoot = lineDiv.querySelector(".saskia-combo.line-target-combo");
    if (!kindSel || !comboRoot) return;

    // Resolve recipe-id from URL (used to exclude circular sub-recipes)
    var recipeId = (window.RECIPE_CONTEXT_ID != null)
      ? window.RECIPE_CONTEXT_ID
      : parseRecipeIdFromPath();
    var input = comboRoot.querySelector(".combo-input");
    var hidden = comboRoot.querySelector('input[type="hidden"]');

    function rebindSource() {
      var kind = kindSel.value || "ingredient";
      comboRoot.dataset.source = sourceFor(kind, recipeId);
      comboRoot.dataset.rowBuilder = rowBuilderFor(kind);
      if (input) {
        input.placeholder = placeholderFor(kind);
        input.value = "";
        input.classList.remove("is-selected");
      }
      if (hidden) hidden.value = "";

      // Re-init the SaskiaCombo instance with new source.
      var Cls = global.SaskiaCombo;
      if (!Cls) return;
      if (comboRoot._saskiaCombo) {
        comboRoot._saskiaCombo.clear();
      }
      comboRoot._saskiaCombo = new Cls(comboRoot, {
        source: comboRoot.dataset.source,
        displayField: "name",
        valueField: "id",
        minChars: 1,
        buildRow: comboRoot.dataset.rowBuilder
          ? global[comboRoot.dataset.rowBuilder]
          : null,
      });
    }

    kindSel.addEventListener("change", rebindSource);

    // Initial init for already-rendered rows (server-side data).
    // (DOMContentLoaded handler below triggers this.)
    rebindSource();
    // Highlight the pre-picked target if hidden has a value
    if (hidden && hidden.value) {
      input.classList.add("is-selected");
    }
  }

  function parseRecipeIdFromPath() {
    var m = window.location.pathname.match(/\/recetas\/(\d+)/);
    return m ? Number(m[1]) : null;
  }

  // Auto-init on existing rows
  function initAll() {
    document.querySelectorAll(".line-row").forEach(attachLineTargetCombo);
    var addBtn = document.getElementById("add-line");
    if (addBtn && !addBtn._recetaCombosHooked) {
      addBtn._recetaCombosHooked = true;
      addBtn.addEventListener("click", function () {
        setTimeout(function () {
          var container = document.getElementById("lines");
          if (container) {
            var newRow = container.lastElementChild;
            if (newRow && newRow.classList.contains("line-row")) {
              attachLineTargetCombo(newRow);
            }
          }
        }, 0);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    // DOM already loaded — run immediately
    initAll();
  }

  global.RecetaCombos = {
    attachLineTargetCombo: attachLineTargetCombo,
    initAll: initAll,
  };
})(window);
