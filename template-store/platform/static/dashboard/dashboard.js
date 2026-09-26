// Forge Templates dashboard — single-file client app (no build step).
// Talks to the same-origin Flask API defined in ../../routes/*.py.

const state = { user: null, company: null, companies: [], leads: [], stats: null };
const $app = () => document.getElementById('app');
let dirtyForm = false;

window.addEventListener('beforeunload', (e) => {
  if (dirtyForm) { e.preventDefault(); e.returnValue = ''; }
});

// ---------------------------------------------------------------- API ----
async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin'
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) throw Object.assign(new Error((data && data.error) || 'Request failed'), { status: res.status, data });
  return data;
}

function toast(message, type = '') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast show ${type}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.className = 'toast'; }, 3200);
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function initials(name) {
  return (name || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
}
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) + ' · ' +
         d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}
function paginationBarHtml(meta) {
  if (meta.total_pages <= 1) return '';
  return `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:1rem 1.5rem; border-top:1px solid var(--border);">
      <span style="font-size:0.82rem; color:var(--ink-muted);">Page ${meta.page} of ${meta.total_pages} · ${meta.total} total</span>
      <div style="display:flex; gap:0.5rem;">
        <button class="btn btn-outline btn-sm" data-page-prev ${meta.page <= 1 ? 'disabled' : ''}>Previous</button>
        <button class="btn btn-outline btn-sm" data-page-next ${meta.page >= meta.total_pages ? 'disabled' : ''}>Next</button>
      </div>
    </div>`;
}
function wirePaginationBar(container, onPrev, onNext) {
  container.querySelector('[data-page-prev]')?.addEventListener('click', onPrev);
  container.querySelector('[data-page-next]')?.addEventListener('click', onNext);
}

// ------------------------------------------------------------ ROUTING ----
function navigate(path) {
  if (location.pathname !== path) history.pushState(null, '', path);
  render();
}
document.addEventListener('click', (e) => {
  const link = e.target.closest('[data-link]');
  if (!link) return;
  e.preventDefault();
  if (dirtyForm && !confirm('You have unsaved changes. Leave this page and discard them?')) return;
  dirtyForm = false;
  navigate(link.getAttribute('href'));
});
window.addEventListener('popstate', render);

async function render() {
  const path = location.pathname;
  if (path === '/login') return renderAuthView('login');
  if (path === '/register') return renderAuthView('register');

  try {
    const me = await api('/api/auth/me');
    state.user = me.user;
    state.company = me.company;
  } catch (_) {
    state.user = null;
    history.replaceState(null, '', '/login');
    return renderAuthView('login');
  }

  if (path === '/') history.replaceState(null, '', '/dashboard');

  if (state.user.role === 'platform_admin' && !state.companies.length) {
    state.companies = await api('/api/companies');
  }

  const view = path.startsWith('/dashboard/') ? path.slice('/dashboard/'.length) : 'overview';
  renderShell(view);
}

// -------------------------------------------------------- AUTH VIEWS ----
function renderAuthView(kind) {
  const isLogin = kind === 'login';
  $app().innerHTML = `
    <div class="auth-wrap">
      <div class="auth-card">
        <div class="auth-logo">Forge<span>Templates</span></div>
        <h1>${isLogin ? 'Welcome back' : 'Start your free trial'}</h1>
        <p class="sub">${isLogin ? 'Sign in to manage your site and leads.' : '14 days free, full access, no credit card required.'}</p>
        <div class="form-error" id="auth-error"></div>
        <form id="auth-form">
          ${isLogin ? '' : `
            <div class="field"><label for="company_name">Company name</label><input id="company_name" name="company_name" required></div>
            <div class="field"><label for="owner_name">Your name</label><input id="owner_name" name="owner_name" required></div>
          `}
          <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" required></div>
          <div class="field"><label for="password">Password</label><input id="password" name="password" type="password" minlength="8" required></div>
          <button class="btn btn-primary btn-block" type="submit">${isLogin ? 'Sign In' : 'Start Free Trial'}</button>
        </form>
        <p class="auth-switch">
          ${isLogin ? `New here? <a href="/register" data-link>Start your free trial</a>` : `Already have an account? <a href="/login" data-link>Sign in</a>`}
        </p>
      </div>
    </div>`;

  document.getElementById('auth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('auth-error');
    errEl.className = 'form-error';
    const payload = Object.fromEntries(new FormData(e.target).entries());
    const btn = e.target.querySelector('button');
    btn.disabled = true;
    try {
      await api(isLogin ? '/api/auth/login' : '/api/auth/register', { method: 'POST', body: payload });
      navigate('/dashboard');
    } catch (err) {
      errEl.textContent = err.message;
      errEl.className = 'form-error show';
    } finally {
      btn.disabled = false;
    }
  });
}

// ----------------------------------------------------------- SHELL ----
const NAV_ITEMS = [
  { key: 'overview', label: 'Overview', icon: '📊' },
  { key: 'leads', label: 'Leads', icon: '📥' },
  { key: 'customers', label: 'Customers', icon: '🧑‍🤝‍🧑' },
  { key: 'products', label: 'Products', icon: '📦' },
  { key: 'appointments', label: 'Appointments', icon: '📅' },
  { key: 'analytics', label: 'Analytics', icon: '📈' },
  { key: 'content', label: 'Content & Branding', icon: '🎨' },
  { key: 'team', label: 'Team', icon: '👥' },
  { key: 'settings', label: 'Settings', icon: '⚙️' }
];

