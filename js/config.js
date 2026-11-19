// ============================================================================
// ZAINPRENEUR ERP — CONFIGURATION (frontend)
// ============================================================================
// The Turso auth token now lives ONLY on the server (server.py, via env vars).
// This frontend calls your own /api/* endpoints — no secrets in the browser.
//
// Set TURSO_DB_URL and TURSO_AUTH_TOKEN on the server to use Turso;
// otherwise the server falls back to data/leads.json automatically.
// ============================================================================
window.ZAIN_CONFIG = {
  appName: 'Zainpreneur ERP',
  version: '1.0.0',

  // Backend API base (same-origin since the server serves this HTML too)
  apiBase: '',

  // Extendable lists (kept in sync with server)
  leadStatuses: ['New', 'Contacted', 'Qualified', 'Proposal', 'Negotiation', 'Closed-Won', 'Closed-Lost'],
  leadSources: ['Website', 'Referral', 'Cold Call', 'Email Campaign', 'Social Media', 'Event', 'Other'],

  // ERP modules (extendable — add customers, products, invoices, etc.)
  modules: [
    { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
    { key: 'leads', label: 'Leads', icon: 'bi-people-fill' },
    { key: 'customers', label: 'Customers', icon: 'bi-person-lines-fill' },
    { key: 'products', label: 'Products', icon: 'bi-box' },
    { key: 'settings', label: 'Settings', icon: 'bi-gear' },
  ],
};
