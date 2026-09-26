from flask import Blueprint, request, jsonify, session, g
from extensions import db
from models import Company
from auth import login_required, role_required, company_scope_required
from utils import content_to_json, content_from_json
from errors import NotFoundError, ValidationError

bp = Blueprint('company', __name__, url_prefix='/api')

ALLOWED_THEMES = {'default', 'emerald', 'rose', 'slate', 'sunset'}


def _company_dict(c):
    return {
        'id': c.id, 'name': c.name, 'slug': c.slug, 'theme': c.theme,
        'brand_name': c.brand_name, 'brand_accent': c.brand_accent,
        'content': content_from_json(c.content_json),
        'timezone': c.timezone, 'currency': c.currency, 'notification_email': c.notification_email,
        'is_active': c.is_active,
        'plan': c.plan, 'trial_ends_at': c.trial_ends_at.isoformat() if c.trial_ends_at else None,
        'trial_days_remaining': c.trial_days_remaining, 'is_trial_expired': c.is_trial_expired
    }


@bp.route('/company', methods=['GET'])
@login_required
@company_scope_required
def get_company():
    company = Company.query.get(g.company_id)
    if not company:
        raise NotFoundError('Company not found.')
    return jsonify(_company_dict(company))


@bp.route('/company', methods=['PATCH'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def update_company():
    data = request.get_json(silent=True) or {}
    company = Company.query.get(g.company_id)
    if not company:
        raise NotFoundError('Company not found.')

    if 'brand_name' in data:
        company.brand_name = data['brand_name']
    if 'brand_accent' in data:
        company.brand_accent = data['brand_accent']
    if 'theme' in data:
        if data['theme'] not in ALLOWED_THEMES:
            raise ValidationError(f'Theme must be one of {sorted(ALLOWED_THEMES)}.')
        company.theme = data['theme']
    if isinstance(data.get('content'), dict):
        content = content_from_json(company.content_json)
        content.update(data['content'])
        company.content_json = content_to_json(content)

    db.session.commit()
    return jsonify(_company_dict(company))


@bp.route('/companies', methods=['GET'])
@login_required
@role_required('platform_admin')
def list_companies():
    companies = Company.query.order_by(Company.name).all()
    return jsonify([{
        'id': c.id, 'name': c.name, 'slug': c.slug, 'is_active': c.is_active,
        'created_at': c.created_at.isoformat(), 'plan': c.plan,
        'trial_days_remaining': c.trial_days_remaining, 'is_trial_expired': c.is_trial_expired
    } for c in companies])


@bp.route('/companies/switch', methods=['POST'])
@login_required
@role_required('platform_admin')
def switch_company():
    data = request.get_json(silent=True) or {}
    company = Company.query.get(data.get('company_id'))
    if not company:
        raise NotFoundError('Company not found.')
    session['active_company_id'] = company.id
    return jsonify({'status': 'ok', 'active_company_id': company.id})


@bp.route('/companies/<int:company_id>/plan', methods=['PATCH'])
@login_required
@role_required('platform_admin')
def upgrade_company_plan(company_id):
    """Flips a company from 'trial' to 'active'. Stands in for what a real
    payment webhook (Stripe, Gumroad, etc.) would call on successful payment —
    there's no billing integration wired up yet, so this is the manual
    equivalent an operator would use in the meantime. See README "Free trial"."""
    company = Company.query.get(company_id)
    if not company:
        raise NotFoundError('Company not found.')
    data = request.get_json(silent=True) or {}
    plan = data.get('plan', 'active')
    if plan not in ('trial', 'active'):
        raise ValidationError("plan must be 'trial' or 'active'.")
    company.plan = plan
    db.session.commit()
    return jsonify(_company_dict(company))