function trialBannerHtml(c) {
  if (!c || c.plan !== 'trial') return '';
  if (c.is_trial_expired) {
    return `<div class="trial-banner expired">
      🔒 Your free trial has ended. Your data is safe and still viewable, but adding or editing is paused until you upgrade.
      <a href="/#pricing" target="_blank" rel="noopener" class="btn btn-primary btn-sm">Upgrade Now</a>
    </div>`;
  }
  const days = c.trial_days_remaining;
  const urgent = days <= 3;
  return `<div class="trial-banner ${urgent ? 'urgent' : ''}">
    ${urgent ? '⏰' : '🎉'} ${days} day${days === 1 ? '' : 's'} left in your free trial.
    <a href="/#pricing" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Upgrade Anytime</a>
  </div>`;
}

function renderShell(view) {
  const u = state.user, c = state.company;
  const isPlatformAdmin = u.role === 'platform_admin';

  $app().innerHTML = `
    <div class="app-shell">
      <aside class="sidebar" id="sidebar">
        <a href="/" class="sidebar-logo" style="text-decoration:none;">Forge<span>Templates</span></a>
        <nav class="sidebar-nav">
          ${NAV_ITEMS.map(i => `<a href="/dashboard/${i.key}" data-link class="${view === i.key ? 'active' : ''}"><span class="icon">${i.icon}</span>${i.label}</a>`).join('')}
        </nav>
        ${c ? `<a href="/site/${c.slug}" target="_blank" rel="noopener" class="btn btn-outline btn-sm" style="justify-content:center;">View Live Site ↗</a>` : ''}
        <div class="sidebar-foot">Forge Templates Platform</div>
      </aside>
      <div>
        <div class="topbar">
          <div style="display:flex; align-items:center; gap:0.75rem;">
            <button class="mobile-toggle" id="menu-toggle" aria-label="Toggle menu">☰</button>
            <h1>${c ? escapeHtml(c.name) : 'No company selected'}</h1>
          </div>
          <div class="topbar-right">
            ${isPlatformAdmin ? `
              <div class="company-switcher">
                <select id="company-select">
                  <option value="">Switch company…</option>
                  ${state.companies.map(co => `<option value="${co.id}" ${c && c.id === co.id ? 'selected' : ''}>${escapeHtml(co.name)}</option>`).join('')}
                </select>
              </div>` : ''}
            <div class="user-chip">
              <div class="avatar-dot">${initials(u.name)}</div>
              <div class="user-meta">
                <strong>${escapeHtml(u.name)}</strong>
                <span class="role-badge">${u.role.replace('_', ' ')}</span>
              </div>
            </div>
            <button class="btn btn-outline btn-sm" id="logout-btn">Log Out</button>
          </div>
        </div>
        ${trialBannerHtml(c)}
        <div class="view" id="view-content"><div class="skeleton" style="height:200px;"></div></div>
      </div>
    </div>`;

  document.getElementById('logout-btn').addEventListener('click', async () => {
    await api('/api/auth/logout', { method: 'POST' });
    state.user = null; state.company = null; state.companies = [];
    navigate('/login');
  });
  document.getElementById('menu-toggle')?.addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
  const companySelect = document.getElementById('company-select');
  if (companySelect) {
    companySelect.addEventListener('change', async () => {
      if (!companySelect.value) return;
      await api('/api/companies/switch', { method: 'POST', body: { company_id: Number(companySelect.value) } });
      const me = await api('/api/auth/me');
      state.company = me.company;
      renderShell(view);
      loadView(view);
    });
  }

  if (!c && !isPlatformAdmin) {
    document.getElementById('view-content').innerHTML = `<div class="empty-state"><div class="icon">🏢</div>No company on this account.</div>`;
    return;
  }
  if (!c && isPlatformAdmin) {
    document.getElementById('view-content').innerHTML = `<div class="empty-state"><div class="icon">🏢</div>Pick a company from the switcher above to manage its dashboard.</div>`;
    return;
  }
  loadView(view);
}

function loadView(view) {
  if (view === 'leads') return renderLeadsView();
  if (view === 'content') return renderContentView();
  if (view === 'team') return renderTeamView();
  if (view === 'customers') return renderResourceView('customers');
  if (view === 'products') return renderResourceView('products');
  if (view === 'appointments') return renderResourceView('appointments');
  if (view === 'analytics') return renderAnalyticsView();
  if (view === 'settings') return renderSettingsView();
  return renderOverviewView();
}

// --------------------------------------------------------- OVERVIEW ----
async function renderOverviewView() {
  const el = document.getElementById('view-content');
  const [stats, leadsPage] = await Promise.all([
    api('/api/leads/stats'),
    api('/api/leads?sort=-created_at&per_page=5')
  ]);
  const recent = leadsPage.items;
  const by = stats.by_status || {};

  el.innerHTML = `
    <div class="view-head"><div><h2>Overview</h2><p class="sub">A snapshot of ${escapeHtml(state.company.name)}'s inbound leads.</p></div></div>
    <div class="stat-grid">
      <div class="stat-card"><div class="label">Total Leads</div><div class="value">${stats.total}</div></div>
      <div class="stat-card"><div class="label">New This Week</div><div class="value">${stats.this_week}</div></div>
      <div class="stat-card"><div class="label">Won</div><div class="value success">${by.won || 0}</div></div>
      <div class="stat-card"><div class="label">Lost</div><div class="value danger">${by.lost || 0}</div></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Recent Leads</h3><a href="/dashboard/leads" data-link class="btn btn-outline btn-sm">View All</a></div>
      <div class="table-wrap">
        ${recent.length ? `
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Status</th><th>Received</th></tr></thead>
          <tbody>
            ${recent.map(l => `<tr data-open-lead="${l.id}"><td>${escapeHtml(l.name)}</td><td>${escapeHtml(l.email)}</td><td><span class="badge badge-${l.status}">${l.status}</span></td><td>${fmtDate(l.created_at)}</td></tr>`).join('')}
          </tbody>
        </table>` : `<div class="empty-state"><div class="icon">📭</div>No leads yet. Once your site is live, submissions show up here.</div>`}
      </div>
    </div>`;

  el.querySelectorAll('[data-open-lead]').forEach(row => {
    row.addEventListener('click', () => openLeadModal(Number(row.dataset.openLead)));
  });
}

