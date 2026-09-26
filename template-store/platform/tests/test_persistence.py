"""
Two-phase persistence check: proves data survives a full server process
restart (not just a page refresh), i.e. that it's stored in the database
file, not in server memory.

Usage:
    python tests/test_persistence.py write
    # ... now fully stop and restart `python app.py` ...
    python tests/test_persistence.py verify

Writes/reads a marker customer under Cafe Verde (elena@cafeverde.demo).
"""
import sys
import requests

BASE = 'http://127.0.0.1:5050'
MARKER_EMAIL = 'persistence.marker@example.com'


def login():
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login', json={'email': 'elena@cafeverde.demo', 'password': 'Demo1234!'})
    assert r.status_code == 200, r.text
    return s


def write():
    s = login()
    r = s.post(f'{BASE}/api/customers', json={'name': 'Persistence Marker', 'email': MARKER_EMAIL, 'phone': '555-0000'})
    assert r.status_code in (201, 409), r.text
    print(f'Marker written (status {r.status_code}). Now fully stop and restart the server, then run: '
          f'python tests/test_persistence.py verify')


def verify():
    s = login()
    r = s.get(f'{BASE}/api/customers', params={'q': MARKER_EMAIL})
    items = r.json()['items']
    if items and items[0]['email'] == MARKER_EMAIL:
        print(f"PASS: marker customer (id={items[0]['id']}, created_at={items[0]['created_at']}) "
              f"survived the server restart.")
    else:
        print('FAIL: marker customer not found after restart — data did not persist.')
        raise SystemExit(1)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('write', 'verify'):
        raise SystemExit('Usage: python test_persistence.py [write|verify]')
    (write if sys.argv[1] == 'write' else verify)()
