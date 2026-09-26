from flask import Blueprint, request, jsonify
from extensions import limiter
from models import Company
from leads_service import validate_lead_input, create_lead
from utils import content_from_json
from errors import NotFoundError

bp = Blueprint('public', __name__, url_prefix='/api/public')


def _get_active_company(slug):
    company = Company.query.filter_by(slug=slug, is_active=True).first()
    if not company:
        raise NotFoundError('Site not found.')
    return company


@bp.route('/companies/<slug>/content', methods=['GET'])
def public_content(slug):
    company = _get_active_company(slug)
    return jsonify({
        'name': company.name,
        'slug': company.slug,
        'theme': company.theme,
        'brand_name': company.brand_name,
        'brand_accent': company.brand_accent,
        'content': content_from_json(company.content_json)
    })


@bp.route('/companies/<slug>/leads', methods=['POST'])
@limiter.limit('20 per minute')
def public_create_lead(slug):
    company = _get_active_company(slug)
    data = request.get_json(silent=True) or {}
    fields = validate_lead_input(data)
    lead, is_dup = create_lead(company.id, fields, source='website')
    return jsonify({'status': 'received', 'duplicate': is_dup}), (200 if is_dup else 201)
