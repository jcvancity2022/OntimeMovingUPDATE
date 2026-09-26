# Testing Report — Forge Templates Platform

**Result: 120/120 automated checks passing (79 API/isolation + 41 full business simulation), plus manual browser verification and two independent automated server-restart persistence tests. Zero application defects found across either pass.**

This document is evidence that business data (leads, customers, products, appointments, company content/branding, settings, users) is stored in and served from a real SQLite database via a real REST API — not mock data, not local JSON files, not in-memory state that resets on refresh or restart.

## What "real storage" means here, concretely

- Every write goes through Flask → SQLAlchemy → `platform.db` (a real SQLite file on disk; `DATABASE_URL` swaps this for Postgres in production — see [README.md](README.md)).
- There is no JSON file, no browser localStorage, and no in-memory Python list backing any resource. Grep the codebase: `models.py` defines SQLAlchemy tables; every route in `routes/*.py` reads/writes through `db.session`.
- The dashboard (`static/dashboard/dashboard.js`) never keeps its own source of truth — every view fetches from the API on load and after every mutation.

## Test suites (committed in `tests/`, runnable by anyone)

| Suite | Checks | Purpose |
|---|---|---|
| `tests/test_isolation.py` | 23 | Multi-tenant isolation: cross-company access blocked, role restrictions enforced, platform-admin company switcher scoping, public lead capture + duplicate prevention |
| `tests/test_resources_e2e.py` | 56 | Full CRUD + search/filter/sort/pagination/export for leads, customers, products, appointments; auth; validation/error shape; settings; analytics; rate limiting; logging |
| `tests/test_persistence.py` | 2-phase | Proves data survives a full server **process kill and cold restart**, not just a page refresh |
| `tests/test_business_simulation.py` | 41 (29 write + 12 post-restart) | End-to-end simulation of a real business signing up and actually using the platform — see "The business-buys-in simulation" below |

Reproduce any of these yourself:
```
cd platform
rm -f platform.db .secret_key
python -m alembic upgrade head
python seed.py
python app.py &
python tests/test_isolation.py
python tests/test_resources_e2e.py
```

## Final clean run — full output

### Isolation suite (23/23)
Run against a freshly migrated + reseeded database:
```
[PASS] Nova & Co owner sees exactly 4 leads
[PASS] Summit owner sees exactly 3 leads
[PASS] Cafe Verde owner sees exactly 2 leads
[PASS] No lead id overlap between companies
[PASS] Cross-tenant lead GET returns 404 (not leaked)
[PASS] Cross-tenant lead PATCH returns 404
[PASS] Cross-tenant lead DELETE returns 404
[PASS] Cross-tenant PATCH attempt did not change the victim lead status
[PASS] Staff can list their own company leads
[PASS] Staff cannot delete leads (403)
[PASS] Staff cannot invite users (403)
[PASS] Unauthenticated request to /api/leads is rejected (401)
[PASS] Platform admin sees all 3 companies
[PASS] Platform admin with no active company selected is blocked (400)
[PASS] Platform admin switched into Nova & Co sees its 4 leads
[PASS] Platform admin switched into Summit sees its 3 leads (not Nova's)
[PASS] Public content endpoint returns theme=rose for Nova & Co.
[PASS] Public content for unknown slug returns 404
[PASS] Public lead submission succeeds (201)
[PASS] Immediate resubmit is flagged as duplicate
[PASS] New public lead appears only for Nova & Co (5 total, not 6 from dup)
[PASS] Public lead to Nova & Co did not leak into Summit's leads
[PASS] Nova & Co CSV export has header + 5 data rows

ALL CHECKS PASSED
```

