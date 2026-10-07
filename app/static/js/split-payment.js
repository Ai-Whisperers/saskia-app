// split-payment.js — WP-1.2 pagos mixtos (2026-10-07)
// "Dividir pago" en el POS: filas método + monto con resta viva
// ("Falta Gs. X" / "Vuelto Gs. X"). Patrón: builders de combo-rows.js.
// El backend exige suma == total del carrito; aquí se lo hacemos visible
// al cajero ANTES de enviar. Single-method (sin split) sigue igual.
(function () {
  'use strict';

  var METHODS = ['efectivo', 'tarjeta', 'qr', 'transferencia'];
  var rowsEl, wrapEl, statusEl, btnEl;
  var seq = 0;

  function fmtGs(n) {
    return 'Gs. ' + String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function cartTotal() {
    var el = document.getElementById('cart-total');
    if (!el) return 0;
    var n = parseInt((el.textContent || '').replace(/[^\d]/g, ''), 10);
    return isNaN(n) ? 0 : n;
  }

  function rowsSum() {
    var sum = 0;
    wrapEl.querySelectorAll('.sp-amount').forEach(function (inp) {
      var v = parseInt(inp.value || '0', 10);
      if (!isNaN(v)) sum += v;
    });
    return sum;
  }

  function buildRow(method, amount) {
    seq += 1;
    var row = document.createElement('div');
    row.className = 'sp-row';
    row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px;';

    var sel = document.createElement('select');
    sel.className = 'sp-method';
    sel.setAttribute('aria-label', 'Método de pago ' + seq);
    sel.style.cssText = 'flex:1;padding:6px;';
    METHODS.forEach(function (m) {
      var opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m.charAt(0).toUpperCase() + m.slice(1);
      if (m === method) opt.selected = true;
      sel.appendChild(opt);
    });

    var amountInp = document.createElement('input');
    amountInp.type = 'number';
    amountInp.className = 'sp-amount';
    amountInp.min = '0';
    amountInp.step = '1';
    amountInp.value = amount != null ? String(amount) : '';
    amountInp.setAttribute('aria-label', 'Monto ' + seq);
    amountInp.placeholder = 'Monto';
    amountInp.style.cssText = 'flex:1;padding:6px;text-align:right;';

    var del = document.createElement('button');
    del.type = 'button';
    del.className = 'btn btn-sm btn-ghost sp-del';
    del.setAttribute('aria-label', 'Quitar pago');
    del.textContent = '\u2715';
    del.addEventListener('click', function () {
      row.remove();
      if (!wrapEl.querySelector('.sp-row')) reset();
      else refresh();
    });

    sel.addEventListener('change', refresh);
    amountInp.addEventListener('input', refresh);

    row.appendChild(sel);
    row.appendChild(amountInp);
    row.appendChild(del);
    return row;
  }

  function refresh() {
    var total = cartTotal();
    var sum = rowsSum();
    var diff = total - sum;
    if (diff > 0) {
      statusEl.textContent = 'Falta ' + fmtGs(diff);
      statusEl.style.color = 'var(--destructive, #b91c1c)';
    } else if (diff < 0) {
      statusEl.textContent = 'Vuelto ' + fmtGs(-diff);
      statusEl.style.color = 'var(--muted-foreground, #6b7280)';
    } else {
      statusEl.textContent = '\u2713 Cuadra';
      statusEl.style.color = 'var(--success, #15803d)';
    }
  }

  function reset() {
    wrapEl.innerHTML = '';
    statusEl.textContent = '';
    wrapEl.style.display = 'none';
    btnEl.setAttribute('aria-expanded', 'false');
  }

  function collect() {
    var out = [];
    var seen = false;
    wrapEl.querySelectorAll('.sp-row').forEach(function (row) {
      var m = row.querySelector('.sp-method').value;
      var a = parseInt(row.querySelector('.sp-amount').value || '0', 10);
      if (!isNaN(a) && a > 0) { out.push({ method: m, amount_gs: a }); seen = true; }
    });
    return seen ? out : null;
  }

  function init() {
    btnEl = document.getElementById('btn-split-payment');
    if (!btnEl) return;
    wrapEl = document.getElementById('split-payment-rows');
    statusEl = document.getElementById('split-payment-status');
    if (!wrapEl || !statusEl) return;

    btnEl.addEventListener('click', function () {
      var open = wrapEl.style.display !== 'none';
      if (open) { reset(); return; }
      wrapEl.style.display = 'block';
      btnEl.setAttribute('aria-expanded', 'true');
      var total = cartTotal();
      // Pre-carga 2 filas: primera con el total completo (caso "parte
      // efectivo, resto tarjeta": el cajero solo edita el segundo monto).
      wrapEl.appendChild(buildRow(METHODS[0], total));
      wrapEl.appendChild(buildRow(METHODS[1], null));
      refresh();
    });

    // Gancho para ventas.html: payload.payments
    window.SplitPayment = { collect: collect };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