// ------------------------------------------------------------ LEADS ----
let leadsQuery = { q: '', status: '', sort: '-created_at', page: 1 };

async function renderLeadsView() {
  const el = document.getElementById('view-content');
  el.innerHTML = `
    <div class="view-head">
      <div><h2>Leads</h2><p class="sub">Every inquiry submitted through your website's contact form.</p></div>
      <div style="display:flex; gap:0.6rem;">
        <button class="btn btn-outline" id="export-btn">Export CSV</button>
        <button class="btn btn-primary" id="add-lead-btn">+ Add Lead</button>
      </div>
    </div>
    <div class="toolbar">
      <input type="search" id="lead-search" placeholder="Search name, email or message…" value="${escapeHtml(leadsQuery.q)}">
      <select id="lead-status-filter">
        <option value="">All statuses</option>
        <option value="new">New</option>
        <option value="contacted">Contacted</option>
        <option value="won">Won</option>
        <option value="lost">Lost</option>
      </select>
      <select id="lead-sort">
        <option value="-created_at">Newest first</option>
        <option value="created_at">Oldest first</option>
        <option value="name">Name A–Z</option>
        <option value="-name">Name Z–A</option>
        <option value="status">Status</option>
      </select>
    </div>
    <div class="panel"><div class="table-wrap" id="leads-table"><div class="skeleton" style="height:240px; margin:1.5rem;"></div></div></div>`;

  document.getElementById('lead-status-filter').value = leadsQuery.status;
  document.getElementById('lead-sort').value = leadsQuery.sort;

  document.getElementById('export-btn').addEventListener('click', () => {
    const { page, ...filters } = leadsQuery;
    const params = new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v)));
    window.open('/api/leads/export?' + params.toString(), '_blank');
  });
  document.getElementById('add-lead-btn').addEventListener('click', () => openAddLeadModal());

  let debounce;
  document.getElementById('lead-search').addEventListener('input', (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { leadsQuery.q = e.target.value; leadsQuery.page = 1; fetchAndRenderLeads(); }, 300);
  });
  document.getElementById('lead-status-filter').addEventListener('change', (e) => {
    leadsQuery.status = e.target.value; leadsQuery.page = 1; fetchAndRenderLeads();
  });
  document.getElementById('lead-sort').addEventListener('change', (e) => {
    leadsQuery.sort = e.target.value; leadsQuery.page = 1; fetchAndRenderLeads();
  });

  fetchAndRenderLeads();
}

async function fetchAndRenderLeads() {
  const box = document.getElementById('leads-table');
  const params = new URLSearchParams(Object.fromEntries(Object.entries(leadsQuery).filter(([, v]) => v)));
  const result = await api('/api/leads?' + params.toString());
  state.leads = result.items;

  if (!result.items.length) {
    box.innerHTML = `<div class="empty-state"><div class="icon">📭</div>No leads match your filters.</div>`;
    return;
  }
  box.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Message</th><th>Status</th><th>Received</th></tr></thead>
      <tbody>
        ${result.items.map(l => `
          <tr data-open-lead="${l.id}">
            <td>${escapeHtml(l.name)}</td>
            <td>${escapeHtml(l.email)}</td>
            <td>${escapeHtml(l.phone) || '—'}</td>
            <td class="message-cell">${escapeHtml(l.message).slice(0, 80)}${l.message.length > 80 ? '…' : ''}</td>
            <td><span class="badge badge-${l.status}">${l.status}</span></td>
            <td>${fmtDate(l.created_at)}</td>
          </tr>`).join('')}
      </tbody>
    </table>
    ${paginationBarHtml(result)}`;
  box.querySelectorAll('[data-open-lead]').forEach(row => {
    row.addEventListener('click', () => openLeadModal(Number(row.dataset.openLead)));
  });
  wirePaginationBar(box, () => { leadsQuery.page--; fetchAndRenderLeads(); }, () => { leadsQuery.page++; fetchAndRenderLeads(); });
}

function openLeadModal(id) {
  const lead = state.leads.find(l => l.id === id) || {};
  const canDelete = state.user.role === 'owner' || state.user.role === 'platform_admin';
  showModal(`Lead #${id}`, `
    <div class="field"><label>Name</label><input id="m-name" value="${escapeHtml(lead.name)}"></div>
    <div class="field-row">
      <div class="field"><label>Email</label><input value="${escapeHtml(lead.email)}" disabled></div>
      <div class="field"><label>Phone</label><input id="m-phone" value="${escapeHtml(lead.phone)}"></div>
    </div>
    <div class="field"><label>Message</label><textarea rows="3" disabled>${escapeHtml(lead.message)}</textarea></div>
    <div class="field"><label>Status</label>
      <select id="m-status">
        ${['new', 'contacted', 'won', 'lost'].map(s => `<option value="${s}" ${lead.status === s ? 'selected' : ''}>${s}</option>`).join('')}
      </select>
    </div>
    <div class="field"><label>Internal notes</label><textarea id="m-notes" rows="3" placeholder="Notes only your team can see">${escapeHtml(lead.notes)}</textarea></div>
    <div class="modal-actions">
      ${canDelete ? `<button class="btn btn-danger" id="m-delete">Delete</button>` : ''}
      <span style="flex:1;"></span>
      <button class="btn btn-outline" id="m-cancel">Cancel</button>
      <button class="btn btn-primary" id="m-save">Save Changes</button>
    </div>`);

  document.getElementById('m-cancel').addEventListener('click', closeModal);
  document.getElementById('m-save').addEventListener('click', async () => {
    try {
      await api(`/api/leads/${id}`, { method: 'PATCH', body: {
        name: document.getElementById('m-name').value,
        phone: document.getElementById('m-phone').value,
        status: document.getElementById('m-status').value,
        notes: document.getElementById('m-notes').value
      }});
      closeModal();
      toast('Lead updated', 'success');
      fetchAndRenderLeads();
    } catch (err) { toast(err.message, 'error'); }
  });
  const delBtn = document.getElementById('m-delete');
  if (delBtn) delBtn.addEventListener('click', () => {
    confirmAction(`Delete this lead? This can't be undone.`, async () => {
      await api(`/api/leads/${id}`, { method: 'DELETE' });
      closeModal();
      toast('Lead deleted', 'success');
      fetchAndRenderLeads();
    });
  });
}

