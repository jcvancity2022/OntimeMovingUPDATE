"""SQLite storage for contact-form leads captured by the template."""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leads.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def insert_lead(name, email, phone, message):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO leads (name, email, phone, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, email, phone, message, datetime.utcnow().isoformat())
    )
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()
    return lead_id


def get_leads():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]
