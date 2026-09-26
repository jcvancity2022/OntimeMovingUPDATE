# Forge Templates Platform

A production-grade, multi-tenant SaaS backend: many small businesses ("companies") each
get their own public marketing site and a private dashboard for managing leads,
customers, products/services, appointments and content — all served from one Flask API
and one database, with strict data isolation between tenants.

**All business data is stored in a real database via a real REST API — SQLite locally,
PostgreSQL in production (same code, swapped by `DATABASE_URL`). Nothing is mocked, and
nothing lives only in the browser.** See [TESTING.md](TESTING.md) for the full
verification report (79 automated checks, a server-restart persistence test, and manual
browser verification).

This is the backend for the storefront/template concept in `../storefront` and
`../products/promax-business`. Those two folders are the single-tenant, "download and
run yourself" version of the template. This `platform/` folder is the hosted,
multi-company SaaS evolution.

## Architecture

```
platform/
  app.py                 Flask app factory, blueprint + extension registration
  config.py               DATABASE_URL / SECRET_KEY / rate-limit / logging config
  extensions.py            Shared SQLAlchemy + Flask-Limiter instances
  models.py                 SQLAlchemy models: Company, User, Lead, Customer, Product, Appointment
  db.py                     Table creation (create_all fallback for zero-config first run)
  auth.py                   Password hashing, sessions, role + company-scope decorators
  errors.py                  Centralized error handlers + structured logging setup
  pagination.py              Shared paginate() helper for all list endpoints
  leads_service.py           Shared lead-creation + duplicate-prevention logic
  utils.py                   Slugs, email validation, default site content
  seed.py                    Demo data — guarded against running in production
  routes/
    auth_routes.py            Register / login / logout / me
    company_routes.py          Branding+content, platform-admin company switcher
    settings_routes.py         Company profile: timezone, currency, notification email
    leads_routes.py             Leads CRUD, search/filter/sort/paginate, CSV export, stats
    customers_routes.py          Customers CRUD, duplicate-email prevention
    products_routes.py            Products/services CRUD, duplicate-SKU prevention
    appointments_routes.py         Appointments CRUD, linked to customers/leads
    analytics_routes.py             Aggregated stats across all resources
    users_routes.py                  Staff invite / role change / removal
    public_routes.py                  Unauthenticated: public site content + lead capture
  migrations/                Alembic migrations (schema history for production upgrades)
  tests/                     Automated test suites — see TESTING.md
  scripts/                   Backup/restore scripts (SQLite + Postgres)
  static/
    dashboard/                The admin dashboard (single-page app, no build step)
    public/                    The public site template, rendered per company
  Dockerfile, docker-compose.yml    Production container setup
```

### Multi-tenant data model

Six tables, every business-data row tagged with `company_id`:

- **companies** — name, slug (public URL + API), theme, branding, `content_json` (site
  copy), plus `timezone`/`currency`/`notification_email` settings.
- **users** — `role` is `owner`, `staff`, or `platform_admin`. Owners/staff have a fixed
  `company_id`; platform admins have `company_id = NULL` and pick an "active company"
  per session via the dashboard's company switcher.
- **leads**, **customers**, **products**, **appointments** — each has `company_id`,
  `created_at`/`updated_at` audit timestamps, and a `deleted_at` **soft-delete** column
  (see "Data integrity" below). Appointments optionally link to a `customer_id` and/or
  `lead_id`, both validated to belong to the same company.

### Security model — how isolation is enforced

The single choke point is `auth.get_active_company_id()`:

- For `owner`/`staff` it always returns their fixed `company_id` from the session —
  never from request input, so it can't be spoofed.
- For `platform_admin` it returns whichever company they've explicitly switched into,
  and returns `None` (→ HTTP 400) until they pick one.

Every company-scoped route is wrapped in `@company_scope_required`, and every query in
`routes/*.py` filters on that `company_id`. A user from Company A requesting another
company's record by ID gets a 404 — the row is filtered out of the query, not just
permission-checked after the fact. Verified by `tests/test_isolation.py` across leads,
and `tests/test_resources_e2e.py` across customers, products and appointments.

Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2). Sessions are
Flask's signed cookie sessions — same-origin, httponly, `SameSite=Lax`; the secret key
persists to `.secret_key` across restarts (or set `SECRET_KEY` in `.env` for
production) so restarting the app doesn't log everyone out. `/api/public/*` routes
allow CORS from any origin (a business may host their static site elsewhere and POST
leads here); every other route is same-origin, cookie-authenticated only.

