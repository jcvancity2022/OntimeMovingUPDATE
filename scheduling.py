"""
OnTime Moving - Time-slot scheduling (SQLite)

Adds arrival-window booking on top of the existing `bookings` table:

  time_slots      - the arrival windows offered each day and how many crews
                    can be booked into each one (capacity)
  blocked_dates   - whole days the company is closed (holidays, fully booked)

Availability is computed in SQL by counting active bookings per window, and
new bookings are inserted inside a write-locked transaction so two customers
can never grab the last crew in the same window at the same time.
"""

import sqlite3
from datetime import datetime, date
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

# Statuses that hold a crew. Cancelled bookings free their slot again.
ACTIVE_STATUSES = ('pending', 'confirmed')

# Values that mean "no specific window" — accepted without a capacity check.
FLEXIBLE_VALUES = {'', 'flexible', 'morning', 'afternoon'}

DEFAULT_SLOTS = [
    # code,          label,                        start,   end,     capacity, sort
    ('08:00-10:00', 'Early morning (8 – 10 AM)',   '08:00', '10:00', 2, 1),
    ('10:00-12:00', 'Late morning (10 AM – 12 PM)', '10:00', '12:00', 2, 2),
    ('12:00-14:00', 'Early afternoon (12 – 2 PM)', '12:00', '14:00', 2, 3),
    ('14:00-16:00', 'Late afternoon (2 – 4 PM)',   '14:00', '16:00', 1, 4),
]


class SlotFullError(Exception):
    """Raised when the requested arrival window has no crews left."""


class DateClosedError(Exception):
    """Raised when the requested date is blocked."""