function openAddLeadModal() {
  showModal('Add Lead', `
    <div class="field"><label>Name</label><input id="a-name" required></div>
    <div class="field-row">
      <div class="field"><label>Email</label><input id="a-email" type="email" required></div>
      <div class="field"><label>Phone</label><input id="a-phone"></div>
    </div>
    <div class="field"><label>Message</label><textarea id="a-message" rows="3" required></textarea></div>
    <div class="modal-actions">
      <button class="btn btn-outline" id="m-cancel">Cancel</button>
      <button class="btn btn-primary" id="a-save">Add Lead</button>
    </div>`);
  document.getElementById('m-cancel').addEventListener('click', closeModal);
  document.getElementById('a-save').addEventListener('click', async () => {
    try {
      await api('/api/leads', { method: 'POST', body: {
        name: document.getElementById('a-name').value,
        email: document.getElementById('a-email').value,
        phone: document.getElementById('a-phone').value,
        message: document.getElementById('a-message').value
      }});
      closeModal();
      toast('Lead added', 'success');
      fetchAndRenderLeads();
    } catch (err) { toast(err.message, 'error'); }
  });
}

// -------------------------------------------------------- CONTENT ----
const THEMES = [
  { key: 'default', from: '#4f46e5', to: '#3730a3' },
  { key: 'emerald', from: '#059669', to: '#065f46' },
  { key: 'rose', from: '#e11d48', to: '#9f1239' },
  { key: 'slate', from: '#334155', to: '#0f172a' },
  { key: 'sunset', from: '#ea580c', to: '#9a3412' }
];

