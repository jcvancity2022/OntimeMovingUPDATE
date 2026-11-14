-- =============================================================================
--  OnTime Moving & Storage — Supabase (PostgreSQL) schema
--
--  Paste this whole file into Supabase → SQL Editor → Run. Safe to re-run.
--
--  Security model
--    • Row Level Security is ON for every table and the website's public key
--      (role "anon") has NO direct table access at all.
--    • Visitors can only call the narrow functions marked "PUBLIC" below:
--      check availability, book a slot, and use their own live chat (proved
--      by a secret per-chat token).
--    • Staff sign in with Supabase Auth; functions marked "STAFF" check that
--      the signed-in user is listed in public.staff before doing anything.
-- =============================================================================

set check_function_bodies = off;

-- -----------------------------------------------------------------------------
--  Tables
-- -----------------------------------------------------------------------------
create table if not exists public.time_slots (
    code        text primary key,                        -- e.g. '08:00-10:00'
    label       text not null,
    start_time  time not null,
    end_time    time not null,
    capacity    integer not null default 1 check (capacity >= 0),   -- crews per window
    sort_order  integer not null default 0,
    active      boolean not null default true
);

create table if not exists public.blocked_dates (
    block_date  date primary key,
    reason      text,
    created_at  timestamptz not null default now()
);

