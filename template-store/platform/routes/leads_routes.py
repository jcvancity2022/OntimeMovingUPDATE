import csv
import io
from flask import Blueprint, request, jsonify, g, Response
from extensions import db
from models import Lead
from auth import login_required, role_required, company_scope_required, current_user
from leads_service import validate_lead_input, create_lead
from pagination import paginate
from errors import NotFoundError, ValidationError

bp = Blueprint('leads', __name__, url_prefix='/api/leads')

SORT_COLUMNS = {'created_at': Lead.created_at, 'name': Lead.name, 'status': Lead.status}
STATUSES = ('new', 'contacted', 'won', 'lost')


def _filtered_query():
    q = Lead.query.filter(Lead.company_id == g.company_id, Lead.deleted_at.is_(None))

    search = (request.args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.message.ilike(like)))

    status = request.args.get('status')
    if status and status in STATUSES:
        q = q.filter(Lead.status == status)

    sort = request.args.get('sort', '-created_at')
    column = SORT_COLUMNS.get(sort.lstrip('-'), Lead.created_at)
    q = q.order_by(column.desc() if sort.startswith('-') or sort == 'created_at' else column.asc())
    return q


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def list_leads():
    return jsonify(paginate(_filtered_query(), lambda l: l.to_dict()))


@bp.route('/stats', methods=['GET'])
@login_required
@company_scope_required
def lead_stats():
    from datetime import datetime, timedelta, timezone
    base = Lead.query.filter(Lead.company_id == g.company_id, Lead.deleted_at.is_(None))
    total = base.count()
    week_cutoff_dt = datetime.now(timezone.utc) - timedelta(days=7)
    this_week = base.filter(Lead.created_at >= week_cutoff_dt).count()
    by_status = {status: base.filter(Lead.status == status).count() for status in STATUSES}
    return jsonify({'total': total, 'this_week': this_week, 'by_status': by_status})


@bp.route('/export', methods=['GET'])
@login_required
@company_scope_required
def export_leads():
    leads = _filtered_query().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['id', 'name', 'email', 'phone', 'message', 'status', 'source', 'notes', 'created_at', 'updated_at'])
    for l in leads:
        writer.writerow([l.id, l.name, l.email, l.phone, l.message, l.status, l.source, l.notes, l.created_at, l.updated_at])
    return Response(buf.getvalue(), mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename=leads.csv'})


@bp.route('', methods=['POST'])
@login_required
@company_scope_required
def add_lead():
    data = request.get_json(silent=True) or {}
    fields = validate_lead_input(data)
    lead, is_dup = create_lead(g.company_id, fields, source='manual', created_by=current_user().id)
    return jsonify(lead.to_dict()), (200 if is_dup else 201)


def _get_owned_lead(lead_id):
    lead = Lead.query.filter_by(id=lead_id, company_id=g.company_id, deleted_at=None).first()
    if not lead:
        raise NotFoundError('Lead not found.')
    return lead


@bp.route('/<int:lead_id>', methods=['GET'])
@login_required
@company_scope_required
def get_lead(lead_id):
    return jsonify(_get_owned_lead(lead_id).to_dict())


@bp.route('/<int:lead_id>', methods=['PATCH'])
@login_required
@company_scope_required
def update_lead(lead_id):
    lead = _get_owned_lead(lead_id)
    data = request.get_json(silent=True) or {}

    if 'status' in data:
        if data['status'] not in STATUSES:
            raise ValidationError(f'Status must be one of {STATUSES}.')
        lead.status = data['status']
    if 'notes' in data:
        lead.notes = data['notes']
    if 'name' in data and str(data['name']).strip():
        lead.name = data['name'].strip()
    if 'phone' in data:
        lead.phone = data['phone']

    db.session.commit()
    return jsonify(lead.to_dict())


@bp.route('/<int:lead_id>', methods=['DELETE'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def delete_lead(lead_id):
    lead = _get_owned_lead(lead_id)
    lead.soft_delete()
    db.session.commit()
    return jsonify({'status': 'deleted'})