class SlotScheduler:
    def __init__(self, db_path: str = 'ontime_moving.db'):
        self.db_path = db_path

    # ------------------------------------------------------------------ setup
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def initialize(self) -> None:
        conn = self._connect()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS time_slots (
                code        TEXT PRIMARY KEY,
                label       TEXT NOT NULL,
                start_time  TEXT NOT NULL,
                end_time    TEXT NOT NULL,
                capacity    INTEGER NOT NULL DEFAULT 1 CHECK (capacity >= 0),
                sort_order  INTEGER NOT NULL DEFAULT 0,
                active      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS blocked_dates (
                block_date  TEXT PRIMARY KEY,          -- YYYY-MM-DD
                reason      TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_date_time
                ON bookings (move_date, preferred_time);
            """)
            conn.executemany(
                """INSERT OR IGNORE INTO time_slots
                   (code, label, start_time, end_time, capacity, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                DEFAULT_SLOTS,
            )
        finally:
            conn.close()

    # ----------------------------------------------------------- availability
    def get_availability(self, move_date: str) -> Dict[str, Any]:
        """Return every active window for a date with booked / remaining counts."""
        _parse_date(move_date)
        placeholders = ','.join('?' * len(ACTIVE_STATUSES))
        conn = self._connect()
        try:
            blocked = conn.execute(
                'SELECT reason FROM blocked_dates WHERE block_date = ?', (move_date,)
            ).fetchone()

            rows = conn.execute(f"""
                SELECT s.code, s.label, s.start_time, s.end_time, s.capacity,
                       COUNT(b.id)                       AS booked,
                       MAX(s.capacity - COUNT(b.id), 0)  AS remaining
                FROM time_slots s
                LEFT JOIN bookings b
                       ON b.preferred_time = s.code
                      AND b.move_date      = ?
                      AND b.status IN ({placeholders})
                WHERE s.active = 1
                GROUP BY s.code
                ORDER BY s.sort_order
            """, (move_date, *ACTIVE_STATUSES)).fetchall()
        finally:
            conn.close()

        slots = []
        for r in rows:
            remaining = 0 if blocked else r['remaining']
            slots.append({
                'code': r['code'],
                'label': r['label'],
                'start_time': r['start_time'],
                'end_time': r['end_time'],
                'capacity': r['capacity'],
                'booked': r['booked'],
                'remaining': remaining,
                'available': remaining > 0,
            })
        return {
            'date': move_date,
            'closed': bool(blocked),
            'closed_reason': blocked['reason'] if blocked else None,
            'slots': slots,
        }

    # ---------------------------------------------------------------- booking
    def book(self, *, customer_name: str, phone: str, email: str,
             moving_from: str, moving_to: str, move_date: str,
             move_size: Optional[str], preferred_time: Optional[str],
             special_instructions: Optional[str] = None,
             notes: Optional[str] = None) -> int:
        """
        Insert a booking. When `preferred_time` is a slot code the capacity
        check and the insert happen inside one BEGIN IMMEDIATE transaction,
        so concurrent requests are serialised by SQLite's write lock.
        """
        slot_code = (preferred_time or '').strip()
        conn = self._connect()
        try:
            conn.execute('BEGIN IMMEDIATE')

            if conn.execute('SELECT 1 FROM blocked_dates WHERE block_date = ?',
                            (move_date,)).fetchone():
                raise DateClosedError(move_date)

            if slot_code.lower() not in FLEXIBLE_VALUES:
                slot = conn.execute(
                    'SELECT capacity FROM time_slots WHERE code = ? AND active = 1',
                    (slot_code,),
                ).fetchone()
                if slot is None:
                    raise ValueError(f'Unknown time slot: {slot_code}')

                placeholders = ','.join('?' * len(ACTIVE_STATUSES))
                taken = conn.execute(
                    f"""SELECT COUNT(*) FROM bookings
                        WHERE move_date = ? AND preferred_time = ?
                          AND status IN ({placeholders})""",
                    (move_date, slot_code, *ACTIVE_STATUSES),
                ).fetchone()[0]
                if taken >= slot['capacity']:
                    raise SlotFullError(slot_code)

            cur = conn.execute(
                """INSERT INTO bookings
                   (customer_name, phone, email, moving_from, moving_to, move_date,
                    move_size, preferred_time, special_instructions, notes, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (customer_name, phone, email, moving_from, moving_to, move_date,
                 move_size, slot_code or None, special_instructions, notes),
            )
            booking_id = cur.lastrowid
            conn.execute('COMMIT')
            return booking_id
        except Exception:
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------ admin tools
    def list_slots(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(
                'SELECT * FROM time_slots ORDER BY sort_order')]
        finally:
            conn.close()

    def update_slot(self, code: str, capacity: Optional[int] = None,
                    active: Optional[bool] = None, label: Optional[str] = None) -> bool:
        sets, params = [], []
        if capacity is not None:
            sets.append('capacity = ?'); params.append(int(capacity))
        if active is not None:
            sets.append('active = ?'); params.append(1 if active else 0)
        if label:
            sets.append('label = ?'); params.append(label)
        if not sets:
            return False
        conn = self._connect()
        try:
            cur = conn.execute(f"UPDATE time_slots SET {', '.join(sets)} WHERE code = ?",
                               (*params, code))
            return cur.rowcount > 0
        finally:
            conn.close()

    def block_date(self, block_date: str, reason: str = '') -> None:
        _parse_date(block_date)
        conn = self._connect()
        try:
            conn.execute('INSERT OR REPLACE INTO blocked_dates (block_date, reason) VALUES (?, ?)',
                         (block_date, reason))
        finally:
            conn.close()

    def unblock_date(self, block_date: str) -> bool:
        conn = self._connect()
        try:
            return conn.execute('DELETE FROM blocked_dates WHERE block_date = ?',
                                (block_date,)).rowcount > 0
        finally:
            conn.close()

    def list_blocked_dates(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(
                'SELECT block_date, reason FROM blocked_dates WHERE block_date >= ? ORDER BY block_date',
                (date.today().isoformat(),))]
        finally:
            conn.close()


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError('Invalid date format. Use YYYY-MM-DD')


# ====================================================================== API
def create_scheduling_blueprint(scheduler: SlotScheduler, require_auth) -> Blueprint:
    bp = Blueprint('scheduling', __name__)

    @bp.route('/api/availability', methods=['GET'])
    def availability():
        move_date = request.args.get('date', '')
        try:
            if _parse_date(move_date) < date.today():
                return jsonify({'success': False, 'error': 'Date is in the past'}), 400
            return jsonify({'success': True, **scheduler.get_availability(move_date)}), 200
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @bp.route('/api/admin/slots', methods=['GET'])
    @require_auth
    def admin_slots():
        return jsonify({'success': True, 'slots': scheduler.list_slots(),
                        'blocked_dates': scheduler.list_blocked_dates()}), 200

    @bp.route('/api/admin/slots/<path:code>', methods=['PATCH'])
    @require_auth
    def admin_update_slot(code):
        data = request.get_json() or {}
        ok = scheduler.update_slot(code, data.get('capacity'), data.get('active'), data.get('label'))
        return jsonify({'success': ok}), (200 if ok else 404)

    @bp.route('/api/admin/blocked-dates', methods=['POST'])
    @require_auth
    def admin_block_date():
        data = request.get_json() or {}
        try:
            scheduler.block_date(data.get('date', ''), data.get('reason', ''))
            return jsonify({'success': True}), 201
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @bp.route('/api/admin/blocked-dates/<block_date>', methods=['DELETE'])
    @require_auth
    def admin_unblock_date(block_date):
        ok = scheduler.unblock_date(block_date)
        return jsonify({'success': ok}), (200 if ok else 404)

    return bp