### Production hardening

- **Rate limiting** (Flask-Limiter): auth endpoints capped at `RATE_LIMIT_AUTH`
  (default 10/min) to blunt credential-stuffing; a global default limit
  (`RATE_LIMIT_DEFAULT`, default 200/min) on everything else. In-memory storage by
  default — set `RATE_LIMIT_STORAGE_URI` to Redis for a multi-process deployment.
- **Centralized error handling** (`errors.py`): every error response — validation,
  auth, not-found, rate-limit, or an unhandled exception — comes back as
  `{"error": "...", "code": "MACHINE_CODE"}` with the right HTTP status, never a raw
  stack trace or an HTML error page.
- **Logging**: every request logs `METHOD path -> status (Nms)` to `logs/platform.log`
  (rotating, 5×2MB) and stdout; unhandled exceptions log a full traceback.
- **Pagination**: every list endpoint (`leads`, `customers`, `products`, `appointments`)
  takes `?page=&per_page=` and returns `{items, page, per_page, total, total_pages}`.
- **Search / filter / sort**: `?q=` (text search), `?status=` (status filter), `?sort=`
  (column, prefix `-` for descending) on every list endpoint.
- **Duplicate prevention**: leads dedupe by (company, email, message) within a 5-minute
  window (configurable via `DUPLICATE_LEAD_WINDOW_SECONDS`); customers reject a
  duplicate email (409); products reject a duplicate SKU (409).
- **Soft deletes**: `DELETE` endpoints set `deleted_at` instead of removing the row.
  Every list/get query filters `deleted_at IS NULL`. This preserves history and avoids
  breaking foreign keys from other rows (e.g. an appointment referencing a "deleted"
  customer). See TESTING.md for a direct database proof.
- **Transactions**: multi-step writes (e.g. registering a company + its owner user) run
  in one SQLAlchemy session and commit together — either both persist or neither does.

### Starter data on registration

Every new company — regardless of which storefront pricing tier they bought — gets a
small, clearly-labeled example dataset at registration (`starter_data.py`), not an
empty dashboard: 3 leads showing the pipeline (new → contacted → won), 2 example
customers, a 3-tier example service catalog, and both an upcoming and a completed
appointment linking a customer to a service. This is ordinary data through the same
CRUD endpoints as anything else — fully editable and deletable, not a special "demo
mode." It exists purely so a first-time owner sees a working example of the data shape
instead of a blank screen, and can replace it with their real business structure.
This is separate from (and always runs, unlike) `seed.py`'s demo companies, which are
gated behind `ALLOW_SEED` and never touch a real registration.

## Local setup

```
pip install -r requirements.txt
copy .env.example .env      (or: cp .env.example .env)
python -m alembic upgrade head    # creates the schema (or db.create_all() runs automatically on first `python app.py` if you skip this)
python seed.py                     # creates 6 demo companies across different verticals + a platform admin
python app.py
```

Open `http://localhost:5050`.

**Demo logins** (all use password `Demo1234!`) — 6 companies spanning different
verticals, each with a full spread of leads, customers, products/listings and
appointments so every dashboard view has something real to show:

| Company | Vertical | Owner | Staff |
|---|---|---|---|
| Nova & Co. Salon | Salon | maria@novasalon.demo | priya@novasalon.demo |
| Summit Contracting | Trades/contracting | sam@summitcontracting.demo | riley@summitcontracting.demo |
| Cafe Verde | Café/retail | elena@cafeverde.demo | noah@cafeverde.demo |
| Coastal Moving Co. | Moving/logistics | jordan@coastalmoving.demo | casey@coastalmoving.demo |
| Flow State Studio | Fitness/yoga (appointment-heavy) | nina@flowstatestudio.demo | owen@flowstatestudio.demo |
| Harbor View Realty | Real estate (products as listings) | morgan@harborviewrealty.demo | taylor@harborviewrealty.demo |

