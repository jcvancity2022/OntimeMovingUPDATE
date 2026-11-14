# Booking automation tests

End-to-end tests that book a move on the website exactly like a customer, then check the
record in the Supabase SQL database — and delete every test booking afterwards.

| Test | What it proves |
|---|---|
| `test_customer_booking_is_recorded` | Filling in **Book Now** saves a booking with exactly what was typed (name, email, addresses, date, window, size, notes) and the window's "crews left" drops by one |
| `test_full_window_is_greyed_out_and_refused` | When the last crew is taken, the window shows **Fully booked**, can't be selected, and the database refuses another booking |
| `test_no_double_booking_when_customers_race` | 6 customers grabbing the last crew at the same instant → exactly **one** booking succeeds |
| `test_bad_bookings_are_rejected` (×4) | Bad email, past date, unknown window and missing name are refused by the database itself |
| `test_visitors_cannot_read_customer_data` | Without a staff login nobody can list bookings or read the table |
| `test_new_booking_shows_in_admin_dashboard` | After signing in, a new booking appears in the admin table |

Test bookings are named `AUTOTEST …`, use `@example.com` emails, and go on dates about 10 months
ahead, so real customers are never affected.

**You can see them in the dashboard.** When a test finishes (pass or fail), its bookings are switched
to status **test**: they appear in the admin table with a purple *test* badge and a
"🧪 test bookings from the latest automated test run" bar, but they **don't use any crews** and
aren't counted in the booking stats. Each new run first removes the previous run's test bookings,
so only the latest run is ever shown. Click **Remove test bookings** in that bar to clear them
yourself, or set `ONTIME_DELETE_TEST_DATA=1` to have the tests delete them instead.

## Run on your computer (Windows)
Double-click **`run_booking_tests.bat`** in the project folder. The first run sets everything up
(about a minute). It asks for your staff email and password (the password is hidden and never
saved) and whether you want to watch the browser.

Or from a terminal:
```bash
cd tests/e2e
pip install -r requirements.txt
python -m playwright install chromium
set ONTIME_STAFF_EMAIL=you@example.com          # PowerShell: $env:ONTIME_STAFF_EMAIL="..."
set ONTIME_STAFF_PASSWORD=your-password
python -m pytest
```

## Run automatically on GitHub
`.github/workflows/booking-tests.yml` runs the tests after every site deploy, every morning,
and whenever you press **Run workflow** (Actions tab → Booking tests). One-time setup:
**GitHub repo → Settings → Secrets and variables → Actions → New repository secret**, add
`ONTIME_STAFF_EMAIL` and `ONTIME_STAFF_PASSWORD`. If a run fails, GitHub emails you and the
run page has screenshots of what the browser saw.

## Options
| Variable | Default | Use |
|---|---|---|
| `ONTIME_BASE_URL` | live GitHub Pages site | test a local copy, e.g. `http://localhost:8080` |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | read from `api-config.js` | test against a different Supabase project |
| `ONTIME_HEADED=1` | off | show the browser while testing |
| `ONTIME_DELETE_TEST_DATA=1` | off | delete test bookings instead of keeping the latest run visible |