async function renderContentView() {
  dirtyForm = false;
  const el = document.getElementById('view-content');
  const full = await api('/api/company');
  const c = full.content || {};
  const hero = c.hero || {}, about = c.about || {}, cta = c.cta || {}, footer = c.footer || {};

  el.innerHTML = `
    <div class="view-head"><div><h2>Content &amp; Branding</h2><p class="sub">Edit your public site's copy, colors and theme — changes appear on your live site instantly.</p></div></div>
    <div class="editor-grid">
      <div>
        <div class="panel"><div class="panel-body">
          <h3 style="margin-bottom:1rem;">Branding</h3>
          <div class="field"><label>Business name</label><input id="c-brand-name" value="${escapeHtml(full.brand_name)}"></div>
          <div class="field"><label>Accent tag (shown after name, e.g. "& Co.")</label><input id="c-brand-accent" value="${escapeHtml(full.brand_accent)}"></div>
          <div class="field"><label>Theme</label>
            <div class="theme-swatch-row">
              ${THEMES.map(t => `<button type="button" class="theme-swatch-btn ${full.theme === t.key ? 'active' : ''}" data-theme="${t.key}" style="background:linear-gradient(135deg,${t.from},${t.to});" title="${t.key}"></button>`).join('')}
            </div>
          </div>
        </div></div>

        <div class="panel" style="margin-top:1.25rem;"><div class="panel-body">
          <h3 style="margin-bottom:1rem;">Homepage Copy</h3>
          <div class="field"><label>Hero badge</label><input id="c-hero-badge" value="${escapeHtml(hero.badge)}"></div>
          <div class="field"><label>Hero title</label><input id="c-hero-title" value="${escapeHtml(hero.title)}"></div>
          <div class="field"><label>Hero subtitle</label><textarea id="c-hero-subtitle" rows="2">${escapeHtml(hero.subtitle)}</textarea></div>
          <div class="field"><label>About text</label><textarea id="c-about-text" rows="2">${escapeHtml(about.text)}</textarea></div>
          <div class="field"><label>Call-to-action title</label><input id="c-cta-title" value="${escapeHtml(cta.title)}"></div>
          <div class="field"><label>Contact email</label><input id="c-cta-email" value="${escapeHtml(cta.email)}"></div>
          <div class="field"><label>Footer tagline</label><input id="c-footer-tagline" value="${escapeHtml(footer.tagline)}"></div>

          <details class="json-advanced">
            <summary>Advanced: edit full content JSON (features, testimonials, pricing…)</summary>
            <textarea id="c-raw-json">${escapeHtml(JSON.stringify(c, null, 2))}</textarea>
          </details>

          <div class="modal-actions" style="margin-top:1.5rem;">
            <button class="btn btn-primary btn-block" id="c-save">Save &amp; Publish</button>
          </div>
        </div></div>
      </div>

      <div class="preview-frame-wrap">
        <div class="preview-frame-bar"><span></span><span></span><span></span></div>
        <iframe id="preview-frame" src="/site/${full.slug}"></iframe>
      </div>
    </div>`;

  let selectedTheme = full.theme;
  el.querySelectorAll('.theme-swatch-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedTheme = btn.dataset.theme;
      dirtyForm = true;
      el.querySelectorAll('.theme-swatch-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
  el.querySelectorAll('input, textarea').forEach(field => {
    field.addEventListener('input', () => { dirtyForm = true; });
  });

  document.getElementById('c-save').addEventListener('click', async () => {
    let contentPatch;
    const rawEl = document.getElementById('c-raw-json');
    try {
      contentPatch = JSON.parse(rawEl.value);
    } catch (err) {
      toast('Advanced JSON is invalid — fix or collapse it before saving.', 'error');
      return;
    }
    contentPatch.hero = { ...(contentPatch.hero || {}), badge: document.getElementById('c-hero-badge').value, title: document.getElementById('c-hero-title').value, subtitle: document.getElementById('c-hero-subtitle').value };
    contentPatch.about = { ...(contentPatch.about || {}), text: document.getElementById('c-about-text').value };
    contentPatch.cta = { ...(contentPatch.cta || {}), title: document.getElementById('c-cta-title').value, email: document.getElementById('c-cta-email').value };
    contentPatch.footer = { ...(contentPatch.footer || {}), tagline: document.getElementById('c-footer-tagline').value };

    try {
      await api('/api/company', { method: 'PATCH', body: {
        brand_name: document.getElementById('c-brand-name').value,
        brand_accent: document.getElementById('c-brand-accent').value,
        theme: selectedTheme,
        content: contentPatch
      }});
      dirtyForm = false;
      toast('Site updated', 'success');
      document.getElementById('preview-frame').src = `/site/${full.slug}?t=${Date.now()}`;
    } catch (err) { toast(err.message, 'error'); }
  });
}

// ---------------------------------------------------------------- TEAM ----
async function renderTeamView() {
  const el = document.getElementById('view-content');
  const canManage = state.user.role === 'owner' || state.user.role === 'platform_admin';
  el.innerHTML = `
    <div class="view-head">
      <div><h2>Team</h2><p class="sub">Everyone with access to ${escapeHtml(state.company.name)}'s dashboard.</p></div>
      ${canManage ? `<button class="btn btn-primary" id="invite-btn">+ Invite Staff</button>` : ''}
    </div>
    <div class="panel"><div class="table-wrap" id="users-table"><div class="skeleton" style="height:180px; margin:1.5rem;"></div></div></div>`;

  if (canManage) document.getElementById('invite-btn').addEventListener('click', openInviteModal);
  await fetchAndRenderUsers();
}

async function fetchAndRenderUsers() {
  const users = await api('/api/users');
  const canManage = state.user.role === 'owner' || state.user.role === 'platform_admin';
  const box = document.getElementById('users-table');
  box.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last Login</th>${canManage ? '<th></th>' : ''}</tr></thead>
      <tbody>
        ${users.map(u => `
          <tr>
            <td>${escapeHtml(u.name)}</td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="role-badge">${u.role}</span></td>
            <td>${u.is_active ? 'Active' : 'Deactivated'}</td>
            <td>${fmtDate(u.last_login_at)}</td>
            ${canManage ? `<td style="display:flex; gap:0.4rem;">
              ${u.id !== state.user.id ? `
                <button class="btn btn-outline btn-sm" data-toggle-active="${u.id}" data-active="${u.is_active}">${u.is_active ? 'Deactivate' : 'Activate'}</button>
                ${u.role !== 'owner' ? `<button class="btn btn-danger btn-sm" data-remove-user="${u.id}">Remove</button>` : ''}
              ` : ''}
            </td>` : ''}
          </tr>`).join('')}
      </tbody>
    </table>`;

  box.querySelectorAll('[data-toggle-active]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const active = btn.dataset.active === '1' || btn.dataset.active === 'true';
      try {
        await api(`/api/users/${btn.dataset.toggleActive}`, { method: 'PATCH', body: { is_active: !active } });
        toast('Updated', 'success');
        fetchAndRenderUsers();
      } catch (err) { toast(err.message, 'error'); }
    });
  });
  box.querySelectorAll('[data-remove-user]').forEach(btn => {
    btn.addEventListener('click', () => {
      confirmAction('Remove this teammate? They will lose access immediately.', async () => {
        await api(`/api/users/${btn.dataset.removeUser}`, { method: 'DELETE' });
        toast('Removed', 'success');
        fetchAndRenderUsers();
      });
    });
  });
}

function openInviteModal() {
  showModal('Invite Staff', `
    <div class="field"><label>Name</label><input id="i-name" required></div>
    <div class="field"><label>Email</label><input id="i-email" type="email" required></div>
    <div class="field"><label>Role</label>
      <select id="i-role"><option value="staff">Staff</option><option value="owner">Owner</option></select>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" id="m-cancel">Cancel</button>
      <button class="btn btn-primary" id="i-save">Send Invite</button>
    </div>`);
  document.getElementById('m-cancel').addEventListener('click', closeModal);
  document.getElementById('i-save').addEventListener('click', async () => {
    try {
      const result = await api('/api/users', { method: 'POST', body: {
        name: document.getElementById('i-name').value,
        email: document.getElementById('i-email').value,
        role: document.getElementById('i-role').value
      }});
      showModal('Staff Added', `
        <p style="color:var(--ink-muted); margin-bottom:1rem; font-size:0.9rem;">Share this temporary password with ${escapeHtml(result.name)} — they should change it after logging in. (This starter kit doesn't send email yet.)</p>
        <div class="field"><input value="${escapeHtml(result.temp_password)}" readonly onclick="this.select()"></div>
        <div class="modal-actions"><button class="btn btn-primary" id="m-done">Done</button></div>`);
      document.getElementById('m-done').addEventListener('click', () => { closeModal(); fetchAndRenderUsers(); });
    } catch (err) { toast(err.message, 'error'); }
  });
}

// ------------------------------------------------------- GENERIC RESOURCE ----
// Customers, Products and Appointments share the same search/filter/sort/
// paginate/add/edit/delete shape, so they're driven off one config table
// instead of three near-identical copies of the Leads view.
const RESOURCE_CONFIGS = {
  customers: {
    label: 'Customers', icon: '🧑‍🤝‍🧑', apiBase: '/api/customers',
    subtitle: 'Everyone you do business with, in one place.',
    searchPlaceholder: 'Search name, email or phone…',
    statusOptions: ['active', 'inactive'],
    sortOptions: [{ v: '-created_at', l: 'Newest first' }, { v: 'created_at', l: 'Oldest first' }, { v: 'name', l: 'Name A–Z' }],
    columns: [
      { key: 'name', label: 'Name' }, { key: 'email', label: 'Email' }, { key: 'phone', label: 'Phone', fallback: '—' },
      { key: 'status', label: 'Status', badge: true }, { key: 'created_at', label: 'Added', fmt: fmtDate }
    ],
    fields: [
      { key: 'name', label: 'Name', type: 'text', required: true },
      { key: 'email', label: 'Email', type: 'email', required: true },
      { key: 'phone', label: 'Phone', type: 'text' },
      { key: 'address', label: 'Address', type: 'text' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
      { key: 'status', label: 'Status', type: 'select', options: ['active', 'inactive'] }
    ]
  },
  products: {
    label: 'Products', icon: '📦', apiBase: '/api/products',
    subtitle: 'Services, listings or catalog items you offer.',
    searchPlaceholder: 'Search name, description or SKU…',
    statusOptions: ['active', 'inactive', 'draft'],
    sortOptions: [{ v: '-created_at', l: 'Newest first' }, { v: 'name', l: 'Name A–Z' }, { v: 'price', l: 'Price' }],
    columns: [
      { key: 'name', label: 'Name' }, { key: 'sku', label: 'SKU', fallback: '—' },
      { key: 'price', label: 'Price', fmt: v => v != null ? '$' + Number(v).toFixed(2) : '—' },
      { key: 'category', label: 'Category', fallback: '—' }, { key: 'status', label: 'Status', badge: true }
    ],
    fields: [
      { key: 'name', label: 'Name', type: 'text', required: true },
      { key: 'sku', label: 'SKU', type: 'text' },
      { key: 'price', label: 'Price', type: 'number' },
      { key: 'category', label: 'Category', type: 'text' },
      { key: 'description', label: 'Description', type: 'textarea' },
      { key: 'status', label: 'Status', type: 'select', options: ['active', 'inactive', 'draft'] }
    ]
  },
  appointments: {
    label: 'Appointments', icon: '📅', apiBase: '/api/appointments',
    subtitle: 'Everything on the calendar.',
    searchPlaceholder: 'Search title…',
    statusOptions: ['scheduled', 'completed', 'cancelled', 'no_show'],
    sortOptions: [{ v: 'scheduled_at', l: 'Soonest first' }, { v: '-scheduled_at', l: 'Latest first' }],
    defaultSort: 'scheduled_at',
    columns: [
      { key: 'title', label: 'Title' }, { key: 'customer_name', label: 'Customer', fallback: '—' },
      { key: 'scheduled_at', label: 'When', fmt: fmtDate }, { key: 'duration_minutes', label: 'Duration', fmt: v => v + ' min' },
      { key: 'status', label: 'Status', badge: true }
    ],
    fields: [
      { key: 'title', label: 'Title', type: 'text', required: true },
      { key: 'scheduled_at', label: 'Date & time', type: 'datetime-local', required: true },
      { key: 'duration_minutes', label: 'Duration (minutes)', type: 'number' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
      { key: 'status', label: 'Status', type: 'select', options: ['scheduled', 'completed', 'cancelled', 'no_show'] }
    ]
  }
};
const resourceQuery = {};

function renderResourceView(key) {
  const cfg = RESOURCE_CONFIGS[key];
  const q = resourceQuery[key] || (resourceQuery[key] = { q: '', status: '', sort: cfg.defaultSort || cfg.sortOptions[0].v, page: 1 });
  const el = document.getElementById('view-content');

  el.innerHTML = `
    <div class="view-head">
      <div><h2>${cfg.icon} ${cfg.label}</h2><p class="sub">${cfg.subtitle}</p></div>
      <button class="btn btn-primary" id="res-add-btn">+ Add ${cfg.label.replace(/s$/, '')}</button>
    </div>
    <div class="toolbar">
      <input type="search" id="res-search" placeholder="${cfg.searchPlaceholder}" value="${escapeHtml(q.q)}">
      <select id="res-status-filter">
        <option value="">All statuses</option>
        ${cfg.statusOptions.map(s => `<option value="${s}">${s.replace('_', ' ')}</option>`).join('')}
      </select>
      <select id="res-sort">
        ${cfg.sortOptions.map(o => `<option value="${o.v}">${o.l}</option>`).join('')}
      </select>
    </div>
    <div class="panel"><div class="table-wrap" id="res-table"><div class="skeleton" style="height:240px; margin:1.5rem;"></div></div></div>`;

  document.getElementById('res-status-filter').value = q.status;
  document.getElementById('res-sort').value = q.sort;
  document.getElementById('res-add-btn').addEventListener('click', () => openResourceModal(key, null));

  let debounce;
  document.getElementById('res-search').addEventListener('input', (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { q.q = e.target.value; q.page = 1; fetchAndRenderResource(key); }, 300);
  });
  document.getElementById('res-status-filter').addEventListener('change', (e) => { q.status = e.target.value; q.page = 1; fetchAndRenderResource(key); });
  document.getElementById('res-sort').addEventListener('change', (e) => { q.sort = e.target.value; q.page = 1; fetchAndRenderResource(key); });

  fetchAndRenderResource(key);
}

async function fetchAndRenderResource(key) {
  const cfg = RESOURCE_CONFIGS[key];
  const q = resourceQuery[key];
  const box = document.getElementById('res-table');
  const params = new URLSearchParams(Object.fromEntries(Object.entries(q).filter(([, v]) => v)));
  const result = await api(`${cfg.apiBase}?${params.toString()}`);
  state[key] = result.items;

  if (!result.items.length) {
    box.innerHTML = `<div class="empty-state"><div class="icon">${cfg.icon}</div>No ${cfg.label.toLowerCase()} match your filters.</div>`;
    return;
  }
  box.innerHTML = `
    <table>
      <thead><tr>${cfg.columns.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>
      <tbody>
        ${result.items.map(item => `
          <tr data-open-item="${item.id}">
            ${cfg.columns.map(c => {
              const raw = item[c.key];
              const val = c.fmt ? c.fmt(raw) : (raw ?? c.fallback ?? '');
              return c.badge ? `<td><span class="badge badge-${raw}">${String(raw).replace('_', ' ')}</span></td>` : `<td>${escapeHtml(val)}</td>`;
            }).join('')}
          </tr>`).join('')}
      </tbody>
    </table>
    ${paginationBarHtml(result)}`;
  box.querySelectorAll('[data-open-item]').forEach(row => {
    row.addEventListener('click', () => openResourceModal(key, Number(row.dataset.openItem)));
  });
  wirePaginationBar(box, () => { q.page--; fetchAndRenderResource(key); }, () => { q.page++; fetchAndRenderResource(key); });
}

function fieldToInputHtml(field, value) {
  const id = `rf-${field.key}`;
  const v = value ?? '';
  if (field.type === 'textarea') return `<div class="field"><label>${field.label}</label><textarea id="${id}" rows="3">${escapeHtml(v)}</textarea></div>`;
  if (field.type === 'select') return `<div class="field"><label>${field.label}</label><select id="${id}">${field.options.map(o => `<option value="${o}" ${v === o ? 'selected' : ''}>${o.replace('_', ' ')}</option>`).join('')}</select></div>`;
  return `<div class="field"><label>${field.label}</label><input id="${id}" type="${field.type}" value="${escapeHtml(v)}" ${field.required ? 'required' : ''}></div>`;
}

function openResourceModal(key, id) {
  const cfg = RESOURCE_CONFIGS[key];
  const item = id ? (state[key] || []).find(i => i.id === id) : null;
  const canDelete = state.user.role === 'owner' || state.user.role === 'platform_admin';
  const values = item ? { ...item } : {};
  if (key === 'appointments' && values.scheduled_at) values.scheduled_at = values.scheduled_at.slice(0, 16);

  showModal(item ? `Edit ${cfg.label.replace(/s$/, '')}` : `Add ${cfg.label.replace(/s$/, '')}`, `
    ${cfg.fields.map(f => fieldToInputHtml(f, values[f.key])).join('')}
    <div class="modal-actions">
      ${item && canDelete ? `<button class="btn btn-danger" id="res-delete">Delete</button>` : ''}
      <span style="flex:1;"></span>
      <button class="btn btn-outline" id="m-cancel">Cancel</button>
      <button class="btn btn-primary" id="res-save">${item ? 'Save Changes' : 'Add ' + cfg.label.replace(/s$/, '')}</button>
    </div>`);

  document.getElementById('m-cancel').addEventListener('click', closeModal);
  document.getElementById('res-save').addEventListener('click', async () => {
    const payload = {};
    cfg.fields.forEach(f => {
      const raw = document.getElementById(`rf-${f.key}`).value;
      payload[f.key] = f.type === 'number' ? (raw === '' ? null : Number(raw)) : raw;
    });
    try {
      if (item) {
        await api(`${cfg.apiBase}/${item.id}`, { method: 'PATCH', body: payload });
        toast(`${cfg.label.replace(/s$/, '')} updated`, 'success');
      } else {
        await api(cfg.apiBase, { method: 'POST', body: payload });
        toast(`${cfg.label.replace(/s$/, '')} added`, 'success');
      }
      closeModal();
      fetchAndRenderResource(key);
    } catch (err) { toast(err.message, 'error'); }
  });
  const delBtn = document.getElementById('res-delete');
  if (delBtn) delBtn.addEventListener('click', () => {
    confirmAction(`Delete this ${cfg.label.toLowerCase().replace(/s$/, '')}? This can't be undone.`, async () => {
      await api(`${cfg.apiBase}/${item.id}`, { method: 'DELETE' });
      toast('Deleted', 'success');
      fetchAndRenderResource(key);
    });
  });
}

