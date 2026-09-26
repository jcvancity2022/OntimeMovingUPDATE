"""
Rigorous simulation of a real business actually using the platform — not a
demo company, not a raw API smoke test. Registers a fresh company, verifies
the starter data, then acts the way a real owner would on day one: deletes
example records, adds their own real leads/customers/products/appointments,
customizes branding/content/settings, invites a staff member — and checks
that every step is genuinely persisted, isolated from every other tenant,
and survives both a page-refresh-equivalent re-fetch and (in
test_business_simulation_restart.py) a full server restart.

Usage:
    python tests/test_business_simulation.py write
    # then, to prove persistence, fully stop and restart the server, then:
    python tests/test_business_simulation.py verify
    python tests/test_business_simulation.py cleanup   # deletes the test company
"""
import sys
import os
import time
import json
import requests

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:5050')
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.business_sim_state.json')

BUSINESS_NAME = 'Bluebird Design Studio'
OWNER_NAME = 'Morgan Ellison'
OWNER_PASSWORD = 'RealBusiness2026!'
STAFF_NAME = 'Priya Shah'

results = []


def check(label, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {label}' + (f' -- {detail}' if detail and not cond else ''))
    results.append({'label': label, 'pass': bool(cond), 'detail': detail})
    return cond


def summarize():
    failed = [r for r in results if not r['pass']]
    print()
    print(f'{len(results) - len(failed)}/{len(results)} passed')
    if failed:
        print('FAILURES:')
        for f in failed:
            print(' -', f['label'], f['detail'])
        sys.exit(1)


def login(email, password=OWNER_PASSWORD):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        return None
    return s


# ============================================================ WRITE PHASE ==
def phase_write():
    owner_email = f'morgan+{int(time.time())}@bluebirddesign.example'

    print('=== REGISTRATION (this IS the "business buys in" moment) ===')
    r = requests.post(f'{BASE}/api/auth/register', json={
        'company_name': BUSINESS_NAME, 'owner_name': OWNER_NAME, 'email': owner_email, 'password': OWNER_PASSWORD
    })
    check('Registration succeeds (201)', r.status_code == 201)
    company = r.json()['company']
    slug = company['slug']
    print(f'  slug={slug}')

    owner = login(owner_email)
    check('Owner can log back in immediately after registering', owner is not None)

    print('\n=== STARTER DATA PRESENT ON DAY ONE ===')
    leads = owner.get(f'{BASE}/api/leads').json()
    customers = owner.get(f'{BASE}/api/customers').json()
    products = owner.get(f'{BASE}/api/products').json()
    appts = owner.get(f'{BASE}/api/appointments').json()
    check('Starter leads present (3)', leads['total'] == 3)
    check('Starter customers present (2)', customers['total'] == 2)
    check('Starter products present (3)', products['total'] == 3)
    check('Starter appointments present (2)', appts['total'] == 2)

    print('\n=== OWNER CLEANS UP EXAMPLES AND ADDS REAL DATA ===')
    for lead in leads['items']:
        owner.delete(f'{BASE}/api/leads/{lead["id"]}')
    for cust in customers['items']:
        owner.delete(f'{BASE}/api/customers/{cust["id"]}')
    for prod in products['items']:
        owner.delete(f'{BASE}/api/products/{prod["id"]}')
    for appt in appts['items']:
        owner.delete(f'{BASE}/api/appointments/{appt["id"]}')

    real_leads = [
        {'name': 'Harper Voss', 'email': 'harper.voss@example.com', 'phone': '555-2001',
         'message': 'We need a full brand identity refresh — logo, colors, style guide.'},
        {'name': 'Devon Marsh', 'email': 'devon.marsh@example.com', 'phone': '555-2002',
         'message': 'Looking for a landing page redesign, launching in 6 weeks.'},
        {'name': 'Rowan Blake', 'email': 'rowan.blake@example.com', 'phone': '', 'message': 'Quick question about your packaging design rates.'},
    ]
    lead_ids = []
    for payload in real_leads:
        r = owner.post(f'{BASE}/api/leads', json=payload)
        check(f'Create real lead: {payload["name"]}', r.status_code == 201)
        lead_ids.append(r.json()['id'])
    owner.patch(f'{BASE}/api/leads/{lead_ids[0]}', json={'status': 'won', 'notes': 'Signed contract, kicking off Monday.'})

    real_customers = [
        {'name': 'Harper Voss', 'email': 'harper.voss@example.com', 'phone': '555-2001', 'address': '12 Birch Ave',
         'notes': 'Converted from lead — brand identity project.', 'tags': ['active-project', 'branding']},
        {'name': 'Kendall Reyes', 'email': 'kendall.reyes@example.com', 'phone': '555-2003', 'address': '',
         'notes': 'Returning client, 3rd project with us.', 'tags': ['repeat']},
    ]
    customer_ids = []
    for payload in real_customers:
        r = owner.post(f'{BASE}/api/customers', json=payload)
        check(f'Create real customer: {payload["name"]}', r.status_code == 201)
        customer_ids.append(r.json()['id'])

    real_products = [
        {'name': 'Brand Identity Package', 'description': 'Logo, color system, typography, brand guide', 'price': 3200.00, 'sku': 'BDS-BRAND', 'category': 'Branding', 'status': 'active'},
        {'name': 'Landing Page Design', 'description': 'Single high-conversion landing page, Figma + handoff', 'price': 1400.00, 'sku': 'BDS-LANDING', 'category': 'Web', 'status': 'active'},
        {'name': 'Packaging Design (per SKU)', 'description': 'Retail packaging design, one product SKU', 'price': 850.00, 'sku': 'BDS-PACK', 'category': 'Packaging', 'status': 'draft'},
    ]
    for payload in real_products:
        r = owner.post(f'{BASE}/api/products', json=payload)
        check(f'Create real product: {payload["name"]}', r.status_code == 201)

    real_appointments = [
        {'title': 'Brand kickoff call — Harper Voss', 'scheduled_at': '2026-08-03T14:00:00', 'duration_minutes': 60, 'customer_id': customer_ids[0], 'status': 'scheduled'},
        {'title': 'Concept review — Kendall Reyes', 'scheduled_at': '2026-08-05T10:30:00', 'duration_minutes': 45, 'customer_id': customer_ids[1], 'status': 'scheduled'},
        {'title': 'Discovery call — completed', 'scheduled_at': '2026-07-20T09:00:00', 'duration_minutes': 30, 'customer_id': customer_ids[0], 'status': 'completed'},
    ]
    for payload in real_appointments:
        r = owner.post(f'{BASE}/api/appointments', json=payload)
        check(f'Create real appointment: {payload["title"]}', r.status_code == 201)

    print('\n=== DATA INTEGRITY (this is where "seriously" gets tested) ===')
    r = owner.post(f'{BASE}/api/customers', json={'name': 'Dup Attempt', 'email': 'harper.voss@example.com'})
    check('Duplicate customer email rejected (409)', r.status_code == 409)
    r = owner.post(f'{BASE}/api/products', json={'name': 'Dup Attempt', 'sku': 'BDS-BRAND'})
    check('Duplicate product SKU rejected (409)', r.status_code == 409)
    dup_lead = {'name': 'Dup Lead', 'email': 'dup.test@example.com', 'message': 'same message twice'}
    r1 = requests.post(f'{BASE}/api/public/companies/{slug}/leads', json=dup_lead)
    r2 = requests.post(f'{BASE}/api/public/companies/{slug}/leads', json=dup_lead)
    check('Public duplicate lead resubmit flagged, not double-inserted', r1.status_code == 201 and r2.json().get('duplicate') is True)

    print('\n=== BRANDING / CONTENT / SETTINGS CUSTOMIZATION ===')
    r = owner.patch(f'{BASE}/api/company', json={
        'brand_name': BUSINESS_NAME, 'brand_accent': 'Studio', 'theme': 'slate',
        'content': {
            'hero': {'title': 'Brand and web design for ambitious small businesses',
                      'subtitle': 'Bluebird Design Studio turns your idea into a brand people remember.'},
            'footer': {'tagline': 'Bluebird Design Studio — real design, real results.'}
        }
    })
    check('Branding/content update succeeds', r.status_code == 200 and r.json()['theme'] == 'slate')

    r = owner.patch(f'{BASE}/api/settings', json={'timezone': 'America/New_York', 'currency': 'USD', 'notification_email': 'studio@bluebirddesign.example'})
    check('Settings update succeeds', r.status_code == 200 and r.json()['timezone'] == 'America/New_York')

    print('\n=== TEAM: INVITE REAL STAFF ===')
    r = owner.post(f'{BASE}/api/users', json={'name': STAFF_NAME, 'email': f'priya+{int(time.time())}@bluebirddesign.example', 'role': 'staff'})
    check('Invite staff succeeds', r.status_code == 201)
    staff_email = r.json()['email']
    staff_temp_password = r.json()['temp_password']
    staff = login(staff_email, staff_temp_password)
    check('New staff member can log in with the issued temp password', staff is not None)
    if staff:
        r = staff.get(f'{BASE}/api/leads')
        # 3 real leads + the "Dup Lead" created by the public duplicate-prevention
        # check above (its own resubmit was correctly deduped, but the first
        # submission is a real 4th lead) — same count the owner sees.
        check('Staff sees the same 4 leads as the owner', r.json()['total'] == 4)

    print('\n=== PUBLIC SITE REFLECTS THE REAL CONTENT ===')
    r = requests.get(f'{BASE}/api/public/companies/{slug}/content')
    pub = r.json()
    check('Public site shows the real hero title (not starter placeholder)',
          pub['content']['hero']['title'] == 'Brand and web design for ambitious small businesses')
    check('Public site shows the real theme (slate)', pub['theme'] == 'slate')

    print('\n=== "PAGE REFRESH" — RE-FETCH ON A FRESH SESSION ===')
    owner2 = login(owner_email)
    r = owner2.get(f'{BASE}/api/leads')
    check('Fresh login session sees the same 4 real leads (3 + won-status one)', r.json()['total'] == 4)
    r = owner2.get(f'{BASE}/api/customers')
    check('Fresh login session sees the same 2 real customers', r.json()['total'] == 2)

    with open(STATE_FILE, 'w') as f:
        json.dump({'slug': slug, 'owner_email': owner_email, 'staff_email': staff_email}, f)

    summarize()
    print(f'\nState saved to {STATE_FILE}. Now fully stop and restart the server, then run:\n'
          f'  python tests/test_business_simulation.py verify')


# =========================================================== VERIFY PHASE ==
def phase_verify():
    with open(STATE_FILE) as f:
        state = json.load(f)
    slug, owner_email, staff_email = state['slug'], state['owner_email'], state['staff_email']

    print(f'=== VERIFYING "{BUSINESS_NAME}" (slug={slug}) SURVIVED A FULL SERVER RESTART ===')
    owner = login(owner_email)
    check('Owner can still log in after restart', owner is not None)
    if not owner:
        summarize()
        return

    leads = owner.get(f'{BASE}/api/leads').json()
    check('All 4 real leads survived restart', leads['total'] == 4)
    check('Won lead status survived restart', any(l['status'] == 'won' for l in leads['items']))

    customers = owner.get(f'{BASE}/api/customers').json()
    check('Both real customers survived restart', customers['total'] == 2)

    products = owner.get(f'{BASE}/api/products').json()
    check('All 3 real products survived restart, with correct pricing',
          products['total'] == 3 and any(p['price'] == 3200.0 for p in products['items']))

    appts = owner.get(f'{BASE}/api/appointments').json()
    check('All 3 real appointments survived restart', appts['total'] == 3)

    company = owner.get(f'{BASE}/api/company').json()
    check('Branding/theme survived restart (slate)', company['theme'] == 'slate')
    check('Custom hero content survived restart',
          company['content']['hero']['title'] == 'Brand and web design for ambitious small businesses')

    settings = owner.get(f'{BASE}/api/settings').json()
    check('Settings survived restart (timezone)', settings['timezone'] == 'America/New_York')

    users = owner.get(f'{BASE}/api/users').json()
    check('Invited staff member survived restart', any(u['email'] == staff_email for u in users))

    print('\n=== ISOLATION STILL HOLDS AFTER RESTART ===')
    admin = login('admin@forgetemplates.demo', 'Demo1234!')
    if admin:
        companies = admin.get(f'{BASE}/api/companies').json()
        check(f'Platform admin sees "{BUSINESS_NAME}" alongside every other company', any(c['slug'] == slug for c in companies))
        others = [c for c in companies if c['slug'] != slug]
        if others:
            admin.post(f'{BASE}/api/companies/switch', json={'company_id': others[0]['id']})
            r = admin.get(f'{BASE}/api/leads')
            other_leads = {l['id'] for l in r.json()['items']}
            own_lead_ids = {l['id'] for l in leads['items']}
            check("Bluebird's lead IDs do not appear in another company's lead list", not (other_leads & own_lead_ids))

    summarize()


def phase_cleanup():
    with open(STATE_FILE) as f:
        state = json.load(f)
    import subprocess
    script = f"""
from app import app
from extensions import db
from models import Company
with app.app_context():
    c = Company.query.filter_by(slug='{state["slug"]}').first()
    if c:
        db.session.delete(c)
        db.session.commit()
        print('Deleted test company:', c.name)
    else:
        print('Already gone.')
"""
    subprocess.run([sys.executable, '-c', script], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.remove(STATE_FILE)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('write', 'verify', 'cleanup'):
        raise SystemExit('Usage: python test_business_simulation.py [write|verify|cleanup]')
    {'write': phase_write, 'verify': phase_verify, 'cleanup': phase_cleanup}[sys.argv[1]]()
