from datetime import datetime
from flask import Blueprint, request, jsonify, g
from extensions import db
from models import Appointment, Customer, Lead
from auth import login_required, role_required, company_scope_required
from utils import require_fields
from pagination import paginate
from errors import NotFoundError, ValidationError

bp = Blueprint('appointments', __name__, url_prefix='/api/appointments')

SORT_COLUMNS = {'scheduled_at': Appointment.scheduled_at, 'created_at': Appointment.created_at, 'status': Appointment.status}
STATUSES = ('scheduled', 'completed', 'cancelled', 'no_show')


def _parse_datetime(value):
    try:
        # Accept both "2026-01-01T10:00" (datetime-local input) and full ISO w/ offset.
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('scheduled_at must be a valid ISO 8601 datetime.')


def _filtered_query():
    q = Appointment.query.filter(Appointment.company_id == g.company_id, Appointment.deleted_at.is_(None))

    search = (request.args.get('q') or '').strip()
    if search:
        q = q.filter(Appointment.title.ilike(f'%{search}%'))

    status = request.args.get('status')
    if status and status in STATUSES:
        q = q.filter(Appointment.status == status)

    customer_id = request.args.get('customer_id')
    if customer_id:
        q = q.filter(Appointment.customer_id == customer_id)

    sort = request.args.get('sort', 'scheduled_at')
    column = SORT_COLUMNS.get(sort.lstrip('-'), Appointment.scheduled_at)
    q = q.order_by(column.desc() if sort.startswith('-') else column.asc())
    return q


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def list_appointments():
    return jsonify(paginate(_filtered_query(), lambda a: a.to_dict()))


def _validate_relations(data):
    customer_id = data.get('customer_id')
    if customer_id is not None:
        if not Customer.query.filter_by(id=customer_id, company_id=g.company_id, deleted_at=None).first():
            raise ValidationError('customer_id does not belong to this company.')
    lead_id = data.get('lead_id')
    if lead_id is not None:
        if not Lead.query.filter_by(id=lead_id, company_id=g.company_id, deleted_at=None).first():
            raise ValidationError('lead_id does not belong to this company.')
    return customer_id, lead_id


@bp.route('', methods=['POST'])
@login_required
@company_scope_required
def add_appointment():
    data = request.get_json(silent=True) or {}
    require_fields(data, 'title', 'scheduled_at')
    customer_id, lead_id = _validate_relations(data)

    status = data.get('status', 'scheduled')
    if status not in STATUSES:
        raise ValidationError(f'Status must be one of {STATUSES}.')

    appt = Appointment(
        company_id=g.company_id, customer_id=customer_id, lead_id=lead_id,
        title=data['title'].strip(), scheduled_at=_parse_datetime(data['scheduled_at']),
        duration_minutes=int(data.get('duration_minutes', 60) or 60), status=status,
        notes=(data.get('notes') or '').strip()
    )
    db.session.add(appt)
    db.session.commit()
    return jsonify(appt.to_dict()), 201


def _get_owned_appointment(appt_id):
    appt = Appointment.query.filter_by(id=appt_id, company_id=g.company_id, deleted_at=None).first()
    if not appt:
        raise NotFoundError('Appointment not found.')
    return appt


@bp.route('/<int:appt_id>', methods=['GET'])
@login_required
@company_scope_required
def get_appointment(appt_id):
    return jsonify(_get_owned_appointment(appt_id).to_dict())


@bp.route('/<int:appt_id>', methods=['PATCH'])
@login_required
@company_scope_required
def update_appointment(appt_id):
    appt = _get_owned_appointment(appt_id)
    data = request.get_json(silent=True) or {}

    if 'title' in data and str(data['title']).strip():
        appt.title = data['title'].strip()
    if 'scheduled_at' in data:
        appt.scheduled_at = _parse_datetime(data['scheduled_at'])
    if 'duration_minutes' in data:
        appt.duration_minutes = int(data['duration_minutes'])
    if 'notes' in data:
        appt.notes = data['notes']
    if 'status' in data:
        if data['status'] not in STATUSES:
            raise ValidationError(f'Status must be one of {STATUSES}.')
        appt.status = data['status']
    if 'customer_id' in data or 'lead_id' in data:
        customer_id, lead_id = _validate_relations(data)
        if 'customer_id' in data:
            appt.customer_id = customer_id
        if 'lead_id' in data:
            appt.lead_id = lead_id

    db.session.commit()
    return jsonify(appt.to_dict())


@bp.route('/<int:appt_id>', methods=['DELETE'])
@login_required
@company_scope_required
def delete_appointment(appt_id):
    appt = _get_owned_appointment(appt_id)
    appt.soft_delete()
    db.session.commit()
    return jsonify({'status': 'deleted'})
