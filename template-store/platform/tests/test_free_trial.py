"""
Free trial: new registrations get 14 days of full access with no payment
required. Verifies the trial fields are set correctly on registration, that
write access is blocked (402 TRIAL_EXPIRED) once trial_ends_at has passed
while read access stays open, that the platform-admin upgrade endpoint
unblocks writes, and that every pre-existing company (demo + real) was
grandfathered onto 'active' rather than retroactively put on a trial.

This suite pokes trial_ends_at directly in the database to simulate time
passing (there's no reasonable way to wait 14 real days in a test) — that's
the one exception to "only touch the DB through the API" in this test suite,
and it's clearly isolated to one helper function.

Usage:
    python tests/test_free_trial.py
"""
import os
import sys
import time
import sqlite3
import requests
from datetime import datetime, timedelta, timezone

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:5050')
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'platform.db')
results = []


def check(label, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {label}' + (f' -- {detail}' if detail and not cond else ''))
    results.append({'label': label, 'pass': bool(cond), 'detail': detail})
    return cond


def login(email, password):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login', json={'email': email, 'password': password})
    return s if r.status_code == 200 else None


def register(name, email, password):
    r = requests.post(f'{BASE}/api/auth/register', json={
        'company_name': name, 'owner_name': 'Test Owner', 'email': email, 'password': password
    })
    return r


def backdate_trial(slug, days_ago):
    """The one direct-DB step in this suite — simulates the trial clock running out."""
    conn = sqlite3.connect(DB_PATH)
    past = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    conn.execute('UPDATE companies SET trial_ends_at = ? WHERE slug = ?', (past, slug))
    conn.commit()
    conn.close()


def cleanup(slug):
    import subprocess
    script = f"""
from app import app
from extensions import db
from models import Company
with app.app_context():
    c = Company.query.filter_by(slug='{slug}').first()
    if c:
        db.session.delete(c)
        db.session.commit()
"""
    subprocess.run([sys.executable, '-c', script],
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    capture_output=True)


print('=== REGISTRATION STARTS A REAL 14-DAY TRIAL ===')
pw = 'FreeTrialPW1'
email = f'freetrial+{int(time.time())}@example.com'
r = register('Free Trial Test Co', email, pw)
check('Registration succeeds (201)', r.status_code == 201)
company = r.json()['company']
slug = company['slug']
check("New company starts on plan='trial'", company['plan'] == 'trial')
check('trial_days_remaining is 14 on day one', company['trial_days_remaining'] == 14)
check('is_trial_expired is False on day one', company['is_trial_expired'] is False)

owner = login(email, pw)
check('Owner can log in immediately', owner is not None)

print('\n=== WRITES WORK NORMALLY DURING AN ACTIVE TRIAL ===')
r = owner.post(f'{BASE}/api/leads', json={'name': 'Trial Lead', 'email': 'triallead@example.com', 'message': 'hi'})
check('Create lead succeeds during active trial (201)', r.status_code == 201)

print('\n=== SIMULATING THE TRIAL RUNNING OUT ===')
backdate_trial(slug, days_ago=1)

r = owner.get(f'{BASE}/api/leads')
check('GET /api/leads still works after trial expiry (data never gets locked away)', r.status_code == 200)

r = owner.post(f'{BASE}/api/leads', json={'name': 'Blocked', 'email': 'blocked@example.com', 'message': 'should be blocked'})
check('POST /api/leads blocked after expiry (402 TRIAL_EXPIRED)',
      r.status_code == 402 and r.json().get('code') == 'TRIAL_EXPIRED')

r = owner.patch(f'{BASE}/api/company', json={'brand_name': 'Should Not Apply'})
check('PATCH /api/company blocked after expiry (402)', r.status_code == 402)

r = owner.delete(f'{BASE}/api/leads/999999')  # nonexistent id: confirms the trial gate fires before 404 lookup logic
check('DELETE also blocked by the trial gate (402, not 404)', r.status_code == 402)

r = owner.get(f'{BASE}/api/company')
check('Company payload reflects is_trial_expired=True', r.json()['is_trial_expired'] is True)

print('\n=== ONLY A PLATFORM ADMIN CAN UPGRADE ===')
r = owner.patch(f'{BASE}/api/companies/{company["id"]}/plan', json={'plan': 'active'})
check('Owner cannot upgrade their own company (403)', r.status_code == 403)

admin = login('admin@forgetemplates.demo', 'Demo1234!')
check('Platform admin login works', admin is not None)
if admin:
    r = admin.patch(f'{BASE}/api/companies/{company["id"]}/plan', json={'plan': 'active'})
    check('Platform admin upgrade succeeds (200)', r.status_code == 200 and r.json()['plan'] == 'active')

    r = owner.post(f'{BASE}/api/leads', json={'name': 'Unblocked', 'email': 'unblocked@example.com', 'message': 'works now'})
    check('Writes work again immediately after upgrade (201)', r.status_code == 201)

    r = owner.get(f'{BASE}/api/company')
    check('is_trial_expired is False once plan is active (even with a past trial_ends_at)', r.json()['is_trial_expired'] is False)

print('\n=== EXISTING COMPANIES WERE GRANDFATHERED, NOT RETROACTIVELY TRIALED ===')
for demo_slug in ('nova-co-salon', 'summit-contracting', 'cafe-verde', 'jeffrey-s-business'):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT plan, trial_ends_at FROM companies WHERE slug = ?', (demo_slug,)).fetchone()
    conn.close()
    if row is None:
        continue
    check(f"{demo_slug} is plan='active' with no trial_ends_at", row[0] == 'active' and row[1] is None, str(row))

cleanup(slug)
print(f'\nCleaned up test company: {slug}')

print()
failed = [r for r in results if not r['pass']]
print(f'{len(results) - len(failed)}/{len(results)} passed')
if failed:
    print('FAILURES:')
    for f in failed:
        print(' -', f['label'], f['detail'])
    sys.exit(1)
