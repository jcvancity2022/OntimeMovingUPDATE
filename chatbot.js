/*
 * OnTime Moving — chat widget
 *
 *  1. AI assistant (Groq via /api/chat) answers first.
 *  2. "Talk to a person" hands the conversation to a real team member, who
 *     replies from admin.html → Live Chat. The visitor's side polls for new
 *     messages, and the conversation survives moving between pages.
 *  3. If no API server is reachable (e.g. the static GitHub Pages site) the
 *     widget answers common questions itself and offers call / text / email.
 *
 * Needs api-config.js loaded first (falls back to localhost:5000).
 */
(function () {
  const API = window.ONTIME_API_BASE !== undefined ? window.ONTIME_API_BASE : 'http://localhost:5000/api';
  const PHONE = '(604) 505-0026';
  const PHONE_TEL = '+16045050026';
  const EMAIL = 'info@ontime-moving.com';
  const WELCOME = "Hi! I'm the OnTime Moving assistant. Ask me anything, or tap “Talk to a person” to chat with our team.";
  const QUICK_REPLIES = ['Get a free quote', 'Service areas', 'Storage options', 'Talk to a person'];
  const LIVE_KEY = 'ontimeLiveChat';
  const POLL_MS = 3000, POLL_HIDDEN_MS = 12000;

  // Answers used when the AI server can't be reached.
  const OFFLINE_FAQ = [
    { k: /quote|price|cost|estimate|how much/i,
      a: `Every move is priced on size and distance, so we give free, no-obligation estimates. Use the Book Now page or call ${PHONE} and we'll have a quote to you quickly.` },
    { k: /area|where|city|cities|serve|burnaby|surrey|vancouver|coquitlam|langley|richmond/i,
      a: 'We serve the whole Lower Mainland — Vancouver, Burnaby, Coquitlam, Port Coquitlam, Port Moody, Surrey, Langley, Richmond and more — plus long-distance moves across BC and to Alberta.' },
    { k: /storage|container|store/i,
      a: 'We offer secure, individual containerized storage at our Port Coquitlam facility — short or long term. Call us to check container availability.' },
    { k: /book|schedule|date|available|availability/i,
      a: 'You can request a date and crew arrival window on the Book Now page — we confirm every booking by phone within 24 hours.' },
    { k: /pack|box|supplies/i,
      a: 'Yes — full or partial packing, unpacking, and moving supplies are available. Mention what you need when you book.' },
    { k: /contact|phone|call|email|hours|address/i,
      a: `Call ${PHONE}, email ${EMAIL}, or visit us at 104-1525 Broadway St, Port Coquitlam.` },
  ];

  let turns = [], busy = false, turnCounter = 0, qrDiv = null;
  let live = null;            // { chatId, token, lastId, status }
  let pollTimer = null, seenIds = new Set(), unread = 0, isOpen = false;
  let staffName = null, primed = false;   // primed: first poll done (don't badge replayed history)

  // ── Build the window ─────────────────────────────────────────────────────
  const oldLauncher   = document.getElementById('chatLauncher');
  const oldChatWidget = document.getElementById('chatWidget');
  const hasLauncher   = !!oldLauncher;
  if (oldChatWidget) { oldChatWidget.hidden = true; oldChatWidget.style.display = 'none'; }

  const win = document.createElement('div');
  win.id = 'chatbot-window';
  win.setAttribute('role', 'dialog');
  win.setAttribute('aria-label', 'OnTime Moving chat');
  win.innerHTML = `
    <div id="chatbot-header">
      <div class="avatar" aria-hidden="true">🚚</div>
      <div class="info">
        <div class="name" id="chatbot-title">OnTime Assistant</div>
        <div class="status"><span class="status-dot" id="chatbot-dot"></span><span id="chatbot-status">Online · replies instantly</span></div>
      </div>
      <button id="chatbot-end" type="button" hidden>End chat</button>
      <button id="chatbot-close" type="button" aria-label="Close chat">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
      </button>
    </div>
    <div id="chatbot-messages" role="log" aria-live="polite"></div>
    <div id="chatbot-footer">
      <input id="chatbot-input" type="text" placeholder="Type a message…" autocomplete="off" maxlength="500" aria-label="Message">
      <button id="chatbot-send" type="button" aria-label="Send">
        <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
      </button>
    </div>`;

  let launcherEl = null, widgetEl = null;
  const badge = document.createElement('span');
  badge.className = 'chatbot-badge';
  badge.hidden = true;

  if (hasLauncher) {
    win.classList.add('launcher-mode');
    document.body.appendChild(win);
    launcherEl = oldLauncher.cloneNode(true);
    oldLauncher.parentNode.replaceChild(launcherEl, oldLauncher);
    launcherEl.addEventListener('click', () => (isOpen ? close() : open()));
  } else {
    widgetEl = document.createElement('div');
    widgetEl.id = 'chatbot-widget';
    const toggle = document.createElement('button');
    toggle.id = 'chatbot-toggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Chat with us');
    toggle.innerHTML = `
      <svg class="chat-icon" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
      <svg class="close-icon" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
    toggle.appendChild(badge);
    widgetEl.append(win, toggle);
    document.body.appendChild(widgetEl);
    toggle.addEventListener('click', () => (isOpen ? close() : open()));
  }

  const msgs   = document.getElementById('chatbot-messages');
  const input  = document.getElementById('chatbot-input');
  const send   = document.getElementById('chatbot-send');
  const endBtn = document.getElementById('chatbot-end');
  const titleEl  = document.getElementById('chatbot-title');
  const statusEl = document.getElementById('chatbot-status');
  const dotEl    = document.getElementById('chatbot-dot');
  document.getElementById('chatbot-close').addEventListener('click', close);
  endBtn.addEventListener('click', endLiveChat);

  // ── Open / close ─────────────────────────────────────────────────────────
  const ICON_CHAT  = `<svg class="chat-launcher-icon" viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg><span class="chat-launcher-label">Chat with us</span>`;
  const ICON_CLOSE = `<svg class="chat-launcher-icon" viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg><span class="chat-launcher-label">Close chat</span>`;

  function open() {
    isOpen = true;
    if (launcherEl) { win.classList.add('open'); launcherEl.innerHTML = ICON_CLOSE; launcherEl.setAttribute('aria-expanded', 'true'); }
    else widgetEl.classList.add('open');
    setUnread(0);
    if (msgs.children.length === 0) initWelcome();
    input.focus();
  }
  function close() {
    isOpen = false;
    if (launcherEl) {
      win.classList.remove('open'); launcherEl.innerHTML = ICON_CHAT;
      launcherEl.appendChild(badge); launcherEl.setAttribute('aria-expanded', 'false');
    } else widgetEl.classList.remove('open');
  }
  if (launcherEl) launcherEl.appendChild(badge);

  function setUnread(n) {
    unread = n;
    badge.textContent = n > 9 ? '9+' : String(n);
    badge.hidden = n === 0;
  }

  function setHeader(title, status, state) {
    titleEl.textContent = title;
    statusEl.textContent = status;
    dotEl.className = 'status-dot ' + (state || '');
  }

  // ── Messages ─────────────────────────────────────────────────────────────
  function initWelcome() {
    addMsg(WELCOME, 'bot', -1);
    showQuickReplies();
  }

  function showQuickReplies() {
    hideQuickReplies();
    if (live) return;
    qrDiv = document.createElement('div');
    qrDiv.className = 'quick-replies';
    QUICK_REPLIES.forEach(label => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'qr-chip' + (label === 'Talk to a person' ? ' qr-human' : '');
      chip.textContent = label;
      chip.addEventListener('click', () => {
        hideQuickReplies();
        label === 'Talk to a person' ? requestHuman() : sendMessage(label);
      });
      qrDiv.appendChild(chip);
    });
    msgs.appendChild(qrDiv);
    scroll();
  }
  function hideQuickReplies() { if (qrDiv) { qrDiv.remove(); qrDiv = null; } }
  function scroll() { msgs.scrollTop = msgs.scrollHeight; }

  function addMsg(text, role, turnIdx, opts = {}) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap';
    wrap.dataset.role = role.split(' ')[0];
    if (turnIdx >= 0) wrap.dataset.turn = turnIdx;

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role}`;
    if (opts.author) {
      const a = document.createElement('div');
      a.className = 'msg-author';
      a.textContent = opts.author;
      msgDiv.appendChild(a);
    }
    msgDiv.appendChild(document.createTextNode(text));
    wrap.appendChild(msgDiv);

    if (turnIdx >= 0 && !live) {
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.className = 'msg-delete';
      delBtn.setAttribute('aria-label', 'Delete message');
      delBtn.innerHTML = '&times;';
      delBtn.addEventListener('click', () => deleteTurn(turnIdx));
      wrap.appendChild(delBtn);
    }
    msgs.appendChild(wrap);
    scroll();
    return wrap;
  }

  function addSystem(text) {
    const div = document.createElement('div');
    div.className = 'chat-system';
    div.textContent = text;
    msgs.appendChild(div);
    scroll();
  }

  function addContactCard(lead) {
    const card = document.createElement('div');
    card.className = 'chat-contact-card';
    const p = document.createElement('p');
    p.textContent = lead;
    card.appendChild(p);
    const row = document.createElement('div');
    row.className = 'chat-contact-actions';
    [['📞 Call', `tel:${PHONE_TEL}`], ['💬 Text', `sms:${PHONE_TEL}`], ['✉️ Email', `mailto:${EMAIL}?subject=Moving%20question`]]
      .forEach(([label, href]) => {
        const a = document.createElement('a');
        a.href = href; a.textContent = label;
        row.appendChild(a);
      });
    card.appendChild(row);
    msgs.appendChild(card);
    scroll();
  }

  function deleteTurn(turnIdx) {
    msgs.querySelectorAll(`[data-turn="${turnIdx}"]`).forEach(el => el.remove());
    turns = turns.filter(t => t.idx !== turnIdx);
    if (turns.length === 0) showQuickReplies();
  }

  function getHistory() {
    const hist = [];
    turns.forEach(t => {
      hist.push({ role: 'user', parts: [{ text: t.user }] });
      if (t.assistant) hist.push({ role: 'assistant', parts: [{ text: t.assistant }] });
    });
    return hist;
  }

  function setBusy(b) { busy = b; send.disabled = b; input.disabled = b; if (!b) input.focus(); }

  // ── AI assistant ─────────────────────────────────────────────────────────
  function offlineAnswer(text) {
    const hit = OFFLINE_FAQ.find(f => f.k.test(text));
    return hit ? hit.a : null;
  }

  async function sendMessage(text) {
    if (!text || busy) return;
    if (live) return sendLive(text);
    if (/\b(human|person|agent|representative|real person|someone)\b/i.test(text) && /talk|speak|chat|connect/i.test(text)) {
      addMsg(text, 'user', turnCounter++);
      input.value = '';
      return requestHuman();
    }

    const idx = turnCounter++;
    addMsg(text, 'user', idx);
    input.value = '';

    if (!API) {   // static site: answer locally
      const a = offlineAnswer(text);
      turns.push({ idx, user: text, assistant: a || '' });
      if (a) addMsg(a, 'bot', idx);
      else addContactCard("I can't answer that one here — our team can help right away:");
      showQuickReplies();
      return;
    }

    const typing = addMsg('Typing…', 'bot typing', -1);
    setBusy(true);
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: getHistory() }),
      });
      const data = await res.json();
      typing.remove();
      if (data.success) {
        turns.push({ idx, user: text, assistant: data.reply });
        addMsg(data.reply, 'bot', idx);
      } else {
        throw new Error(data.error);
      }
    } catch {
      typing.remove();
      const a = offlineAnswer(text);
      turns.push({ idx, user: text, assistant: a || '' });
      if (a) addMsg(a, 'bot', idx);
      else addContactCard('Our assistant is taking a break — you can reach the team directly:');
    } finally {
      setBusy(false);
      showQuickReplies();   // keep "Talk to a person" one tap away
    }
  }

  // ── Live chat with a person ──────────────────────────────────────────────
  function requestHuman() {
    hideQuickReplies();
    if (!API) {
      addContactCard(`Our team is happy to help! Live chat isn't available on this page, but you can reach a real person here:`);
      return;
    }
    addMsg("Sure — let's connect you with someone from our team. What's your name and the best phone or email to reach you if we get disconnected?", 'bot', -1);

    const form = document.createElement('form');
    form.className = 'chat-handoff-form';
    form.innerHTML = `
      <label>Your name<input name="name" required maxlength="80" autocomplete="name"></label>
      <label>Phone or email<input name="contact" required maxlength="120" autocomplete="email"></label>
      <div class="handoff-actions">
        <button type="submit">Connect me</button>
        <button type="button" class="handoff-cancel">Cancel</button>
      </div>`;
    msgs.appendChild(form);
    scroll();
    form.querySelector('input').focus();
    form.querySelector('.handoff-cancel').addEventListener('click', () => { form.remove(); showQuickReplies(); });
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const fd = new FormData(form);
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true; btn.textContent = 'Connecting…';
      try {
        const transcript = [];
        turns.forEach(t => {
          transcript.push({ role: 'user', text: t.user });
          if (t.assistant) transcript.push({ role: 'bot', text: t.assistant });
        });
        const res = await fetch(`${API}/live-chat/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: fd.get('name'), contact: fd.get('contact'), page: location.pathname, transcript }),
        });
        const data = await res.json();
        if (!data.success) throw new Error();
        form.remove();
        startLive({ chatId: data.chat_id, token: data.token, lastId: 0, status: 'waiting' }, false);
        addSystem(data.staff_online
          ? 'You\'re in the queue — a team member will join in a moment.'
          : `Our team isn't online right now. Leave your question here and we'll get back to you by phone or email — or call ${PHONE}.`);
      } catch {
        form.remove();
        addContactCard("We couldn't start a live chat just now. Reach the team directly:");
      }
    });
  }

  function saveLive() {
    try { live ? sessionStorage.setItem(LIVE_KEY, JSON.stringify(live)) : sessionStorage.removeItem(LIVE_KEY); } catch {}
  }

  function startLive(session, resuming) {
    live = session;
    saveLive();
    hideQuickReplies();
    msgs.querySelectorAll('.msg-delete').forEach(b => b.remove());
    endBtn.hidden = false;
    input.placeholder = 'Message our team…';
    updateLiveHeader(true);
    primed = false;
    if (resuming) { msgs.innerHTML = ''; seenIds.clear(); live.lastId = 0; }
    poll();
  }

  function updateLiveHeader(online) {
    if (!live) return;
    if (live.status === 'closed') setHeader('Chat ended', 'Thanks for chatting with OnTime', 'off');
    else if (live.status === 'active') setHeader(staffName || 'OnTime team', 'Live · a real person is replying', 'live');
    else setHeader('Connecting you…', online ? 'Waiting for a team member' : 'Team offline · we\'ll follow up', online ? 'wait' : 'off');
  }

  function renderLiveMessage(m) {
    if (seenIds.has(m.id)) return;
    seenIds.add(m.id);
    if (m.sender === 'visitor') addMsg(m.body, 'user', -1);
    else if (m.sender === 'bot') addMsg(m.body, 'bot', -1);
    else if (m.sender === 'system') addSystem(m.body);
    else {
      staffName = m.sender_name || staffName;
      addMsg(m.body, 'bot staff', -1, { author: m.sender_name || 'OnTime team' });
      if (!isOpen && primed) setUnread(unread + 1);
    }
  }

  async function poll() {
    clearTimeout(pollTimer);
    if (!live) return;
    try {
      const res = await fetch(`${API}/live-chat/${live.chatId}/messages?token=${encodeURIComponent(live.token)}&after=${live.lastId}`);
      if (res.status === 404) { endLocal(); return; }
      const data = await res.json();
      if (data.success) {
        data.messages.forEach(m => { renderLiveMessage(m); live.lastId = Math.max(live.lastId, m.id); });
        live.status = data.status;
        if (data.assigned_to) staffName = data.assigned_to;
        saveLive();
        primed = true;
        updateLiveHeader(data.staff_online);
        if (data.status === 'closed') { finishLive(); return; }
      }
    } catch { /* network blip — keep polling */ }
    pollTimer = setTimeout(poll, document.hidden ? POLL_HIDDEN_MS : POLL_MS);
  }

  async function sendLive(text) {
    input.value = '';
    const bubble = addMsg(text, 'user pending', -1);
    try {
      const res = await fetch(`${API}/live-chat/${live.chatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: live.token, body: text }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      seenIds.add(data.id);
      bubble.querySelector('.chat-msg').classList.remove('pending');
      poll();
    } catch (e) {
      bubble.querySelector('.chat-msg').classList.add('failed');
      addSystem(e.message === 'rate_limited' ? 'You\'re sending messages quickly — please wait a moment.'
              : e.message === 'closed' ? 'This chat has ended.' : 'Message not sent — check your connection.');
    }
  }

  async function endLiveChat() {
    if (!live || live.status === 'closed') return endLocal();
    try {
      await fetch(`${API}/live-chat/${live.chatId}/close`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: live.token }),
      });
    } catch {}
    poll();
  }

  function finishLive() {
    clearTimeout(pollTimer);
    endBtn.textContent = 'Start over';
    addContactCard('Need anything else? We\'re always reachable here:');
  }

  function endLocal() {
    clearTimeout(pollTimer);
    live = null; staffName = null; saveLive();
    endBtn.hidden = true; endBtn.textContent = 'End chat';
    input.placeholder = 'Type a message…';
    setHeader('OnTime Assistant', API ? 'Online · replies instantly' : 'Quick answers · call for more', API ? 'live' : '');
    msgs.innerHTML = ''; turns = []; seenIds.clear();
    initWelcome();
  }

  document.addEventListener('visibilitychange', () => { if (live && !document.hidden) poll(); });

  // ── Wire up input ────────────────────────────────────────────────────────
  send.addEventListener('click', () => sendMessage(input.value.trim()));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input.value.trim()); }
  });

  // Initial header + resume a live chat started on another page
  setHeader('OnTime Assistant', API ? 'Online · replies instantly' : 'Quick answers · call for more', API ? 'live' : '');
  try {
    const saved = JSON.parse(sessionStorage.getItem(LIVE_KEY) || 'null');
    if (saved && saved.chatId && saved.token && API) startLive(saved, true);
  } catch {}
})();
