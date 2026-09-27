/* app.js — Section 20: Global Search, Notification Center, Copy-to-Clipboard
 * Loaded by base.html on every page.
 */
(function () {
  'use strict';

  /* ─── Helpers ───────────────────────────────────────────────────────────── */

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  /* ─── js-confirm-form: intercept forms with class="js-confirm-form" and use
     SaskiaConfirmModal instead of native confirm() ──────────────────────── */
  var __nextConfirmId = 1;
  function __wrapFormWithId(form) {
    if (form.id) return form.id;
    form.id = 'js-confirm-form-' + (__nextConfirmId++);
    return form.id;
  }
  function initConfirmForms() {
    var forms = document.querySelectorAll('form.js-confirm-form');
    for (var i = 0; i < forms.length; i++) {
      (function (form) {
        if (form.__saskiaConfirmBound) return;
        form.__saskiaConfirmBound = true;
        var formId = __wrapFormWithId(form);
        form.addEventListener('submit', function (e) {
          if (form.__saskiaConfirmed) return; // already confirmed
          e.preventDefault();
          var title = form.dataset.confirmTitle || '¿Estás seguro?';
          var body = form.dataset.confirmBody || 'Esta acción no se puede deshacer.';
          var danger = form.dataset.confirmDanger === 'true';
          if (window.SaskiaConfirmModal) {
            SaskiaConfirmModal.show({
              title: title,
              body: body,
              formId: formId,
              confirmLabel: 'Confirmar',
              danger: danger
            });
          } else {
            // Fallback to native confirm
            if (!window.confirm(title + '\n\n' + body)) return;
            form.__saskiaConfirmed = true;
            form.submit();
          }
        });
      })(forms[i]);
    }
  }

  function relativeTime(dateStr) {
    if (!dateStr) return '';
    try {
      var d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
      var diff = (Date.now() - d) / 1000;
      if (diff < 60) return 'hace un momento';
      if (diff < 3600) return 'hace ' + Math.floor(diff / 60) + ' min';
      if (diff < 86400) return 'hace ' + Math.floor(diff / 3600) + ' h';
      return 'hace ' + Math.floor(diff / 86400) + ' d';
    } catch (e) { return dateStr; }
  }

  /* ─── Global Search Modal (Cmd+K / Ctrl+K) ──────────────────────────────── */

  var searchModal = document.getElementById('search-modal');
  var searchInput = document.getElementById('global-search-input');
  var searchResults = document.getElementById('search-results');
  var searchBtn = document.getElementById('global-search-btn');
  var searchBackdrop = document.getElementById('search-backdrop');
  var searchTimer = null;

  function openSearch() {
    if (!searchModal) return;
    searchModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    setTimeout(function () { if (searchInput) searchInput.focus(); }, 30);
  }

  function closeSearch() {
    if (!searchModal) return;
    searchModal.style.display = 'none';
    document.body.style.overflow = '';
    if (searchInput) searchInput.value = '';
    if (searchResults) searchResults.innerHTML = '<p class="search-hint">Escribí para buscar en clientes, productos, pedidos y recetas.</p>';
  }

  if (searchBtn) {
    searchBtn.addEventListener('click', openSearch);
  }
  if (searchBackdrop) {
    searchBackdrop.addEventListener('click', closeSearch);
  }

  document.addEventListener('keydown', function (e) {
    // Cmd+K or Ctrl+K — open search
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (searchModal && searchModal.style.display === 'flex') {
        closeSearch();
      } else {
        openSearch();
      }
      return;
    }
    // Escape — close search
    if (e.key === 'Escape' && searchModal && searchModal.style.display === 'flex') {
      closeSearch();
    }
  });

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimer);
      var q = this.value.trim();
      if (!q || q.length < 2) {
        searchResults.innerHTML = '<p class="search-hint">Escribí al menos 2 caracteres para buscar.</p>';
        return;
      }
      searchTimer = setTimeout(function () { performSearch(q); }, 250);
    });
  }

  function performSearch(q) {
    searchResults.innerHTML = '<p class="search-hint">Buscando…</p>';
    var url = '/api/search?q=' + encodeURIComponent(q);

    fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('search failed');
        return r.json();
      })
      .then(function (data) {
        renderSearchResults(data, q);
      })
      .catch(function () {
        searchResults.innerHTML = '<p class="search-empty">Error al buscar. Intentalo de nuevo.</p>';
      });
  }

  function renderSearchResults(data, q) {
    var sections = [];
    var total = 0;

    function addSection(label, items) {
      if (!items || items.length === 0) return;
      total += items.length;
      var html = '<div class="search-section-label">' + label + '</div>';
      items.slice(0, 6).forEach(function (item) {
        var href = item.url || '#';
        var badge = item.badge || '';
        var badgeClass = item.badge_class || 'badge-neutral';
        var sub = item.sub || '';
        html += '<a href="' + href + '" class="search-result-item" data-type="' + label + '">\
          <div class="result-main">\
            <div class="result-name">' + escapeHtml(item.name) + '</div>\
            ' + (sub ? '<div class="result-sub">' + escapeHtml(sub) + '</div>' : '') + '\
          </div>\
          ' + (badge ? '<span class="result-badge badge-' + badgeClass + '">' + escapeHtml(badge) + '</span>' : '') + '\
        </a>';
      });
      if (items.length > 6) {
        html += '<a href="/search?q=' + encodeURIComponent(q) + '" class="search-result-item" style="color:var(--color-text-muted);font-size:var(--text-xs);justify-content:center;">Ver todos (' + items.length + ')</a>';
      }
      sections.push(html);
    }

    addSection('Clientes', data.customers);
    addSection('Productos', data.products);
    addSection('Pedidos', data.pedidos);
    addSection('Recetas', data.recipes);

    if (sections.length === 0) {
      searchResults.innerHTML = '<div class="search-no-results">No se encontraron resultados para "<strong>' + escapeHtml(q) + '</strong>"</div>';
    } else {
      searchResults.innerHTML = sections.join('');
    }
  }

  function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ─── Notification Center ───────────────────────────────────────────────── */

  var notifBtn = document.getElementById('notif-btn');
  var notifCenter = document.getElementById('notif-center');
  var notifDropdown = document.getElementById('notif-dropdown');
  var notifList = document.getElementById('notif-list');
  var notifBadge = document.getElementById('notif-badge');
  var notifClear = document.getElementById('notif-clear');
  var notifications = [];

  function loadNotifications() {
    try {
      var stored = localStorage.getItem('saskia-notifications');
      if (stored) notifications = JSON.parse(stored);
    } catch (e) {}
    renderNotifications();
  }

  function saveNotifications() {
    try {
      localStorage.setItem('saskia-notifications', JSON.stringify(notifications));
    } catch (e) {}
  }

  function addNotification(text, kind, link) {
    notifications.unshift({
      id: Date.now(),
      text: text,
      kind: kind || 'info',
      link: link || null,
      time: new Date().toISOString()
    });
    if (notifications.length > 50) notifications = notifications.slice(0, 50);
    saveNotifications();
    renderNotifications();
  }

  function renderNotifications() {
    if (!notifList) return;
    if (notifications.length === 0) {
      notifList.innerHTML = '<p class="notif-empty">Sin notificaciones</p>';
      if (notifBadge) notifBadge.style.display = 'none';
      return;
    }
    var unread = notifications.filter(function (n) { return !n.read; }).length;
    if (notifBadge) {
      if (unread > 0) {
        notifBadge.textContent = unread > 9 ? '9+' : unread;
        notifBadge.style.display = 'flex';
      } else {
        notifBadge.style.display = 'none';
      }
    }
    var html = '';
    notifications.slice(0, 20).forEach(function (n) {
      var iconMap = { danger: '#icon-warn', warn: '#icon-warn', info: '#icon-info', success: '#icon-check' };
      var icon = iconMap[n.kind] || '#icon-info';
      var itemHtml = '\
        <div class="notif-item' + (n.read ? ' is-read' : '') + '"' + (n.link ? ' onclick="window.location=\'' + n.link + '\'"' : '') + '>\
          <svg class="icon ' + (n.kind === 'danger' || n.kind === 'warn' ? 'text-' + n.kind : '') + '" style="flex-shrink:0;" aria-hidden="true"><use href="' + icon + '"/></svg>\
          <div class="notif-text">\
            <div>' + escapeHtml(n.text) + '</div>\
            <div class="notif-time">' + relativeTime(n.time) + '</div>\
          </div>\
        </div>';
      html += itemHtml;
    });
    notifList.innerHTML = html;
  }

  if (notifBtn && notifCenter) {
    notifBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var isOpen = notifCenter.classList.contains('is-open');
      notifCenter.classList.toggle('is-open', !isOpen);
      notifBtn.setAttribute('aria-expanded', String(!isOpen));
      if (!isOpen) {
        // Mark all as read on open
        notifications.forEach(function (n) { n.read = true; });
        saveNotifications();
        renderNotifications();
      }
    });
  }

  document.addEventListener('click', function (e) {
    if (notifCenter && !notifCenter.contains(e.target)) {
      notifCenter.classList.remove('is-open');
      if (notifBtn) notifBtn.setAttribute('aria-expanded', 'false');
    }
  });

  if (notifClear) {
    notifClear.addEventListener('click', function (e) {
      e.stopPropagation();
      notifications = [];
      saveNotifications();
      renderNotifications();
    });
  }

  // Expose globally so router pages can add notifications
  window.SaskiaNotifications = {
    add: addNotification,
    load: loadNotifications
  };

  /* ─── Copy-to-Clipboard on data-id fields ──────────────────────────────── */

  function initCopyToClipboard() {
    $$('[data-copy]').forEach(function (el) {
      if (el._copyWired) return;
      el._copyWired = true;
      // Ensure we have a tooltip element
      var tip = document.createElement('span');
      tip.className = 'copy-tooltip';
      tip.textContent = 'Copiar';
      el.style.position = 'relative';
      el.appendChild(tip);
      el.setAttribute('tabindex', '0');
      el.setAttribute('role', 'button');
      el.setAttribute('aria-label', 'Copiar ' + (el.textContent.trim() || 'ID'));
      el.addEventListener('click', function () { copyText(el); });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); copyText(el); }
      });
    });
  }

  function copyText(el) {
    var text = el.getAttribute('data-copy') || el.textContent.trim();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        showCopyFeedback(el, '¡Copiado!');
      }).catch(function () {
        fallbackCopy(text, el);
      });
    } else {
      fallbackCopy(text, el);
    }
  }

  function fallbackCopy(text, el) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); showCopyFeedback(el, '¡Copiado!'); } catch (e) {}
    document.body.removeChild(ta);
  }

  function showCopyFeedback(el, msg) {
    var tip = el.querySelector('.copy-tooltip');
    if (tip) { tip.textContent = msg; setTimeout(function () { tip.textContent = 'Copiar'; }, 1500); }
  }

  /* ─── Loading Skeleton helpers ─────────────────────────────────────────── */

  // Replace skeleton placeholder with actual content
  window.SaskiaShowContent = function (selector, html) {
    var el = typeof selector === 'string' ? $(selector) : selector;
    if (el) el.innerHTML = html;
  };

  /* ─── Tag picker (pill toggles + custom add) ───────────────────────────── */

  // Look for any element matching the pattern: a .tag-pills div with sibling
  // .tag-custom-row + hidden input[name]. Used by producto_form, receta_form,
  // and anywhere the {% from _components/tags.html import tag_picker %} macro
  // is dropped in.
  function initTagPickers() {
    document.querySelectorAll('.tag-picker').forEach(function (picker) {
      var hidden = picker.querySelector('input[type="hidden"]');
      if (!hidden) return;
      var pills = picker.querySelectorAll('.tag-pill');
      var customInput = picker.querySelector('.tag-custom-input');
      var customAdd = picker.querySelector('.tag-custom-add');

      function currentTags() {
        return (hidden.value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      }
      function setTags(arr) {
        var unique = [];
        arr.forEach(function (t) {
          var k = (t || '').trim();
          if (k && unique.indexOf(k) === -1) unique.push(k);
        });
        hidden.value = unique.join(', ');
        pills.forEach(function (p) {
          var v = p.getAttribute('data-value');
          var active = unique.indexOf(v) !== -1;
          p.classList.toggle('is-active', active);
          p.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        renderCustomTags(unique);
      }
      function renderCustomTags(unique) {
        picker.querySelectorAll('.tag-pill.is-custom').forEach(function (n) { n.remove(); });
        var staticValues = Array.from(picker.querySelectorAll('.tag-pill:not(.is-custom)'))
          .map(function (p) { return p.getAttribute('data-value'); });
        var customTags = unique.filter(function (t) { return staticValues.indexOf(t) === -1; });
        var pillsContainer = picker.querySelector('.tag-pills');
        customTags.forEach(function (t) {
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'tag-pill is-active is-custom';
          btn.setAttribute('data-value', t);
          btn.setAttribute('aria-pressed', 'true');
          btn.textContent = t + ' ×';
          pillsContainer.appendChild(btn);
          btn.addEventListener('click', function () {
            var tags = currentTags().filter(function (x) { return x !== t; });
            setTags(tags);
          });
        });
      }

      pills.forEach(function (pill) {
        pill.addEventListener('click', function () {
          var v = pill.getAttribute('data-value');
          var tags = currentTags();
          var i = tags.indexOf(v);
          if (i === -1) tags.push(v); else tags.splice(i, 1);
          setTags(tags);
        });
      });

      if (customAdd && customInput) {
        customAdd.addEventListener('click', function () {
          var v = customInput.value.trim();
          if (!v) return;
          var tags = currentTags();
          if (tags.indexOf(v) === -1) tags.push(v);
          setTags(tags);
          customInput.value = '';
        });
        customInput.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') { e.preventDefault(); customAdd.click(); }
        });
      }
    });
  }

  /* ─── Init ──────────────────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    loadNotifications();
    initCopyToClipboard();
    initTagPickers();
    initConfirmForms();
  });

  // Re-init after dynamic content (e.g. from HTMX or fetch)
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(initCopyToClipboard, 100);
    setTimeout(initTagPickers, 100);
  setTimeout(initConfirmForms, 100);
  }

})();
