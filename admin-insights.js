/*
 * OnTime Moving — Booking tracking panel for admin.html
 * All numbers come from the SQL function staff_booking_insights() (Supabase).
 * Test bookings are excluded by the database.
 */
(function () {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const SEQ = ['#eef2f7', '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95'];  // empty → full
  const BAR = '#2a78d6';
  let days = 30, timer = null, lastData = null;

  // ---------- helpers ----------
  const parseDay = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const fmtDay = (s, opts) => parseDay(s).toLocaleDateString('en-CA', opts || { month: 'short', day: 'numeric' });
  const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  const tip = document.createElement('div');
  tip.className = 'ins-tip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true;
  document.body.appendChild(tip);
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.min(window.innerWidth - r.width - 8, Math.max(8, x - r.width / 2)) + 'px';
    tip.style.top = Math.max(8, y - r.height - 12) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };
  function attachTips(root) {
    root.querySelectorAll('[data-tip]').forEach(el => {
      const show = () => { const b = el.getBoundingClientRect(); showTip(el.dataset.tip, b.left + b.width / 2, b.top); };
      el.addEventListener('mouseenter', show); el.addEventListener('focus', show);
      el.addEventListener('mouseleave', hideTip); el.addEventListener('blur', hideTip);
    });
  }

  // ---------- KPI tiles ----------
  function renderKpis(d) {
    const k = d.kpis, prev = k.new_prev_period, cur = k.new_period;
    let delta = '<span class="ins-delta flat">no earlier data</span>';
    if (prev > 0 || cur > 0) {
      const diff = cur - prev, p = prev ? Math.round((100 * diff) / prev) : null;
      const cls = diff > 0 ? 'up' : diff < 0 ? 'down' : 'flat';
      const arrow = diff > 0 ? '▲' : diff < 0 ? '▼' : '■';
      delta = `<span class="ins-delta ${cls}">${arrow} ${diff >= 0 ? '+' : ''}${diff}${p !== null ? ` (${p >= 0 ? '+' : ''}${p}%)` : ''} vs previous ${d.period_days} days</span>`;
    }
    const util = pct(k.crews_booked_14, k.crews_total_14);
    $('insKpis').innerHTML = `
      <div class="ins-kpi"><div class="ins-kpi-label">New bookings · last ${d.period_days} days</div>
        <div class="ins-kpi-value">${cur}</div>${delta}
        <div class="ins-kpi-sub">${plural(k.new_today, 'booking')} today</div></div>
      <div class="ins-kpi"><div class="ins-kpi-label">Upcoming moves · next 30 days</div>
        <div class="ins-kpi-value">${k.upcoming_30}</div>
        <div class="ins-kpi-sub">${k.upcoming_7} in the next 7 days · ${k.pending_now} awaiting confirmation</div></div>
      <div class="ins-kpi"><div class="ins-kpi-label">Crew utilisation · next 14 days</div>
        <div class="ins-kpi-value">${util}<span class="ins-unit">%</span></div>
        <div class="ins-meter" role="img" aria-label="${util}% of crews booked"><span style="width:${Math.min(util, 100)}%"></span></div>
        <div class="ins-kpi-sub">${k.crews_booked_14} of ${k.crews_total_14} crew slots booked</div></div>
      <div class="ins-kpi"><div class="ins-kpi-label">Cancellation rate · last ${d.period_days} days</div>
        <div class="ins-kpi-value">${k.cancel_rate_period ?? 0}<span class="ins-unit">%</span></div>
        <div class="ins-kpi-sub">${k.cancelled_period} of ${k.new_period} new bookings cancelled</div></div>`;
  }

  // ---------- daily trend (single-series bars, SVG) ----------
  function renderTrend(d) {
    const pts = d.daily, n = pts.length, max = Math.max(1, ...pts.map(p => p.count));
    const total = pts.reduce((s, p) => s + p.count, 0);
    const W = 720, H = 200, L = 30, R = 8, T = 14, B = 26, cw = (W - L - R) / n, bw = Math.max(2, cw - 2);
    const y = v => T + (H - T - B) * (1 - v / max);
    const step = max <= 4 ? 1 : Math.ceil(max / 4);
    let grid = '';
    for (let v = 0; v <= max; v += step) {
      grid += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="ins-grid"/><text x="${L - 6}" y="${y(v) + 4}" class="ins-axis" text-anchor="end">${v}</text>`;
    }
    const peak = pts.reduce((a, p) => (p.count > a.count ? p : a), pts[0]);
    const labelEvery = n <= 10 ? 1 : n <= 31 ? 7 : 14;
    let bars = '', ticks = '';
    pts.forEach((p, i) => {
      const x = L + i * cw + (cw - bw) / 2, h = (H - T - B) - (y(p.count) - T);
      const r = Math.min(4, bw / 2);
      if (p.count > 0) {
        bars += `<path d="M${x},${y(0)} V${y(p.count) + r} Q${x},${y(p.count)} ${x + r},${y(p.count)} H${x + bw - r} Q${x + bw},${y(p.count)} ${x + bw},${y(p.count) + r} V${y(0)} Z" fill="${BAR}"/>`;
      }
      bars += `<rect x="${L + i * cw}" y="${T}" width="${cw}" height="${H - T - B}" class="ins-hit" tabindex="0"
               data-tip="<strong>${fmtDay(p.date, { weekday: 'short', month: 'short', day: 'numeric' })}</strong><br>${plural(p.count, 'new booking')}"/>`;
      if ((n - 1 - i) % labelEvery === 0) ticks += `<text x="${L + i * cw + cw / 2}" y="${H - 8}" class="ins-axis" text-anchor="middle">${fmtDay(p.date)}</text>`;
    });
    const peakLabel = peak.count > 0
      ? `<text x="${L + pts.indexOf(peak) * cw + cw / 2}" y="${y(peak.count) - 4}" class="ins-peak" text-anchor="middle">${peak.count}</text>` : '';
    $('insTrend').innerHTML = `
      <div class="ins-card-head"><h3>New bookings per day</h3><span class="ins-muted">${plural(total, 'booking')} in the last ${d.period_days} days</span></div>
      <svg viewBox="0 0 ${W} ${H}" class="ins-svg" role="img" aria-label="Bar chart of new bookings per day; ${total} in total, peak ${peak.count} on ${fmtDay(peak.date)}">
        ${grid}<line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" class="ins-baseline"/>${bars}${peakLabel}${ticks}</svg>`;
    attachTips($('insTrend'));
  }

  // ---------- crew schedule heatmap ----------
  function renderSchedule(d) {
    const s = d.schedule, booked = {}, closed = {};
    s.booked.forEach(b => { booked[b.date + '|' + b.code] = b.count; });
    s.closed.forEach(c => { closed[c.date] = c.reason || 'Closed'; });
    const head = s.dates.map(dt => {
      const day = parseDay(dt), wk = day.getDay() === 0 || day.getDay() === 6;
      return `<th scope="col" class="${wk ? 'wkend' : ''}"><span>${day.toLocaleDateString('en-CA', { weekday: 'short' })}</span>${day.getDate()}</th>`;
    }).join('');
    const rows = s.windows.map(w => {
      const cells = s.dates.map(dt => {
        if (closed[dt]) return `<td class="ins-cell closed" tabindex="0" data-tip="<strong>${fmtDay(dt)}</strong><br>Closed — ${esc(closed[dt])}">—</td>`;
        const n = booked[dt + '|' + w.code] || 0, cap = w.capacity;
        const lvl = cap ? (n >= cap ? 6 : Math.max(n ? 1 : 0, Math.round((n / cap) * 5))) : 0;
        const full = cap && n >= cap;
        return `<td class="ins-cell l${lvl}${full ? ' full' : ''}" style="background:${SEQ[lvl]}" tabindex="0"
                 data-tip="<strong>${fmtDay(dt, { weekday: 'short', month: 'short', day: 'numeric' })} · ${esc(w.label)}</strong><br>${n} of ${cap} crews booked${full ? ' — <b>full</b>' : ''}">${n}/${cap}</td>`;
      }).join('');
      return `<tr><th scope="row">${esc(w.label.replace(/\s*\(.*\)/, ''))}<small>${esc(w.code.replace('-', '–'))}</small></th>${cells}</tr>`;
    }).join('');
    $('insSchedule').innerHTML = `
      <div class="ins-card-head"><h3>Crew schedule · next 14 days</h3>
        <span class="ins-legend"><span>Free</span>${SEQ.slice(0, 7).map(c => `<i style="background:${c}"></i>`).join('')}<span>Full</span><i class="closed"></i><span>Closed</span></span></div>
      <div class="ins-table-wrap"><table class="ins-heat"><thead><tr><th></th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
      <p class="ins-muted ins-note">Booked crews / crews available, per arrival window. Flexible bookings are scheduled by phone and aren't shown here.</p>`;
    attachTips($('insSchedule'));
  }

  // ---------- breakdowns ----------
  function barList(title, items, labelOf) {
    const max = Math.max(1, ...items.map(i => i.count)), total = items.reduce((s, i) => s + i.count, 0);
    return `<div class="ins-break"><h4>${title}</h4>${items.length ? items.map(i => `
      <div class="ins-row" tabindex="0" data-tip="<strong>${esc(labelOf(i))}</strong><br>${i.count} (${pct(i.count, total)}%)">
        <span class="ins-row-label">${esc(labelOf(i))}</span>
        <span class="ins-row-bar">${i.count ? `<span style="width:${(100 * i.count) / max}%"></span>` : ''}</span>
        <span class="ins-row-val">${i.count}</span></div>`).join('') : '<p class="ins-muted">No bookings yet.</p>'}</div>`;
  }
  function renderBreakdowns(d) {
    $('insBreakdowns').innerHTML =
      barList('By status · all time', d.by_status, i => i.status[0].toUpperCase() + i.status.slice(1)) +
      barList('By move size · all time', d.by_size, i => i.size) +
      barList('Upcoming by arrival window', d.by_window, i => i.label.replace(/\s*\(.*\)/, '').replace(' / no window', ''));
    attachTips($('insBreakdowns'));
  }

  // ---------- activity log ----------
  function renderActivity(d) {
    const label = e => e.event === 'created' ? 'New booking'
      : e.event === 'deleted' ? 'Deleted'
      : `${esc(e.old_status)} → <strong>${esc(e.new_status)}</strong>`;
    const when = ts => {
      const t = new Date(ts), mins = Math.round((Date.now() - t) / 60000);
      if (mins < 1) return 'just now';
      if (mins < 60) return `${mins} min ago`;
      if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
      return t.toLocaleDateString('en-CA', { month: 'short', day: 'numeric' });
    };
    $('insActivity').innerHTML = `
      <div class="ins-card-head"><h3>Recent activity</h3><span class="ins-muted">recorded by the database</span></div>
      ${d.activity.length ? `<ol class="ins-feed">${d.activity.map(e => `
        <li class="ev-${esc(e.event)}">
          <span class="ins-dot" aria-hidden="true"></span>
          <div><div><strong>#${Number(e.booking_id)}</strong> ${esc(e.customer_name || '')} · ${label(e)}</div>
          <small>${esc(e.actor)} · ${when(e.at)}${e.move_date ? ` · move ${fmtDay(e.move_date)}` : ''}${e.preferred_time ? ' ' + esc(e.preferred_time) : ''}</small></div>
        </li>`).join('')}</ol>` : '<p class="ins-muted">No activity yet — new bookings and status changes will appear here.</p>'}`;
  }

  // ---------- load ----------
  async function load() {
    clearTimeout(timer);
    const status = $('insStatus');
    try {
      const res = await fetch(`${API_BASE_URL}/admin/insights?days=${days}`, { headers: setAuthHeader() });
      if (res.status === 401) { if (typeof redirectToLogin === 'function') redirectToLogin(); return; }
      if (res.status === 404) {
        $('insBody').hidden = true;
        $('insUnavailable').hidden = false;
        return;
      }
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      lastData = data;
      $('insBody').hidden = false; $('insUnavailable').hidden = true;
      renderKpis(data); renderTrend(data); renderSchedule(data); renderBreakdowns(data); renderActivity(data);
      status.textContent = 'Updated ' + new Date().toLocaleTimeString('en-CA', { hour: 'numeric', minute: '2-digit' });
    } catch (e) {
      status.textContent = 'Could not load tracking data — retrying';
    }
    timer = setTimeout(load, 60000);
  }

  function start() {
    document.querySelectorAll('#insPeriod button').forEach(b => b.addEventListener('click', () => {
      days = Number(b.dataset.days);
      document.querySelectorAll('#insPeriod button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      load();
    }));
    load();
  }

  window.Insights = { start, refresh: load, data: () => lastData };
})();

/* Export the bookings currently shown in the table (after filters) as CSV. */
window.exportBookingsCsv = function (bookings) {
  const cols = ['id', 'status', 'customer_name', 'email', 'phone', 'moving_from', 'moving_to',
                'move_date', 'preferred_time', 'move_size', 'special_instructions', 'notes', 'created_at'];
  const cell = v => {
    let s = String(v ?? '');
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;          // stop spreadsheet formula injection
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [cols.join(',')].concat(bookings.map(b => cols.map(c => cell(b[c])).join(','))).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `ontime-bookings-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
