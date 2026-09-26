from flask import Blueprint, request, jsonify, g
from extensions import db
from models import Company
from auth import login_required, role_required, company_scope_required
from errors import NotFoundError, ValidationError

bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def get_settings():
    company = Company.query.get(g.company_id)
    if not company:
        raise NotFoundError('Company not found.')
    return jsonify({
        'timezone': company.timezone,
        'currency': company.currency,
        'notification_email': company.notification_email,
        'is_active': company.is_active
    })


@bp.route('', methods=['PATCH'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def update_settings():
    data = request.get_json(silent=True) or {}
    company = Company.query.get(g.company_id)
    if not company:
        raise NotFoundError('Company not found.')

    if 'timezone' in data:
        if not str(data['timezone']).strip():
            raise ValidationError('Timezone cannot be empty.')
        company.timezone = data['timezone'].strip()
    if 'currency' in data:
        company.currency = (data['currency'] or 'USD').strip().upper()[:10]
    if 'notification_email' in data:
        company.notification_email = (data['notification_email'] or '').strip() or None

    db.session.commit()
    return jsonify({
        'timezone': company.timezone, 'currency': company.currency,
        'notification_email': company.notification_email, 'is_active': company.is_active
    })
