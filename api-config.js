/*
 * OnTime Moving — where the booking / chat / admin data lives.
 *
 * ┌───────────────────────────────────────────────────────────────────────┐
 * │  LIVE SITE (GitHub Pages) → Supabase                                 │
 * │  Paste your project's URL and public key below (Supabase dashboard → │
 * │  Project Settings → API). The public "anon"/"publishable" key is     │
 * │  meant to be in the browser — the SQL in supabase/schema.sql decides │
 * │  what it may do. NEVER paste the service_role / secret key here.     │
 * └───────────────────────────────────────────────────────────────────────┘
 */
const SUPABASE_URL = '';        // e.g. 'https://abcdefghijkl.supabase.co'
const SUPABASE_ANON_KEY = '';   // e.g. 'eyJhbGciOi…'  or  'sb_publishable_…'

/* Optional: a hosted copy of server.py, only needed for the AI assistant
   (Groq). Booking and live chat don't need it once Supabase is set. */
const PRODUCTION_API = '';      // e.g. 'https://ontime-api.onrender.com/api'

(function () {
  const host = location.hostname;
  const isLocal = location.protocol === 'file:' || host === 'localhost' || host === '127.0.0.1';
  const servedByFlask = isLocal && location.port === '5000';
  const useSupabase = !!(SUPABASE_URL && SUPABASE_ANON_KEY) && !servedByFlask;

  if (!useSupabase) {
    // Flask (server.py) mode — local development or a hosted Flask server
    if (servedByFlask) window.ONTIME_API_BASE = '/api';
    else if (isLocal) window.ONTIME_API_BASE = 'http://localhost:5000/api';
    else window.ONTIME_API_BASE = PRODUCTION_API || null;   // null = no backend: phone / email fallbacks
    return;
  }

  /* ===================================================================
   *  Supabase mode. Pages keep calling fetch(`${ONTIME_API_BASE}/…`);
   *  those calls are answered here by the SQL functions in Supabase,
   *  returning the same JSON shapes server.py does.
   * =================================================================== */
  const BASE = '/__ontime__/api';
  window.ONTIME_API_BASE = BASE;
  window.ONTIME_BACKEND = 'supabase';

  const SB = SUPABASE_URL.replace(/\/+$/, '');
  const SESSION_KEY = 'ontimeSupabaseSession';
  const nativeFetch = window.fetch.bind(window);

  // ---- staff session (Supabase Auth) ---------------------------------
  function loadSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY) || 'null');
    } catch { return null; }
  }
  function saveSession(s, remember) {
    try {
      localStorage.removeItem(SESSION_KEY); sessionStorage.removeItem(SESSION_KEY);
      if (s) (remember ? localStorage : sessionStorage).setItem(SESSION_KEY, JSON.stringify({ ...s, remember }));
    } catch {}
  }
  async function authCall(path, body, token) {
    const headers = { apikey: SUPABASE_ANON_KEY, 'Content-Type': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await nativeFetch(`${SB}/auth/v1/${path}`, { method: 'POST', headers, body: JSON.stringify(body || {}) });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }
  async function accessToken() {
    const s = loadSession();
    if (!s) return null;
    if (Date.now() / 1000 < s.expires_at - 60) return s.access_token;
    const r = await authCall('token?grant_type=refresh_token', { refresh_token: s.refresh_token });
    if (!r.ok) { saveSession(null); return null; }
    saveSession(toSession(r.data), s.remember);
    return r.data.access_token;
  }
  function toSession(d) {
    return { access_token: d.access_token, refresh_token: d.refresh_token,
             expires_at: d.expires_at || Math.floor(Date.now() / 1000) + (d.expires_in || 3600) };
  }

  // ---- call a SQL function ------------------------------------------
  async function rpc(fn, args, asStaff) {
    const headers = { apikey: SUPABASE_ANON_KEY, 'Content-Type': 'application/json' };
    if (asStaff) {
      const t = await accessToken();
      if (!t) return { ok: false, status: 401, error: 'not_signed_in' };
      headers.Authorization = `Bearer ${t}`;
    } else if (SUPABASE_ANON_KEY.startsWith('eyJ')) {
      headers.Authorization = `Bearer ${SUPABASE_ANON_KEY}`;   // legacy anon key
    }
    const res = await nativeFetch(`${SB}/rest/v1/rpc/${fn}`, { method: 'POST', headers, body: JSON.stringify(args || {}) });
    const data = await res.json().catch(() => null);
    if (res.ok) return { ok: true, status: res.status, data };
    const msg = (data && (data.message || data.error)) || 'error';
    const status = res.status === 401 || res.status === 403 || msg === 'not_staff' ? 401 : res.status;
    return { ok: false, status, error: msg };
  }

  // ---- friendly messages for SQL error codes -------------------------
  const MESSAGES = {
    slot_full: ['That arrival window was just booked. Please pick another time.', 409],
    date_closed: ['We are not booking moves on that date. Please choose another day.', 409],
    date_in_past: ['Move date must be in the future.', 400],
    date_too_far: ['Please choose a date within the next 12 months.', 400],
    invalid_date: ['Please choose a valid future date.', 400],
    invalid_email: ['Please enter a valid email address.', 400],
    missing_fields: ['Please fill in all required fields.', 400],
    unknown_slot: ['Please choose one of the listed arrival windows.', 400],
    rate_limited: ['Too many requests — please try again later or call (604) 505-0026.', 429],
    not_found: ['not_found', 404],
    closed: ['closed', 409],
    empty: ['Message is empty', 400],
    not_signed_in: ['Please sign in again.', 401],
    not_staff: ['This account is not set up as OnTime staff.', 401],
  };
  function fail(r) {
    const [msg, code] = MESSAGES[r.error] || [r.status === 401 ? 'Please sign in again.' : 'Something went wrong. Please call (604) 505-0026.', r.status || 500];
    return reply({ success: false, error: msg, code: r.error }, r.status === 401 ? 401 : code);
  }
  function reply(body, status = 200) {
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }

  // ---- route table: same URLs as server.py ---------------------------
  async function handle(path, init) {
    const url = new URL(path, location.origin);
    const p = url.pathname, q = url.searchParams;
    const method = ((init && init.method) || 'GET').toUpperCase();
    let body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch {}
    let m, r;

    if (p === '/health') return reply({ success: true, status: 'healthy', backend: 'supabase' });

    // public: availability + booking
    if (p === '/availability' && method === 'GET') {
      r = await rpc('get_availability', { p_date: q.get('date') || null });
      return r.ok ? reply({ success: true, ...r.data }) : fail(r);
    }
    if (p === '/booking' && method === 'POST') {
      r = await rpc('book_slot', {
        p_customer_name: body.customer_name, p_phone: body.phone, p_email: body.email,
        p_moving_from: body.moving_from, p_moving_to: body.moving_to, p_move_date: body.move_date || null,
        p_move_size: body.move_size || null, p_preferred_time: body.preferred_time || null,
        p_special_instructions: body.special_instructions || null, p_notes: body.notes || null });
      return r.ok ? reply({ success: true, booking_id: r.data, message: 'Booking created successfully' }, 201) : fail(r);
    }

    // AI assistant needs server.py (Groq); without it the widget uses its built-in answers
    if (p === '/chat') {
      if (PRODUCTION_API) return nativeFetch(PRODUCTION_API + '/chat', init);
      return reply({ success: false, error: 'AI assistant offline' }, 503);
    }

    // public: live chat (visitor)
    if (p === '/live-chat/status') {
      r = await rpc('staff_online', {});
      return r.ok ? reply({ success: true, staff_online: r.data }) : fail(r);
    }
    if (p === '/live-chat/start' && method === 'POST') {
      r = await rpc('live_chat_start', { p_name: body.name || '', p_contact: body.contact || '',
                                         p_page: body.page || '', p_transcript: body.transcript || [] });
      return r.ok ? reply({ success: true, ...r.data }, 201) : fail(r);
    }
    if ((m = p.match(/^\/live-chat\/(\d+)\/messages$/))) {
      if (method === 'POST') {
        r = await rpc('live_chat_send', { p_chat_id: +m[1], p_token: body.token || '', p_body: body.body || '' });
        return r.ok ? reply({ success: true, id: r.data }, 201) : reply({ success: false, error: r.error }, (MESSAGES[r.error] || [0, r.status])[1]);
      }
      r = await rpc('live_chat_poll', { p_chat_id: +m[1], p_token: q.get('token') || '', p_after: +(q.get('after') || 0) });
      return r.ok ? reply({ success: true, ...r.data }) : reply({ success: false, error: r.error }, (MESSAGES[r.error] || [0, r.status])[1]);
    }
    if ((m = p.match(/^\/live-chat\/(\d+)\/close$/))) {
      r = await rpc('live_chat_close', { p_chat_id: +m[1], p_token: body.token || '' });
      return r.ok ? reply({ success: true }) : fail(r);
    }

    // staff: sign in / out (Supabase Auth, email + password)
    if (p === '/auth/login' && method === 'POST') {
      const a = await authCall('token?grant_type=password', { email: (body.username || '').trim(), password: body.password || '' });
      if (!a.ok) return reply({ success: false, error: 'Invalid email or password' }, 401);
      saveSession(toSession(a.data), !!body.remember);
      r = await rpc('staff_me', {}, true);
      if (!r.ok) { saveSession(null); return fail(r.error === 'not_staff' ? r : { ...r, error: 'not_staff' }); }
      return reply({ success: true, token: a.data.access_token, user: r.data });
    }
    if (p === '/auth/verify') {
      r = await rpc('staff_me', {}, true);
      return r.ok ? reply({ success: true, user: r.data }) : fail(r);
    }
    if (p === '/auth/logout') {
      const t = loadSession();
      if (t) await authCall('logout', {}, t.access_token).catch(() => {});
      saveSession(null);
      return reply({ success: true, message: 'Logged out successfully' });
    }

    // staff: bookings
    if (p === '/bookings' && method === 'GET') {
      r = await rpc('staff_list_bookings', { p_search: q.get('search') || null, p_status: q.get('status') || null,
                                             p_date: q.get('date') || null }, true);
      return r.ok ? reply({ success: true, bookings: r.data, count: r.data.length }) : fail(r);
    }
    if ((m = p.match(/^\/booking\/(\d+)\/status$/))) {
      r = await rpc('staff_update_booking_status', { p_id: +m[1], p_status: body.status }, true);
      return r.ok ? reply({ success: r.data, message: r.data ? 'Status updated' : 'Booking not found' }, r.data ? 200 : 404) : fail(r);
    }
    if ((m = p.match(/^\/booking\/(\d+)$/))) {
      if (method === 'DELETE') {
        r = await rpc('staff_delete_booking', { p_id: +m[1] }, true);
        return r.ok ? reply({ success: r.data, message: 'Booking deleted' }, r.data ? 200 : 404) : fail(r);
      }
      r = await rpc('staff_get_booking', { p_id: +m[1] }, true);
      if (!r.ok) return fail(r);
      return r.data ? reply({ success: true, booking: r.data }) : reply({ success: false, error: 'Booking not found' }, 404);
    }

    // staff: live chat inbox
    if (p === '/admin/live-chats') {
      r = await rpc('staff_list_chats', { p_include_closed: q.get('all') === '1' }, true);
      return r.ok ? reply({ success: true, ...r.data }) : fail(r);
    }
    if ((m = p.match(/^\/admin\/live-chats\/(\d+)\/messages$/))) {
      if (method === 'POST') {
        r = await rpc('staff_chat_send', { p_chat_id: +m[1], p_body: body.body || '' }, true);
        return r.ok ? reply({ success: true, id: r.data }, 201) : (r.status === 401 ? fail(r) : reply({ success: false, error: 'Chat not found or closed' }, 409));
      }
      r = await rpc('staff_chat_messages', { p_chat_id: +m[1], p_after: +(q.get('after') || 0) }, true);
      return r.ok ? reply({ success: true, ...r.data }) : fail(r);
    }
    if ((m = p.match(/^\/admin\/live-chats\/(\d+)\/close$/))) {
      r = await rpc('staff_chat_close', { p_chat_id: +m[1] }, true);
      return r.ok ? reply({ success: r.data }) : fail(r);
    }

    return reply({ success: false, error: 'Endpoint not found' }, 404);
  }

  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.startsWith(BASE)) {
      return handle(url.slice(BASE.length), init).catch(err => {
        console.error('[OnTime] Supabase request failed:', err);
        return reply({ success: false, error: 'Service unavailable — please call (604) 505-0026.' }, 503);
      });
    }
    return nativeFetch(input, init);
  };
})();
