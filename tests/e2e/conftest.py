"""
Shared setup for the OnTime booking automation tests.

Configuration (environment variables — all optional except the staff login):

  ONTIME_STAFF_EMAIL      staff login used to verify and clean up test bookings
  ONTIME_STAFF_PASSWORD   (never commit these — set them in your terminal or as
                           GitHub Actions secrets)
  ONTIME_BASE_URL         site to test. Default: the live GitHub Pages site
  SUPABASE_URL            Supabase project. Default: read from api-config.js
  SUPABASE_ANON_KEY       public key.       Default: read from api-config.js
  ONTIME_HEADED=1         show the browser while the tests run
"""
import os
import re
import uuid
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import requests
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
BC = ZoneInfo("America/Vancouver")
TEST_EMAIL_DOMAIN = "example.com"          # reserved domain — never a real customer
TEST_NAME_PREFIX = "AUTOTEST"


def _from_api_config(name: str) -> str:
    m = re.search(rf"const {name} = '([^']*)'", (REPO / "api-config.js").read_text(encoding="utf-8"))
    return m.group(1) if m else ""


BASE_URL = os.getenv("ONTIME_BASE_URL", "https://jcvancity2022.github.io/OntimeMovingUPDATE").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL") or _from_api_config("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY") or _from_api_config("SUPABASE_ANON_KEY")


def today_bc() -> dt.date:
    return dt.datetime.now(BC).date()


def unique_customer() -> dict:
    tag = uuid.uuid4().hex[:8]
    return {
        "name": f"{TEST_NAME_PREFIX} {tag}",
        "email": f"autotest+{tag}@{TEST_EMAIL_DOMAIN}",
        "phone": "604-555-0100",
        "from": "100 Test St, Port Coquitlam, BC",
        "to": "200 Sample Ave, Burnaby, BC",
    }


class Supabase:
    """Small client for the SQL functions in supabase/schema.sql."""

    def __init__(self, url: str, key: str):
        self.url, self.key = url.rstrip("/"), key
        self.staff_token = None

    def _headers(self, staff: bool) -> dict:
        h = {"apikey": self.key, "Content-Type": "application/json"}
        if staff:
            h["Authorization"] = f"Bearer {self.staff_token}"
        elif self.key.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.key}"
        return h

    def rpc(self, fn: str, staff: bool = False, **args) -> requests.Response:
        return requests.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, headers=self._headers(staff), timeout=20)

    def sign_in(self, email: str, password: str) -> None:
        r = requests.post(f"{self.url}/auth/v1/token?grant_type=password",
                          json={"email": email, "password": password},
                          headers={"apikey": self.key, "Content-Type": "application/json"}, timeout=20)
        assert r.ok, f"Staff sign-in failed ({r.status_code}). Check ONTIME_STAFF_EMAIL / ONTIME_STAFF_PASSWORD."
        self.staff_token = r.json()["access_token"]

    # -- helpers used by the tests --
    def availability(self, date: dt.date) -> dict:
        r = self.rpc("get_availability", p_date=date.isoformat())
        assert r.ok, r.text
        return {s["code"]: s for s in r.json()["slots"]}

    def book(self, customer: dict, date: dt.date, slot: str) -> requests.Response:
        return self.rpc("book_slot", p_customer_name=customer["name"], p_phone=customer["phone"],
                        p_email=customer["email"], p_moving_from=customer["from"], p_moving_to=customer["to"],
                        p_move_date=date.isoformat(), p_move_size="studio", p_preferred_time=slot)

    def get_booking(self, booking_id: int) -> dict:
        r = self.rpc("staff_get_booking", staff=True, p_id=booking_id)
        assert r.ok, r.text
        return r.json()

    def delete_booking(self, booking_id: int) -> None:
        self.rpc("staff_delete_booking", staff=True, p_id=booking_id)

    def leftover_test_bookings(self) -> list:
        r = self.rpc("staff_list_bookings", staff=True, p_search=TEST_NAME_PREFIX)
        return [b for b in (r.json() if r.ok else [])
                if b["customer_name"].startswith(TEST_NAME_PREFIX) and b["email"].endswith("@" + TEST_EMAIL_DOMAIN)]


@pytest.fixture(scope="session")
def sb() -> Supabase:
    assert SUPABASE_URL and SUPABASE_KEY, "Supabase URL/key not found in api-config.js or environment."
    email, password = os.getenv("ONTIME_STAFF_EMAIL"), os.getenv("ONTIME_STAFF_PASSWORD")
    if not (email and password):
        pytest.exit("Set ONTIME_STAFF_EMAIL and ONTIME_STAFF_PASSWORD (a staff login) — the tests use it "
                    "to verify each booking and delete it afterwards.", returncode=2)
    client = Supabase(SUPABASE_URL, SUPABASE_KEY)
    client.sign_in(email, password)
    yield client
    # Safety net: remove anything a crashed test left behind
    for b in client.leftover_test_bookings():
        client.delete_booking(b["id"])


@pytest.fixture
def created(sb):
    """Collects booking IDs a test creates; deletes them when the test ends (pass or fail)."""
    ids = []
    yield ids
    for i in ids:
        sb.delete_booking(i)


def find_date(sb: Supabase, slot: str, need_empty: bool = True, start_days: int = 300) -> dt.date:
    """A date far ahead (so real customers aren't affected) where `slot` has no bookings yet."""
    for offset in range(start_days, 365):
        d = today_bc() + dt.timedelta(days=offset)
        s = sb.availability(d).get(slot)
        if s and s["available"] and (not need_empty or s["booked"] == 0):
            return d
    pytest.fail(f"No free date found for slot {slot}")


# ---------------------------------------------------------------- browser
@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=os.getenv("ONTIME_HEADED") != "1")
        yield b
        b.close()


@pytest.fixture
def page(browser, request):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, timezone_id="America/Vancouver")
    # When testing against a different Supabase project than the one in api-config.js
    # (e.g. a test project), point the page at it without editing the site.
    if os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_ANON_KEY"):
        def rewrite(route):
            body = route.fetch().text()
            body = re.sub(r"const SUPABASE_URL = '[^']*'", f"const SUPABASE_URL = '{SUPABASE_URL}'", body)
            body = re.sub(r"const SUPABASE_ANON_KEY = '[^']*'", f"const SUPABASE_ANON_KEY = '{SUPABASE_KEY}'", body)
            route.fulfill(body=body, content_type="application/javascript")
        ctx.route("**/api-config.js*", rewrite)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    yield pg
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        ARTIFACTS.mkdir(exist_ok=True)
        pg.screenshot(path=str(ARTIFACTS / f"{request.node.name}.png"), full_page=True)
    ctx.close()
    assert not errors, f"JavaScript errors on the page: {errors}"


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
