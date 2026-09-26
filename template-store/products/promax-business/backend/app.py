"""
Pro Max Business Template — local server.
Serves the static site and a small API for storing contact-form leads.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000
"""
import os
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'change-me')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)
database.init_db()


@app.route('/')
def home():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/admin.html')
def admin():
    return send_from_directory(BASE_DIR, 'admin.html')


@app.route('/api/leads', methods=['POST'])
def create_lead():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    message = (data.get('message') or '').strip()

    if not name or not message:
        return jsonify({'error': 'Name and message are required.'}), 400
    if not EMAIL_RE.match(email):
        return jsonify({'error': 'A valid email address is required.'}), 400

    lead_id = database.insert_lead(name, email, phone, message)
    return jsonify({'id': lead_id, 'status': 'saved'}), 201


@app.route('/api/leads', methods=['GET'])
def list_leads():
    token = request.args.get('token', '')
    if token != ADMIN_TOKEN:
        return jsonify({'error': 'Unauthorized.'}), 401
    return jsonify(database.get_leads())


if __name__ == '__main__':
    app.run(debug=True, port=5000)
