"""
Multi-tenant isolation regression test — 23 checks proving that per-company
data (leads, in this suite) can never be read, edited, or deleted by another
company, that role restrictions are enforced server-side, and that the
platform-admin company switcher only ever exposes the selected company.

Requires a freshly reset + reseeded database (counts are asserted exactly):
    rm -f platform.db && python -m alembic upgrade head && python seed.py
    python app.py &
    python tests/test_isolation.py
"""
import os
import requests

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:5050')
PW = 'Demo1234!'
failures = []


def check(label, cond):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {label}')
    if not cond:
        failures.append(label)


def login(email):
    s = requests.Session()
    r = s.post(f'{BASE}/api/auth/login', json={'email': email, 'password': PW})
    assert r.status_code == 200, (email, r.status_code, r.text)
    return s


# --- basic per-company login + lead counts ---
maria = login('maria@novasalon.demo')
sam = login('sam@summitcontracting.demo')
elena = login('elena@cafeverde.demo')
priya = login('priya@novasalon.demo')  # staff at Nova & Co.

maria_leads = maria.get(f'{BASE}/api/leads').json()['items']
sam_leads = sam.get(f'{BASE}/api/leads').json()['items']
elena_leads = elena.get(f'{BASE}/api/leads').json()['items']

check('Nova & Co owner sees exactly 4 leads', len(maria_leads) == 4)
check('Summit owner sees exactly 3 leads', len(sam_leads) == 3)
check('Cafe Verde owner sees exactly 2 leads', len(elena_leads) == 2)

maria_ids = {l['id'] for l in maria_leads}
sam_ids = {l['id'] for l in sam_leads}
elena_ids = {l['id'] for l in elena_leads}
check('No lead id overlap between companies', not (maria_ids & sam_ids) and not (maria_ids & elena_ids) and not (sam_ids & elena_ids))

# --- cross-tenant access attempt: Nova owner tries to fetch Summit's lead by id ---
victim_id = list(sam_ids)[0]
r = maria.get(f'{BASE}/api/leads/{victim_id}')
check('Cross-tenant lead GET returns 404 (not leaked)', r.status_code == 404)

r = maria.patch(f'{BASE}/api/leads/{victim_id}', json={'status': 'won'})
check('Cross-tenant lead PATCH returns 404', r.status_code == 404)

r = maria.delete(f'{BASE}/api/leads/{victim_id}')
check('Cross-tenant lead DELETE returns 404', r.status_code == 404)

# confirm Summit's lead was NOT modified by the attempted cross-tenant patch
sam_leads_after = sam.get(f'{BASE}/api/leads').json()['items']
victim_after = next(l for l in sam_leads_after if l['id'] == victim_id)
check('Cross-tenant PATCH attempt did not change the victim lead status', victim_after['status'] != 'won')

# --- staff role restrictions ---
r = priya.get(f'{BASE}/api/leads')
check('Staff can list their own company leads', r.status_code == 200 and len(r.json()['items']) == 4)
some_id = r.json()['items'][0]['id']
r = priya.delete(f'{BASE}/api/leads/{some_id}')
check('Staff cannot delete leads (403)', r.status_code == 403)
r = priya.post(f'{BASE}/api/users', json={'name': 'X', 'email': 'x@example.com', 'role': 'staff'})
check('Staff cannot invite users (403)', r.status_code == 403)

# --- unauthenticated access ---
anon = requests.Session()
r = anon.get(f'{BASE}/api/leads')
check('Unauthenticated request to /api/leads is rejected (401)', r.status_code == 401)

# --- platform admin company switcher ---
admin = login('admin@forgetemplates.demo')
companies = admin.get(f'{BASE}/api/companies').json()
check('Platform admin sees all 3 companies', len(companies) == 3)

r = admin.get(f'{BASE}/api/leads')
check('Platform admin with no active company selected is blocked (400)', r.status_code == 400)

nova = next(c for c in companies if c['slug'] == 'nova-co-salon')
admin.post(f'{BASE}/api/companies/switch', json={'company_id': nova['id']})
r = admin.get(f'{BASE}/api/leads')
check("Platform admin switched into Nova & Co sees its 4 leads", r.status_code == 200 and len(r.json()['items']) == 4)

summit = next(c for c in companies if c['slug'] == 'summit-contracting')
admin.post(f'{BASE}/api/companies/switch', json={'company_id': summit['id']})
r = admin.get(f'{BASE}/api/leads')
check("Platform admin switched into Summit sees its 3 leads (not Nova's)", r.status_code == 200 and len(r.json()['items']) == 3)

# --- public site content + lead capture, duplicate prevention ---
r = requests.get(f'{BASE}/api/public/companies/nova-co-salon/content')
check('Public content endpoint returns theme=rose for Nova & Co.', r.status_code == 200 and r.json()['theme'] == 'rose')

r = requests.get(f'{BASE}/api/public/companies/does-not-exist/content')
check('Public content for unknown slug returns 404', r.status_code == 404)

payload = {'name': 'Isolation Test', 'email': 'isolation.test@example.com', 'phone': '555-9999', 'message': 'Testing public lead capture.'}
r1 = requests.post(f'{BASE}/api/public/companies/nova-co-salon/leads', json=payload)
check('Public lead submission succeeds (201)', r1.status_code == 201)
r2 = requests.post(f'{BASE}/api/public/companies/nova-co-salon/leads', json=payload)
check('Immediate resubmit is flagged as duplicate', r2.status_code == 200 and r2.json().get('duplicate') is True)

maria_leads_after = maria.get(f'{BASE}/api/leads').json()['items']
check('New public lead appears only for Nova & Co (5 total, not 6 from dup)', len(maria_leads_after) == 5)
sam_leads_final = sam.get(f'{BASE}/api/leads').json()['items']
check("Public lead to Nova & Co did not leak into Summit's leads", len(sam_leads_final) == 3)

# --- CSV export scoping ---
r = maria.get(f'{BASE}/api/leads/export')
csv_lines = [l for l in r.text.splitlines() if l.strip()]
check('Nova & Co CSV export has header + 5 data rows', len(csv_lines) == 6)

print()
if failures:
    print(f'{len(failures)} FAILURE(S):')
    for f in failures:
        print(' -', f)
    raise SystemExit(1)
else:
    print('ALL CHECKS PASSED')