create table if not exists public.bookings (
    id                   bigint generated always as identity primary key,
    customer_name        text not null check (length(customer_name) between 1 and 120),
    phone                text not null check (length(phone) between 3 and 40),
    email                text not null check (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' and length(email) <= 200),
    moving_from          text not null check (length(moving_from) <= 300),
    moving_to            text not null check (length(moving_to) <= 300),
    move_date            date not null,
    move_size            text check (length(move_size) <= 60),
    preferred_time       text check (length(preferred_time) <= 40),
    special_instructions text check (length(special_instructions) <= 2000),
    notes                text check (length(notes) <= 2000),
    status               text not null default 'pending'
                         check (status in ('pending', 'confirmed', 'completed', 'cancelled')),
    created_at           timestamptz not null default now()
);
create index if not exists bookings_date_time_idx on public.bookings (move_date, preferred_time);
create index if not exists bookings_status_idx    on public.bookings (status);

create table if not exists public.staff (
    user_id       uuid primary key references auth.users (id) on delete cascade,
    display_name  text not null,
    last_seen     timestamptz
);

create table if not exists public.live_chats (
    id               bigint generated always as identity primary key,
    visitor_token    text not null unique,
    visitor_name     text,
    visitor_contact  text,
    page_url         text,
    status           text not null default 'waiting' check (status in ('waiting', 'active', 'closed')),
    assigned_to      text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists live_chats_status_idx on public.live_chats (status, updated_at desc);

create table if not exists public.live_chat_messages (
    id           bigint generated always as identity primary key,
    chat_id      bigint not null references public.live_chats (id) on delete cascade,
    sender       text not null check (sender in ('visitor', 'staff', 'system', 'bot')),
    sender_name  text,
    body         text not null check (length(body) between 1 and 1000),
    created_at   timestamptz not null default now()
);
create index if not exists live_chat_messages_chat_idx on public.live_chat_messages (chat_id, id);

-- Default arrival windows (edit capacities any time in Table Editor → time_slots)
insert into public.time_slots (code, label, start_time, end_time, capacity, sort_order) values
    ('08:00-10:00', 'Early morning (8 – 10 AM)',    '08:00', '10:00', 2, 1),
    ('10:00-12:00', 'Late morning (10 AM – 12 PM)', '10:00', '12:00', 2, 2),
    ('12:00-14:00', 'Early afternoon (12 – 2 PM)',  '12:00', '14:00', 2, 3),
    ('14:00-16:00', 'Late afternoon (2 – 4 PM)',    '14:00', '16:00', 1, 4)
on conflict (code) do nothing;

-- -----------------------------------------------------------------------------
--  Lock the tables down: RLS on, no direct access for the public key.
--  Staff get read/write policies so the dashboard can also be used directly.
-- -----------------------------------------------------------------------------
alter table public.time_slots         enable row level security;
alter table public.blocked_dates      enable row level security;
alter table public.bookings           enable row level security;
alter table public.staff              enable row level security;
alter table public.live_chats         enable row level security;
alter table public.live_chat_messages enable row level security;

revoke all on public.time_slots, public.blocked_dates, public.bookings, public.staff,
              public.live_chats, public.live_chat_messages from anon;

-- -----------------------------------------------------------------------------
--  Helpers
-- -----------------------------------------------------------------------------
create or replace function public.is_staff()
returns boolean language sql stable security definer set search_path = public as $$
    select exists (select 1 from public.staff where user_id = auth.uid());
$$;

create or replace function public._require_staff()
returns text language plpgsql security definer set search_path = public as $$
declare v_name text;
begin
    update public.staff set last_seen = now() where user_id = auth.uid()
        returning display_name into v_name;
    if v_name is null then
        raise exception 'not_staff' using errcode = '42501';
    end if;
    return v_name;
end $$;

create or replace function public._today_bc()
returns date language sql stable set search_path = '' as $$
    select (pg_catalog.now() at time zone 'America/Vancouver')::date;
$$;

-- Staff-only policies (direct table access for signed-in staff)
do $$
declare t text;
begin
    foreach t in array array['time_slots','blocked_dates','bookings','live_chats','live_chat_messages'] loop
        execute format('drop policy if exists staff_all on public.%I', t);
        execute format('create policy staff_all on public.%I for all to authenticated using (public.is_staff()) with check (public.is_staff())', t);
    end loop;
    drop policy if exists staff_self on public.staff;
    create policy staff_self on public.staff for select to authenticated using (user_id = auth.uid());
end $$;

-- =============================================================================
--  PUBLIC — availability & booking
-- =============================================================================

-- Availability for one date: every active window with booked / remaining crews.
create or replace function public.get_availability(p_date date)
returns json language plpgsql stable security definer set search_path = public as $$
declare
    v_block public.blocked_dates;
begin
    if p_date is null or p_date < public._today_bc() then
        raise exception 'invalid_date' using errcode = '22023';
    end if;
    select * into v_block from public.blocked_dates where block_date = p_date;

    return json_build_object(
        'date', p_date,
        'closed', v_block.block_date is not null,
        'closed_reason', v_block.reason,
        'slots', coalesce((
            select json_agg(json_build_object(
                       'code', s.code, 'label', s.label,
                       'start_time', to_char(s.start_time, 'HH24:MI'),
                       'end_time',   to_char(s.end_time,   'HH24:MI'),
                       'capacity', s.capacity, 'booked', s.booked,
                       'remaining', case when v_block.block_date is null then greatest(s.capacity - s.booked, 0) else 0 end,
                       'available', v_block.block_date is null and s.capacity > s.booked)
                   order by s.sort_order)
            from (
                select t.*, (select count(*) from public.bookings b
                              where b.move_date = p_date and b.preferred_time = t.code
                                and b.status in ('pending', 'confirmed'))::int as booked
                from public.time_slots t where t.active
            ) s), '[]'::json)
    );
end $$;

-- Book a move. The chosen window's row is locked (FOR UPDATE) while the
-- capacity is checked and the booking inserted, so two visitors can never
-- take the last crew in the same window at the same moment.
create or replace function public.book_slot(
    p_customer_name text, p_phone text, p_email text,
    p_moving_from text, p_moving_to text, p_move_date date,
    p_move_size text default null, p_preferred_time text default null,
    p_special_instructions text default null, p_notes text default null)
returns bigint language plpgsql volatile security definer set search_path = public as $$
declare
    v_slot   text := nullif(trim(coalesce(p_preferred_time, '')), '');
    v_cap    integer;
    v_taken  integer;
    v_id     bigint;
begin
    if coalesce(trim(p_customer_name), '') = '' or coalesce(trim(p_phone), '') = ''
       or coalesce(trim(p_email), '') = '' or coalesce(trim(p_moving_from), '') = ''
       or coalesce(trim(p_moving_to), '') = '' or p_move_date is null then
        raise exception 'missing_fields' using errcode = '22023';
    end if;
    if trim(p_email) !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
        raise exception 'invalid_email' using errcode = '22023';
    end if;
    if p_move_date < public._today_bc() then
        raise exception 'date_in_past' using errcode = '22023';
    end if;
    if p_move_date > public._today_bc() + 365 then
        raise exception 'date_too_far' using errcode = '22023';
    end if;
    -- simple anti-spam: max 5 booking requests per email per day
    if (select count(*) from public.bookings
         where lower(email) = lower(trim(p_email)) and created_at > now() - interval '1 day') >= 5 then
        raise exception 'rate_limited' using errcode = '22023';
    end if;
    if exists (select 1 from public.blocked_dates where block_date = p_move_date) then
        raise exception 'date_closed' using errcode = '22023';
    end if;

    if v_slot is not null and lower(v_slot) not in ('flexible', 'morning', 'afternoon') then
        select capacity into v_cap from public.time_slots
         where code = v_slot and active
         for update;                                  -- serialises bookings for this window
        if not found then
            raise exception 'unknown_slot' using errcode = '22023';
        end if;
        select count(*) into v_taken from public.bookings
         where move_date = p_move_date and preferred_time = v_slot
           and status in ('pending', 'confirmed');
        if v_taken >= v_cap then
            raise exception 'slot_full' using errcode = '22023';
        end if;
    end if;

    insert into public.bookings (customer_name, phone, email, moving_from, moving_to, move_date,
                                 move_size, preferred_time, special_instructions, notes)
    values (trim(p_customer_name), trim(p_phone), lower(trim(p_email)), trim(p_moving_from), trim(p_moving_to),
            p_move_date, nullif(trim(coalesce(p_move_size, '')), ''), v_slot,
            nullif(trim(coalesce(p_special_instructions, '')), ''), nullif(trim(coalesce(p_notes, '')), ''))
    returning id into v_id;
    return v_id;
end $$;

-- =============================================================================
--  PUBLIC — live chat (visitor side, authorised by the per-chat token)
-- =============================================================================
create or replace function public.staff_online()
returns boolean language sql stable security definer set search_path = public as $$
    select exists (select 1 from public.staff where last_seen > now() - interval '90 seconds');
$$;

create or replace function public.live_chat_start(p_name text, p_contact text, p_page text, p_transcript jsonb default '[]')
returns json language plpgsql volatile security definer set search_path = public as $$
declare
    v_token text := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
    v_id    bigint;
begin
    -- flood guard for the whole site
    if (select count(*) from public.live_chats where created_at > now() - interval '10 minutes') >= 60 then
        raise exception 'rate_limited' using errcode = '22023';
    end if;
    insert into public.live_chats (visitor_token, visitor_name, visitor_contact, page_url)
    values (v_token, coalesce(nullif(left(trim(p_name), 80), ''), 'Website visitor'),
            left(trim(coalesce(p_contact, '')), 120), left(coalesce(p_page, ''), 300))
    returning id into v_id;

    -- carry the last 12 AI-chat turns over so staff have context
    if jsonb_typeof(p_transcript) = 'array' then
        insert into public.live_chat_messages (chat_id, sender, body)
        select v_id, case when e->>'role' = 'user' then 'visitor' else 'bot' end, left(e->>'text', 1000)
          from (select value as e, n from jsonb_array_elements(p_transcript) with ordinality t(value, n)
                 order by n desc limit 12) last12
         where coalesce(e->>'text', '') <> ''
         order by n;
    end if;
    insert into public.live_chat_messages (chat_id, sender, body)
    values (v_id, 'system', 'Visitor asked to talk to a person.');

    return json_build_object('chat_id', v_id, 'token', v_token, 'staff_online', public.staff_online());
end $$;

create or replace function public._visitor_chat(p_chat_id bigint, p_token text)
returns public.live_chats language sql stable security definer set search_path = public as $$
    select * from public.live_chats where id = p_chat_id and visitor_token = p_token;
$$;

create or replace function public.live_chat_send(p_chat_id bigint, p_token text, p_body text)
returns bigint language plpgsql volatile security definer set search_path = public as $$
declare
    v_chat public.live_chats := public._visitor_chat(p_chat_id, p_token);
    v_id   bigint;
begin
    if v_chat.id is null then raise exception 'not_found' using errcode = '22023'; end if;
    if v_chat.status = 'closed' then raise exception 'closed' using errcode = '22023'; end if;
    if coalesce(trim(p_body), '') = '' then raise exception 'empty' using errcode = '22023'; end if;
    if (select count(*) from public.live_chat_messages
         where chat_id = p_chat_id and sender = 'visitor' and created_at > now() - interval '5 minutes') >= 30 then
        raise exception 'rate_limited' using errcode = '22023';
    end if;
    insert into public.live_chat_messages (chat_id, sender, body)
    values (p_chat_id, 'visitor', left(trim(p_body), 1000)) returning id into v_id;
    update public.live_chats set updated_at = now() where id = p_chat_id;
    return v_id;
end $$;

create or replace function public.live_chat_poll(p_chat_id bigint, p_token text, p_after bigint default 0)
returns json language plpgsql stable security definer set search_path = public as $$
declare v_chat public.live_chats := public._visitor_chat(p_chat_id, p_token);
begin
    if v_chat.id is null then raise exception 'not_found' using errcode = '22023'; end if;
    return json_build_object(
        'status', v_chat.status, 'assigned_to', v_chat.assigned_to, 'staff_online', public.staff_online(),
        'messages', coalesce((select json_agg(json_build_object('id', m.id, 'sender', m.sender,
                                   'sender_name', m.sender_name, 'body', m.body, 'created_at', m.created_at) order by m.id)
                              from (select * from public.live_chat_messages
                                     where chat_id = p_chat_id and id > coalesce(p_after, 0)
                                     order by id limit 200) m), '[]'::json));
end $$;

create or replace function public.live_chat_close(p_chat_id bigint, p_token text)
returns boolean language plpgsql volatile security definer set search_path = public as $$
declare v_chat public.live_chats := public._visitor_chat(p_chat_id, p_token);
begin
    if v_chat.id is null then raise exception 'not_found' using errcode = '22023'; end if;
    if v_chat.status <> 'closed' then
        update public.live_chats set status = 'closed', updated_at = now() where id = p_chat_id;
        insert into public.live_chat_messages (chat_id, sender, body) values (p_chat_id, 'system', 'Chat ended by visitor.');
    end if;
    return true;
end $$;

-- =============================================================================
--  STAFF — dashboard functions (require a signed-in user listed in public.staff)
-- =============================================================================
create or replace function public.staff_me()
returns json language plpgsql volatile security definer set search_path = public as $$
declare v_name text := public._require_staff();
begin
    return json_build_object('id', auth.uid(), 'username', v_name, 'full_name', v_name,
                             'email', (select email from auth.users where id = auth.uid()), 'role', 'admin');
end $$;

create or replace function public.staff_list_bookings(p_search text default null, p_status text default null,
                                                      p_date date default null)
returns json language plpgsql volatile security definer set search_path = public as $$
begin
    perform public._require_staff();
    return coalesce((select json_agg(b order by b.created_at desc) from public.bookings b
                     where (p_status is null or p_status = '' or b.status = p_status)
                       and (p_date is null or b.move_date = p_date)
                       and (p_search is null or p_search = '' or
                            b.customer_name ilike '%' || p_search || '%' or b.email ilike '%' || p_search || '%' or
                            b.phone ilike '%' || p_search || '%' or b.moving_from ilike '%' || p_search || '%' or
                            b.moving_to ilike '%' || p_search || '%')), '[]'::json);
end $$;

create or replace function public.staff_get_booking(p_id bigint)
returns json language plpgsql volatile security definer set search_path = public as $$
begin
    perform public._require_staff();
    return (select row_to_json(b) from public.bookings b where id = p_id);
end $$;

create or replace function public.staff_update_booking_status(p_id bigint, p_status text)
returns boolean language plpgsql volatile security definer set search_path = public as $$
begin
    perform public._require_staff();
    update public.bookings set status = p_status where id = p_id;
    return found;
end $$;

create or replace function public.staff_delete_booking(p_id bigint)
returns boolean language plpgsql volatile security definer set search_path = public as $$
begin
    perform public._require_staff();
    delete from public.bookings where id = p_id;
    return found;
end $$;

create or replace function public.staff_list_chats(p_include_closed boolean default false)
returns json language plpgsql volatile security definer set search_path = public as $$
declare v_chats json;
begin
    perform public._require_staff();
    select coalesce(json_agg(c order by c.ord, c.updated_at desc), '[]'::json) into v_chats from (
        select l.id, l.visitor_name, l.visitor_contact, l.page_url, l.status, l.assigned_to,
               l.created_at, l.updated_at,
               case l.status when 'waiting' then 0 when 'active' then 1 else 2 end as ord,
               (select body   from public.live_chat_messages m where m.chat_id = l.id order by m.id desc limit 1) as last_message,
               (select sender from public.live_chat_messages m where m.chat_id = l.id order by m.id desc limit 1) as last_sender
          from public.live_chats l
         where p_include_closed or l.status <> 'closed'
         order by l.updated_at desc limit 100) c;
    return json_build_object('chats', v_chats,
        'waiting', (select count(*) from public.live_chats where status = 'waiting'));
end $$;

create or replace function public.staff_chat_messages(p_chat_id bigint, p_after bigint default 0)
returns json language plpgsql volatile security definer set search_path = public as $$
declare v_chat public.live_chats;
begin
    perform public._require_staff();
    select * into v_chat from public.live_chats where id = p_chat_id;
    if v_chat.id is null then raise exception 'not_found' using errcode = '22023'; end if;
    return json_build_object(
        'chat', json_build_object('id', v_chat.id, 'visitor_name', v_chat.visitor_name,
                    'visitor_contact', v_chat.visitor_contact, 'page_url', v_chat.page_url,
                    'status', v_chat.status, 'assigned_to', v_chat.assigned_to, 'created_at', v_chat.created_at),
        'messages', coalesce((select json_agg(json_build_object('id', m.id, 'sender', m.sender,
                                   'sender_name', m.sender_name, 'body', m.body, 'created_at', m.created_at) order by m.id)
                              from public.live_chat_messages m
                             where m.chat_id = p_chat_id and m.id > coalesce(p_after, 0)), '[]'::json));
end $$;

create or replace function public.staff_chat_send(p_chat_id bigint, p_body text)
returns bigint language plpgsql volatile security definer set search_path = public as $$
declare
    v_name   text := public._require_staff();
    v_status text;
    v_id     bigint;
begin
    select status into v_status from public.live_chats where id = p_chat_id for update;
    if v_status is null or v_status = 'closed' then raise exception 'closed' using errcode = '22023'; end if;
    if coalesce(trim(p_body), '') = '' then raise exception 'empty' using errcode = '22023'; end if;
    if v_status = 'waiting' then
        insert into public.live_chat_messages (chat_id, sender, body) values (p_chat_id, 'system', v_name || ' joined the chat.');
    end if;
    insert into public.live_chat_messages (chat_id, sender, sender_name, body)
    values (p_chat_id, 'staff', v_name, left(trim(p_body), 1000)) returning id into v_id;
    update public.live_chats set status = 'active', assigned_to = v_name, updated_at = now() where id = p_chat_id;
    return v_id;
end $$;

create or replace function public.staff_chat_close(p_chat_id bigint)
returns boolean language plpgsql volatile security definer set search_path = public as $$
declare v_name text := public._require_staff();
begin
    update public.live_chats set status = 'closed', updated_at = now() where id = p_chat_id and status <> 'closed';
    if found then
        insert into public.live_chat_messages (chat_id, sender, body) values (p_chat_id, 'system', 'Chat ended by ' || v_name || '.');
    end if;
    return found;
end $$;

-- -----------------------------------------------------------------------------
--  Who may call what
-- -----------------------------------------------------------------------------
-- Revoke the default PUBLIC grant on OnTime's own functions only (other
-- projects sharing this database are left untouched), then grant precisely.
do $$
declare f regprocedure;
begin
    for f in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
              where n.nspname = 'public' and p.proname in (
                'is_staff','_require_staff','_today_bc','_visitor_chat','get_availability','book_slot',
                'staff_online','live_chat_start','live_chat_send','live_chat_poll','live_chat_close',
                'staff_me','staff_list_bookings','staff_get_booking','staff_update_booking_status',
                'staff_delete_booking','staff_list_chats','staff_chat_messages','staff_chat_send','staff_chat_close')
    loop
        execute format('revoke execute on function %s from public, anon, authenticated', f);
    end loop;
end $$;

grant execute on function public.get_availability(date)                                   to anon, authenticated;
grant execute on function public.book_slot(text, text, text, text, text, date, text, text, text, text) to anon, authenticated;
grant execute on function public.staff_online()                                            to anon, authenticated;
grant execute on function public.live_chat_start(text, text, text, jsonb)                  to anon, authenticated;
grant execute on function public.live_chat_send(bigint, text, text)                        to anon, authenticated;
grant execute on function public.live_chat_poll(bigint, text, bigint)                      to anon, authenticated;
grant execute on function public.live_chat_close(bigint, text)                             to anon, authenticated;

grant execute on function public.is_staff()                                                to authenticated;
grant execute on function public.staff_me()                                                to authenticated;
grant execute on function public.staff_list_bookings(text, text, date)                     to authenticated;
grant execute on function public.staff_get_booking(bigint)                                 to authenticated;
grant execute on function public.staff_update_booking_status(bigint, text)                 to authenticated;
grant execute on function public.staff_delete_booking(bigint)                              to authenticated;
grant execute on function public.staff_list_chats(boolean)                                 to authenticated;
grant execute on function public.staff_chat_messages(bigint, bigint)                       to authenticated;
grant execute on function public.staff_chat_send(bigint, text)                             to authenticated;
grant execute on function public.staff_chat_close(bigint)                                  to authenticated;

