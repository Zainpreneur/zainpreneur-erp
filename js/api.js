// ============================================================================
// ZAINPRENEUR ERP — DATA ACCESS LAYER
// Calls the Python backend /api/* endpoints via HTMX.
// The Turso token never reaches the browser — it stays server-side in server.py.
// Extendable: add customers, products, invoices resources below.
// ============================================================================
window.ZAIN_API = (function (config, htmx) {
  'use strict';

  var base = config.apiBase || '';

  // Issue an HTMX AJAX request and resolve/reject via the htmx:afterRequest event.
  function ajax(method, url, body) {
    return new Promise(function (resolve, reject) {
      var done = false;
      var onResponse = function (evt) {
        if (done) return;
        done = true;
        document.body.removeEventListener('htmx:afterRequest', onResponse);
        var xhr = evt.detail.xhr;
        try {
          if (xhr.status >= 200 && xhr.status < 300) {
            var text = xhr.responseText || '{}';
            resolve(text ? JSON.parse(text) : {});
          } else {
            reject(new Error('HTTP ' + xhr.status + ' ' + (xhr.responseText || '')));
          }
        } catch (e) {
          reject(e);
        }
      };
      document.body.addEventListener('htmx:afterRequest', onResponse);

      var cfg = {
        headers: { 'Content-Type': 'application/json' },
      };
      if (body) {
        cfg.body = JSON.stringify(body);
      }

      htmx.ajax(method, base + url, cfg);

      setTimeout(function () {
        if (!done) {
          done = true;
          document.body.removeEventListener('htmx:afterRequest', onResponse);
          reject(new Error('Request timed out'));
        }
      }, 20000);
    });
  }

  return {
    init: function () {
      return ajax('GET', '/api/health').then(function (res) {
        console.log('[ZAIN_API] storage:', res.storage);
        return true;
      });
    },

    list: function () {
      return ajax('GET', '/api/leads').then(function (res) {
        return res.leads || [];
      });
    },

    get: function (id) {
      return ajax('GET', '/api/leads/' + id).then(function (res) {
        return res.lead || null;
      });
    },

    create: function (data) {
      return ajax('POST', '/api/leads', data).then(function (res) {
        return res.lead;
      });
    },

    update: function (id, data) {
      return ajax('PUT', '/api/leads/' + id, data).then(function (res) {
        return res.lead;
      });
    },

    delete: function (id) {
      return ajax('DELETE', '/api/leads/' + id).then(function (res) {
        return res.deleted;
      });
    },
  };
})(window.ZAIN_CONFIG, window.htmx);