// ----------------------------------------------------------- ANALYTICS ----
async function renderAnalyticsView() {
  const el = document.getElementById('view-content');
  el.innerHTML = `<div class="view-head"><div><h2>📈 Analytics</h2><p class="sub">How ${escapeHtml(state.company.name)} is trending.</p></div></div><div class="skeleton" style="height:300px;"></div>`;
  const a = await api('/api/analytics');

  const maxTrend = Math.max(1, ...a.leads.trend_14d.map(d => d.count));
  el.innerHTML = `
    <div class="view-head"><div><h2>📈 Analytics</h2><p class="sub">How ${escapeHtml(state.company.name)} is trending.</p></div></div>
    <div class="stat-grid">
      <div class="stat-card"><div class="label">Total Leads</div><div class="value">${a.leads.total}</div></div>
      <div class="stat-card"><div class="label">Customers</div><div class="value">${a.customers.total}</div></div>
      <div class="stat-card"><div class="label">Products</div><div class="value">${a.products.total}</div></div>
      <div class="stat-card"><div class="label">Upcoming Appointments</div><div class="value">${a.appointments.upcoming}</div></div>
    </div>
    <div class="panel"><div class="panel-body">
      <h3 style="margin-bottom:1.25rem;">Leads, last 14 days</h3>
      <div style="display:flex; align-items:flex-end; gap:0.4rem; height:140px;">
        ${a.leads.trend_14d.map(d => `
          <div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:0.4rem;" title="${d.date}: ${d.count}">
            <div style="width:100%; background:var(--gradient); border-radius:4px 4px 0 0; height:${Math.max(4, (d.count / maxTrend) * 100)}px;"></div>
            <span style="font-size:0.65rem; color:var(--ink-muted);">${d.date.slice(5)}</span>
          </div>`).join('')}
      </div>
    </div></div>`;
}

