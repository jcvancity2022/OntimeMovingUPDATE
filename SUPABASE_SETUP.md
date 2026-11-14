# Connecting the live site to Supabase (SQL database)

GitHub Pages can only serve files, so the live site keeps its bookings and live chats in a free
**Supabase** PostgreSQL database. All the logic lives in SQL (`supabase/schema.sql`):

| What | How it works in SQL |
|---|---|
| Crew arrival windows | `time_slots` table — 4 windows, each with a crew `capacity` |
| Availability | `get_availability(date)` counts active bookings per window |
| Booking | `book_slot(...)` locks the window's row (`FOR UPDATE`), checks capacity, inserts — so the last crew can never be double-booked |
| Closed days | add a row to `blocked_dates` |
| Live chat | `live_chats` + `live_chat_messages`, visitor proves ownership with a secret token |
| Staff dashboard | `staff_*` functions only work for signed-in users listed in `staff` |
| Security | Row Level Security on every table; the public key can't read any table directly |

Takes about 10 minutes.

## 1. Create the project
1. Sign up at **supabase.com** (free plan is fine) → **New project**.
2. Name it `ontime-moving`, choose a strong database password (save it somewhere), region **Canada (Central)** or **US West**.
3. Wait ~2 minutes for it to finish setting up.

## 2. Create the tables and functions
1. Left sidebar → **SQL Editor** → **New query**.
2. Open `supabase/schema.sql` from this repo, copy **all** of it, paste, click **Run**.
3. You should see "Success. No rows returned". (It's safe to run again after future updates.)

## 3. Create your staff login
1. Left sidebar → **Authentication** → **Users** → **Add user** → **Create new user**.
   Enter your email and a password, and tick **Auto Confirm User**.
2. Back in **SQL Editor**, run (change the email and name):
   ```sql
   insert into public.staff (user_id, display_name)
   select id, 'Jeffrey' from auth.users where email = 'you@example.com';
   ```
   `display_name` is what visitors see in live chat ("Jeffrey joined the chat").
3. Recommended: **Authentication → Sign In / Providers** → turn off **Allow new users to sign up**,
   so only accounts you create can exist. (Others couldn't see anything anyway — they're not in `staff`.)

## 4. Connect the website
1. **Project Settings → API** (or **API Keys**). Copy:
   - **Project URL** — like `https://abcdefghijkl.supabase.co`
   - the **anon / publishable** key — starts with `eyJ…` or `sb_publishable_…`
   - ⚠️ **Never** use the `service_role` / secret key in the website.
2. Open `api-config.js` and paste them in:
   ```js
   const SUPABASE_URL = 'https://abcdefghijkl.supabase.co';
   const SUPABASE_ANON_KEY = 'sb_publishable_…';
   ```
3. Commit and push. GitHub Pages updates in a minute or two.

## 5. Try it
- **Book Now** → pick a date → the arrival windows show "2 crews available" from the database.
- **login.html** → sign in with your staff email → bookings and the **Live Chat** inbox load from Supabase.
- Open the site on your phone, tap **Chat with us → Talk to a person**, and reply from the dashboard.

## Day-to-day
- **Change crew numbers:** Table Editor → `time_slots` → edit `capacity` (0 closes that window).
- **Close a day:** Table Editor → `blocked_dates` → insert a row with the date and a reason.
- **Free plan note:** Supabase pauses a free project after a week with no activity; it wakes up when you
  open the dashboard. Regular site traffic keeps it awake.

## Local development
Running `python server.py` still works exactly as before (SQLite, plus the Groq AI assistant).
When the site is served by Flask on port 5000 it uses Flask; everywhere else it uses Supabase once
the keys are set. The AI assistant only runs with server.py — on the Supabase-only live site the chat
answers common questions itself and hands off to a real person.
