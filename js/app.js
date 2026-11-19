// ============================================================================
// ZAINPRENEUR ERP — APPLICATION LOGIC (Alpine.js)
// ============================================================================
(function () {
  'use strict';

  var appData = function () {
    return {
      // State
      currentSection: 'dashboard',
      leads: [],
      loading: false,
      storageMode: 'file',
      storageProvider: 'local file (data/leads.json)',
      statuses: (window.ZAIN_CONFIG && window.ZAIN_CONFIG.leadStatuses) || [],
      sources: (window.ZAIN_CONFIG && window.ZAIN_CONFIG.leadSources) || [],
      modules: (window.ZAIN_CONFIG && window.ZAIN_CONFIG.modules) || [],

      openLeadModal: false,
      editingId: null,
      form: {
        name: '', email: '', phone: '', company: '',
        status: 'New', source: 'Website', value: '',
        assigned_to: '', notes: '',
      },

      filterSearch: '',
      filterStatus: '',

      // Toast
      toastMsg: '',
      toastType: 'success',
      toastShow: false,

      // ---------- Lifecycle ----------
      init: async function () {
        try {
          if (window.ZAIN_API && typeof window.ZAIN_API.init === 'function') {
            var health = await window.ZAIN_API.init();
            this.storageMode = (health && health.storage) || 'file';
            this.storageProvider = this.storageMode === 'turso'
              ? 'Turso (libSQL)'
              : 'local file (data/leads.json)';
          }
        } catch (e) {
          console.error('[ERP] init storage error', e);
        }
        this.showToast('ERP ready — ' + this.storageProvider, 'success');
        try { await this.loadLeads(); } catch (e) { console.error('[ERP] loadLeads', e); }
      },

      // ---------- Navigation ----------
      setSection: function (key) {
        this.currentSection = key;
        var sidebar = document.getElementById('erpSidebar');
        if (sidebar) sidebar.classList.add('collapsed');
        var overlay = document.getElementById('erpOverlay');
        if (overlay) overlay.classList.remove('show');
      },

      isActive: function (key) {
        return this.currentSection === key;
      },

      // ---------- Leads ----------
      loadLeads: async function () {
        this.loading = true;
        try {
          this.leads = await window.ZAIN_API.list();
        } catch (e) {
          console.error('[ERP] loadLeads error', e);
          this.showToast('Failed to load leads: ' + (e && e.message ? e.message : e), 'error');
        } finally {
          this.loading = false;
        }
      },

      get filteredLeads() {
        try {
          var self = this;
          return this.leads.filter(function (l) {
            var term = (self.filterSearch || '').toLowerCase();
            var match =
              ((l && l.name) || '').toLowerCase().includes(term) ||
              ((l && l.company) || '').toLowerCase().includes(term) ||
              ((l && l.email) || '').toLowerCase().includes(term);
            var statusOk = !self.filterStatus || l.status === self.filterStatus;
            return match && statusOk;
          });
        } catch (e) {
          return [];
        }
      },

      stats: function () {
        try {
          var total = this.leads.length;
          var won = this.leads.filter(function (l) { return l && l.status === 'Closed-Won'; }).length;
          var value = this.leads.reduce(function (sum, l) { return sum + parseFloat((l && l.value) || 0); }, 0);
          var rate = total ? Math.round((won / total) * 100) : 0;
          return { total: total, won: won, rate: rate, value: value };
        } catch (e) {
          return { total: 0, won: 0, rate: 0, value: 0 };
        }
      },

      openCreate: function () {
        this.editingId = null;
        this.form = {
          name: '', email: '', phone: '', company: '',
          status: 'New', source: 'Website', value: '',
          assigned_to: '', notes: '',
        };
        this.openLeadModal = true;
      },

      openEdit: function (lead) {
        this.editingId = lead && lead.id;
        this.form = lead ? Object.assign({}, lead) : {
          name: '', email: '', phone: '', company: '',
          status: 'New', source: 'Website', value: '',
          assigned_to: '', notes: '',
        };
        this.openLeadModal = true;
      },

      saveLead: async function () {
        this.loading = true;
        try {
          var data = Object.assign({}, this.form, {
            value: this.form.value ? parseFloat(this.form.value) : null,
          });
          if (this.editingId) {
            await window.ZAIN_API.update(this.editingId, data);
            this.showToast('Lead updated', 'success');
          } else {
            await window.ZAIN_API.create(data);
            this.showToast('Lead created', 'success');
          }
          this.openLeadModal = false;
          await this.loadLeads();
        } catch (e) {
          console.error('[ERP] saveLead error', e);
          this.showToast('Save failed: ' + (e && e.message ? e.message : e), 'error');
        } finally {
          this.loading = false;
        }
      },

      deleteLead: async function (id) {
        if (!confirm('Delete this lead? This cannot be undone.')) return;
        try {
          await window.ZAIN_API.delete(id);
          await this.loadLeads();
          this.showToast('Lead deleted', 'success');
        } catch (e) {
          console.error('[ERP] deleteLead error', e);
          this.showToast('Delete failed: ' + (e && e.message ? e.message : e), 'error');
        }
      },

      // ---------- Toast ----------
      showToast: function (msg, type) {
        this.toastMsg = msg || '';
        this.toastType = type || 'success';
        this.toastShow = true;
        var self = this;
        setTimeout(function () { self.toastShow = false; }, 3500);
      },

      formatCurrency: function (v) {
        try { return parseFloat(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } catch (e) { return '0.00'; }
      },

      formatDate: function (iso) {
        if (!iso) return '—';
        try { return new Date(iso).toLocaleDateString(); } catch (e) { return '—'; }
      },

      statusBadge: function (status) {
        var map = {
          'New': 'bg-primary',
          'Contacted': 'bg-info',
          'Qualified': 'bg-warning',
          'Proposal': 'bg-indigo',
          'Negotiation': 'bg-orange',
          'Closed-Won': 'bg-success',
          'Closed-Lost': 'bg-danger',
        };
        return map[status] || 'bg-secondary';
      },
    };
  };

  // Register component and start Alpine defensively
  try {
    if (window.Alpine) {
      Alpine.data('erpApp', appData);
      Alpine.start();
    } else {
      document.addEventListener('alpine:init', function () {
        Alpine.data('erpApp', appData);
        Alpine.start();
      });
    }
  } catch (e) {
    console.error('[ERP] Alpine registration failed', e);
  }
})();