// ------------------------------------------------------------ SETTINGS ----
async function renderSettingsView() {
  dirtyForm = false;
  const el = document.getElementById('view-content');
  const s = await api('/api/settings');
  el.innerHTML = `
    <div class="view-head"><div><h2>⚙️ Settings</h2><p class="sub">Company profile used across your dashboard and notifications.</p></div></div>
    <div class="panel" style="max-width:520px;"><div class="panel-body">
      <div class="field"><label>Timezone</label><input id="s-timezone" value="${escapeHtml(s.timezone)}" placeholder="e.g. America/Vancouver"></div>
      <div class="field"><label>Currency</label><input id="s-currency" value="${escapeHtml(s.currency)}" maxlength="10"></div>
      <div class="field"><label>Notification email</label><input id="s-notify" type="email" value="${escapeHtml(s.notification_email || '')}" placeholder="where lead alerts should go"></div>
      <button class="btn btn-primary" id="s-save">Save Settings</button>
    </div></div>`;

  el.querySelectorAll('input').forEach(f => f.addEventListener('input', () => { dirtyForm = true; }));
  document.getElementById('s-save').addEventListener('click', async () => {
    try {
      await api('/api/settings', { method: 'PATCH', body: {
        timezone: document.getElementById('s-timezone').value,
        currency: document.getElementById('s-currency').value,
        notification_email: document.getElementById('s-notify').value
      }});
      dirtyForm = false;
      toast('Settings saved', 'success');
    } catch (err) { toast(err.message, 'error'); }
  });
}

// ------------------------------------------------------------- MODALS ----
function showModal(title, bodyHtml) {
  let overlay = document.getElementById('modal-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'modal-overlay';
    overlay.className = 'overlay';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
  }
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-head"><h3>${title}</h3><button class="modal-close" id="modal-x" aria-label="Close">×</button></div>
      <div class="modal-body">${bodyHtml}</div>
    </div>`;
  overlay.classList.add('open');
  document.getElementById('modal-x').addEventListener('click', closeModal);
}
function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  if (overlay) overlay.classList.remove('open');
}
function confirmAction(message, onConfirm) {
  showModal('Please confirm', `
    <p style="font-size:0.92rem; color:var(--ink-muted);">${message}</p>
    <div class="modal-actions">
      <button class="btn btn-outline" id="m-cancel">Cancel</button>
      <button class="btn btn-danger" id="m-confirm">Confirm</button>
    </div>`);
  document.getElementById('m-cancel').addEventListener('click', closeModal);
  document.getElementById('m-confirm').addEventListener('click', async () => {
    closeModal();
    try { await onConfirm(); } catch (err) { toast(err.message, 'error'); }
  });
}

document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

// ------------------------------------------------------------- START ----
render();
