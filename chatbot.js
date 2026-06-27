(function () {
  const API_URL = 'http://localhost:5000/api/chat';
  const WELCOME = "Hi! I'm the OnTime Moving assistant. How can I help you today?";
  const QUICK_REPLIES = ['Get a free quote', 'Service areas', 'Storage options', 'Contact us'];

  let turns = [];
  let busy = false;
  let turnCounter = 0;
  let qrDiv = null;

  // ── Detect whether this page has the "Chat with us" launcher button ────────
  const oldLauncher   = document.getElementById('chatLauncher');
  const oldChatWidget = document.getElementById('chatWidget');
  const hasLauncher   = !!oldLauncher;

  if (oldChatWidget) { oldChatWidget.hidden = true; oldChatWidget.style.display = 'none'; }

  // ── Build the chat WINDOW ──────────────────────────────────────────────────
  const win = document.createElement('div');
  win.id = 'chatbot-window';
  win.innerHTML = `
    <div id="chatbot-header">
      <div class="avatar">🚚</div>
      <div class="info">
        <div class="name">OnTime Assistant</div>
        <div class="status">Online · typically replies instantly</div>
      </div>
      <button id="chatbot-close" aria-label="Close chat">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
      </button>
    </div>
    <div id="chatbot-messages"></div>
    <div id="chatbot-footer">
      <input id="chatbot-input" type="text" placeholder="Type a message…" autocomplete="off" maxlength="500">
      <button id="chatbot-send" aria-label="Send">
        <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
      </button>
    </div>`;

  let closeFn = null; // set after mode detection

  if (hasLauncher) {
    win.classList.add('launcher-mode');
    document.body.appendChild(win);

    const launcher = oldLauncher.cloneNode(true);
    oldLauncher.parentNode.replaceChild(launcher, oldLauncher);

    closeFn = () => closeChat(launcher);

    launcher.addEventListener('click', () => {
      win.classList.contains('open') ? closeChat(launcher) : openChat(launcher);
    });

  } else {
    const widget = document.createElement('div');
    widget.id = 'chatbot-widget';

    const toggle = document.createElement('button');
    toggle.id = 'chatbot-toggle';
    toggle.setAttribute('aria-label', 'Chat with us');
    toggle.innerHTML = `
      <svg class="chat-icon" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
      <svg class="close-icon" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;

    widget.appendChild(win);
    widget.appendChild(toggle);
    document.body.appendChild(widget);

    closeFn = () => closeBubble(widget);

    toggle.addEventListener('click', () => {
      widget.classList.contains('open') ? closeBubble(widget) : openBubble(widget);
    });
  }

  const msgs  = document.getElementById('chatbot-messages');
  const input = document.getElementById('chatbot-input');
  const send  = document.getElementById('chatbot-send');
  const closeBtn = document.getElementById('chatbot-close');

  closeBtn.addEventListener('click', () => { if (closeFn) closeFn(); });

  // ── Open / close (launcher mode) ──────────────────────────────────────────
  const ICON_CHAT  = `<svg class="chat-launcher-icon" viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg><span class="chat-launcher-label">Chat with us</span>`;
  const ICON_CLOSE = `<svg class="chat-launcher-icon" viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg><span class="chat-launcher-label">Close chat</span>`;

  function openChat(launcher) {
    win.classList.add('open');
    launcher.innerHTML = ICON_CLOSE;
    input.focus();
    if (msgs.children.length === 0) initWelcome();
  }
  function closeChat(launcher) {
    win.classList.remove('open');
    launcher.innerHTML = ICON_CHAT;
  }

  function openBubble(widget) {
    widget.classList.add('open');
    input.focus();
    if (msgs.children.length === 0) initWelcome();
  }
  function closeBubble(widget) { widget.classList.remove('open'); }

  // ── Welcome + persistent quick replies ────────────────────────────────────
  function initWelcome() {
    addMsg(WELCOME, 'bot', -1);
    showQuickReplies();
  }

  function showQuickReplies() {
    if (qrDiv) qrDiv.remove();
    qrDiv = document.createElement('div');
    qrDiv.className = 'quick-replies';
    QUICK_REPLIES.forEach(label => {
      const chip = document.createElement('button');
      chip.className = 'qr-chip';
      chip.textContent = label;
      chip.addEventListener('click', () => { hideQuickReplies(); sendMessage(label); });
      qrDiv.appendChild(chip);
    });
    msgs.appendChild(qrDiv);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function hideQuickReplies() {
    if (qrDiv) { qrDiv.remove(); qrDiv = null; }
  }

  // ── Message helpers ────────────────────────────────────────────────────────
  function createMsgWrap(text, role, turnIdx) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap';
    wrap.dataset.role = role;
    if (turnIdx >= 0) wrap.dataset.turn = turnIdx;

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role}`;
    msgDiv.textContent = text;
    wrap.appendChild(msgDiv);

    if (turnIdx >= 0) {
      const delBtn = document.createElement('button');
      delBtn.className = 'msg-delete';
      delBtn.setAttribute('aria-label', 'Delete message');
      delBtn.innerHTML = '&times;';
      delBtn.addEventListener('click', () => deleteTurn(turnIdx));
      wrap.appendChild(delBtn);
    }
    return wrap;
  }

  function addMsg(text, role, turnIdx) {
    const wrap = createMsgWrap(text, role, turnIdx);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
    return wrap;
  }

  function addBotMsg(text, turnIdx) {
    addMsg(text, 'bot', turnIdx);
  }

  function deleteTurn(turnIdx) {
    msgs.querySelectorAll(`[data-turn="${turnIdx}"]`).forEach(el => el.remove());
    turns = turns.filter(t => t.idx !== turnIdx);
    // Re-show quick replies when conversation is cleared
    if (turns.length === 0) showQuickReplies();
  }

  function getHistory() {
    const hist = [];
    turns.forEach(t => {
      hist.push({ role: 'user',      parts: [{ text: t.user }] });
      if (t.assistant) hist.push({ role: 'assistant', parts: [{ text: t.assistant }] });
    });
    return hist;
  }

  // ── Send message ───────────────────────────────────────────────────────────
  async function sendMessage(text) {
    if (!text || busy) return;
    const idx = turnCounter++;
    addMsg(text, 'user', idx);
    input.value = '';

    const typingWrap = addMsg('Typing…', 'bot typing', -1);
    busy = true; send.disabled = true; input.disabled = true;

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: getHistory() }),
      });
      const data = await res.json();
      typingWrap.remove();

      if (data.success) {
        turns.push({ idx, user: text, assistant: data.reply });
        addMsg(data.reply, 'bot', idx);
      } else {
        msgs.querySelectorAll(`[data-turn="${idx}"]`).forEach(el => el.remove());
        turnCounter--;
        addBotMsg(data.error || 'Something went wrong. Please call (604) 505-0026.', -1);
      }
    } catch {
      typingWrap.remove();
      msgs.querySelectorAll(`[data-turn="${idx}"]`).forEach(el => el.remove());
      turnCounter--;
      addBotMsg('Cannot reach the chat server. Please call us at (604) 505-0026.', -1);
    } finally {
      busy = false; send.disabled = false; input.disabled = false; input.focus();
    }
  }

  send.addEventListener('click', () => sendMessage(input.value.trim()));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input.value.trim()); }
  });
})();
