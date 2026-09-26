from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, g
from models import Lead, Customer, Product, Appointment
from auth import login_required, company_scope_required

bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

LEAD_STATUSES = ('new', 'contacted', 'won', 'lost')
APPT_STATUSES = ('scheduled', 'completed', 'cancelled', 'no_show')


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def analytics():
    cid = g.company_id
    now = datetime.now(timezone.utc)

    leads = Lead.query.filter(Lead.company_id == cid, Lead.deleted_at.is_(None))
    customers = Customer.query.filter(Customer.company_id == cid, Customer.deleted_at.is_(None))
    products = Product.query.filter(Product.company_id == cid, Product.deleted_at.is_(None))
    appointments = Appointment.query.filter(Appointment.company_id == cid, Appointment.deleted_at.is_(None))

    # 14-day daily lead trend, oldest first — cheap enough client-side rather
    # than pushing this aggregation down to SQL and losing DB portability.
    trend = []
    all_recent_leads = leads.filter(Lead.created_at >= now - timedelta(days=14)).all()
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = sum(1 for l in all_recent_leads if l.created_at.date() == day)
        trend.append({'date': day.isoformat(), 'count': count})

    return jsonify({
        'leads': {
            'total': leads.count(),
            'this_week': leads.filter(Lead.created_at >= now - timedelta(days=7)).count(),
            'by_status': {s: leads.filter(Lead.status == s).count() for s in LEAD_STATUSES},
            'trend_14d': trend
        },
        'customers': {
            'total': customers.count(),
            'active': customers.filter(Customer.status == 'active').count()
        },
        'products': {
            'total': products.count(),
            'active': products.filter(Product.status == 'active').count()
        },
        'appointments': {
            'total': appointments.count(),
            'upcoming': appointments.filter(Appointment.scheduled_at >= now, Appointment.status == 'scheduled').count(),
            'by_status': {s: appointments.filter(Appointment.status == s).count() for s in APPT_STATUSES}
        }
    })
