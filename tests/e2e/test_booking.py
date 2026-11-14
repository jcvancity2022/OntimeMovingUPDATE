"""
OnTime Moving — booking automation tests.

Each test books like a real customer, checks the record in the SQL database,
and deletes its test bookings afterwards. Test bookings use names starting
with "AUTOTEST" and @example.com emails, on dates ~10 months ahead.

Run:  pytest tests/e2e -v
"""
import re
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pytest
from playwright.sync_api import expect

from conftest import BASE_URL, find_date, today_bc, unique_customer

SLOT_LAST = "14:00-16:00"     # the 1-crew window — easiest to fill
SLOT_MORNING = "08:00-10:00"


def tap(page, selector):
    """Scroll an element to the middle of the screen (clear of the sticky header and
    bottom banner), then click it — the way a real visitor would."""
    el = page.locator(selector).first
    el.evaluate("e => e.scrollIntoView({block: 'center'})")
    el.click()


def open_booking_page(page, date):
    page.goto(f"{BASE_URL}/booknow.html")
    page.fill("#moveDate", date.isoformat())
    page.dispatch_event("#moveDate", "change")
    expect(page.locator("#slotGrid .slot-option small").first).to_be_visible(timeout=15_000)


# --------------------------------------------------------------------------
def test_customer_booking_is_recorded(page, sb, created):
    """Fill the Book Now form → booking saved in SQL with exactly what was typed."""
    date = find_date(sb, SLOT_MORNING)
    before = sb.availability(date)[SLOT_MORNING]["remaining"]
    c = unique_customer()

    open_booking_page(page, date)
    page.fill("#name", c["name"])
    page.fill("#phone", c["phone"])
    page.fill("#email", c["email"])
    page.fill("#movingFrom", c["from"])
    page.fill("#movingTo", c["to"])
    page.select_option("#moveSize", "2-bedroom")
    tap(page, f'label.slot-option:has(input[value="{SLOT_MORNING}"])')
    page.fill("#moveDetails", "Automated test — piano on the 2nd floor")
    tap(page, ".submit-btn")

    toast = page.locator(".toast.success")
    expect(toast).to_contain_text("Booking Submitted", timeout=15_000)
    booking_id = int(re.search(r"Booking ID: (\d+)", toast.inner_text()).group(1))
    created.append(booking_id)

    rec = sb.get_booking(booking_id)
    assert rec["customer_name"] == c["name"]
    assert rec["email"] == c["email"]
    assert rec["moving_from"] == c["from"] and rec["moving_to"] == c["to"]
    assert rec["move_date"] == date.isoformat()
    assert rec["preferred_time"] == SLOT_MORNING
    assert rec["move_size"] == "2-bedroom"
    assert rec["status"] == "pending"
    assert "piano" in (rec["notes"] or "")
    assert sb.availability(date)[SLOT_MORNING]["remaining"] == before - 1


def test_full_window_is_greyed_out_and_refused(page, sb, created):
    """When the last crew is taken, the window shows 'Fully booked' and can't be booked."""
    date = find_date(sb, SLOT_LAST)
    r = sb.book(unique_customer(), date, SLOT_LAST)
    assert r.ok, r.text
    created.append(r.json())

    open_booking_page(page, date)
    radio = page.locator(f'input[name="preferredTime"][value="{SLOT_LAST}"]')
    expect(radio).to_be_disabled()
    expect(page.locator(f'label.slot-option:has(input[value="{SLOT_LAST}"])')).to_contain_text("Fully booked")

    second = sb.book(unique_customer(), date, SLOT_LAST)
    assert not second.ok and "slot_full" in second.text


def test_no_double_booking_when_customers_race(sb, created):
    """Six customers grab the last crew at the same instant → exactly one wins."""
    date = find_date(sb, SLOT_LAST)
    customers = [unique_customer() for _ in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda c: sb.book(c, date, SLOT_LAST), customers))

    winners = [r for r in results if r.ok]
    created.extend(r.json() for r in winners)
    assert len(winners) == 1, [r.text for r in results]
    assert all("slot_full" in r.text for r in results if not r.ok)


@pytest.mark.parametrize("change, error", [
    ({"email": "not-an-email"}, "invalid_email"),
    ({"date": "past"}, "date_in_past"),
    ({"slot": "25:00-26:00"}, "unknown_slot"),
    ({"name": ""}, "missing_fields"),
])
def test_bad_bookings_are_rejected(sb, change, error):
    """The database refuses invalid bookings, whatever the website sends."""
    c = unique_customer()
    if "email" in change:
        c["email"] = change["email"]
    if "name" in change:
        c["name"] = change["name"]
    date = today_bc() - dt.timedelta(days=1) if change.get("date") == "past" else today_bc() + dt.timedelta(days=330)
    r = sb.book(c, date, change.get("slot", SLOT_MORNING))
    assert not r.ok and error in r.text, r.text


def test_visitors_cannot_read_customer_data(sb):
    """Without a staff login, nobody can list bookings or read the table."""
    from conftest import Supabase, SUPABASE_URL, SUPABASE_KEY
    import requests
    anon = Supabase(SUPABASE_URL, SUPABASE_KEY)
    assert anon.rpc("staff_list_bookings").status_code in (401, 403)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/bookings?select=*", headers=anon._headers(staff=False), timeout=20)
    assert r.status_code in (401, 403) or r.json() == [], r.text


def test_new_booking_shows_in_admin_dashboard(page, sb, created):
    """A booking appears in the staff dashboard after signing in."""
    import os
    c = unique_customer()
    date = find_date(sb, SLOT_MORNING)
    r = sb.book(c, date, SLOT_MORNING)
    assert r.ok, r.text
    created.append(r.json())

    page.goto(f"{BASE_URL}/login.html")
    page.fill("#username", os.environ["ONTIME_STAFF_EMAIL"])
    page.fill("#password", os.environ["ONTIME_STAFF_PASSWORD"])
    tap(page, "button[type=submit]")
    page.wait_for_url("**/admin.html", timeout=15_000)
    row = page.locator("#bookingsTableBody tr", has_text=c["email"])
    expect(row).to_be_visible(timeout=15_000)
    expect(row).to_contain_text(c["name"])
    expect(row).to_contain_text("pending")