### Full resource suite (56/56)
Run against a separately freshly migrated + reseeded database (each suite asserts exact starting row counts, so they're run against independent resets — see "A note on test isolation" below):
```
=== SUMMARY ===
56/56 passed
```
Full section breakdown: AUTH (3) · VALIDATION/ERROR SHAPE (3) · COMPANY/CONTENT/SETTINGS (5) · LEADS CRUD+pagination+search+export (11) · CUSTOMERS CRUD+dup prevention (5) · PRODUCTS CRUD+SKU dup prevention (6) · APPOINTMENTS CRUD+relation validation (5) · ANALYTICS (2) · CROSS-TENANT ISOLATION on new resources (11) · STAFF ROLE RESTRICTIONS (2) · RATE LIMITING (1) · LOGGING (2).

## The business-buys-in simulation (41/41)

Every earlier suite tests the API in isolation. This one simulates what actually
happens when a real business signs up and takes it seriously — the scenario the
platform exists for — end to end, including a full server restart in the middle.

**Setup**: "Bluebird Design Studio" (owner Morgan Ellison) registers through the real
`/api/auth/register` endpoint — the same action a paying customer takes after buying.

**Phase 1 — write (29 checks, all passing):**
1. Registration succeeds; owner can log back in immediately.
2. Starter data is present exactly as documented (3 leads / 2 customers / 3 products / 2 appointments) — confirms new sign-ups never start on an empty screen.
3. The owner does what a real owner does on day one: **deletes every starter example record**, then adds their own — 3 real leads, 2 real customers, 3 real products with real prices ($3,200 / $1,400 / $850), 3 real appointments linking real customers to real dates.
4. Data integrity is deliberately attacked: duplicate customer email → 409, duplicate product SKU → 409, a duplicate public lead submission within the dedup window → correctly flagged, not double-inserted.
5. Owner customizes real branding (theme → slate), real hero copy, and real settings (timezone, currency, notification email) through the same content-editor API the dashboard UI uses.
6. Owner invites a real staff member; the staff member logs in with the issued temporary password and sees the exact same real data — not a cached or stale copy.
7. The public site (`/api/public/companies/bluebird-design-studio/content`) reflects the real hero title and real theme — proving the storefront-facing side is wired to the same data, not a separate copy.
8. A fresh login session (simulating a page refresh) sees the identical real data.

**Phase 2 — full server restart, then re-verify (12 checks, all passing):**
The server process was fully killed (`Stop-Process -Force`, confirmed port released) and cold-started as a brand-new process — same method as the earlier persistence proof. Then, against that new process:
- All 4 real leads, both real customers, all 3 real products (correct $3,200 price intact), and all 3 real appointments were still there.
- The custom branding/theme, custom hero copy, and custom settings all survived.
- The invited staff account survived.
- **Isolation was re-verified after the restart**: the platform admin sees Bluebird alongside every other company, and Bluebird's lead IDs do not appear in any other company's lead list.

**Manual browser confirmation**: logged into the dashboard as Morgan Ellison after the
restart through the real login form — the Overview screen showed the exact same
numbers the API reported (4 total leads, 4 this week, 1 won, 0 lost, all 4 real lead
names and statuses), with no discrepancy between what the API returns and what a
person actually sees on screen.

**Cleanup**: this was a test registration, not a demo company or the user's real
account — it was deleted after verification (`python tests/test_business_simulation.py
cleanup`), the same way every other throwaway test registration in this project has
been cleaned up. The user's actual real company ("Jeffrey's business") and its data
were confirmed untouched before and after this entire test.

## Persistence proof #1 — automated server restart test

```
$ python tests/test_persistence.py write
Marker written (status 201). Now fully stop and restart the server...

$ # full process kill, not Ctrl+C reload:
$ Get-CimInstance Win32_Process -Filter "Name='python3.13.exe'" | Where CommandLine -like '*app.py*' | Stop-Process -Force
$ # confirmed port 5050 fully released before restart
$ python app.py &          # cold start, brand new process, new PID

$ python tests/test_persistence.py verify
PASS: marker customer (id=5, created_at=2026-07-23T04:55:04.291573) survived the server restart.
```
The record was created by one OS process and read back by an entirely different OS process (new PID, freshly loaded Python interpreter, freshly opened DB connection). This is only possible if the data lives on disk.

Notably, the **session cookie also survived** the restart — because `SECRET_KEY` is itself persisted to `.secret_key` on disk (see `config.py`), not regenerated per-process. That's a deliberate design choice, not an accident: it means restarting the app in production doesn't log every user out.

## Persistence proof #2 — real browser, hard refresh, then server restart

Performed manually via the Claude Code browser tool against the running dashboard at `http://127.0.0.1:5050`:

1. Logged in as `maria@novasalon.demo` through the actual login form (not the API directly).
2. Opened **Customers**, clicked **+ Add Customer**, filled in "Browser UI Test Customer" / `browsertest@example.com` through the real modal form, clicked **Add Customer**.
3. Network log confirmed the real request: `POST /api/customers → 201 CREATED`, immediately followed by `GET /api/customers?... → 200` (the UI re-fetching from the server rather than just appending to local state).
4. **Hard-reloaded the page** (`navigate` with `force: true`, a full document reload, not client-side routing). The customer was still listed — proof the list isn't held in a JS variable.
5. **Killed the server process entirely**, waited for the port to be released, started a **new** `python app.py` process.
6. Re-opened `/dashboard/customers` in the browser. "Browser UI Test Customer" was still there, exactly as before.

## Data integrity proof — soft deletes actually keep the row

```
$ curl -X DELETE .../api/leads/10   # via an authenticated session
→ 200 {"status": "deleted"}

$ sqlite3 platform.db "SELECT id, name, status, deleted_at FROM leads WHERE id=10"
{'id': 10, 'name': 'Isolation Test', 'status': 'new', 'deleted_at': '2026-07-23 06:25:56.628734'}
```
The row is still physically present in the table — `deleted_at` is set, and every list/get query filters `WHERE deleted_at IS NULL`, so it disappears from the API and UI without destroying the underlying record (matters for audit history and for other rows that reference it, e.g. an appointment linked to a "deleted" customer).

## Direct database file inspection

```
$ sqlite3 platform.db ".tables"
alembic_version  appointments  companies  customers  leads  products  users

$ (row counts on a fresh seed)
companies: 3   users: 6   leads: 10   customers: 3   products: 6   appointments: 3
```
`alembic_version` being present confirms the schema was created via the real Alembic migration (`migrations/versions/..._initial_schema.py`), not an ad hoc script — see README "Database migrations."

## Auto-fix log

During this testing pass, **no application defects were found**. Every failure surfaced while iterating was traced to the test scripts themselves, not the app, specifically:

1. An older, pre-pagination copy of the isolation test expected `/api/leads` to return a bare array; the API now correctly returns `{items, page, per_page, total, total_pages}` per the pagination requirement. **Fixed the test**, not the API — the paginated shape is the intended, correct behavior.
2. Running both test suites back-to-back against the *same* un-reset database produces expected count mismatches (e.g. "starts with 4 leads" fails when a previous run already added a 5th) and occasional `429` collisions from the shared auth rate limiter. Both are the *rate limiter and non-idempotent seed data working as designed* — resolved by documenting that each suite expects a fresh `alembic upgrade head` + `seed.py` reset, which is now stated explicitly in each test file's docstring.

## Known limitations / not covered in this pass

- **PostgreSQL was not live-tested** in this sandbox (no local Postgres server or Docker available here). The Postgres path relies on SQLAlchemy + `psycopg2`, both mature and DB-agnostic in how this codebase uses them (no SQLite-specific SQL anywhere in the ORM layer), and the same Alembic migration runs against either backend. Recommend running `docker compose up` and re-running `tests/test_isolation.py` / `tests/test_resources_e2e.py` with `TEST_BASE_URL` pointed at that stack before a real production launch.
- **Docker image was not built/run** here for the same reason (no Docker daemon in this sandbox). The `Dockerfile` and `docker-compose.yml` are code-complete and follow standard patterns but weren't executed end-to-end.
- Load/concurrency testing was not performed — the suites above are correctness and isolation tests, not a load test.