Platform admin (can switch between all companies, including any real ones registered
on this instance): `admin@forgetemplates.demo`

Each company's public site is live at `http://localhost:5050/site/<slug>`, e.g.
`/site/nova-co-salon`.

## Demo vs. production data

`seed.py` refuses to run when `FLASK_ENV=production` unless you explicitly set
`ALLOW_SEED=1` — demo companies must never land in a real deployment by accident. Demo
users all use `@*.demo` email addresses so they're trivially identifiable and never
collide with a real signup.

## Database migrations

Schema changes go through Alembic, not ad hoc SQL:

```
# after changing models.py:
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

`db.create_all()` (called on every app startup) is a no-op against tables that already
exist, so it's safe to leave as a zero-config fallback for first-time local setup — but
a deployed instance with real data should always go through `alembic upgrade head`,
never rely on `create_all()` for schema changes.

## Deploying

### Docker (recommended)
```
cp .env.example .env    # set a real SECRET_KEY
docker compose up --build
```
This starts a Postgres container plus the app (gunicorn, 4 workers), running
`alembic upgrade head` automatically before serving. See `Dockerfile` /
`docker-compose.yml`.

### Render / Railway / DigitalOcean App Platform
All three follow the same shape:
1. Point the platform at this `platform/` directory as the app root.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `python -m alembic upgrade head && gunicorn -w 4 -b 0.0.0.0:$PORT app:app`.
4. Add a managed Postgres database (all three offer one) and set `DATABASE_URL` to its
   connection string — Render/Railway inject this automatically when you attach their
   Postgres add-on.
5. Set `SECRET_KEY` to a long random value (`python -c "import secrets; print(secrets.token_hex(32))"`).
6. Set `FLASK_ENV=production`. Leave `ALLOW_SEED` unset.
7. Optional: `RATE_LIMIT_STORAGE_URI` to a Redis add-on's URL if you run more than one
   app instance (the default in-memory limiter doesn't share state across processes).

## Backup and restore

```
# SQLite (local dev / small deployments)
python scripts/backup_sqlite.py backup --keep 10
python scripts/backup_sqlite.py restore backups/platform_20260101_120000.db

# PostgreSQL (production)
DATABASE_URL=postgresql://... ./scripts/backup_postgres.sh --keep 10
DATABASE_URL=postgresql://... ./scripts/restore_postgres.sh backups/platform_20260101_120000.sql.gz
```
Restoring always makes a safety copy of the current database first (SQLite:
`platform.db.before-restore`).

## Customizing branding and website content

All public-site copy lives in `companies.content_json`. The dashboard's Content &
Branding page edits the common fields (hero, about, CTA, footer) as a form, plus an
"Advanced: edit full content JSON" textarea for arrays (features, testimonials, hero
stats) not covered by the quick-edit fields. `brand_name`, `brand_accent`, and `theme`
(`default`/`emerald`/`rose`/`slate`/`sunset`) are separate columns, also editable there.

## UX notes

- **Unsaved-changes warning**: editing Content & Branding or Settings without saving
  triggers a confirmation before navigating away in-app, and a native browser warning
  on tab close/refresh.
- **Loading states**: skeleton placeholders while data loads; buttons disable during
  in-flight requests.
- **Toasts**: every save/delete/error surfaces a toast — no silent failures.
- **Responsive**: sidebar collapses to a slide-out drawer under 980px; tables scroll
  horizontally rather than breaking layout.

## Testing

See [TESTING.md](TESTING.md) for the full verification report. Quick version:
```
cd platform
rm -f platform.db .secret_key && python -m alembic upgrade head && python seed.py
python app.py &
python tests/test_isolation.py        # 23 checks
python tests/test_resources_e2e.py    # 56 checks
python tests/test_persistence.py write   # then restart the server, then:
python tests/test_persistence.py verify
```

## Not included (intentional scope cuts for this starter kit)

- Outbound email (staff invites show a one-time password instead of emailing it; no
  "forgot password" flow yet).
- Company deletion / self-service billing — add before charging real customers.
- A distinct "customer detail page" beyond the customers table — appointments link to
  customers, and leads have a status pipeline, but there's no combined 360° customer
  timeline view yet.
