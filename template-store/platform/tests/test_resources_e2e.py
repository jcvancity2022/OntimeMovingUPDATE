"""
Full end-to-end regression suite: auth, validation/error shape, company
content + settings, and CRUD (search/filter/sort/paginate/export) for leads,
customers, products and appointments — plus analytics, cross-tenant
isolation on every new resource, staff role restrictions, rate limiting and
logging. 56 checks total.

Requires a freshly reset + reseeded database (several checks assert exact
starting counts):
    rm -f platform.db && python -m alembic upgrade head && python seed.py
    python app.py &
    python tests/test_resources_e2e.py

Note: this suite intentionally triggers the auth rate limiter near the end
(15 rapid login attempts) to prove it works. Running it back-to-back with
another script that also logs in a lot may cause spurious 429s until the
window (RATE_LIMIT_AUTH, default 10/minute) resets.
"""
import os
import time
import requests

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:5050')
PW = 'Demo1234!'
PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []


def check(label, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {label}' + (f' -- {detail}' if detail and not cond else ''))
    results.append({'label': label, 'pass': bool(cond), 'detail': detail})
    return cond


def login(email, pw=PW):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login', json={'email': email, 'password': pw})
    assert r.status_code == 200, (email, r.status_code, r.text)
    return s


print('=== AUTH ===')
maria = login('maria@novasalon.demo')
sam = login('sam@summitcontracting.demo')
elena = login('elena@cafeverde.demo')
priya = login('priya@novasalon.demo')
admin = login('admin@forgetemplates.demo')

r = requests.post(f'{BASE}/api/auth/login', json={'email': 'maria@novasalon.demo', 'password': 'wrong'})
check('Wrong password rejected (401)', r.status_code == 401)

r = maria.get(f'{BASE}/api/auth/me')
check('/me returns correct user+company', r.status_code == 200 and r.json()['company']['slug'] == 'nova-co-salon')

new_email = f'owner+{int(time.time())}@newbiz.demo'
r = requests.post(f'{BASE}/api/auth/register', json={
    'company_name': 'Test Register Co', 'owner_name': 'New Owner', 'email': new_email, 'password': 'RegisterPW1'
})
check('Register creates company+owner (201)', r.status_code == 201)

print('\n=== VALIDATION / ERROR SHAPE ===')
r = requests.post(f'{BASE}/api/auth/register', json={'company_name': '', 'owner_name': '', 'email': '', 'password': ''})
body = r.json()
check('Empty register rejected with consistent error shape', r.status_code == 400 and 'error' in body and 'code' in body, body)

r = maria.get(f'{BASE}/api/leads/999999')
check('Unknown lead id -> 404 with code NOT_FOUND', r.status_code == 404 and r.json().get('code') == 'NOT_FOUND')

r = requests.get(f'{BASE}/this-route-does-not-exist')
check('Unknown route -> 404 JSON (not Flask HTML page)', r.status_code == 404 and r.headers.get('content-type', '').startswith('application/json'))

print('\n=== COMPANY / CONTENT / SETTINGS ===')
r = maria.get(f'{BASE}/api/company')
check('GET /api/company returns content blob', r.status_code == 200 and 'hero' in r.json()['content'])

r = maria.patch(f'{BASE}/api/company', json={'brand_name': 'Nova & Co. Salon', 'content': {'hero': {'title': 'E2E Test Title'}}})
check('PATCH /api/company updates content', r.status_code == 200 and r.json()['content']['hero']['title'] == 'E2E Test Title')

r = requests.get(f'{BASE}/api/public/companies/nova-co-salon/content')
check('Public content reflects the just-saved title', r.status_code == 200 and r.json()['content']['hero']['title'] == 'E2E Test Title')

r = maria.patch(f'{BASE}/api/settings', json={'timezone': 'America/Vancouver', 'currency': 'CAD', 'notification_email': 'alerts@novasalon.demo'})
check('PATCH /api/settings persists', r.status_code == 200 and r.json()['timezone'] == 'America/Vancouver' and r.json()['currency'] == 'CAD')

r = maria.get(f'{BASE}/api/settings')
check('GET /api/settings reflects saved values', r.json()['notification_email'] == 'alerts@novasalon.demo')

print('\n=== LEADS: CRUD + pagination + search/filter/sort + export ===')
r = maria.get(f'{BASE}/api/leads')
page1 = r.json()
check('Leads list is paginated shape', all(k in page1 for k in ('items', 'page', 'per_page', 'total', 'total_pages')))
check('Nova & Co starts with 4 seeded leads', page1['total'] == 4)

r = maria.post(f'{BASE}/api/leads', json={'name': 'Manual Lead', 'email': 'manual@example.com', 'phone': '555-1', 'message': 'Manually added via dashboard'})
check('Create lead (201)', r.status_code == 201)
new_lead_id = r.json()['id']

r = maria.get(f'{BASE}/api/leads?q=Manual')
check('Search finds the new lead', r.json()['total'] == 1 and r.json()['items'][0]['id'] == new_lead_id)

r = maria.get(f'{BASE}/api/leads?status=won')
check('Status filter works', all(l['status'] == 'won' for l in r.json()['items']))

r = maria.get(f'{BASE}/api/leads?sort=name&per_page=2')
names = [l['name'] for l in r.json()['items']]
check('Sort by name + per_page=2 returns 2 sorted items', len(names) == 2 and names == sorted(names))

r = maria.patch(f'{BASE}/api/leads/{new_lead_id}', json={'status': 'contacted', 'notes': 'Called back'})
check('Update lead status+notes', r.status_code == 200 and r.json()['status'] == 'contacted' and r.json()['notes'] == 'Called back')

r = maria.get(f'{BASE}/api/leads/export')
csv_rows = [l for l in r.text.splitlines() if l.strip()]
check('CSV export has header + all rows', r.headers['Content-Type'].startswith('text/csv') and len(csv_rows) == 6)

dup_payload = {'name': 'Dup Test', 'email': 'dup@example.com', 'message': 'dup check'}
r1 = requests.post(f'{BASE}/api/public/companies/nova-co-salon/leads', json=dup_payload)
r2 = requests.post(f'{BASE}/api/public/companies/nova-co-salon/leads', json=dup_payload)
check('Immediate duplicate resubmit flagged, not double-inserted', r1.status_code == 201 and r2.status_code == 200 and r2.json()['duplicate'] is True)

r = maria.delete(f'{BASE}/api/leads/{new_lead_id}')
check('Delete (soft) lead succeeds', r.status_code == 200)
r = maria.get(f'{BASE}/api/leads/{new_lead_id}')
check('Soft-deleted lead no longer retrievable via API', r.status_code == 404)

print('\n=== CUSTOMERS: CRUD + duplicate prevention ===')
r = maria.get(f'{BASE}/api/customers')
check('Nova & Co starts with 2 seeded customers', r.json()['total'] == 2)

r = maria.post(f'{BASE}/api/customers', json={'name': 'New Customer', 'email': 'newcust@example.com', 'phone': '555-9', 'tags': ['loyal', 'referral']})
check('Create customer (201) with tags', r.status_code == 201 and r.json()['tags'] == ['loyal', 'referral'])
cust_id = r.json()['id']

r = maria.post(f'{BASE}/api/customers', json={'name': 'Dup', 'email': 'newcust@example.com'})
check('Duplicate customer email rejected (409)', r.status_code == 409)

r = maria.patch(f'{BASE}/api/customers/{cust_id}', json={'status': 'inactive'})
check('Update customer status', r.status_code == 200 and r.json()['status'] == 'inactive')

r = maria.delete(f'{BASE}/api/customers/{cust_id}')
check('Delete (soft) customer', r.status_code == 200)

print('\n=== PRODUCTS: CRUD + SKU duplicate prevention ===')
r = maria.get(f'{BASE}/api/products')
check('Nova & Co starts with 3 seeded products', r.json()['total'] == 3)

r = maria.post(f'{BASE}/api/products', json={'name': 'Test Product', 'price': 42.5, 'sku': 'TEST-SKU-1'})
check('Create product (201)', r.status_code == 201 and r.json()['price'] == 42.5)
prod_id = r.json()['id']

r = maria.post(f'{BASE}/api/products', json={'name': 'Another', 'sku': 'TEST-SKU-1'})
check('Duplicate SKU rejected (409)', r.status_code == 409)

r = maria.patch(f'{BASE}/api/products/{prod_id}', json={'price': 55})
check('Update product price', r.status_code == 200 and r.json()['price'] == 55.0)

r = maria.get(f'{BASE}/api/products?sort=price')
prices = [p['price'] for p in r.json()['items'] if p['price'] is not None]
check('Sort by price ascending', prices == sorted(prices))

r = maria.delete(f'{BASE}/api/products/{prod_id}')
check('Delete (soft) product', r.status_code == 200)

print('\n=== APPOINTMENTS: CRUD + relation validation ===')
r = maria.get(f'{BASE}/api/appointments')
check('Nova & Co starts with 2 seeded appointments', r.json()['total'] == 2)

r = maria.get(f'{BASE}/api/customers?status=active')
active_cust = r.json()['items'][0]['id'] if r.json()['items'] else None

r = maria.post(f'{BASE}/api/appointments', json={
    'title': 'Test Appt', 'scheduled_at': '2026-08-01T10:00:00', 'duration_minutes': 30, 'customer_id': active_cust
})
check('Create appointment (201) linked to own customer', r.status_code == 201)
appt_id = r.json()['id']

r = sam.get(f'{BASE}/api/customers')
sam_cust_id = r.json()['items'][0]['id']
r = maria.post(f'{BASE}/api/appointments', json={'title': 'Cross-tenant attempt', 'scheduled_at': '2026-08-01T10:00:00', 'customer_id': sam_cust_id})
check("Appointment can't reference another company's customer (400)", r.status_code == 400)

r = maria.patch(f'{BASE}/api/appointments/{appt_id}', json={'status': 'completed'})
check('Update appointment status', r.status_code == 200 and r.json()['status'] == 'completed')

r = maria.delete(f'{BASE}/api/appointments/{appt_id}')
check('Delete (soft) appointment', r.status_code == 200)

print('\n=== ANALYTICS ===')
r = maria.get(f'{BASE}/api/analytics')
a = r.json()
check('Analytics returns leads/customers/products/appointments blocks', all(k in a for k in ('leads', 'customers', 'products', 'appointments')))
check('Analytics trend_14d has 14 days', len(a['leads']['trend_14d']) == 14)

print('\n=== CROSS-TENANT ISOLATION (new resources) ===')
r = sam.get(f'{BASE}/api/customers')
sam_customers = r.json()['items']
r = maria.get(f'{BASE}/api/customers')
maria_customers = r.json()['items']
check('No customer id overlap between companies', not ({c["id"] for c in sam_customers} & {c["id"] for c in maria_customers}))

victim_customer = sam_customers[0]['id']
r = maria.get(f'{BASE}/api/customers/{victim_customer}')
check("Cross-tenant customer GET returns 404", r.status_code == 404)
r = maria.patch(f'{BASE}/api/customers/{victim_customer}', json={'status': 'inactive'})
check("Cross-tenant customer PATCH returns 404 (not leaked)", r.status_code == 404)
r = maria.delete(f'{BASE}/api/customers/{victim_customer}')
check("Cross-tenant customer DELETE returns 404", r.status_code == 404)

r = sam.get(f'{BASE}/api/products')
victim_product = r.json()['items'][0]['id']
r = maria.get(f'{BASE}/api/products/{victim_product}')
check("Cross-tenant product GET returns 404", r.status_code == 404)

r = sam.get(f'{BASE}/api/appointments')
victim_appt = r.json()['items'][0]['id']
r = maria.get(f'{BASE}/api/appointments/{victim_appt}')
check("Cross-tenant appointment GET returns 404", r.status_code == 404)

anon = requests.Session()
for path in ('/api/customers', '/api/products', '/api/appointments', '/api/analytics', '/api/settings'):
    r = anon.get(f'{BASE}{path}')
    check(f'Unauthenticated {path} rejected (401)', r.status_code == 401)

print('\n=== STAFF ROLE RESTRICTIONS (new resources) ===')
r = priya.get(f'{BASE}/api/customers')
check('Staff can list customers', r.status_code == 200)
r = priya.post(f'{BASE}/api/products', json={'name': 'Staff added product'})
check('Staff CAN create products (not owner-restricted)', r.status_code == 201)

print('\n=== RATE LIMITING ===')
codes = []
for i in range(15):
    r = requests.post(f'{BASE}/api/auth/login', json={'email': 'nobody@example.com', 'password': 'wrong'})
    codes.append(r.status_code)
check('Repeated rapid login attempts eventually rate-limited (429 seen)', 429 in codes, f'codes={codes}')

print('\n=== LOGGING ===')
log_path = os.path.join(PLATFORM_DIR, 'logs', 'platform.log')
check('Log file exists', os.path.exists(log_path))
if os.path.exists(log_path):
    with open(log_path) as f:
        full_log = f.read()
    check('Log file contains request entries for this run', 'api/leads' in full_log and full_log.count('\n') > 20)

print('\n=== SUMMARY ===')
failed = [r for r in results if not r['pass']]
print(f'{len(results) - len(failed)}/{len(results)} passed')
if failed:
    print('FAILURES:')
    for f in failed:
        print(' -', f['label'], f['detail'])
    raise SystemExit(1)
