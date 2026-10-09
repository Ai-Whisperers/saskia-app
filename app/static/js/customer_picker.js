/* app/static/js/customer_picker.js
 *
 * Tier 4.2 (2026-10-01): extracted from app/templates/_components/_customer_picker.html
 * so the inline 714-line <script> block becomes a cacheable bundle. The picker
 * template now does <script src="/static/js/customer_picker.js" defer></script>.
 *
 * Vanilla JS for the customer picker widget on /ventas:
 *   - ui-combo selection → fetch customer detail → render card
 *   - inline "Nuevo cliente" form → POST /clientes/api/create → render card
 *   - Phase 4 loyalty POS redeem (live preview, clamping)
 *   - Tier 2.1 one-tap auto-redeem for balances >= 100 pts
 *   - Phase 4 decision C auto-suggestions (cumple_cerca, dormant, lapsed, vip)
 *   - Tier 1.4 visible failure badge when a suggestion can't apply
 *   - Tier 2.5 nudge focus redirect
 *   - Tier 3.2 fire-and-forget analytics ping on suggestion tap
 *
 * The DOM nodes this script reads/writes are defined in:
 *   app/templates/_components/_customer_picker.html  (combo widget + new-customer form)
 *   app/templates/_components/_customer_card.html     (info card, will be added next)
 *   app/templates/_components/_customer_nudge.html    (Tier 2.5 nudge, will be added next)
 *
 * Backed by:
 *   GET  /clientes/api/search?q=...      → {"results":[...]}
 *   GET  /clientes/api/{id}              → {...full payload incl. stats + suggestions}
 *   POST /clientes/api/create             → {"id": N, "customer": {...}}
 *   POST /clientes/api/{id}/suggestion-applied (fire-and-forget analytics)
 */
