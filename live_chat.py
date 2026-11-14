"""
OnTime Moving - Live chat with a real person (SQLite + polling)

The AI assistant answers first. When a visitor taps "Talk to a person" the
widget opens a live chat here; staff see it in admin.html and reply in real
time. Both sides poll every few seconds, so it works on any plain Flask host
with no WebSocket server to run.

Tables
  live_chats           one row per conversation (visitor token, status)
  live_chat_messages   every message, from the visitor, staff or the system
  staff_presence       when each staff member last had the inbox open
                       (used to tell visitors whether someone is online)
"""

import secrets
import sqlite3
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

STAFF_ONLINE_SECONDS = 90      # inbox polled within this window = "online"
MAX_BODY = 1000
MAX_MSGS_PER_5_MIN = 30        # basic flood protection per conversation


class LiveChatStore:
    def __init__(self, db_path: str = 'ontime_moving.db'):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def initialize(self) -> None:
        conn = self._connect()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS live_chats (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_token  TEXT NOT NULL UNIQUE,
                visitor_name   TEXT,
                visitor_contact TEXT,
                page_url       TEXT,
                status         TEXT NOT NULL DEFAULT 'waiting'
                               CHECK (status IN ('waiting', 'active', 'closed')),
                assigned_to    TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS live_chat_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL REFERENCES live_chats(id) ON DELETE CASCADE,
                sender      TEXT NOT NULL CHECK (sender IN ('visitor', 'staff', 'system', 'bot')),
                sender_name TEXT,
                body        TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_live_msgs_chat ON live_chat_messages (chat_id, id);
            CREATE INDEX IF NOT EXISTS idx_live_chats_status ON live_chats (status, updated_at);

            CREATE TABLE IF NOT EXISTS staff_presence (
                username   TEXT PRIMARY KEY,
                last_seen  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        finally:
            conn.close()

    # --------------------------------------------------------------- presence
    def touch_staff(self, username: str) -> None:
        conn = self._connect()
        try:
            conn.execute("""INSERT INTO staff_presence (username, last_seen)
                            VALUES (?, CURRENT_TIMESTAMP)
                            ON CONFLICT(username) DO UPDATE SET last_seen = CURRENT_TIMESTAMP""",
                         (username,))
        finally:
            conn.close()

    def staff_online(self) -> bool:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT 1 FROM staff_presence WHERE last_seen >= datetime('now', ?)",
                (f'-{STAFF_ONLINE_SECONDS} seconds',)).fetchone() is not None
        finally:
            conn.close()

    # ---------------------------------------------------------------- visitor
    def start_chat(self, name: str, contact: str, page_url: str,
                   transcript: List[Dict[str, str]]) -> Dict[str, Any]:
        token = secrets.token_urlsafe(24)
        conn = self._connect()
        try:
            conn.execute('BEGIN')
            chat_id = conn.execute(
                """INSERT INTO live_chats (visitor_token, visitor_name, visitor_contact, page_url)
                   VALUES (?, ?, ?, ?)""",
                (token, name[:80] or 'Website visitor', contact[:120], page_url[:300]),
            ).lastrowid
            # Carry the AI conversation over so staff have context.
            for t in transcript[-12:]:
                role = 'visitor' if t.get('role') == 'user' else 'bot'
                text = str(t.get('text', ''))[:MAX_BODY]
                if text:
                    conn.execute('INSERT INTO live_chat_messages (chat_id, sender, body) VALUES (?, ?, ?)',
                                 (chat_id, role, text))
            conn.execute("INSERT INTO live_chat_messages (chat_id, sender, body) VALUES (?, 'system', ?)",
                         (chat_id, 'Visitor asked to talk to a person.'))
            conn.execute('COMMIT')
        except Exception:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()
        return {'chat_id': chat_id, 'token': token}

    def _chat_for_token(self, conn, chat_id: int, token: str) -> Optional[sqlite3.Row]:
        row = conn.execute('SELECT * FROM live_chats WHERE id = ?', (chat_id,)).fetchone()
        if row and secrets.compare_digest(row['visitor_token'], token or ''):
            return row
        return None

    def visitor_send(self, chat_id: int, token: str, body: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            chat = self._chat_for_token(conn, chat_id, token)
            if not chat:
                return {'error': 'not_found'}
            if chat['status'] == 'closed':
                return {'error': 'closed'}
            recent = conn.execute(
                """SELECT COUNT(*) FROM live_chat_messages
                   WHERE chat_id = ? AND sender = 'visitor'
                     AND created_at >= datetime('now', '-5 minutes')""", (chat_id,)).fetchone()[0]
            if recent >= MAX_MSGS_PER_5_MIN:
                return {'error': 'rate_limited'}
            msg_id = conn.execute(
                "INSERT INTO live_chat_messages (chat_id, sender, body) VALUES (?, 'visitor', ?)",
                (chat_id, body)).lastrowid
            conn.execute('UPDATE live_chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (chat_id,))
            return {'id': msg_id}
        finally:
            conn.close()

    def visitor_poll(self, chat_id: int, token: str, after: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            chat = self._chat_for_token(conn, chat_id, token)
            if not chat:
                return None
            msgs = conn.execute(
                """SELECT id, sender, sender_name, body, created_at FROM live_chat_messages
                   WHERE chat_id = ? AND id > ? ORDER BY id LIMIT 200""",
                (chat_id, after)).fetchall()
            return {'status': chat['status'], 'assigned_to': chat['assigned_to'],
                    'messages': [dict(m) for m in msgs]}
        finally:
            conn.close()

    # ------------------------------------------------------------------ staff
    def list_chats(self, include_closed: bool = False) -> List[Dict[str, Any]]:
        where = '' if include_closed else "WHERE c.status != 'closed'"
        conn = self._connect()
        try:
            rows = conn.execute(f"""
                SELECT c.id, c.visitor_name, c.visitor_contact, c.page_url, c.status,
                       c.assigned_to, c.created_at, c.updated_at,
                       (SELECT body FROM live_chat_messages m
                         WHERE m.chat_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                       (SELECT sender FROM live_chat_messages m
                         WHERE m.chat_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_sender
                FROM live_chats c {where}
                ORDER BY CASE c.status WHEN 'waiting' THEN 0 WHEN 'active' THEN 1 ELSE 2 END,
                         c.updated_at DESC
                LIMIT 100""").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def staff_messages(self, chat_id: int, after: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            chat = conn.execute('SELECT * FROM live_chats WHERE id = ?', (chat_id,)).fetchone()
            if not chat:
                return None
            msgs = conn.execute(
                """SELECT id, sender, sender_name, body, created_at FROM live_chat_messages
                   WHERE chat_id = ? AND id > ? ORDER BY id""", (chat_id, after)).fetchall()
            info = {k: chat[k] for k in ('id', 'visitor_name', 'visitor_contact', 'page_url',
                                         'status', 'assigned_to', 'created_at')}
            return {'chat': info, 'messages': [dict(m) for m in msgs]}
        finally:
            conn.close()

    def staff_send(self, chat_id: int, staff_name: str, body: str) -> Optional[int]:
        conn = self._connect()
        try:
            conn.execute('BEGIN')
            chat = conn.execute('SELECT status FROM live_chats WHERE id = ?', (chat_id,)).fetchone()
            if not chat or chat['status'] == 'closed':
                conn.execute('ROLLBACK')
                return None
            if chat['status'] == 'waiting':
                conn.execute("""INSERT INTO live_chat_messages (chat_id, sender, body)
                                VALUES (?, 'system', ?)""",
                             (chat_id, f'{staff_name} joined the chat.'))
            msg_id = conn.execute(
                """INSERT INTO live_chat_messages (chat_id, sender, sender_name, body)
                   VALUES (?, 'staff', ?, ?)""", (chat_id, staff_name, body)).lastrowid
            conn.execute("""UPDATE live_chats SET status = 'active', assigned_to = ?,
                            updated_at = CURRENT_TIMESTAMP WHERE id = ?""", (staff_name, chat_id))
            conn.execute('COMMIT')
            return msg_id
        except Exception:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()

    def close_chat(self, chat_id: int, closed_by: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("""UPDATE live_chats SET status = 'closed', updated_at = CURRENT_TIMESTAMP
                                  WHERE id = ? AND status != 'closed'""", (chat_id,))
            if cur.rowcount:
                conn.execute("INSERT INTO live_chat_messages (chat_id, sender, body) VALUES (?, 'system', ?)",
                             (chat_id, f'Chat ended by {closed_by}.'))
            return cur.rowcount > 0
        finally:
            conn.close()


def _clean(text: Any, limit: int = MAX_BODY) -> str:
    return str(text or '').strip()[:limit]


def _email_office(notifier, chat_id: int, name: str) -> None:
    """Heads-up email to the office, sent in the background so the visitor never waits on SMTP."""
    import html
    import threading

    def send():
        try:
            notifier._send_email(
                to_email=notifier.business_email,
                subject=f'💬 Live chat request #{chat_id}',
                body=(f'<p><strong>{html.escape(name or "A website visitor")}</strong> '
                      f'asked to talk to a person.</p><p>Open the admin dashboard → Live Chat to reply.</p>'))
        except Exception as e:
            print(f'Live chat email failed: {e}')

    threading.Thread(target=send, daemon=True).start()


def _staff_name() -> str:
    user = getattr(request, 'current_user', None) or {}
    return user.get('full_name') or user.get('username') or 'OnTime team'


# ====================================================================== API
def create_live_chat_blueprint(store: LiveChatStore, require_auth, notifier=None) -> Blueprint:
    bp = Blueprint('live_chat', __name__)

    # ---- visitor side (authorised by the per-chat token) ----
    @bp.route('/api/live-chat/status', methods=['GET'])
    def status():
        return jsonify({'success': True, 'staff_online': store.staff_online()}), 200

    @bp.route('/api/live-chat/start', methods=['POST'])
    def start():
        data = request.get_json() or {}
        transcript = data.get('transcript') if isinstance(data.get('transcript'), list) else []
        result = store.start_chat(_clean(data.get('name'), 80), _clean(data.get('contact'), 120),
                                  _clean(data.get('page'), 300), transcript)
        online = store.staff_online()
        if notifier and getattr(notifier, 'enabled', False):
            _email_office(notifier, result['chat_id'], _clean(data.get('name'), 80))
        return jsonify({'success': True, 'staff_online': online, **result}), 201

    @bp.route('/api/live-chat/<int:chat_id>/messages', methods=['POST'])
    def visitor_send(chat_id):
        data = request.get_json() or {}
        body = _clean(data.get('body'))
        if not body:
            return jsonify({'success': False, 'error': 'Message is empty'}), 400
        res = store.visitor_send(chat_id, data.get('token', ''), body)
        errors = {'not_found': 404, 'closed': 409, 'rate_limited': 429}
        if 'error' in res:
            return jsonify({'success': False, 'error': res['error']}), errors[res['error']]
        return jsonify({'success': True, 'id': res['id']}), 201

    @bp.route('/api/live-chat/<int:chat_id>/messages', methods=['GET'])
    def visitor_poll(chat_id):
        res = store.visitor_poll(chat_id, request.args.get('token', ''),
                                 request.args.get('after', 0, type=int))
        if res is None:
            return jsonify({'success': False, 'error': 'not_found'}), 404
        return jsonify({'success': True, 'staff_online': store.staff_online(), **res}), 200

    @bp.route('/api/live-chat/<int:chat_id>/close', methods=['POST'])
    def visitor_close(chat_id):
        data = request.get_json() or {}
        conn_ok = store.visitor_poll(chat_id, data.get('token', ''), 0)
        if conn_ok is None:
            return jsonify({'success': False, 'error': 'not_found'}), 404
        store.close_chat(chat_id, 'visitor')
        return jsonify({'success': True}), 200

    # ---- staff side (admin session required) ----
    @bp.route('/api/admin/live-chats', methods=['GET'])
    @require_auth
    def staff_list():
        store.touch_staff(request.current_user.get('username', 'staff'))
        chats = store.list_chats(request.args.get('all') == '1')
        return jsonify({'success': True, 'chats': chats,
                        'waiting': sum(c['status'] == 'waiting' for c in chats)}), 200

    @bp.route('/api/admin/live-chats/<int:chat_id>/messages', methods=['GET'])
    @require_auth
    def staff_messages(chat_id):
        store.touch_staff(request.current_user.get('username', 'staff'))
        res = store.staff_messages(chat_id, request.args.get('after', 0, type=int))
        if res is None:
            return jsonify({'success': False, 'error': 'not_found'}), 404
        return jsonify({'success': True, **res}), 200

    @bp.route('/api/admin/live-chats/<int:chat_id>/messages', methods=['POST'])
    @require_auth
    def staff_send(chat_id):
        body = _clean((request.get_json() or {}).get('body'))
        if not body:
            return jsonify({'success': False, 'error': 'Message is empty'}), 400
        msg_id = store.staff_send(chat_id, _staff_name(), body)
        if msg_id is None:
            return jsonify({'success': False, 'error': 'Chat not found or closed'}), 409
        return jsonify({'success': True, 'id': msg_id}), 201

    @bp.route('/api/admin/live-chats/<int:chat_id>/close', methods=['POST'])
    @require_auth
    def staff_close(chat_id):
        ok = store.close_chat(chat_id, _staff_name())
        return jsonify({'success': ok}), (200 if ok else 404)

    return bp