(function() {
  'use strict';

  // Allergen vocabulary. Closed list — do NOT add new allergens without
  // updating the QA gate + the cashier training notes. Source of truth for
  // the warning chip in the customer info card. Case-insensitive substring
  // match against the customer's free-text notes.
  var ALLERGENS = [
    'gluten', 'lactosa', 'frutos secos', 'huevo', 'soja',
    'maní', 'man\u00ed', 's\u00e9samo', 'leche', 'nuez', 'marisco'
  ];

  // 2026-09-29 fix: ui-combo doesn't expose its `name` as `id`, so
  // getElementById('customer_id_combo') returns null. Use the [name=...]
  // attribute selector instead. (Also: ui-combo's `value` is the
  // native HTMLElement.value which returns undefined for custom elements —
  // use the JS getter `getValue()`.)
  var combo = document.querySelector('ui-combo[name="customer_id_combo"]');
  var hidden = document.getElementById('customer_id');
  var hint = document.getElementById('customer_picker_hint');

  var card = document.getElementById('customer-card');
  var cardName = document.getElementById('customer-card-name');
  var cardContact = document.getElementById('customer-card-contact');
  var cardVisits = document.getElementById('customer-card-visits');
  var cardLastVisit = document.getElementById('customer-card-last-visit');
  var cardLifetime = document.getElementById('customer-card-lifetime');
  var cardPoints = document.getElementById('customer-card-points');
  var cardTier = document.getElementById('customer-card-tier');
  var cardTop = document.getElementById('customer-card-top');
  var cardTopList = document.getElementById('customer-card-top-list');
  var cardAllergenChip = document.getElementById('customer-card-allergen-chip');
  var cardDietaryChip = document.getElementById('customer-card-dietary-chip');
  var cardDietaryTags = document.getElementById('customer-card-dietary-tags');
  var cardDietaryNote = document.getElementById('customer-card-dietary-note');
  var cardNotes = document.getElementById('customer-card-notes');
  var cardNotesText = document.getElementById('customer-card-notes-text');
  var cardLoading = document.getElementById('customer-card-loading');
  var cardError = document.getElementById('customer-card-error');
  var cardQuitBtn = document.getElementById('customer-card-quit');

  // Tier label mapping (the LoyaltyTier enum has 'bronze|silver|gold|platinum';
  // 'platinum' is renamed to 'VIP' for the cashier-facing label per the
  // ventas-redesign phase A spec).
  var TIER_LABELS = {
    'bronze': 'Bronce',
    'silver': 'Plata',
    'gold': 'Oro',
    'platinum': 'VIP'
  };

  // ── Card rendering ─────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function relativeDate(iso) {
    if (!iso) return '\u2014';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '\u2014';
    var now = new Date();
    var diffMs = now - d;
    var diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return 'futuro';
    if (diffDays === 0) return 'hoy';
    if (diffDays === 1) return 'ayer';
    if (diffDays < 7) return 'hace ' + diffDays + ' d\u00edas';
    if (diffDays < 30) return 'hace ' + Math.floor(diffDays / 7) + ' sem';
    if (diffDays < 365) return 'hace ' + Math.floor(diffDays / 30) + ' meses';
    return 'hace ' + Math.floor(diffDays / 365) + ' a\u00f1o' + (diffDays >= 730 ? 's' : '');
  }

  function clearCard() {
    if (!card) return;
    card.hidden = true;
    // Tier 2.5 (2026-10-01): publish the cleared customer state so
    // ventas.html can re-evaluate the "no customer" nudge when the
    // cashier quits the customer card.
    try { window.CURRENT_CUSTOMER_ID = null; } catch (e) {}
    if (cardName) cardName.textContent = '\u2014';
    if (cardContact) cardContact.textContent = '\u2014';
    if (cardVisits) cardVisits.textContent = '\u2014';
    if (cardLastVisit) cardLastVisit.textContent = '\u2014';
    if (cardLifetime) cardLifetime.textContent = '\u2014';
    if (cardPoints) cardPoints.textContent = '\u2014';
    if (cardTier) { cardTier.textContent = '\u2014'; cardTier.dataset.tier = ''; }
    if (cardTop) { cardTop.hidden = true; }
    if (cardAllergenChip) cardAllergenChip.hidden = true;
    if (cardDietaryChip) cardDietaryChip.hidden = true;
    var chEl = document.getElementById("customer-card-channel");
    if (chEl) chEl.hidden = true;
    if (cardNotes) cardNotes.hidden = true;
    if (cardLoading) cardLoading.hidden = true;
    if (cardError) { cardError.hidden = true; cardError.textContent = ''; }
    card.classList.remove('is-loading');
    card.style.cursor = '';
  }

  function showCardLoading(on) {
    if (!card) return;
    card.classList.toggle('is-loading', !!on);
    if (cardLoading) cardLoading.hidden = !on;
    card.style.cursor = on ? 'wait' : '';
  }

  function showCardError(msg) {
    if (!cardError) return;
    if (msg) {
      cardError.textContent = msg;
      cardError.hidden = false;
    } else {
      cardError.hidden = true;
      cardError.textContent = '';
    }
  }

  function hasAllergen(notes) {
    if (!notes) return false;
    var n = String(notes).toLowerCase();
    for (var i = 0; i < ALLERGENS.length; i++) {
      if (n.indexOf(ALLERGENS[i]) !== -1) return true;
    }
    return false;
  }

  function renderCard(data) {
    if (!card || !data) return;
    card.hidden = false;
    // Tier 2.5 (2026-10-01): publish the picked customer ID on window
    // so the ventas.html "no customer" nudge can re-evaluate. The
    // sales router also reads window.CURRENT_CUSTOMER_ID to wire
    // the hidden customer_id field on form submit.
    try { window.CURRENT_CUSTOMER_ID = data.id || null; } catch (e) {}
    // Hide the nudge the moment a customer is picked.
    var nudge = document.getElementById('nudge-no-customer');
    if (nudge && window.CURRENT_CUSTOMER_ID) nudge.hidden = true;

    if (cardName) cardName.textContent = data.name || '(sin nombre)';

    // Contact row: phone · cedula · email
    var bits = [];
    if (data.phone) bits.push(escapeHtml(data.phone));
    if (data.cedula) bits.push('CI ' + escapeHtml(data.cedula));
    if (data.email) bits.push(escapeHtml(data.email));
    if (cardContact) cardContact.textContent = bits.length ? bits.join(' \u00b7 ') : '\u2014';

    if (cardVisits) cardVisits.textContent = data.n_sales != null ? String(data.n_sales) : '\u2014';
    if (cardLastVisit) cardLastVisit.textContent = relativeDate(data.last_sale_at);
    if (cardLifetime) cardLifetime.textContent = data.lifetime_label || '\u2014';
    if (cardPoints) cardPoints.textContent = data.loyalty_points != null ? String(data.loyalty_points) : '\u2014';

    // Phase 4 decision C (2026-10-01): render auto-suggested offers
    // for this customer. Pure-function output from /clientes/api/{id}
    // (see app/rms/loyalty_suggestions.py). The list is up to 3
    // cards with title + body; clicking a suggestion pre-fills the
    // existing #discount-gs-total field with discount_pct × unit price
    // (cashier confirms or clears).
    renderSuggestions(data.suggestions || []);

    // Phase 4 loyalty POS redeem (2026-10-01): populate the inline
    // "Usar puntos" form when a customer is picked. The form lives in
    // _customer_picker.html; we toggle its hidden state here and stash
    // the customer's available points so the live preview can clamp.
    var redeemBlock = document.getElementById('customer-card-redeem');
    var redeemAvailableEl = document.getElementById('points-redeem-available');
    var redeemInput = document.getElementById('points_to_redeem_input');
    var available = data.loyalty_points != null ? Number(data.loyalty_points) : 0;
    if (redeemBlock) redeemBlock.hidden = !(available > 0);
    if (redeemAvailableEl) redeemAvailableEl.textContent = String(available);
    if (redeemInput) {
      redeemInput.max = String(available);
      // Reset the input and the hidden form value when a different
      // customer is picked so old typed values don't leak.
      redeemInput.value = '0';
      var hiddenPts = document.getElementById('points_to_redeem');
      if (hiddenPts) hiddenPts.value = '0';
      var redeemPreview = document.getElementById('points-redeem-preview');
      if (redeemPreview) redeemPreview.textContent = '1 punto = 1.000 Gs. de descuento';
    }

    // Tier 2.1 (2026-10-01): one-tap auto-redeem block. Show when
    // available >= 100 points (≥ Gs. 100.000 of meaningful discount)
    // — below that, the small manual input is enough. Hide otherwise.
    var AUTO_REDEEM_MIN = 100;
    var autoBlock = document.getElementById('customer-card-auto-redeem');
    var autoPtsEl = document.getElementById('auto-redeem-points');
    var autoAmtEl = document.getElementById('auto-redeem-amount');
    if (autoBlock && autoPtsEl && autoAmtEl) {
      if (available >= AUTO_REDEEM_MIN) {
        autoPtsEl.textContent = String(available);
        // T-2026-10-01: use the live rate from window.SASKIA_POINTS_VALUE_GS
        // (set by _customer_card.html) instead of the hardcoded 1000 that
        // assumed a 100% lifetime-spend return rate.
        var ptsVal = (typeof window.SASKIA_POINTS_VALUE_GS === 'number')
          ? window.SASKIA_POINTS_VALUE_GS : 100;
        autoAmtEl.textContent = '−' + formatGs(available * ptsVal) + ' Gs.';
        autoBlock.hidden = false;
      } else {
        autoBlock.hidden = true;
      }
    }

    var tierKey = (data.tier || '').toLowerCase();
    if (cardTier) {
      cardTier.textContent = TIER_LABELS[tierKey] || data.tier || '\u2014';
      cardTier.dataset.tier = tierKey;
    }

    // Top products line
    if (cardTop && cardTopList) {
      var tops = data.top_products || [];
      if (tops.length > 0) {
        cardTopList.textContent = tops.map(function(t) {
          return escapeHtml(t.name) + ' (\u00d7' + (t.count != null ? t.count : 0) + ')';
        }).join(', ');
        cardTop.hidden = false;
      } else {
        cardTop.hidden = true;
      }
    }

    // Allergen chip
    if (cardAllergenChip) {
      cardAllergenChip.hidden = !hasAllergen(data.notes);
    }

    // P3 profile: preferred channel hint for the cashier
    if (data.preferred_channel) {
      var ch = document.getElementById("customer-card-channel");
      if (!ch) {
        ch = document.createElement("div");
        ch.id = "customer-card-channel";
        ch.style.cssText = "margin-top:6px;font-size:0.85rem;color:var(--muted-foreground);";
        cardContact.parentElement.appendChild(ch);
      }
      ch.textContent = "Prefiere: " + data.preferred_channel;
      ch.hidden = false;
    } else {
      var ch0 = document.getElementById("customer-card-channel");
      if (ch0) ch0.hidden = true;
    }

    // P3 dietary: structured restrictions from the API (not notes-guessing)
    if (cardDietaryChip) {
      var restrictions = data.dietary_restrictions || [];
      if (restrictions.length) {
        cardDietaryTags.textContent = restrictions.join(', ');
        cardDietaryNote.textContent = data.dietary_confirm_always
          ? 'Preguntar siempre antes de sustituir'
          : 'Verificar en cada pedido';
        cardDietaryChip.hidden = false;
      } else {
        cardDietaryChip.hidden = true;
      }
    }

    // Notes (only if non-empty)
    if (cardNotes && cardNotesText) {
      if (data.notes && String(data.notes).trim()) {
        cardNotesText.textContent = data.notes;
        cardNotes.hidden = false;
      } else {
        cardNotes.hidden = true;
      }
    }

    showCardError('');
  }

  function fillCardFromData(data) {
    if (!data) { clearCard(); return; }
    renderCard(data);
  }

  function fetchAndFillCard(customerId) {
    if (!customerId) { clearCard(); return; }
    showCardLoading(true);
    showCardError('');
    // Card must be visible while loading so the spinner shows.
    if (card) { card.hidden = false; card.classList.add('is-loading'); }
    fetch('/clientes/api/' + customerId, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    })
      .then(function(res) {
        if (res.status === 404) {
          if (hidden) hidden.value = '';
          if (combo && typeof combo.setValue === 'function') combo.setValue('', '');
          throw new Error('Cliente no encontrado.');
        }
        if (!res.ok) throw new Error('Error al cargar cliente (' + res.status + ').');
        return res.json();
      })
      .then(function(data) { fillCardFromData(data); })
      .catch(function(err) {
        showCardError(err && err.message ? err.message : 'Error al cargar cliente.');
      })
      .then(function() { showCardLoading(false); });
  }

  // ── Quit button: clear hidden field, combo, and card ────────────────────
  if (cardQuitBtn) {
    cardQuitBtn.addEventListener('click', function() {
      if (hidden) hidden.value = '';
      if (combo && typeof combo.setValue === 'function') combo.setValue('', '');
      clearCard();
    });
  }

  // ── Phase 4 loyalty POS redeem (2026-10-01): live preview + clamping.
  // The cashier types a points amount; we update the hidden form field
  // (which rides along with /ventas/nueva's POST) and the live preview
  // showing the equivalent Gs. discount. Clamps to available balance
  // so the cashier gets instant feedback.
  var redeemInput = document.getElementById('points_to_redeem_input');
  var redeemClear = document.getElementById('points-redeem-clear');
  var hiddenPts = document.getElementById('points_to_redeem');
  var redeemPreview = document.getElementById('points-redeem-preview');
  var redeemAvailableEl = document.getElementById('points-redeem-available');
  function getAvailablePoints() {
    return redeemAvailableEl ? Number(redeemAvailableEl.textContent) || 0 : 0;
  }
  function formatGs(n) {
    // Insert thousands separators; matches the rest of the app's number format.
    var s = String(Math.round(n));
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function updateRedeemPreview() {
    if (!redeemInput || !hiddenPts || !redeemPreview) return;
    var typed = Math.floor(Number(redeemInput.value) || 0);
    if (typed < 0) typed = 0;
    var available = getAvailablePoints();
    if (typed > available) {
      typed = available;
      redeemInput.value = String(typed);
    }
    hiddenPts.value = String(typed);
    // T-2026-10-01: use the live rate (server-injected via window
    // global in _customer_card.html) instead of the hardcoded 1000
    // that assumed 1 pt = 1000 Gs. The displayed rate text and the
    // computed discount both read from the same source.
    var ptsVal = (typeof window.SASKIA_POINTS_VALUE_GS === 'number')
      ? window.SASKIA_POINTS_VALUE_GS : 100;
    var rateLabel = '1 punto = ' + formatGs(ptsVal) + ' Gs. de descuento';
    var rateEl = document.getElementById('points-redeem-rate-display');
    if (rateEl) rateEl.textContent = rateLabel;
    if (typed === 0) {
      redeemPreview.textContent = rateLabel;
      redeemPreview.style.color = '';
    } else {
      var gs = typed * ptsVal;
      redeemPreview.textContent =
        typed + ' punto' + (typed === 1 ? ' = ' : 's = ') +
        formatGs(gs) + ' Gs. de descuento';
      redeemPreview.style.color = 'var(--color-success, #16a34a)';
    }
  }
  if (redeemInput) {
    redeemInput.addEventListener('input', updateRedeemPreview);
    redeemInput.addEventListener('change', updateRedeemPreview);
  }
  if (redeemClear) {
    redeemClear.addEventListener('click', function() {
      if (redeemInput) redeemInput.value = '0';
      updateRedeemPreview();
    });
  }

  // Tier 2.1 (2026-10-01): one-tap auto-redeem button. Clicking
  // pre-fills the inline redeem input with the full available
  // balance, fires updateRedeemPreview() so the hidden form field
  // + preview update, and visually marks the button as "applied"
  // so the cashier knows their click landed. Cashier still hits
  // Confirmar venta to actually run the sale — we never bypass it.
  var autoBtn = document.getElementById('auto-redeem-btn');
  if (autoBtn && redeemInput) {
    autoBtn.addEventListener('click', function () {
      var available = getAvailablePoints();
      if (available <= 0) return;
      redeemInput.value = String(available);
      updateRedeemPreview();
      // Visual: collapse button → small "✓ Listo" pill for 1.5s
      autoBtn.disabled = true;
      autoBtn.style.opacity = '0.7';
      var originalHtml = autoBtn.innerHTML;
      autoBtn.innerHTML = '✓ ' + available + ' puntos listos para canjear';
      setTimeout(function () {
        autoBtn.innerHTML = originalHtml;
        autoBtn.disabled = false;
        autoBtn.style.opacity = '1';
      }, 1500);
    });
  }

  // ── Phase 4 decision C (2026-10-01): auto-suggestions renderer.
  // The /clientes/api/{id} payload includes up to 3 suggestions;
  // we render them as small cards with a "tap to apply" affordance.
  // Clicking a suggestion with a discount_pct pre-fills the existing
  // #discount-gs-total field (the cashier confirms or clears before
  // submitting the sale — we never bypass that step).
  function renderSuggestions(suggestions) {
    var wrap = document.getElementById('customer-card-suggestions');
    var list = document.getElementById('customer-card-suggestions-list');
    if (!wrap || !list) return;
    if (!Array.isArray(suggestions) || suggestions.length === 0) {
      wrap.hidden = true;
      list.innerHTML = '';
      return;
    }
    wrap.hidden = false;
    list.innerHTML = '';
    suggestions.forEach(function (s) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'customer-suggestion-card';
      btn.dataset.kind = s.kind || '';
      btn.dataset.discountPct = s.discount_pct != null ? String(s.discount_pct) : '';
      btn.style.cssText = [
        'text-align:left',
        'padding:8px 10px',
        'border:1px solid var(--color-primary,#3b82f6)',
        'border-radius:6px',
        'background:#fff',
        'cursor:pointer',
        'font-size:0.85rem',
        'line-height:1.3',
        'transition:background 0.1s',
      ].join(';');
      var title = document.createElement('div');
      title.style.cssText = 'font-weight:600;color:var(--color-primary,#3b82f6);margin-bottom:2px;';
      title.textContent = s.title || '';
      var body = document.createElement('div');
      body.style.cssText = 'color:var(--color-text,#333);font-weight:400;';
      body.textContent = s.body || '';
      btn.appendChild(title);
      btn.appendChild(body);
      btn.addEventListener('click', function () {
        applySuggestion(s);
      });
      btn.addEventListener('mouseover', function () {
        btn.style.background = 'rgba(59,130,246,.08)';
      });
      btn.addEventListener('mouseout', function () {
        btn.style.background = '#fff';
      });
      list.appendChild(btn);
    });
  }

  // Apply a suggestion: pre-fill the hidden discount_gs field with
  // discount_pct × current unit price (read from the sale form's
  // #discount-gs-total field if it exists, otherwise from any visible
  // price cell). Cashier still has to hit "Confirmar venta" — we never
  // bypass the submit step.
  //
  // Tier 1.4 (2026-10-01): if no unit price can be resolved, surface a
  // visible warning badge near the discount field (and a console.warn
  // for QA). Previously the card flashed green even when nothing was
  // written — false positive that hid real bugs.
  function applySuggestion(suggestion) {
    var pct = suggestion && suggestion.discount_pct;
    if (!pct || pct <= 0 || pct > 100) {
      console.warn('[ui-suggestions] invalid discount_pct:', pct);
      return;
    }

    // Try the most common field names the template exposes for the
    // current unit price. Defensive — every form variant is different
    // and we don't want to crash if the operator is on a less common
    // flow. We just set the hidden total-discount field that every
    // POS form on /ventas carries.
    var unitPrice = null;
    var unitPriceSource = null;
    // 1) Look for an explicit price cell on the visible cart row
    var priceEl = document.querySelector(
      '[data-current-unit-price], .cart-row [data-price-gs], .current-sale-price'
    );
    if (priceEl) {
      var raw = priceEl.getAttribute('data-current-unit-price')
        || priceEl.getAttribute('data-price-gs')
        || priceEl.textContent;
      var parsed = parseInt(String(raw).replace(/[^0-9]/g, ''), 10);
      if (!isNaN(parsed) && parsed > 0) {
        unitPrice = parsed;
        unitPriceSource = 'cart-row-data';
      }
    }
    // 2) Fallback: parse a unit price out of the product picker if it's
    //    a <select> with visible Gs. labels like "Chipita — 12.000 Gs."
    if (!unitPrice) {
      var selectEl = document.querySelector(
        'select[name="product_id"], select#product_id'
      );
      if (selectEl && selectEl.selectedOptions && selectEl.selectedOptions[0]) {
        var labelText = selectEl.selectedOptions[0].textContent || '';
        var m = labelText.match(/([\d.]+)\s*Gs/);
        if (m) {
          var cleaned = m[1].replace(/\./g, '').replace(/,/g, '');
          var parsed2 = parseInt(cleaned, 10);
          if (!isNaN(parsed2) && parsed2 > 0) {
            unitPrice = parsed2;
            unitPriceSource = 'select-label';
          }
        }
      }
    }

    var discountField = document.getElementById('discount-gs-total');
    if (!discountField) {
      console.warn(
        '[ui-suggestions] discount-gs-total field missing; cannot apply.'
      );
      flashSuggestionFeedback(
        suggestion,
        false,
        'No se pudo aplicar — falta el campo de descuento.'
      );
      return;
    }

    if (!unitPrice || unitPrice <= 0) {
      console.warn(
        '[ui-suggestions] no unit price resolvable from current form;',
        'suggestion:', suggestion && suggestion.kind,
        'pct:', pct
      );
      flashSuggestionFeedback(
        suggestion,
        false,
        'No se pudo aplicar — seleccioná un producto primero.'
      );
      return;
    }

    var discount = Math.round((unitPrice * pct) / 100);
    discountField.value = String(discount);
    // Fire an input event so any live-total preview updates.
    discountField.dispatchEvent(new Event('input', { bubbles: true }));
    discountField.dispatchEvent(new Event('change', { bubbles: true }));
    console.info(
      '[ui-suggestions] applied', suggestion.kind, '→ Gs.',
      discount, '(unit price Gs.', unitPrice, 'from', unitPriceSource + ')'
    );
    // Tier 3.2 (2026-10-01): fire-and-forget analytics ping. We
    // don't await — never block the UX on this. Failure logs to
    // console but doesn't undo the apply.
    try {
      var customerId =
        (window.CURRENT_CUSTOMER_ID) ||
        (document.getElementById('customer_id') || {}).value ||
        null;
      if (customerId) {
        fetch(
          '/clientes/api/' + encodeURIComponent(customerId) + '/suggestion-applied',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              kind: suggestion.kind,
              discount_pct: pct,
              unit_price_gs: unitPrice,
              unit_price_source: unitPriceSource,
            }),
            keepalive: true,
          }
        ).catch(function (e) {
          console.warn('[ui-suggestions] analytics ping failed:', e);
        });
      }
    } catch (e) {
      console.warn('[ui-suggestions] could not fire analytics:', e);
    }
    flashSuggestionFeedback(
      suggestion,
      true,
      formatGs(discount) + ' Gs. de descuento aplicados.'
    );
  }

  // Render a small inline status message near the discount field for
  // 2.5s. Tier 1.4 (2026-10-01) — replaces the previous false-positive
  // green-flash when the suggestion didn't actually apply.
  function flashSuggestionFeedback(suggestion, ok, msg) {
    // Card visual feedback — green only on success.
    var cards = document.querySelectorAll('.customer-suggestion-card');
    cards.forEach(function (c) {
      c.style.background = '#fff';
      c.style.borderColor = 'var(--color-primary,#3b82f6)';
    });
    var clicked = document.querySelector(
      '.customer-suggestion-card[data-kind="' + (suggestion && suggestion.kind || '') + '"]'
    );
    if (clicked) {
      if (ok) {
        clicked.style.background = 'rgba(59,130,246,.15)';
        clicked.style.borderColor = 'var(--color-success,#16a34a)';
      } else {
        clicked.style.background = 'rgba(220,50,50,.10)';
        clicked.style.borderColor = 'var(--color-danger,#d33)';
      }
    }
    // Inline status badge near the discount field — only on failure
    // (success is already loud via the card flash + post-save toast).
    if (ok) return;
    var discountField = document.getElementById('discount-gs-total');
    var anchor = discountField ? discountField.parentNode : null;
    if (!anchor) return;
    var badge = document.createElement('div');
    badge.className = 'ui-suggestion-feedback';
    badge.setAttribute('role', 'status');
    badge.style.cssText = [
      'margin-top:6px',
      'padding:6px 10px',
      'border-radius:4px',
      'background:rgba(220,50,50,.10)',
      'border:1px solid var(--color-danger,#d33)',
      'color:var(--color-danger,#d33)',
      'font-size:0.85rem',
    ].join(';');
    badge.textContent = msg || 'No se pudo aplicar la sugerencia.';
    // Remove any prior badge so the message never stacks.
    var prior = anchor.querySelector('.ui-suggestion-feedback');
    if (prior) prior.remove();
    anchor.appendChild(badge);
    setTimeout(function () {
      if (badge.parentNode) badge.parentNode.removeChild(badge);
    }, 2500);
  }

  // ── Combo change → fetch detail + populate card ────────────────────────
  // 2026-09-29 fix: ui-combo's `value` is the native HTMLElement.value
  // (returns attribute value, not the JS _value). The getter we want is
  // `getValue()`. Without this fix, hidden.value is set to '' on every
  // selection → customer_id never reaches the backend → no client attached
  // to the sale. Symptom: customer info card stays hidden after selection.
  if (combo && hidden) {
    combo.addEventListener('change', function() {
      var selectedId = combo.getValue ? combo.getValue() : combo.value;
      hidden.value = selectedId || '';
      if (hint) {
        var data = combo.getSelectedData ? combo.getSelectedData() : null;
        if (data && data.hint) {
          hint.textContent = data.hint;
          hint.hidden = false;
        } else {
          hint.hidden = true;
        }
      }
      var id = parseInt(selectedId, 10);
      if (id) {
        fetchAndFillCard(id);
      } else {
        clearCard();
      }
    });
  }

  // ── Inline "Nuevo cliente" form ────────────────────────────────────────
  var form = document.getElementById('customer_picker_new_form');
  var errBox = document.getElementById('cp_new_error');
  if (!form) return;
  form.addEventListener('submit', async function(ev) {
    ev.preventDefault();
    errBox.hidden = true;
    var fd = new FormData(form);
    var payload = {};
    fd.forEach(function(v, k) { payload[k] = v; });
    try {
      var resp = await fetch('/clientes/api/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      });
      if (!resp.ok) {
        var err = await resp.json().catch(function() { return { detail: 'Error al crear cliente.' }; });
        errBox.textContent = err.detail || 'Error al crear cliente.';
        errBox.hidden = false;
        return;
      }
      var data = await resp.json();
      // New customer row + full detail payload (notes/stats/top_products)
      // comes back from the server — no second fetch needed.
      hidden.value = data.id || '';
      if (combo && typeof combo.setValue === 'function') {
        combo.setValue(data.id || '', data.customer && data.customer.name || data.name || '');
      }
      // Populate the card from the create response.
      fillCardFromData(data.customer || data);
      form.reset();
      var details = document.getElementById('customer_picker_new_panel');
      if (details) details.open = false;
    } catch (e) {
      errBox.textContent = 'Error de red al crear cliente.';
      errBox.hidden = false;
    }
  });
})();

// Tier 2.5 (2026-10-01): focus the customer-combo input when the
// "Buscar cliente" nudge button is clicked. Runs outside the IIFE
// because the nudge element is rendered in the ventas.html template,
// not in this component.
document.addEventListener('DOMContentLoaded', function () {
  var focusBtn = document.getElementById('nudge-no-customer-focus');
  if (!focusBtn) return;
  focusBtn.addEventListener('click', function () {
    // Try the ui-combo widget first (it's an async component).
    var comboInput = document.querySelector(
      'input[name="customer_combo"], #customer-combo, .ui-combo input'
    );
    if (comboInput) {
      comboInput.focus();
      comboInput.click();
      return;
    }
    // Fallback: any visible customer search input.
    var any = document.querySelector(
      'input[id*="customer" i], input[name*="customer" i], input[placeholder*="cliente" i]'
    );
    if (any) any.focus();
  });
});
